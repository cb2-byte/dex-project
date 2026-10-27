#!/usr/bin/env python3
"""
Frank-Wolfe Portfolio Optimizer for Polymarket Trading Bots
Projection-free optimization for capital allocation across multiple trades

Based on: "The Frank-Wolfe Algorithm: A Short Introduction" (Pokutta, 2024)
https://link.springer.com/article/10.1365/s13291-023-00275-x
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TradeOpportunity:
    """Represents a single trading opportunity"""
    market_id: str
    direction: str  # 'UP' or 'DOWN'
    asset: str  # 'ETH', 'BTC', 'LINK', etc.
    edge: float  # Expected edge (0.0 to 1.0)
    confidence: float  # Signal confidence (0.0 to 1.0)
    min_stake: float = 1.0  # Minimum stake in USDC
    max_stake: float = 50.0  # Maximum stake per trade
    
    def expected_value(self, stake: float) -> float:
        """Calculate expected value for given stake"""
        return stake * self.edge * self.confidence


class FrankWolfeOptimizer:
    """
    Frank-Wolfe optimizer for portfolio allocation
    
    Constraints supported:
    - Max per-trade stake
    - Max daily exposure
    - Max bankroll percentage
    - Per-asset caps
    """
    
    def __init__(
        self,
        total_budget: float,
        max_daily_exposure: float = 100.0,
        max_per_trade: float = 50.0,
        max_bankroll_pct: float = 0.30,
        per_asset_caps: Optional[Dict[str, float]] = None,
        paper_mode: bool = True
    ):
        self.total_budget = total_budget
        self.max_daily_exposure = max_daily_exposure
        self.max_per_trade = max_per_trade
        self.max_bankroll_pct = max_bankroll_pct
        self.per_asset_caps = per_asset_caps or {}
        self.paper_mode = paper_mode
        
        # Adaptive step-size parameters
        self.L = 1.0  # Smoothness estimate
        self.delta = 0.1  # Step-size tolerance
        
    def _linear_minimization_oracle(
        self,
        opportunities: List[TradeOpportunity],
        gradient: List[float]
    ) -> int:
        """
        LMO: Find the vertex that minimizes linear objective
        Returns index of best opportunity to allocate to
        """
        if len(opportunities) == 0:
            return -1
            
        # Gradient points in direction of steepest ascent
        # We want to minimize -gradient (maximize expected value)
        best_idx = max(range(len(gradient)), key=lambda i: gradient[i])
        return best_idx
    
    def _compute_gradient(
        self,
        opportunities: List[TradeOpportunity],
        current_allocation: List[float]
    ) -> List[float]:
        """
        Compute gradient of objective function
        Objective: maximize sum of expected values
        """
        gradient = []
        for i, opp in enumerate(opportunities):
            if current_allocation[i] < opp.max_stake:
                # Marginal expected value
                gradient.append(opp.edge * opp.confidence)
            else:
                gradient.append(0.0)
        return gradient
    
    def _get_feasible_step_size(
        self,
        current_allocation: List[float],
        vertex: List[float]
    ) -> float:
        """
        Find maximum feasible step size for moving from x toward vertex
        x_new = x + gamma * (vertex - x)
        """
        # Start with full step
        gamma = 1.0
        
        # Constraint: Total budget (bankroll %)
        max_total = self.total_budget * self.max_bankroll_pct
        current_total = sum(current_allocation)
        vertex_total = sum(vertex)
        if vertex_total > current_total:
            gamma = min(gamma, (max_total - current_total) / (vertex_total - current_total + 1e-10))
        
        # Constraint: Daily exposure
        if vertex_total > current_total:
            gamma = min(gamma, (self.max_daily_exposure - current_total) / (vertex_total - current_total + 1e-10))
        
        # Constraint: Per-asset caps
        for asset, cap in self.per_asset_caps.items():
            asset_indices = [i for i, opp in enumerate(self.opportunities) if opp.asset == asset]
            if asset_indices:
                current_asset = sum(current_allocation[i] for i in asset_indices)
                vertex_asset = sum(vertex[i] for i in asset_indices)
                if vertex_asset > current_asset:
                    gamma = min(gamma, (cap - current_asset) / (vertex_asset - current_asset + 1e-10))
        
        return max(0.0, min(1.0, gamma))
    
    def _adaptive_step_size(
        self,
        t: int,
        primal_gap: float
    ) -> float:
        """
        Adaptive step-size strategy (Pokutta 2024, Sect 4.5)
        """
        if primal_gap <= 0:
            return 0.0
        
        # Classic Frank-Wolfe step size with adaptive adjustment
        gamma = 2.0 / (2.0 + t)
        
        # Adjust based on primal gap
        if primal_gap > self.delta:
            gamma = min(1.0, gamma * (1.0 + self.delta / primal_gap))
        else:
            gamma = max(0.1, gamma * 0.9)
        
        return gamma
    
    def optimize(
        self,
        opportunities: List[TradeOpportunity],
        max_iterations: int = 50,
        tolerance: float = 1e-4
    ) -> Tuple[List[float], Dict]:
        """
        Run Frank-Wolfe optimization
        
        Returns:
        - Optimal allocation array
        - Optimization metadata
        """
        if not opportunities:
            return [], {"converged": True, "iterations": 0}
        
        self.opportunities = opportunities
        n = len(opportunities)
        
        # Initialize at origin (no allocation)
        x = [0.0] * n
        
        history = {
            "objective": [],
            "primal_gap": [],
            "allocations": []
        }
        
        converged = False
        iterations = 0
        
        for t in range(max_iterations):
            iterations = t + 1
            
            # Compute gradient
            gradient = self._compute_gradient(opportunities, x)
            
            # LMO: find best vertex
            vertex_idx = self._linear_minimization_oracle(opportunities, gradient)
            if vertex_idx < 0:
                break
            
            # Construct vertex (allocate max to best opportunity)
            vertex = [0.0] * n
            vertex[vertex_idx] = opportunities[vertex_idx].max_stake
            
            # Compute primal gap (direction of improvement)
            # gap = max_v <gradient, v - x> = <gradient, vertex - x>
            primal_gap = sum(g * (vertex[i] - x[i]) for i, g in enumerate(gradient))
            
            # Debug print for first iteration
            if t == 0:
                print(f"  [DEBUG] Iteration 0: gradient={[f'{g:.3f}' for g in gradient]}, vertex_idx={vertex_idx}")
                print(f"  [DEBUG] vertex={vertex}, primal_gap={primal_gap:.4f}")
            
            # Check convergence
            if primal_gap < tolerance:
                converged = True
                if t == 0:
                    print(f"  [DEBUG] Converged immediately - primal_gap < tolerance")
                break
            
            # Adaptive step-size
            gamma = self._adaptive_step_size(t, primal_gap)
            
            # Ensure feasibility
            feasible_gamma = self._get_feasible_step_size(x, vertex)
            gamma = min(gamma, feasible_gamma)
            
            # Update
            x = [x[i] + gamma * (vertex[i] - x[i]) for i in range(n)]
            
            # Record history
            obj_value = sum(opp.expected_value(x[i]) for i, opp in enumerate(opportunities))
            history["objective"].append(obj_value)
            history["primal_gap"].append(primal_gap)
            history["allocations"].append(x[:])  # Copy list
        
        # Build result
        metadata = {
            "converged": converged,
            "iterations": iterations,
            "total_allocated": sum(x),
            "total_expected_value": sum(opp.expected_value(x[i]) for i, opp in enumerate(opportunities)),
            "paper_mode": self.paper_mode,
            "timestamp": datetime.now().isoformat(),
            "history": history
        }
        
        return x, metadata
    
    def compare_with_kelly(
        self,
        opportunities: List[TradeOpportunity],
        kelly_fraction: float = 0.25
    ) -> Dict:
        """
        Compare FW optimization vs simple Kelly sizing
        """
        fw_allocation, fw_meta = self.optimize(opportunities)
        
        # Simple Kelly: edge * fraction, capped at max_stake
        kelly_allocation = [0.0] * len(opportunities)
        for i, opp in enumerate(opportunities):
            kelly_stake = opp.edge * kelly_fraction * self.total_budget
            kelly_allocation[i] = min(kelly_stake, opp.max_stake)
        
        kelly_ev = sum(opp.expected_value(kelly_allocation[i]) for i, opp in enumerate(opportunities))
        fw_ev = fw_meta["total_expected_value"]
        
        return {
            "frank_wolfe": {
                "total_stake": fw_meta["total_allocated"],
                "expected_value": fw_ev,
                "iterations": fw_meta["iterations"]
            },
            "kelly": {
                "total_stake": sum(kelly_allocation),
                "expected_value": kelly_ev
            },
            "improvement": (fw_ev - kelly_ev) / kelly_ev if kelly_ev > 0 else 0,
            "recommendation": "frank_wolfe" if fw_ev > kelly_ev else "kelly"
        }


# Example usage / testing
if __name__ == "__main__":
    # Test with sample opportunities
    opportunities = [
        TradeOpportunity("eth_5m_up", "UP", "ETH", 0.08, 0.75),
        TradeOpportunity("btc_5m_up", "UP", "BTC", 0.06, 0.80),
        TradeOpportunity("link_5m_down", "DOWN", "LINK", 0.10, 0.65),
    ]
    
    print("Testing Frank-Wolfe Optimizer")
    print("=" * 50)
    
    optimizer = FrankWolfeOptimizer(
        total_budget=100.0,
        max_daily_exposure=100.0,
        max_per_trade=50.0,
        paper_mode=True
    )
    
    # Debug gradient
    gradient = optimizer._compute_gradient(opportunities, [0.0, 0.0, 0.0])
    print(f"\nGradient at origin: {gradient}")
    
    vertex_idx = optimizer._linear_minimization_oracle(opportunities, gradient)
    print(f"Best vertex index: {vertex_idx} (should be 2, LINK with highest edge*conf)")
    
    allocation, metadata = optimizer.optimize(opportunities)
    
    print("\n=== Frank-Wolfe Portfolio Optimization ===\n")
    print(f"Mode: {'PAPER' if metadata['paper_mode'] else 'LIVE'}")
    print(f"Converged: {metadata['converged']} ({metadata['iterations']} iterations)")
    print(f"Total allocated: ${metadata['total_allocated']:.2f}")
    print(f"Total expected value: ${metadata['total_expected_value']:.2f}\n")
    
    print("Allocation:")
    for i, opp in enumerate(opportunities):
        print(f"  {opp.asset} {opp.direction}: ${allocation[i]:.2f} (edge: {opp.edge:.1%}, conf: {opp.confidence:.1%})")
    
    # Compare with Kelly
    comparison = optimizer.compare_with_kelly(opportunities)
    print(f"\n=== vs Kelly (quarter) ===")
    print(f"Kelly EV: ${comparison['kelly']['expected_value']:.2f}")
    print(f"FW EV: ${comparison['frank_wolfe']['expected_value']:.2f}")
    print(f"Improvement: {comparison['improvement']:.1%}")
    print(f"Recommendation: {comparison['recommendation']}")
