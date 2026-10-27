#!/usr/bin/env python3
"""
Portfolio Trading Wrapper for Polymarket Bots
Uses Frank-Wolfe optimization for capital allocation across multiple signals

Drop-in replacement for individual bot sizing logic
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, fields

from frank_wolfe_optimizer import FrankWolfeOptimizer, TradeOpportunity

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '.portfolio-config.json')
STATE_FILE = os.path.join(os.path.dirname(__file__), '.portfolio-state.json')

@dataclass
class PortfolioConfig:
    """Portfolio-level trading configuration"""
    total_budget: float = 100.0
    max_daily_exposure: float = 100.0
    max_daily_drawdown: float = 20.0  # Max loss allowed per day before veto
    max_per_trade: float = 50.0
    max_bankroll_pct: float = 0.30
    kelly_fraction: float = 0.25  # quarter Kelly
    paper_mode: bool = True  # Start in paper mode
    per_asset_caps: Dict[str, float] = None
    
    def __post_init__(self):
        if self.per_asset_caps is None:
            self.per_asset_caps = {
                "ETH": 40.0,
                "BTC": 40.0,
                "LINK": 30.0,
                "SOL": 20.0,
                "WEATHER": 30.0
            }
    
    @classmethod
    def load(cls, config_file: str = CONFIG_FILE) -> 'PortfolioConfig':
        """Load config from file or use defaults"""
        if os.path.exists(config_file):
            with open(config_file) as f:
                data = json.load(f)
                # Filter to only valid fields
                valid_fields = {f.name for f in fields(cls)}
                filtered = {k: v for k, v in data.items() if k in valid_fields}
                return cls(**filtered)
        return cls()
        return cls()
    
    def save(self, config_file: str = CONFIG_FILE):
        """Save config to file"""
        with open(config_file, 'w') as f:
            json.dump(asdict(self), f, indent=2)


@dataclass
class DailyState:
    """Track daily trading state"""
    date: str
    total_traded: float = 0.0
    trade_count: int = 0
    total_pnl: float = 0.0
    realized_pnl: float = 0.0  # Track actual losses/gains for the day
    
    @classmethod
    def load(cls, state_file: str = STATE_FILE) -> 'DailyState':
        """Load today's state or create new"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
                # Filter to only valid fields
                valid_fields = {f.name for f in fields(cls)}
                filtered = {k: v for k, v in data.items() if k in valid_fields}
                if filtered.get("date") == today:
                    return cls(**filtered)
        
        return cls(date=today)
    
    def save(self, state_file: str = STATE_FILE):
        """Save state to file"""
        with open(state_file, 'w') as f:
            json.dump(asdict(self), f, indent=2)


