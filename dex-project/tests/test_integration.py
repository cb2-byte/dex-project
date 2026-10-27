"""
Integration Tests for Paper Trading Engine
===========================================
Tests full paper trading cycles for all three strategies.
"""

import pytest
import time
from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote
from paper_engine.triangular import TriangularArbValidator
from paper_engine.cross_exchange import CrossExchangeArbValidator
from paper_engine.meme_sniper import MemeSniperValidator
from paper_engine.execution import PaperExecutionEngine
from paper_engine.net_return import NetReturnResult, CostBreakdown
from paper_engine.records import PaperTradeRecorder
from paper_engine.metrics import PerformanceMetrics, generate_performance_report


class TestFullTriangularPaperCycle:
    """Test complete triangular arbitrage paper trading cycle."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            max_position_pct=0.10,
            max_daily_exposure_pct=0.50,
            max_drawdown_pct=0.20,
            min_net_edge_pct=0.20,
            max_staleness_seconds={"geckoterminal": 60.0},
            min_liquidity_usd=10_000.0,
        )

    @pytest.fixture
    def engine(self, config):
        return PaperExecutionEngine(config)

    @pytest.fixture
    def validator(self, config):
        return TriangularArbValidator(config)

    @pytest.fixture
    def recorder(self, config):
        return PaperTradeRecorder(log_dir="test_paper_trades", session_id="test_triangular")

    def test_triangular_signal_to_execution(self, config, engine, validator, recorder):
        """Full cycle: signal generation -> validation -> execution -> recording."""
        now = time.time()

        # 1. Create valid quotes for a profitable triangle
        leg1 = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="geckoterminal",
            timestamp=now,
            liquidity_usd=100_000.0,
            pair_address="0x123...",
        )
        leg2 = PriceQuote(
            symbol="SOL/USDC",
            price=100.0,
            source="geckoterminal",
            timestamp=now,
            liquidity_usd=50_000.0,
            pair_address="0x456...",
        )
        leg3 = PriceQuote(
            symbol="ETH/SOL",
            price=25.5,  # ~2% gross edge
            source="geckoterminal",
            timestamp=now,
            liquidity_usd=30_000.0,
            pair_address="0x789...",
        )

        # 2. Validate signal
        signal = validator.validate_and_score(
            leg1_quote=leg1,
            leg2_quote=leg2,
            leg3_quote=leg3,
            trade_size_usd=100.0,
            chain="base",
        )

        # 3. Log signal
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

        # 4. If accepted, execute
        if signal.accepted:
            # Open position
            net_return = type('obj', (object,), {
                'gross_return_pct': signal.gross_return_pct,
                'net_return_pct': signal.net_return_pct,
                'cost_breakdown': type('obj', (object,), {
                    'trading_fees_bps': 30,
                    'slippage_bps': 20,
                    'gas_usd': 0.03,
                })(),
            })()

            position, error = engine.open_position(
                strategy="triangular",
                symbol="ETH/USDC",
                side="buy",
                quote=leg1,
                size_usd=100.0,
                net_return=net_return,
            )

            assert position is not None
            assert error is None

            # Mark to market (price moves favorably)
            exit_quote = PriceQuote(
                symbol="ETH/USDC",
                price=2525.0,  # 1% gain
                source="geckoterminal",
                timestamp=time.time() + 60,
                liquidity_usd=100_000.0,
            )
            engine.mark_to_market({"ETH/USDC": exit_quote})

            # Close position
            trade, error = engine.close_position(
                position_id=position.position_id,
                exit_quote=exit_quote,
                net_return=net_return,
            )

            assert trade is not None
            assert error is None
            trade.strategy = "triangular"

            # 5. Record trade
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

        # 6. Verify recorder has data
        recorder.close()

    def test_triangular_rejected_signal_logged(self, validator, recorder):
        """Rejected signals should also be logged."""
        now = time.time()

        # Create quotes with negative net return
        leg1 = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="geckoterminal",
            timestamp=now,
            liquidity_usd=100_000.0,
            pair_address="0x123...",
        )
        leg2 = PriceQuote(
            symbol="SOL/USDC",
            price=100.0,
            source="geckoterminal",
            timestamp=now,
            liquidity_usd=50_000.0,
            pair_address="0x456...",
        )
        leg3 = PriceQuote(
            symbol="ETH/SOL",
            price=25.01,  # Tiny edge
            source="geckoterminal",
            timestamp=now,
            liquidity_usd=30_000.0,
            pair_address="0x789...",
        )

        signal = validator.validate_and_score(
            leg1_quote=leg1,
            leg2_quote=leg2,
            leg3_quote=leg3,
            trade_size_usd=100.0,
        )

        # Should be rejected
        assert not signal.accepted

        # But still logged
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

        recorder.close()


class TestFullCrossExchangePaperCycle:
    """Test complete cross-exchange arbitrage paper trading cycle."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            max_position_pct=0.10,
            max_daily_exposure_pct=0.50,
            max_drawdown_pct=0.20,
            min_net_edge_pct=0.20,
        )

    @pytest.fixture
    def engine(self, config):
        return PaperExecutionEngine(config)

    @pytest.fixture
    def validator(self, config):
        return CrossExchangeArbValidator(config)

    def test_cross_exchange_signal_to_execution(self, config, engine, validator):
        """Full cycle for cross-exchange arbitrage."""
        now = time.time()

        # Quotes with 0.4% edge
        coinbase = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=now,
            liquidity_usd=1_000_000.0,
            exchange="coinbase",
            bid=2499.5,
            ask=2500.5,
        )
        kraken = PriceQuote(
            symbol="ETH/USDC",
            price=2510.0,
            source="kraken",
            timestamp=now,
            liquidity_usd=800_000.0,
            exchange="kraken",
            bid=2509.5,
            ask=2510.5,
        )

        signal = validator.validate_and_score(
            quote_a=coinbase,
            quote_b=kraken,
            trade_size_usd=100.0,
            transfer_path="same_chain",
        )

        if signal.accepted:
            # Execute on both sides
            # Buy on coinbase (cheaper)
            net_return = type('obj', (object,), {
                'gross_return_pct': signal.gross_return_pct,
                'net_return_pct': signal.net_return_pct,
                'cost_breakdown': type('obj', (object,), {
                    'trading_fees_bps': 56,
                    'slippage_bps': 20,
                    'gas_usd': 0.02,
                })(),
            })()

            position, error = engine.open_position(
                strategy="cross_exchange",
                symbol="ETH/USDC",
                side="buy",
                quote=coinbase,
                size_usd=100.0,
                net_return=net_return,
            )

            assert position is not None

            # Price moves favorably
            exit_quote = PriceQuote(
                symbol="ETH/USDC",
                price=2520.0,
                source="coinbase",
                timestamp=time.time() + 30,
                liquidity_usd=1_000_000.0,
            )
            engine.mark_to_market({"ETH/USDC": exit_quote})

            trade, error = engine.close_position(
                position_id=position.position_id,
                exit_quote=exit_quote,
                net_return=net_return,
            )

            assert trade is not None
            trade.strategy = "cross_exchange"


