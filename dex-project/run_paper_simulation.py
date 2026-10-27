#!/usr/bin/env python3
"""
Paper Trading Simulation Entry Point
=====================================
Runs the paper trading engine with all three strategies using mocked or live market data.
This is the main entry point for the paper_engine package.

Does NOT modify the original paper_dex_sniper.py - uses the new paper_engine modules.
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from paper_engine.config import PaperConfig, load_config
from paper_engine.market_data import (
    MarketDataValidator,
    PriceQuote,
    create_quote_from_cex,
    create_quote_from_geckoterminal,
)
from paper_engine.triangular import TriangularArbValidator
from paper_engine.cross_exchange import CrossExchangeArbValidator, TransferPath
from paper_engine.meme_sniper import MemeSniperValidator
from paper_engine.execution import PaperExecutionEngine, NetReturnResult
from paper_engine.net_return import CostBreakdown
from paper_engine.records import PaperTradeRecorder
from paper_engine.metrics import PerformanceMetrics, generate_performance_report
from paper_engine.boundaries import set_paper_mode, get_boundary


def load_mock_market_data():
    """Generate mock market data for testing."""
    now = time.time()

    # CEX quotes
    coinbase_eth = create_quote_from_cex(
        "ETH/USDC", 2500.0, "coinbase",
        bid=2499.5, ask=2500.5,
        liquidity_usd=1_000_000.0,
    )
    kraken_eth = create_quote_from_cex(
        "ETH/USDC", 2510.0, "kraken",
        bid=2509.5, ask=2510.5,
        liquidity_usd=800_000.0,
    )
    coinbase_sol = create_quote_from_cex(
        "SOL/USDC", 100.0, "coinbase",
        bid=99.9, ask=100.1,
        liquidity_usd=500_000.0,
    )

    # DEX quotes (GeckoTerminal style)
    dex_quotes = {
        "ETH/USDC": create_quote_from_geckoterminal(
            "ETH/USDC", 2500.0, "0x123...", 100_000.0, 500_000.0, 5.0,
        ),
        "SOL/USDC": create_quote_from_geckoterminal(
            "SOL/USDC", 100.0, "0x456...", 50_000.0, 200_000.0, 5.0,
        ),
        "ETH/SOL": create_quote_from_geckoterminal(
            "ETH/SOL", 25.5, "0x789...", 30_000.0, 100_000.0, 5.0,
        ),
    }

    # Meme pools
    meme_pools = [
        {
            "id": "0xmeme1...",
            "attributes": {
                "base_token_symbol": "PEPE",
                "quote_token_symbol": "USDC",
                "price_usd": 0.000001,
                "price_change_percentage": {"h24": 15.0},
                "reserve_in_usd": 80_000.0,
                "volume_usd": {"h24": 500_000.0},
                "fee": 0.003,
            },
        },
        {
            "id": "0xmeme2...",
            "attributes": {
                "base_token_symbol": "WOJAK",
                "quote_token_symbol": "USDC",
                "price_usd": 0.000005,
                "price_change_percentage": {"h24": 8.0},
                "reserve_in_usd": 40_000.0,
                "volume_usd": {"h24": 200_000.0},
                "fee": 0.003,
            },
        },
        {
            "id": "0xmeme3...",
            "attributes": {
                "base_token_symbol": "TURBO",
                "quote_token_symbol": "USDC",
                "price_usd": 0.00001,
                "price_change_percentage": {"h24": 0.5},  # Low momentum
                "reserve_in_usd": 30_000.0,
                "volume_usd": {"h24": 100_000.0},
                "fee": 0.003,
            },
        },
    ]

    return {
        "cex": {
            "coinbase": {"ETH/USDC": coinbase_eth, "SOL/USDC": coinbase_sol},
            "kraken": {"ETH/USDC": kraken_eth},
        },
        "dex": dex_quotes,
        "meme_pools": meme_pools,
    }


def run_triangular_strategy(config, engine, validator, recorder, market_data, trade_size_usd):
    """Run triangular arbitrage strategy."""
    print("\n" + "="*60)
    print("RUNNING TRIANGULAR ARBITRAGE")
    print("="*60)

    dex = market_data["dex"]
    signal = validator.validate_and_score(
        leg1_quote=dex["ETH/USDC"],
        leg2_quote=dex["SOL/USDC"],
        leg3_quote=dex["ETH/SOL"],
        trade_size_usd=trade_size_usd,
        chain="base",
    )

    recorder.log_signal(
        strategy="triangular",
        symbol="ETH/SOL/USDC",
        accepted=signal.accepted,
        gross_return_pct=signal.gross_return_pct,
        net_return_pct=signal.net_return_pct,
        rejection_reason=signal.rejection_reason,
        rejection_message=signal.rejection_message,
        trade_size_usd=signal.trade_size_usd,
        quotes=signal.quotes_used,
        validation_details=signal.validation_details,
    )

    print(f"Signal: {'ACCEPTED' if signal.accepted else 'REJECTED'}")
    print(f"  Gross Return: {signal.gross_return_pct:.4f}%")
    print(f"  Net Return:   {signal.net_return_pct:.4f}%")
    if signal.rejection_message:
        print(f"  Reason: {signal.rejection_message}")

    if signal.accepted:
        # Create net return object for execution
        net_return = NetReturnResult(
            gross_return_pct=signal.gross_return_pct,
            net_return_pct=signal.net_return_pct,
            cost_breakdown=CostBreakdown(
                trading_fees_bps=signal.cost_breakdown.get("trading_fees_bps", 0),
                slippage_bps=signal.cost_breakdown.get("slippage_bps", 0),
                gas_usd=signal.cost_breakdown.get("gas_usd", 0),
            ),
            passes_threshold=True,
            trade_size_usd=signal.trade_size_usd,
        )

        position, error = engine.open_position(
            strategy="triangular",
            symbol="ETH/USDC",
            side="buy",
            quote=dex["ETH/USDC"],
            size_usd=trade_size_usd,
            net_return=net_return,
        )

        if position:
            print(f"  Opened position: {position.position_id} (${position.size_usd:.2f})")

            # Simulate price movement
            time.sleep(0.1)  # Simulate time passing
            exit_quote = PriceQuote(
                symbol="ETH/USDC",
                price=dex["ETH/USDC"].price * 1.01,  # 1% favorable move
                source="geckoterminal",
                timestamp=time.time(),
                liquidity_usd=dex["ETH/USDC"].liquidity_usd,
            )
            engine.mark_to_market({"ETH/USDC": exit_quote})

            trade, error = engine.close_position(
                position_id=position.position_id,
                exit_quote=exit_quote,
                net_return=net_return,
            )

            if trade:
                trade.strategy = "triangular"
                print(f"  Closed position: Net P&L ${trade.net_pnl_usd:.4f} ({trade.return_pct:.4f}%)")
                recorder.log_trade(
                    strategy="triangular",
                    symbol=trade.symbol,
                    side=trade.side,
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    size_usd=trade.size_usd,
                    fees_usd=trade.fees_usd,
                    slippage_usd=trade.slippage_usd,
                    gas_usd=trade.gas_usd,
                    gross_pnl_usd=trade.gross_pnl_usd,
                    net_pnl_usd=trade.net_pnl_usd,
                    hold_seconds=trade.hold_seconds,
                    return_pct=trade.return_pct,
                    entry_fill=position.entry_fill.__dict__,
                    exit_fill=position.exit_fill.__dict__,
                    validation_details=signal.validation_details,
                )
            else:
                print(f"  Close error: {error}")

    return signal


def run_cross_exchange_strategy(config, engine, validator, recorder, market_data, trade_size_usd):
    """Run cross-exchange arbitrage strategy."""
    print("\n" + "="*60)
    print("RUNNING CROSS-EXCHANGE ARBITRAGE")
    print("="*60)

    cex = market_data["cex"]
    signal = validator.validate_and_score(
        quote_a=cex["coinbase"]["ETH/USDC"],
        quote_b=cex["kraken"]["ETH/USDC"],
        trade_size_usd=trade_size_usd,
        transfer_path=TransferPath.SAME_CHAIN,
    )

    recorder.log_signal(
        strategy="cross_exchange",
        symbol="ETH/USDC",
        accepted=signal.accepted,
        gross_return_pct=signal.gross_return_pct,
        net_return_pct=signal.net_return_pct,
        rejection_reason=signal.rejection_reason,
        rejection_message=signal.rejection_message,
        trade_size_usd=signal.trade_size_usd,
        quotes=signal.quotes_used,
        validation_details=signal.validation_details,
    )

    print(f"Signal: {'ACCEPTED' if signal.accepted else 'REJECTED'}")
    print(f"  Gross Return: {signal.gross_return_pct:.4f}%")
    print(f"  Net Return:   {signal.net_return_pct:.4f}%")
    if signal.rejection_message:
        print(f"  Reason: {signal.rejection_message}")

    if signal.accepted:
        net_return = NetReturnResult(
            gross_return_pct=signal.gross_return_pct,
            net_return_pct=signal.net_return_pct,
            cost_breakdown=CostBreakdown(
                trading_fees_bps=signal.cost_breakdown.get("trading_fees_bps", 0),
                slippage_bps=signal.cost_breakdown.get("slippage_bps", 0),
                gas_usd=signal.cost_breakdown.get("gas_usd", 0),
            ),
            passes_threshold=True,
            trade_size_usd=signal.trade_size_usd,
        )

        position, error = engine.open_position(
            strategy="cross_exchange",
            symbol="ETH/USDC",
            side="buy",
            quote=cex["coinbase"]["ETH/USDC"],
            size_usd=trade_size_usd,
            net_return=net_return,
        )

        if position:
            print(f"  Opened position: {position.position_id} (${position.size_usd:.2f})")

            time.sleep(0.1)
            exit_quote = PriceQuote(
                symbol="ETH/USDC",
                price=cex["coinbase"]["ETH/USDC"].price * 1.008,
                source="coinbase",
                timestamp=time.time(),
                liquidity_usd=cex["coinbase"]["ETH/USDC"].liquidity_usd,
            )
            engine.mark_to_market({"ETH/USDC": exit_quote})

            trade, error = engine.close_position(
                position_id=position.position_id,
                exit_quote=exit_quote,
                net_return=net_return,
            )

            if trade:
                trade.strategy = "cross_exchange"
                print(f"  Closed position: Net P&L ${trade.net_pnl_usd:.4f} ({trade.return_pct:.4f}%)")
                recorder.log_trade(
                    strategy="cross_exchange",
                    symbol=trade.symbol,
                    side=trade.side,
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    size_usd=trade.size_usd,
                    fees_usd=trade.fees_usd,
                    slippage_usd=trade.slippage_usd,
                    gas_usd=trade.gas_usd,
                    gross_pnl_usd=trade.gross_pnl_usd,
                    net_pnl_usd=trade.net_pnl_usd,
                    hold_seconds=trade.hold_seconds,
                    return_pct=trade.return_pct,
                    entry_fill=position.entry_fill.__dict__,
                    exit_fill=position.exit_fill.__dict__,
                    validation_details=signal.validation_details,
                )
            else:
                print(f"  Close error: {error}")

    return signal


def run_meme_sniper_strategy(config, engine, validator, recorder, market_data, trade_size_usd):
    """Run meme sniper strategy."""
    print("\n" + "="*60)
    print("RUNNING MEME SNIPER")
    print("="*60)

    signals = []
    for pool in market_data["meme_pools"]:
        attrs = pool["attributes"]
        symbol = f"{attrs['base_token_symbol']}/{attrs['quote_token_symbol']}"

        entry_quote = create_quote_from_geckoterminal(
            symbol=symbol,
            price=attrs["price_usd"],
            pair_address=pool["id"],
            liquidity_usd=attrs["reserve_in_usd"],
            volume_24h_usd=attrs["volume_usd"]["h24"],
            fee_tier_bps=attrs["fee"] * 10000,
        )

        # Projected exit with momentum
        momentum = min(attrs["price_change_percentage"]["h24"], config.meme_momentum_cap_pct)
        exit_price = entry_quote.price * (1 + momentum / 100.0)
        exit_quote = PriceQuote(
            symbol=symbol,
            price=exit_price,
            source="geckoterminal_projected",
            timestamp=time.time(),
            liquidity_usd=entry_quote.liquidity_usd,
        )

        signal = validator.validate_and_score(
            pool_data=pool,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=trade_size_usd,
        )

        recorder.log_signal(
            strategy="meme_sniper",
            symbol=symbol,
            accepted=signal.accepted,
            gross_return_pct=signal.gross_return_pct,
            net_return_pct=signal.net_return_pct,
            rejection_reason=signal.rejection_reason,
            rejection_message=signal.rejection_message,
            trade_size_usd=signal.trade_size_usd,
            quotes=signal.quotes_used,
            validation_details=signal.validation_details,
        )

        signals.append(signal)

        print(f"\n  {symbol}:")
        print(f"    Momentum: {attrs['price_change_percentage']['h24']:.1f}% (capped: {signal.momentum_signal_pct:.1f}%)")
        print(f"    Signal: {'ACCEPTED' if signal.accepted else 'REJECTED'}")
        print(f"    Net Return: {signal.net_return_pct:.4f}%")
        if signal.rejection_message:
            print(f"    Reason: {signal.rejection_message}")

        if signal.accepted:
            net_return = NetReturnResult(
                gross_return_pct=signal.gross_return_pct,
                net_return_pct=signal.net_return_pct,
                cost_breakdown=CostBreakdown(
                    trading_fees_bps=signal.cost_breakdown.get("trading_fees_bps", 0),
                    slippage_bps=signal.cost_breakdown.get("slippage_bps", 0),
                    adverse_drift_bps=signal.cost_breakdown.get("adverse_drift_bps", 0),
                    gas_usd=signal.cost_breakdown.get("gas_usd", 0),
                ),
                passes_threshold=True,
                trade_size_usd=signal.trade_size_usd,
            )

            position, error = engine.open_position(
                strategy="meme_sniper",
                symbol=symbol,
                side="buy",
                quote=entry_quote,
                size_usd=trade_size_usd,
                net_return=net_return,
            )

            if position:
                print(f"    Opened position: {position.position_id} (${position.size_usd:.2f})")

                time.sleep(0.1)
                # Meme coins - quick exit with slight slippage
                exit_quote2 = PriceQuote(
                    symbol=symbol,
                    price=exit_quote.price * 0.995,  # Slight adverse move
                    source="geckoterminal",
                    timestamp=time.time() + 120,
                    liquidity_usd=entry_quote.liquidity_usd,
                )
                engine.mark_to_market({symbol: exit_quote2})

                trade, error = engine.close_position(
                    position_id=position.position_id,
                    exit_quote=exit_quote2,
                    net_return=net_return,
                )

                if trade:
                    trade.strategy = "meme_sniper"
                    print(f"    Closed: Net P&L ${trade.net_pnl_usd:.4f} ({trade.return_pct:.4f}%)")
                    recorder.log_trade(
                        strategy="meme_sniper",
                        symbol=trade.symbol,
                        side=trade.side,
                        entry_time=trade.entry_time,
                        exit_time=trade.exit_time,
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        size_usd=trade.size_usd,
                        fees_usd=trade.fees_usd,
                        slippage_usd=trade.slippage_usd,
                        gas_usd=trade.gas_usd,
                        gross_pnl_usd=trade.gross_pnl_usd,
                        net_pnl_usd=trade.net_pnl_usd,
                        hold_seconds=trade.hold_seconds,
                        return_pct=trade.return_pct,
                        entry_fill=position.entry_fill.__dict__,
                        exit_fill=position.exit_fill.__dict__,
                        validation_details=signal.validation_details,
                    )

    return signals


def run_paper_simulation(config_path=None, trade_size_usd=100.0, mock_data=True):
    """Main simulation entry point."""
    print("="*60)
    print("PAPER TRADING SIMULATION")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Mode: PAPER (no live execution)")

    # Set paper mode boundary
    set_paper_mode(True)
    boundary = get_boundary()
    print(f"Execution boundary: ACTIVE (paper_mode={boundary.paper_mode})")

    # Load configuration
    config = load_config(config_path)
    print(f"Starting capital: ${config.starting_capital_usd:.2f}")
    print(f"Max position: {config.max_position_pct:.0%} (${config.starting_capital_usd * config.max_position_pct:.2f})")
    print(f"Max daily exposure: {config.max_daily_exposure_pct:.0%} (${config.starting_capital_usd * config.max_daily_exposure_pct:.2f})")
    print(f"Max drawdown: {config.max_drawdown_pct:.0%}")
    print(f"Min net edge: {config.min_net_edge_pct:.2f}%")

    # Initialize components
    engine = PaperExecutionEngine(config)
    triangular_validator = TriangularArbValidator(config)
    cross_exchange_validator = CrossExchangeArbValidator(config)
    meme_sniper_validator = MemeSniperValidator(config)

    # Initialize recorder
    session_id = f"sim_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    log_dir = Path(__file__).parent / "paper_trades"
    recorder = PaperTradeRecorder(log_dir=str(log_dir), session_id=session_id)
    print(f"Recorder: {log_dir} (session: {session_id})")

    # Load market data
    if mock_data:
        market_data = load_mock_market_data()
        print("\nUsing MOCK market data")
    else:
        # TODO: Implement live data fetching
        raise NotImplementedError("Live data fetching not yet implemented")
        market_data = {}

    # Run all strategies
    triangular_signal = run_triangular_strategy(
        config, engine, triangular_validator, recorder, market_data, trade_size_usd
    )
    cross_exchange_signal = run_cross_exchange_strategy(
        config, engine, cross_exchange_validator, recorder, market_data, trade_size_usd
    )
    meme_signals = run_meme_sniper_strategy(
        config, engine, meme_sniper_validator, recorder, market_data, trade_size_usd
    )

    # Final portfolio state
    print("\n" + "="*60)
    print("FINAL PORTFOLIO STATE")
    print("="*60)
    state = engine.get_state()
    print(f"Starting Capital: ${state['starting_capital_usd']:.2f}")
    print(f"Final Equity:     ${state['portfolio_value_usd']:.2f}")
    print(f"Total Return:     {state['total_return_pct']:.4f}%")
    print(f"Open Positions:   {state['open_positions']}")
    print(f"Closed Trades:    {state['closed_trades']}")
    print(f"Daily P&L:        ${state['daily_pnl_usd']:.4f} ({state['daily_pnl_pct']:.4f}%)")
    print(f"Max Drawdown:     {state['max_drawdown_pct']:.4f}%")
    print(f"Kill Switch:      {'TRIGGERED' if state['kill_switch_triggered'] else 'OK'}")

    # Performance metrics
    if engine.closed_trades:
        print("\n" + "="*60)
        print("PERFORMANCE METRICS")
        print("="*60)
        metrics = PerformanceMetrics()
        trade_dicts = [t.to_dict() for t in engine.closed_trades]
        result = metrics.calculate(trade_dicts)
        print(generate_performance_report(result))

    # Daily snapshot
    recorder.log_daily_snapshot(state)
    recorder.close()

    print(f"\nSimulation complete. Logs saved to: {log_dir}")
    print(f"Session ID: {session_id}")

    return {
        "session_id": session_id,
        "engine_state": state,
        "triangular_signal": triangular_signal.to_dict() if hasattr(triangular_signal, 'to_dict') else str(triangular_signal),
        "cross_exchange_signal": cross_exchange_signal.to_dict() if hasattr(cross_exchange_signal, 'to_dict') else str(cross_exchange_signal),
        "meme_signals": [s.to_dict() if hasattr(s, 'to_dict') else str(s) for s in meme_signals],
    }


def main():
    parser = argparse.ArgumentParser(description="Paper Trading Simulation")
    parser.add_argument("--config", "-c", help="Path to config YAML file")
    parser.add_argument("--trade-size", "-s", type=float, default=100.0, help="Trade size in USD")
    parser.add_argument("--mock", action="store_true", default=True, help="Use mock data (default)")
    parser.add_argument("--live", action="store_true", help="Use live data (not implemented)")
    args = parser.parse_args()

    if args.live:
        print("ERROR: Live data mode not yet implemented")
        sys.exit(1)

    try:
        result = run_paper_simulation(
            config_path=args.config,
            trade_size_usd=args.trade_size,
            mock_data=args.mock,
        )
        print("\n✅ Simulation completed successfully")
    except Exception as e:
        print(f"\n❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()