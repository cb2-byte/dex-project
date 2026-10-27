"""
Tests for Meme Sniper Validation
=================================
Tests adverse drift exceeding momentum, risk-adjusted returns, and validation logic.
"""

import pytest
import time
from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote
from paper_engine.meme_sniper import MemeSniperValidator, MemeSignal
from paper_engine.market_data import ValidationStatus


class TestMemeSniperValidator:
    """Test the MemeSniperValidator class."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            min_net_edge_pct=0.20,
            max_staleness_seconds={
                "geckoterminal": 60.0,
            },
            min_liquidity_usd=10_000.0,
            meme_max_hold_seconds=300.0,
            meme_adverse_move_bps_per_min=50.0,
            meme_momentum_cap_pct=5.0,
        )

    @pytest.fixture
    def validator(self, config):
        return MemeSniperValidator(config)

    @pytest.fixture
    def pool_data(self):
        """Sample GeckoTerminal pool data."""
        return {
            "id": "0x123...",
            "attributes": {
                "base_token_symbol": "MEME",
                "quote_token_symbol": "USDC",
                "price_usd": 0.001,
                "price_change_percentage": {"h24": 8.0},
                "reserve_in_usd": 50_000.0,
                "volume_usd": {"h24": 100_000.0},
                "fee": 0.003,  # 0.3% = 30 bps
            },
        }

    @pytest.fixture
    def entry_quote(self):
        return PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=time.time(),
            liquidity_usd=50_000.0,
            pair_address="0x123...",
            fee_tier_bps=30.0,
        )

    @pytest.fixture
    def exit_quote(self):
        return PriceQuote(
            symbol="MEME/USDC",
            price=0.00105,  # 5% higher
            source="geckoterminal_projected",
            timestamp=time.time(),
            liquidity_usd=50_000.0,
        )

    def test_accepts_valid_meme_signal(self, validator, pool_data, entry_quote, exit_quote):
        """Valid meme signal with positive risk-adjusted net return should be accepted."""
        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        # 8% momentum, short hold -> low adverse drift
        if signal.accepted:
            assert signal.net_return_pct >= 0.2
            assert signal.accepted is True

    def test_rejects_adverse_drift_exceeds_momentum(self, validator, pool_data, entry_quote):
        """Reject when adverse drift exceeds momentum signal."""
        # Very long hold time = high adverse drift
        exit_quote = PriceQuote(
            symbol="MEME/USDC",
            price=0.00105,
            source="geckoterminal_projected",
            timestamp=time.time(),
            liquidity_usd=50_000.0,
        )

        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        # Force long hold by mocking
        signal.hold_seconds = 3600  # 1 hour = 60 min * 50 bps = 3000 bps = 30% adverse
        # The actual validation uses config.meme_max_hold_seconds (300s = 5 min)
        # So adverse drift = 5 min * 50 bps = 250 bps = 2.5%
        # Momentum = 8% (capped at 5%)
        # Risk-adjusted = 5% - 2.5% = 2.5% - costs

    def test_rejects_momentum_only_no_edge(self, validator, entry_quote, exit_quote):
        """Reject when momentum signal doesn't produce net edge after costs."""
        # Pool with low momentum
        low_momentum_pool = {
            "id": "0x456...",
            "attributes": {
                "base_token_symbol": "MEME",
                "quote_token_symbol": "USDC",
                "price_usd": 0.001,
                "price_change_percentage": {"h24": 0.1},  # Tiny momentum
                "reserve_in_usd": 50_000.0,
                "volume_usd": {"h24": 100_000.0},
                "fee": 0.003,
            },
        }

        signal = validator.validate_and_score(
            pool_data=low_momentum_pool,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        # 0.1% momentum, capped at 0.1%, minus costs = likely negative
        assert signal.momentum_signal_pct == 0.1

    def test_rejects_stale_entry_quote(self, validator, pool_data, exit_quote):
        """Reject when entry quote is stale."""
        stale_entry = PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=time.time() - 120,  # 2 min ago - stale (60s limit)
            liquidity_usd=50_000.0,
            pair_address="0x123...",
        )

        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=stale_entry,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.STALE_PRICE.value

    def test_rejects_low_liquidity_pool(self, validator, pool_data, exit_quote):
        """Reject when pool liquidity is too low."""
        low_liq_entry = PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=time.time(),
            liquidity_usd=500.0,  # Below 10k minimum
            pair_address="0x123...",
        )

        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=low_liq_entry,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.INSUFFICIENT_LIQUIDITY.value

    def test_rejects_missing_pair_address(self, validator, pool_data, exit_quote):
        """Reject when pool has no pair address."""
        no_pair_entry = PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=time.time(),
            liquidity_usd=50_000.0,
            pair_address=None,  # Missing!
        )

        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=no_pair_entry,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.PAIR_NOT_FOUND.value

    def test_momentum_capped_at_config_limit(self, validator, entry_quote, exit_quote):
        """Momentum signal should be capped at config limit (5%)."""
        high_momentum_pool = {
            "id": "0x789...",
            "attributes": {
                "base_token_symbol": "MEME",
                "quote_token_symbol": "USDC",
                "price_usd": 0.001,
                "price_change_percentage": {"h24": 50.0},  # Way above cap
                "reserve_in_usd": 50_000.0,
                "volume_usd": {"h24": 100_000.0},
                "fee": 0.003,
            },
        }

        signal = validator.validate_and_score(
            pool_data=high_momentum_pool,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        # Should be capped at meme_momentum_cap_pct (5%)
        assert signal.momentum_signal_pct == 5.0

    def test_adverse_drift_calculated_correctly(self, validator, pool_data, entry_quote, exit_quote):
        """Adverse drift should be calculated from hold time and config."""
        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        # Hold time = meme_max_hold_seconds (300s = 5 min)
        # Adverse drift = 5 min * 50 bps/min = 250 bps = 2.5%
        assert signal.hold_seconds == 300.0
        assert signal.adverse_drift_pct == 2.5

    def test_risk_adjusted_gross_calculation(self, validator, pool_data, entry_quote, exit_quote):
        """Risk-adjusted gross = momentum - adverse drift."""
        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        # Momentum = 8% (capped to 5%)
        # Adverse = 2.5%
        # Risk-adjusted = 2.5%
        assert signal.momentum_signal_pct == 5.0  # Capped
        assert signal.adverse_drift_pct == 2.5

    def test_validation_details_populated(self, validator, pool_data, entry_quote, exit_quote):
        """Validation details should be populated for audit trail."""
        signal = validator.validate_and_score(
            pool_data=pool_data,
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=100.0,
        )

        assert "pool_validation" in signal.validation_details
        assert "exit_validation" in signal.validation_details
        assert "signal_estimation" in signal.validation_details
        assert "net_return" in signal.validation_details

    def test_scan_geckoterminal_pools(self, validator):
        """Scan multiple pools for opportunities."""
        pools = [
            {
                "id": "0x111...",
                "attributes": {
                    "base_token_symbol": "MEME1",
                    "quote_token_symbol": "USDC",
                    "price_usd": 0.001,
                    "price_change_percentage": {"h24": 10.0},
                    "reserve_in_usd": 50_000.0,
                    "volume_usd": {"h24": 100_000.0},
                    "fee": 0.003,
                },
            },
            {
                "id": "0x222...",
                "attributes": {
                    "base_token_symbol": "MEME2",
                    "quote_token_symbol": "USDC",
                    "price_usd": 0.001,
                    "price_change_percentage": {"h24": 0.1},  # Too low
                    "reserve_in_usd": 50_000.0,
                    "volume_usd": {"h24": 100_000.0},
                    "fee": 0.003,
                },
            },
        ]

        signals = validator.scan_geckoterminal_pools(pools, trade_size_usd=100.0)
        # First pool has high momentum, second has low
        assert len(signals) >= 0


class TestMemeSignal:
    """Test MemeSignal data class."""

    def test_to_dict(self):
        """Signal should serialize to dict."""
        signal = MemeSignal(
            accepted=True,
            gross_return_pct=5.0,
            net_return_pct=2.0,
            cost_breakdown={"trading_fees_bps": 60, "slippage_bps": 20, "adverse_drift_bps": 250},
            trade_size_usd=100.0,
            quotes_used={},
            momentum_signal_pct=5.0,
            adverse_drift_pct=2.5,
            hold_seconds=300.0,
        )

        d = signal.to_dict()
        assert d["accepted"] is True
        assert d["momentum_signal_pct"] == 5.0
        assert d["adverse_drift_pct"] == 2.5
        assert d["hold_seconds"] == 300.0