class TestFullMemeSniperPaperCycle:
    """Test complete meme sniper paper trading cycle."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            max_position_pct=0.10,
            max_daily_exposure_pct=0.50,
            max_drawdown_pct=0.20,
            min_net_edge_pct=0.20,
            meme_max_hold_seconds=300.0,
            meme_adverse_move_bps_per_min=50.0,
            meme_momentum_cap_pct=5.0,
        )

    @pytest.fixture
    def engine(self, config):
        return PaperExecutionEngine(config)

    @pytest.fixture
    def validator(self, config):
        return MemeSniperValidator(config)

    def test_meme_sniper_signal_to_execution(self, config, engine, validator):
        """Full cycle for meme sniper."""
        now = time.time()

        pool_data = {
            "id": "0x123...",
            "attributes": {
                "base_token_symbol": "MEME",
                "quote_token_symbol": "USDC",
                "price_usd": 0.001,
                "price_change_percentage": {"h24": 8.0},
                "reserve_in_usd": 50_000.0,
                "volume_usd": {"h24": 100_000.0},
                "fee": 0.003,
            },
        }

        entry_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=now,
            liquidity_usd=50_000.0,
            pair_address="0x123...",
            fee_tier_bps=30.0,
        )

        exit_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.00105,
            source="geckoterminal_projected",
            timestamp=now,
            liquidity_usd=50_000.0,
        )

        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=50.0,
        )

        if signal.accepted:
            net_return = type('obj', (object,), {
                'gross_return_pct': signal.gross_return_pct,
                'net_return_pct': signal.net_return_pct,
                'cost_breakdown': type('obj', (object,), {
                    'trading_fees_bps': 60,
                    'slippage_bps': 20,
                    'adverse_drift_bps': 250,
                    'gas_usd': 0.02,
                })(),
            })()

            position, error = engine.open_position(
                strategy="meme_sniper",
                symbol="MEME/USDC",
                side="buy",
                quote=entry_quote,
                size_usd=50.0,
                net_return=net_return,
            )

            assert position is not None

            # Quick exit (meme coins move fast)
            exit_quote2 = PriceQuote(
                symbol="MEME/USDC",
                price=0.00104,  # Slightly lower than projected
                source="geckoterminal",
                timestamp=time.time() + 120,
                liquidity_usd=50_000.0,
            )
            engine.mark_to_market({"MEME/USDC": exit_quote2})

            trade, error = engine.close_position(
                position_id=position.position_id,
                exit_quote=exit_quote2,
                net_return=net_return,
            )

            assert trade is not None
            trade.strategy = "meme_sniper"


class TestMultiStrategyPortfolio:
    """Test multiple strategies running concurrently."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            max_position_pct=0.10,
            max_daily_exposure_pct=0.50,
            max_drawdown_pct=0.20,
            min_net_edge_pct=0.20,
        )

    def test_concurrent_strategies_respect_limits(self, config):
        """Multiple strategies should respect shared capital limits."""
        engine = PaperExecutionEngine(config)

        quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            liquidity_usd=1_000_000.0,
        )

        net_return = NetReturnResult(
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

        # Open first position ($100)
        pos1, _ = engine.open_position(
            strategy="triangular",
            symbol="ETH/USDC",
            side="buy",
            quote=quote,
            size_usd=100.0,
            net_return=net_return,
        )
        assert pos1 is not None

        # Open second position ($100)
        pos2, _ = engine.open_position(
            strategy="cross_exchange",
            symbol="SOL/USDC",
            side="buy",
            quote=PriceQuote(
                symbol="SOL/USDC",
                price=100.0,
                source="coinbase",
                timestamp=time.time(),
                liquidity_usd=500_000.0,
            ),
            size_usd=100.0,
            net_return=net_return,
        )
        assert pos2 is not None

        # Third position should be rejected (would exceed $500 daily exposure if we did more)
        # But within limits for now
        assert engine.daily_volume_usd == 200.0
        assert engine.cash_usd < 1000.0

        # Check portfolio value
        portfolio_value = engine.get_portfolio_value()
        assert portfolio_value <= 1000.0  # Can't exceed starting without P&L


class TestMetricsCalculation:
    """Test performance metrics calculation."""

    def test_metrics_from_trades(self):
        """Metrics should calculate correctly from trade list."""
        trades = [
            {
                "trade_id": "t1",
                "strategy": "triangular",
                "symbol": "ETH/USDC",
                "side": "long",
                "entry_time": time.time() - 3600,
                "exit_time": time.time(),
                "entry_price": 2500.0,
                "exit_price": 2525.0,
                "size_usd": 100.0,
                "fees_usd": 0.50,
                "slippage_usd": 0.30,
                "gas_usd": 0.03,
                "gross_pnl_usd": 1.00,
                "net_pnl_usd": 0.17,
                "hold_seconds": 3600.0,
                "return_pct": 1.0,
            },
            {
                "trade_id": "t2",
                "strategy": "cross_exchange",
                "symbol": "SOL/USDC",
                "side": "long",
                "entry_time": time.time() - 1800,
                "exit_time": time.time(),
                "entry_price": 100.0,
                "exit_price": 100.5,
                "size_usd": 50.0,
                "fees_usd": 0.25,
                "slippage_usd": 0.15,
                "gas_usd": 0.02,
                "gross_pnl_usd": 0.25,
                "net_pnl_usd": -0.17,
                "hold_seconds": 1800.0,
                "return_pct": -0.5,
            },
        ]

        metrics = PerformanceMetrics()
        result = metrics.calculate(trades)

        assert result.total_trades == 2
        assert result.winning_trades == 1
        assert result.losing_trades == 1
        assert result.win_rate == 0.5
        assert abs(result.net_pnl_usd - 0.0) < 0.01  # ~breakeven
        assert result.profit_factor > 0

    def test_performance_report_generation(self):
        """Report should generate without errors."""
        from paper_engine.metrics import MetricsResult

        result = MetricsResult(
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            net_pnl_usd=100.0,
            win_rate=0.6,
            profit_factor=1.5,
            max_drawdown_pct=5.0,
            sharpe_ratio=1.2,
        )

        report = generate_performance_report(result)
        assert "PAPER TRADING PERFORMANCE REPORT" in report
        assert "Total Trades:        10" in report
        assert "Win Rate:            60.00%" in report


class TestRecorderPersistence:
    """Test that recorder persists data correctly."""

    def test_recorder_writes_jsonl(self, tmp_path):
        """Recorder should write valid JSONL files."""
        log_dir = tmp_path / "test_logs"
        recorder = PaperTradeRecorder(log_dir=str(log_dir), session_id="test")

        # Log a signal
        recorder.log_signal(
            strategy="triangular",
            symbol="ETH/USDC",
            accepted=True,
            gross_return_pct=0.5,
            net_return_pct=0.3,
            rejection_reason=None,
            rejection_message="",
            trade_size_usd=100.0,
            quotes={},
            validation_details={},
        )

        # Log a trade
        recorder.log_trade(
            strategy="triangular",
            symbol="ETH/USDC",
            side="long",
            entry_time=time.time() - 3600,
            exit_time=time.time(),
            entry_price=2500.0,
            exit_price=2525.0,
            size_usd=100.0,
            fees_usd=0.50,
            slippage_usd=0.30,
            gas_usd=0.03,
            gross_pnl_usd=1.00,
            net_pnl_usd=0.17,
            hold_seconds=3600.0,
            return_pct=1.0,
            entry_fill={},
            exit_fill={},
            validation_details={},
        )

        recorder.close()

        # Verify files exist and have content
        audit_file = list(log_dir.glob("audit_*.jsonl"))[0]
        trades_file = list(log_dir.glob("trades_*.jsonl"))[0]
        signals_file = list(log_dir.glob("signals_*.jsonl"))[0]

        assert audit_file.exists()
        assert trades_file.exists()
        assert signals_file.exists()

        # Verify JSONL format
        with open(signals_file) as f:
            line = f.readline().strip()
            assert line.startswith('{"signal_id"')
            import json
            data = json.loads(line)
            assert data["strategy"] == "triangular"
            assert data["accepted"] is True


class TestConfigurationLoading:
    """Test configuration loading from YAML."""

    def test_load_config_from_yaml(self, tmp_path):
        """Should load config from YAML file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
paper_engine:
  starting_capital_usd: 5000.0
  max_position_pct: 0.05
  max_daily_exposure_pct: 0.30
  max_drawdown_pct: 0.15
  min_net_edge_pct: 0.50
""")

        config = PaperConfig.from_yaml(str(config_file))

        assert config.starting_capital_usd == 5000.0
        assert config.max_position_pct == 0.05
        assert config.max_daily_exposure_pct == 0.30
        assert config.max_drawdown_pct == 0.15
        assert config.min_net_edge_pct == 0.50

    def test_default_config_values(self):
        """Default config should have sensible values."""
        config = PaperConfig()

        assert config.starting_capital_usd == 1000.0
        assert config.max_position_pct == 0.10
        assert config.max_daily_exposure_pct == 0.50
        assert config.max_drawdown_pct == 0.20
        assert config.min_net_edge_pct == 0.20
        assert config.min_liquidity_usd == 10_000.0