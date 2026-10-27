"""
Tests for Net Return Calculations
==================================
Tests negative net returns, cost models, slippage, fees, transfer costs.
"""

import pytest
from paper_engine.config import PaperConfig, FeeSchedule, SlippageModel
from paper_engine.market_data import PriceQuote
from paper_engine.net_return import (
    NetReturnCalculator,
    NetReturnResult,
    CostBreakdown,
    RejectionReason,
    TransferPath,
)


class TestNetReturnCalculator:
    """Test the NetReturnCalculator class."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            min_net_edge_pct=0.20,
            fee_schedule=FeeSchedule(
                trading_fee_bps={
                    "coinbase": 30.0,
                    "kraken": 26.0,
                    "uniswap_v3_base": 5.0,
                },
                gas_estimate_usd={"base": 0.01, "ethereum": 5.0},
                withdrawal_fee_usd={"coinbase": 0.0, "kraken": 2.5},
                bridge_fee_bps={"hop": 5.0},
            ),
            slippage_model=SlippageModel(base_bps=10.0, alpha=0.5),
        )

    @pytest.fixture
    def calculator(self, config):
        return NetReturnCalculator(config)

    @pytest.fixture
    def eth_quote(self):
        return PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=__import__('time').time(),
            liquidity_usd=1_000_000.0,
        )

    @pytest.fixture
    def sol_quote(self):
        return PriceQuote(
            symbol="SOL/USDC",
            price=100.0,
            source="coinbase",
            timestamp=__import__('time').time(),
            liquidity_usd=500_000.0,
        )

    @pytest.fixture
    def eth_sol_quote(self):
        return PriceQuote(
            symbol="ETH/SOL",
            price=25.0,
            source="uniswap_v3_base",
            timestamp=__import__('time').time(),
            liquidity_usd=200_000.0,
        )

    # ============================================================
    # Triangular Arbitrage Tests
    # ============================================================
    def test_triangular_positive_gross_negative_net(self, calculator, eth_quote, sol_quote, eth_sol_quote):
        """Test that positive gross return can become negative net after costs."""
        # Create quotes that give positive gross but costs exceed it
        # ETH/USDC = 2500, SOL/USDC = 100, ETH/SOL = 25.1 (slightly favorable)
        eth_quote.price = 2500.0
        sol_quote.price = 100.0
        eth_sol_quote.price = 25.1  # 1 ETH = 25.1 SOL

        # Round trip: 1000 USDC -> 0.4 ETH -> 10.04 SOL -> 1004 USDC = 0.4% gross
        # But costs: 3 legs * (30+10) bps fees+slippage + gas = ~1.2% costs
        # Net should be negative

        result = calculator.triangular_net_return(
            leg1_quote=eth_quote,
            leg2_quote=sol_quote,
            leg3_quote=eth_sol_quote,
            trade_size_usd=1000.0,
            chain="base",
        )

        # Should detect negative net return
        assert result.rejection_reason == RejectionReason.NEGATIVE_NET_RETURN
        assert not result.passes_threshold
        assert result.net_return_pct < 0

    def test_triangular_profitable_after_costs(self, calculator, eth_quote, sol_quote, eth_sol_quote):
        """Test triangular with enough edge to be profitable after costs."""
        # Make prices very favorable
        eth_quote.price = 2500.0
        sol_quote.price = 100.0
        eth_sol_quote.price = 30.0  # 1 ETH = 30 SOL (20% edge)

        result = calculator.triangular_net_return(
            leg1_quote=eth_quote,
            leg2_quote=sol_quote,
            leg3_quote=eth_sol_quote,
            trade_size_usd=1000.0,
            chain="base",
        )

        # Should be profitable after costs
        assert result.net_return_pct > 0
        assert result.passes_threshold

    def test_triangular_invalid_quote_rejected(self, calculator, eth_quote, sol_quote, eth_sol_quote):
        """Test that invalid quotes are rejected."""
        eth_quote.price = -100  # Invalid

        result = calculator.triangular_net_return(
            leg1_quote=eth_quote,
            leg2_quote=sol_quote,
            leg3_quote=eth_sol_quote,
            trade_size_usd=1000.0,
        )

        assert result.rejection_reason == RejectionReason.INVALID_QUOTE
        assert not result.passes_threshold

    def test_triangular_cost_breakdown_populated(self, calculator, eth_quote, sol_quote, eth_sol_quote):
        """Test that cost breakdown includes all components."""
        eth_quote.price = 2500.0
        sol_quote.price = 100.0
        eth_sol_quote.price = 30.0

        result = calculator.triangular_net_return(
            leg1_quote=eth_quote,
            leg2_quote=sol_quote,
            leg3_quote=eth_sol_quote,
            trade_size_usd=1000.0,
            chain="base",
        )

        cb = result.cost_breakdown
        assert cb.trading_fees_bps > 0
        assert cb.slippage_bps > 0
        assert cb.gas_usd > 0
        assert cb.total_cost_bps == cb.trading_fees_bps + cb.slippage_bps

    # ============================================================
    # Cross-Exchange Arbitrage Tests
    # ============================================================
    def test_cross_exchange_same_chain(self, calculator):
        """Test cross-exchange on same chain (low transfer cost)."""
        buy_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,  # Cheaper
            source="coinbase",
            timestamp=__import__('time').time(),
            liquidity_usd=1_000_000.0,
            exchange="coinbase",
        )
        sell_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2510.0,  # More expensive (0.4% edge)
            source="kraken",
            timestamp=__import__('time').time(),
            liquidity_usd=800_000.0,
            exchange="kraken",
        )

        result = calculator.cross_exchange_net_return(
            buy_quote=buy_quote,
            sell_quote=sell_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.SAME_CHAIN,
        )

        # 0.4% gross - fees (30+26 bps) - slippage - gas
        assert result.gross_return_pct > 0
        assert result.cost_breakdown.gas_usd > 0
        assert result.cost_breakdown.trading_fees_bps == 56.0  # 30 + 26

    def test_cross_exchange_withdraw_deposit(self, calculator):
        """Test cross-exchange with withdraw/deposit costs."""
        buy_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=__import__('time').time(),
            liquidity_usd=1_000_000.0,
            exchange="coinbase",
        )
        sell_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2520.0,  # 0.8% edge
            source="kraken",
            timestamp=__import__('time').time(),
            liquidity_usd=800_000.0,
            exchange="kraken",
        )

        result = calculator.cross_exchange_net_return(
            buy_quote=buy_quote,
            sell_quote=sell_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.WITHDRAW_DEPOSIT,
        )

        # Should include withdrawal + deposit fees
        assert result.cost_breakdown.withdrawal_fees_usd >= 0
        assert result.cost_breakdown.deposit_fees_usd >= 0
        assert result.cost_breakdown.gas_usd > 0

    def test_cross_exchange_bridge(self, calculator):
        """Test cross-exchange with bridge costs."""
        buy_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="uniswap_v3_base",
            timestamp=__import__('time').time(),
            liquidity_usd=1_000_000.0,
        )
        sell_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2550.0,  # 2% edge
            source="uniswap_v3_ethereum",
            timestamp=__import__('time').time(),
            liquidity_usd=2_000_000.0,
        )

        result = calculator.cross_exchange_net_return(
            buy_quote=buy_quote,
            sell_quote=sell_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.BRIDGE,
            bridge_name="hop",
        )

        assert result.cost_breakdown.bridge_fees_bps > 0
        assert result.cost_breakdown.gas_usd > 0

    def test_cross_exchange_no_edge_rejected(self, calculator):
        """Test that no price edge is rejected."""
        buy_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2510.0,
            source="coinbase",
            timestamp=__import__('time').time(),
        )
        sell_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,  # Sell price LOWER than buy - no edge
            source="kraken",
            timestamp=__import__('time').time(),
        )

        result = calculator.cross_exchange_net_return(
            buy_quote=buy_quote,
            sell_quote=sell_quote,
            trade_size_usd=1000.0,
        )

        assert result.rejection_reason == RejectionReason.NEGATIVE_NET_RETURN

    def test_cross_exchange_transfer_cost_exceeds_edge(self, calculator):
        """Test rejection when transfer costs exceed gross edge."""
        # Tiny edge but high transfer costs
        buy_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=__import__('time').time(),
            liquidity_usd=1_000_000.0,
        )
        sell_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2501.0,  # Only 0.04% edge
            source="kraken",
            timestamp=__import__('time').time(),
            liquidity_usd=800_000.0,
        )

        result = calculator.cross_exchange_net_return(
            buy_quote=buy_quote,
            sell_quote=sell_quote,
            trade_size_usd=1000.0,
            transfer_path=TransferPath.WITHDRAW_DEPOSIT,  # $2.50 withdrawal fee
        )

        # Transfer costs should exceed 0.04% edge on $1000 = $0.40
        assert result.rejection_reason in [
            RejectionReason.NEGATIVE_NET_RETURN,
            RejectionReason.TRANSFER_COST_EXCEEDS_EDGE,
        ]

    # ============================================================
    # Meme Sniper Tests
    # ============================================================
    def test_meme_sniper_adverse_drift_exceeds_momentum(self, calculator):
        """Test rejection when adverse drift exceeds momentum signal."""
        entry_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=__import__('time').time(),
            liquidity_usd=50_000.0,
        )
        exit_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.00105,  # 5% projected gain
            source="geckoterminal_projected",
            timestamp=__import__('time').time(),
            liquidity_usd=50_000.0,
        )

        # Long hold time = high adverse drift
        result = calculator.meme_sniper_net_return(
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
            hold_seconds=3600,  # 1 hour = 60 min * 50 bps/min = 3000 bps = 30% adverse drift!
            momentum_signal_pct=5.0,
        )

        # Adverse drift (30%) >> momentum (5%) = negative risk-adjusted return
        assert result.rejection_reason == RejectionReason.NEGATIVE_NET_RETURN
        assert result.net_return_pct < 0

    def test_meme_sniper_short_hold_accepted(self, calculator):
        """Test acceptance with short hold time."""
        entry_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=__import__('time').time(),
            liquidity_usd=50_000.0,
        )
        exit_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.0011,  # 10% projected gain
            source="geckoterminal_projected",
            timestamp=__import__('time').time(),
            liquidity_usd=50_000.0,
        )

        result = calculator.meme_sniper_net_return(
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
            hold_seconds=60,  # 1 minute = 50 bps adverse drift
            momentum_signal_pct=10.0,
        )

        # 10% momentum - 0.5% adverse - costs ≈ positive
        assert result.gross_return_pct == 10.0
        assert result.cost_breakdown.adverse_drift_bps == 50.0

    def test_meme_sniper_momentum_capped(self, calculator):
        """Test that momentum signal is capped at config limit."""
        entry_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=__import__('time').time(),
        )
        exit_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.002,  # 100% gain
            source="geckoterminal_projected",
            timestamp=__import__('time').time(),
        )

        result = calculator.meme_sniper_net_return(
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
            hold_seconds=60,
            momentum_signal_pct=100.0,  # Way above 5% cap
        )

        # Should be capped at config.meme_momentum_cap_pct (5%)
        assert result.gross_return_pct == 5.0


class TestCostBreakdown:
    """Test CostBreakdown calculations."""

    def test_total_cost_bps(self):
        cb = CostBreakdown(
            trading_fees_bps=50.0,
            slippage_bps=30.0,
            bridge_fees_bps=5.0,
            adverse_drift_bps=100.0,
        )
        assert cb.total_cost_bps == 185.0

    def test_total_cost_usd(self):
        cb = CostBreakdown(gas_usd=0.03, withdrawal_fees_usd=2.5, deposit_fees_usd=0.0)
        assert cb.total_cost_usd == 2.53


class TestSlippageModel:
    """Test slippage model calculations."""

    def test_slippage_increases_with_size(self):
        model = SlippageModel(base_bps=10.0, alpha=0.5)
        slip_small = model.estimate_slippage_bps(100.0, 100_000.0)
        slip_large = model.estimate_slippage_bps(10_000.0, 100_000.0)
        assert slip_large > slip_small

    def test_slippage_decreases_with_liquidity(self):
        model = SlippageModel(base_bps=10.0, alpha=0.5)
        slip_low_liq = model.estimate_slippage_bps(1000.0, 10_000.0)
        slip_high_liq = model.estimate_slippage_bps(1000.0, 1_000_000.0)
        assert slip_high_liq < slip_low_liq

    def test_slippage_capped_at_max(self):
        model = SlippageModel(base_bps=10.0, alpha=0.5, max_slippage_bps=100.0)
        # Very large trade relative to liquidity
        slip = model.estimate_slippage_bps(100_000.0, 10_000.0)
        assert slip == 100.0

    def test_zero_liquidity_returns_max(self):
        model = SlippageModel(base_bps=10.0, max_slippage_bps=500.0)
        slip = model.estimate_slippage_bps(1000.0, 0.0)
        assert slip == 500.0