class PortfolioTrader:
    """
    Main portfolio trading interface
    
    Usage:
        trader = PortfolioTrader()
        trader.add_signal("ETH", "UP", edge=0.08, confidence=0.75, market_id="abc123")
        trader.add_signal("BTC", "UP", edge=0.06, confidence=0.80, market_id="def456")
        allocations = trader.optimize_and_execute()
    """
    
    def __init__(self, config: Optional[PortfolioConfig] = None):
        self.config = config or PortfolioConfig.load()
        self.state = DailyState.load()
        self.signals: List[Dict] = []
        self.optimizer = FrankWolfeOptimizer(
            total_budget=self.config.total_budget,
            max_daily_exposure=self.config.max_daily_exposure,
            max_per_trade=self.config.max_per_trade,
            max_bankroll_pct=self.config.max_bankroll_pct,
            per_asset_caps=self.config.per_asset_caps,
            paper_mode=self.config.paper_mode
        )
    
    def add_signal(
        self,
        asset: str,
        direction: str,
        edge: float,
        confidence: float,
        market_id: str,
        min_stake: float = 1.0,
        max_stake: float = 50.0
    ):
        """Add a trading signal to the portfolio"""
        self.signals.append({
            "asset": asset,
            "direction": direction,
            "edge": edge,
            "confidence": confidence,
            "market_id": market_id,
            "min_stake": min_stake,
            "max_stake": max_stake,
            "timestamp": datetime.now().isoformat()
        })
    
    def optimize(self) -> Dict:
        """
        Run Frank-Wolfe optimization on current signals
        
        Returns allocation dict with metadata
        """
        if not self.signals:
            return {"error": "No signals to optimize", "allocations": []}
        
        # Check daily exposure limit
        remaining_budget = self.config.max_daily_exposure - self.state.total_traded
        if remaining_budget <= 0:
            return {
                "error": "Daily exposure limit reached",
                "total_traded_today": self.state.total_traded,
                "allocations": []
            }
        
        # RISK MANAGER VETO: Check for maximum daily drawdown
        # If realized_pnl is negative and its absolute value exceeds the limit, kill the session.
        if self.state.realized_pnl < 0 and abs(self.state.realized_pnl) >= self.config.max_daily_drawdown:
            return {
                "error": "CRITICAL_RISK_VETO: Maximum daily drawdown reached",
                "drawdown": self.state.realized_pnl,
                "limit": -self.config.max_daily_drawdown,
                "allocations": []
            }
        
        # Convert signals to TradeOpportunity objects
        opportunities = [
            TradeOpportunity(
                market_id=sig["market_id"],
                direction=sig["direction"],
                asset=sig["asset"],
                edge=sig["edge"],
                confidence=sig["confidence"],
                min_stake=sig["min_stake"],
                max_stake=min(sig["max_stake"], remaining_budget)
            )
            for sig in self.signals
        ]
        
        # Run optimization
        allocation, metadata = self.optimizer.optimize(opportunities)
        
        # Build result
        allocations = []
        for i, opp in enumerate(opportunities):
            stake = float(allocation[i])
            # Round up small allocations to minimum (if optimizer suggests > 0)
            if stake > 0 and stake < opp.min_stake:
                stake = opp.min_stake  # Round up to minimum
            if stake >= opp.min_stake:
                allocations.append({
                    "asset": opp.asset,
                    "direction": opp.direction,
                    "market_id": opp.market_id,
                    "stake": stake,
                    "expected_value": opp.expected_value(stake),
                    "edge": opp.edge,
                    "confidence": opp.confidence
                })
        
        return {
            "success": True,
            "allocations": allocations,
            "total_stake": metadata["total_allocated"],
            "total_expected_value": metadata["total_expected_value"],
            "iterations": metadata["iterations"],
            "paper_mode": metadata["paper_mode"],
            "timestamp": metadata["timestamp"]
        }
    
    def execute_allocations(self, allocations: List[Dict], execution_callback) -> Dict:
        """
        Execute the optimized allocations
        
        execution_callback: function(market_id, stake, direction) -> order_id
        """
        results = []
        total_executed = 0.0
        
        for alloc in allocations:
            if self.config.paper_mode:
                # Paper mode: just log
                print(f"[PAPER] Would execute: {alloc['asset']} {alloc['direction']} ${alloc['stake']:.2f}")
                results.append({
                    **alloc,
                    "status": "paper",
                    "order_id": None
                })
            else:
                # Live mode: execute
                try:
                    order_id = execution_callback(
                        market_id=alloc["market_id"],
                        stake=alloc["stake"],
                        direction=alloc["direction"]
                    )
                    results.append({
                        **alloc,
                        "status": "executed",
                        "order_id": order_id
                    })
                    total_executed += alloc["stake"]
                except Exception as e:
                    results.append({
                        **alloc,
                        "status": "failed",
                        "error": str(e)
                    })
        
        # Update daily state
        if not self.config.paper_mode:
            self.state.total_traded += total_executed
            self.state.trade_count += len([r for r in results if r["status"] == "executed"])
            self.state.save()
        
        return {
            "executed": len([r for r in results if r["status"] == "executed"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "total_stake": total_executed,
            "results": results
        }
    
    def optimize_and_execute(self, execution_callback=None) -> Dict:
        """
        Full pipeline: optimize + execute
        
        execution_callback: function(market_id, stake, direction) -> order_id
        """
        # Optimize
        opt_result = self.optimize()
        
        if "error" in opt_result:
            return opt_result
        
        # Execute if we have allocations
        if opt_result["allocations"] and execution_callback:
            exec_result = self.execute_allocations(
                opt_result["allocations"],
                execution_callback
            )
            return {**opt_result, "execution": exec_result}
        
        return opt_result
    
    def reset_daily_state(self):
        """Reset daily state (call at midnight or bot startup)"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.date != today:
            self.state = DailyState(date=today)
            self.state.save()
            return True
        return False
    
    def get_comparison(self) -> Dict:
        """Compare FW vs Kelly sizing for current signals"""
        if not self.signals:
            return {"error": "No signals"}
        
        opportunities = [
            TradeOpportunity(
                market_id=sig["market_id"],
                direction=sig["direction"],
                asset=sig["asset"],
                edge=sig["edge"],
                confidence=sig["confidence"],
                min_stake=sig["min_stake"],
                max_stake=sig["max_stake"]
            )
            for sig in self.signals
        ]
        
        return self.optimizer.compare_with_kelly(
            opportunities,
            kelly_fraction=self.config.kelly_fraction
        )


# Example usage
if __name__ == "__main__":
    # Initialize
    trader = PortfolioTrader()
    
    # Add some test signals
    trader.add_signal("ETH", "UP", edge=0.08, confidence=0.75, market_id="eth_5m_up")
    trader.add_signal("BTC", "UP", edge=0.06, confidence=0.80, market_id="btc_5m_up")
    trader.add_signal("LINK", "DOWN", edge=0.10, confidence=0.65, market_id="link_5m_down")
    
    # Optimize
    result = trader.optimize()
    
    print("\n=== Portfolio Optimization Result ===\n")
    print(f"Mode: {'PAPER' if result.get('paper_mode') else 'LIVE'}")
    print(f"Total stake: ${result.get('total_stake', 0):.2f}")
    print(f"Expected value: ${result.get('total_expected_value', 0):.2f}")
    print(f"Optimization iterations: {result.get('iterations', 0)}\n")
    
    print("Allocations:")
    for alloc in result.get("allocations", []):
        print(f"  {alloc['asset']} {alloc['direction']}: ${alloc['stake']:.2f} "
              f"(edge: {alloc['edge']:.1%}, EV: ${alloc['expected_value']:.2f})")
    
    # Compare with Kelly
    print("\n=== FW vs Kelly Comparison ===")
    comparison = trader.get_comparison()
    if "error" not in comparison:
        print(f"Kelly EV: ${comparison['kelly']['expected_value']:.2f}")
        print(f"FW EV: ${comparison['frank_wolfe']['expected_value']:.2f}")
        print(f"Improvement: {comparison['improvement']:.1%}")
        print(f"Recommendation: {comparison['recommendation']}")
