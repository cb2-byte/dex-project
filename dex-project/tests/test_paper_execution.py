"""
Tests for Paper Execution Engine
=================================
Tests position sizing, fills, mark-to-market, close positions, kill switch.
"""

import pytest
import time
from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote
from paper_engine.net_return import NetReturnResult, CostBreakdown, RejectionReason
from paper_engine.execution import (
    PaperExecutionEngine,
    PaperPosition,
    PaperTrade,
    PaperFill,
    FillStatus,
    PositionSide,
)


class TestPaperExecutionEngine:
    """Test the PaperExecutionEngine class."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            max_position_pct=0.10,      # $100 max position
            max_daily_exposure_pct=0.50, # $500 daily
            max_drawdown_pct=0.20,       # 20% kill switch
            min_net_edge_pct=0.20,
        )

    @pytest.fixture
    def engine(self, config):
        return PaperExecutionEngine(config)

    @pytest.fixture
    def quote(self):
        return PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            liquidity_usd=1_000_000.0,
        )

    @pytest.fixture
    def net_return(self):
        return NetReturnResult(
            gross_return_pct=0.5,
            net_return_pct=0.3,
            cost_breakdown=CostBreakdown(
                trading_fees_bps=50.0,
                slippage_bps=30.0,
                gas_usd=0.03,
            ),
            passes_threshold=True,
            trade_size_usd=100.0,
        )

    def test_initial_state(self, engine):
        """Engine should start with correct capital."""
        assert engine.cash_usd == 1000.0
        assert engine.get_portfolio_value() == 1000.0
        assert len(engine.positions) == 0
        assert len(engine.closed_trades) == 0
        assert not engine.kill_switch_triggered

    def test_can_open_position_within_limits(self, engine, quote, net_return):
        """Should allow position within all limits."""
        can_open, reason = engine.can_open_position(50.0)
        assert can_open
        assert reason == "OK"

    def test_rejects_position_exceeds_max_size(self, engine, quote, net_return):
        """Should reject position exceeding max position size."""
        can_open, reason = engine.can_open_position(150.0)  # > $100 limit
        assert not can_open
        assert "exceeds max" in reason.lower()

    def test_rejects_position_exceeds_daily_exposure(self, engine, quote, net_return):
        """Should reject position exceeding daily exposure."""
        # First use up some daily exposure
        engine.daily_volume_usd = 480.0
        can_open, reason = engine.can_open_position(50.0)  # Would exceed $500
        assert not can_open
        assert "daily exposure" in reason.lower()

    def test_rejects_insufficient_cash(self, engine, quote, net_return):
        """Should reject when insufficient cash."""
        engine.cash_usd = 50.0
        can_open, reason = engine.can_open_position(100.0)
        assert not can_open
        assert "insufficient cash" in reason.lower()

    def test_simulate_fill_buy(self, engine, quote):
        """Buy fill should apply positive slippage."""
        fill = engine.simulate_fill(
            signal_side="buy",
            quote=quote,
            size_usd=100.0,
            slippage_bps=30.0,
            fee_bps=30.0,
            gas_usd=0.01,
        )

        assert fill.side == "buy"
        assert fill.fill_price > quote.mid_price  # Pay more when buying
        assert fill.fees_usd == 0.03  # 100 * 30/10000
        assert fill.status == FillStatus.FILLED

    def test_simulate_fill_sell(self, engine, quote):
        """Sell fill should apply negative slippage."""
        fill = engine.simulate_fill(
            signal_side="sell",
            quote=quote,
            size_usd=100.0,
            slippage_bps=30.0,
            fee_bps=30.0,
            gas_usd=0.01,
        )

        assert fill.side == "sell"
        assert fill.fill_price < quote.mid_price  # Receive less when selling
        assert fill.fees_usd == 0.03

    def test_open_position_long(self, engine, quote, net_return):
        """Open long position should succeed and update state."""
        position, error = engine.open_position(
            strategy="triangular",
            symbol="ETH/USDC",
            side="buy",
            quote=quote,
            size_usd=100.0,
            net_return=net_return,
        )

        assert position is not None
        assert error is None
        assert position.side == PositionSide.LONG
        assert position.size_usd == 100.0
        assert len(engine.positions) == 1
        # Cash reduced by position size + fees
        assert engine.cash_usd < 900.0  # 1000 - 100 - fees

    def test_open_position_short(self, engine, quote, net_return):
        """Open short position should succeed."""
        position, error = engine.open_position(
            strategy="cross_exchange",
            symbol="ETH/USDC",
            side="sell",
            quote=quote,
            size_usd=100.0,
            net_return=net_return,
        )

        assert position is not None
        assert position.side == PositionSide.SHORT

    def test_reject_open_position_kill_switch(self, engine, quote, net_return):
        """Should reject new positions when kill switch triggered."""
        engine.kill_switch_triggered = True
        engine.kill_switch_reason = "Test kill"

        position, error = engine.open_position(
            strategy="triangular",
            symbol="ETH/USDC",
            side="buy",
            quote=quote,
            size_usd=100.0,
            net_return=net_return,
        )

        assert position is None
        assert "kill switch" in error.lower()

    def test_mark_to_market_updates_unrealized(self, engine, quote, net_return):
        """Mark to market should update unrealized P&L."""
        # Open position
        position, _ = engine.open_position(
            strategy="triangular",
            symbol="ETH/USDC",
            side="buy",
            quote=quote,
            size_usd=100.0,
            net_return=net_return,
        )

        # Price moves up 1%
        new_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2525.0,  # 1% higher
            source="coinbase",
            timestamp=time.time(),
            liquidity_usd=1_000_000.0,
        )

        engine.mark_to_market({"ETH/USDC": new_quote})

        # Long position should have positive unrealized P&L
        assert position.unrealized_pnl_usd > 0
        assert abs(position.unrealized_pnl_usd - 1.0) < 0.1  # ~1% of $100 = $1

    def test_close_position_realizes_pnl(self, engine, quote, net_return):
        """Closing position should realize P&L and update cash."""
        # Open position
        position, _ = engine.open_position(
            strategy="triangular",
            symbol="ETH/USDC",
            side="buy",
            quote=quote,
            size_usd=100.0,
            net_return=net_return,
        )

        # Price moves up 1%
        exit_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2525.0,
            source="coinbase",
            timestamp=time.time(),
            liquidity_usd=1_000_000.0,
        )

        trade, error = engine.close_position(
            position_id=position.position_id,
            exit_quote=exit_quote,
            net_return=net_return,
        )

        assert trade is not None
        assert error is None
        assert trade.net_pnl_usd > 0  # Profit on long + price increase
        assert position.is_open is False
        assert len(engine.closed_trades) == 1
        # Cash should increase by position value + P&L
        assert engine.cash_usd > 1000.0 - 100.0  # More than just position return

    def test_close_nonexistent_position(self, engine, quote, net_return):
        """Closing non-existent position should return error."""
        trade, error = engine.close_position(
            position_id="nonexistent",
            exit_quote=quote,
            net_return=net_return,
        )

        assert trade is None
        assert "not found" in error.lower()

    def test_kill_switch_triggers_on_drawdown(self, engine, quote, net_return):
        """Kill switch should trigger when drawdown exceeds limit."""
        # Simulate large loss by directly manipulating equity
        engine.cash_usd = 700.0  # 30% drawdown from 1000
        engine.peak_equity = 1000.0

        triggered = engine.check_kill_switch()
        assert triggered
        assert engine.kill_switch_triggered
        assert "drawdown" in engine.kill_switch_reason.lower()

    def test_portfolio_value_includes_unrealized(self, engine, quote, net_return):
        """Portfolio value should include unrealized P&L."""
        position, _ = engine.open_position(
            strategy="triangular",
            symbol="ETH/USDC",
            side="buy",
            quote=quote,
            size_usd=100.0,
            net_return=net_return,
        )

        # Price moves up
        new_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2525.0,
            source="coinbase",
            timestamp=time.time(),
        )
        engine.mark_to_market({"ETH/USDC": new_quote})

        portfolio_value = engine.get_portfolio_value()
        assert portfolio_value == engine.cash_usd + position.unrealized_pnl_usd

    def test_get_state_returns_complete_snapshot(self, engine, quote, net_return):
        """Get state should return complete engine snapshot."""
        state = engine.get_state()

        assert "starting_capital_usd" in state
        assert "cash_usd" in state
        assert "portfolio_value_usd" in state
        assert "total_return_pct" in state
        assert "open_positions" in state
        assert "closed_trades" in state
        assert "positions" in state

    def test_reset_daily(self, engine):
        """Reset daily should clear daily counters."""
        engine.daily_pnl_usd = 100.0
        engine.daily_volume_usd = 300.0
        engine.daily_trades = 5

        engine.reset_daily()

        assert engine.daily_pnl_usd == 0.0
        assert engine.daily_volume_usd == 0.0
        assert engine.daily_trades == 0


class TestPaperFill:
    """Test PaperFill data class."""

    def test_total_cost_usd(self):
        """Total cost should include fees and gas."""
        fill = PaperFill(
            fill_id="test1",
            symbol="ETH/USDC",
            side="buy",
            requested_size_usd=100.0,
            filled_size_usd=100.0,
            fill_price=2500.0,
            slippage_bps=30.0,
            fees_usd=0.30,
            gas_usd=0.01,
            timestamp=time.time(),
        )

        assert fill.total_cost_usd == 0.31


class TestPaperPosition:
    """Test PaperPosition data class."""

    def test_is_open(self):
        """Position should be open until closed."""
        position = PaperPosition(
            position_id="pos1",
            symbol="ETH/USDC",
            side=PositionSide.LONG,
            entry_price=2500.0,
            size_usd=100.0,
            entry_time=time.time(),
            entry_fill=PaperFill(
                fill_id="f1", symbol="ETH/USDC", side="buy",
                requested_size_usd=100, filled_size_usd=100,
                fill_price=2500, slippage_bps=10, fees_usd=0.1, gas_usd=0.01,
                timestamp=time.time(),
            ),
        )

        assert position.is_open

        # Close it
        position.exit_fill = PaperFill(
            fill_id="f2", symbol="ETH/USDC", side="sell",
            requested_size_usd=100, filled_size_usd=100,
            fill_price=2525, slippage_bps=10, fees_usd=0.1, gas_usd=0.01,
            timestamp=time.time(),
        )
        position.exit_time = time.time()

        assert not position.is_open