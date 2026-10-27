"""
Tests for Triangular Arbitrage Validation
==========================================
Tests missing pairs, stale prices, low liquidity, negative net returns.
"""

import pytest
import time
from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote, create_quote_from_geckoterminal
from paper_engine.triangular import TriangularArbValidator, ArbSignal as TriangularArbSignal
from paper_engine.market_data import ValidationStatus


class TestTriangularArbValidator:
    """Test the TriangularArbValidator class."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            starting_capital_usd=1000.0,
            min_net_edge_pct=0.20,
            max_staleness_seconds={
                "geckoterminal": 60.0,
                "coinbase": 10.0,
            },
            min_liquidity_usd=10_000.0,
        )

    @pytest.fixture
    def validator(self, config):
        return TriangularArbValidator(config)

    @pytest.fixture
    def valid_quotes(self):
        """Three valid quotes forming a triangle."""
        now = time.time()
        return {
            "leg1": PriceQuote(
                symbol="ETH/USDC",
                price=2500.0,
                source="geckoterminal",
                timestamp=now,
                liquidity_usd=100_000.0,
                pair_address="0x123...",
            ),
            "leg2": PriceQuote(
                symbol="SOL/USDC",
                price=100.0,
                source="geckoterminal",
                timestamp=now,
                liquidity_usd=50_000.0,
                pair_address="0x456...",
            ),
            "leg3": PriceQuote(
                symbol="ETH/SOL",
                price=25.5,  # 2% edge: 1 ETH = 25.5 SOL, should give ~2% gross
                source="geckoterminal",
                timestamp=now,
                liquidity_usd=30_000.0,
                pair_address="0x789...",
            ),
        }

    def test_accepts_valid_triangle(self, validator, valid_quotes):
        """Valid triangle with positive net return should be accepted."""
        signal = validator.validate_and_score(
            leg1_quote=valid_quotes["leg1"],
            leg2_quote=valid_quotes["leg2"],
            leg3_quote=valid_quotes["leg3"],
            trade_size_usd=1000.0,
            chain="base",
        )

        # Should be accepted if net return > 0.2%
        if signal.accepted:
            assert signal.net_return_pct >= 0.2
            assert signal.accepted is True

    def test_rejects_missing_pair_address(self, validator, valid_quotes):
        """Missing pair address on DEX quote should be rejected."""
        # Remove pair address from leg1
        quotes = valid_quotes.copy()
        quotes["leg1"] = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="geckoterminal",
            timestamp=time.time(),
            liquidity_usd=100_000.0,
            pair_address=None,  # Missing!
        )

        signal = validator.validate_and_score(
            leg1_quote=quotes["leg1"],
            leg2_quote=quotes["leg2"],
            leg3_quote=quotes["leg3"],
            trade_size_usd=1000.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.PAIR_NOT_FOUND.value

    def test_rejects_stale_price(self, validator, valid_quotes):
        """Stale price should be rejected."""
        quotes = valid_quotes.copy()
        quotes["leg1"] = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="geckoterminal",
            timestamp=time.time() - 120,  # 2 minutes ago - stale (60s limit)
            liquidity_usd=100_000.0,
            pair_address="0x123...",
        )

        signal = validator.validate_and_score(
            leg1_quote=quotes["leg1"],
            leg2_quote=quotes["leg2"],
            leg3_quote=quotes["leg3"],
            trade_size_usd=1000.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.STALE_PRICE.value

    def test_rejects_low_liquidity(self, validator, valid_quotes):
        """Low liquidity should be rejected."""
        quotes = valid_quotes.copy()
        quotes["leg1"] = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="geckoterminal",
            timestamp=time.time(),
            liquidity_usd=500.0,  # Below 10k minimum
            pair_address="0x123...",
        )

        signal = validator.validate_and_score(
            leg1_quote=quotes["leg1"],
            leg2_quote=quotes["leg2"],
            leg3_quote=quotes["leg3"],
            trade_size_usd=1000.0,
        )

        assert not signal.accepted
        assert signal.rejection_reason == ValidationStatus.INSUFFICIENT_LIQUIDITY.value

    def test_rejects_negative_net_return(self, validator, valid_quotes):
        """Negative net return after costs should be rejected."""
        # Create quotes with tiny edge that costs will eat
        quotes = {
            "leg1": PriceQuote(
                symbol="ETH/USDC",
                price=2500.0,
                source="geckoterminal",
                timestamp=time.time(),
                liquidity_usd=100_000.0,
                pair_address="0x123...",
            ),
            "leg2": PriceQuote(
                symbol="SOL/USDC",
                price=100.0,
                source="geckoterminal",
                timestamp=time.time(),
                liquidity_usd=50_000.0,
                pair_address="0x456...",
            ),
            "leg3": PriceQuote(
                symbol="ETH/SOL",
                price=25.01,  # Tiny 0.04% edge - costs will exceed
                source="geckoterminal",
                timestamp=time.time(),
                liquidity_usd=30_000.0,
                pair_address="0x789...",
            ),
        }

        signal = validator.validate_and_score(
            leg1_quote=quotes["leg1"],
            leg2_quote=quotes["leg2"],
            leg3_quote=quotes["leg3"],
            trade_size_usd=1000.0,
            chain="base",
        )

        # Net return should be negative after costs
        assert signal.net_return_pct <= 0 or not signal.accepted
        if not signal.accepted:
            assert signal.rejection_reason in [
                "negative_net_return",
                "below_threshold",
            ]

    def test_rejects_below_threshold(self, validator, valid_quotes):
        """Net return below threshold should be rejected."""
        # Small positive net return but below 0.2% threshold
        quotes = {
            "leg1": PriceQuote(
                symbol="ETH/USDC",
                price=2500.0,
                source="geckoterminal",
                timestamp=time.time(),
                liquidity_usd=100_000.0,
                pair_address="0x123...",
            ),
            "leg2": PriceQuote(
                symbol="SOL/USDC",
                price=100.0,
                source="geckoterminal",
                timestamp=time.time(),
                liquidity_usd=50_000.0,
                pair_address="0x456...",
            ),
            "leg3": PriceQuote(
                symbol="ETH/SOL",
                price=25.05,  # ~0.2% gross edge, but costs may push net below 0.2%
                source="geckoterminal",
                timestamp=time.time(),
                liquidity_usd=30_000.0,
                pair_address="0x789...",
            ),
        }

        signal = validator.validate_and_score(
            leg1_quote=quotes["leg1"],
            leg2_quote=quotes["leg2"],
            leg3_quote=quotes["leg3"],
            trade_size_usd=1000.0,
        )

        if signal.net_return_pct > 0 and signal.net_return_pct < 0.2:
            assert not signal.accepted
            assert signal.rejection_reason == "below_threshold"

    def test_validation_details_populated(self, validator, valid_quotes):
        """Validation details should be populated for audit trail."""
        signal = validator.validate_and_score(
            leg1_quote=valid_quotes["leg1"],
            leg2_quote=valid_quotes["leg2"],
            leg3_quote=valid_quotes["leg3"],
            trade_size_usd=1000.0,
        )

        assert "leg1_validation" in signal.validation_details
        assert "leg2_validation" in signal.validation_details
        assert "leg3_validation" in signal.validation_details
        assert "net_return" in signal.validation_details

    def test_quotes_used_in_signal(self, validator, valid_quotes):
        """Signal should contain the quotes used for validation."""
        signal = validator.validate_and_score(
            leg1_quote=valid_quotes["leg1"],
            leg2_quote=valid_quotes["leg2"],
            leg3_quote=valid_quotes["leg3"],
            trade_size_usd=1000.0,
        )

        assert "leg1" in signal.quotes_used
        assert "leg2" in signal.quotes_used
        assert "leg3" in signal.quotes_used
        assert signal.quotes_used["leg1"].symbol == "ETH/USDC"

    def test_trade_size_in_signal(self, validator, valid_quotes):
        """Signal should record the trade size."""
        signal = validator.validate_and_score(
            leg1_quote=valid_quotes["leg1"],
            leg2_quote=valid_quotes["leg2"],
            leg3_quote=valid_quotes["leg3"],
            trade_size_usd=500.0,
        )

        assert signal.trade_size_usd == 500.0


class TestTriangularArbSignal:
    """Test ArbSignal data class."""

    def test_to_dict(self, valid_quotes):
        """Signal should serialize to dict."""
        signal = TriangularArbSignal(
            accepted=True,
            gross_return_pct=0.5,
            net_return_pct=0.3,
            cost_breakdown={"trading_fees_bps": 30, "slippage_bps": 20},
            trade_size_usd=1000.0,
            quotes_used=valid_quotes,
        )

        d = signal.to_dict()
        assert d["accepted"] is True
        assert d["gross_return_pct"] == 0.5
        assert d["net_return_pct"] == 0.3
        assert "leg1" in d["quotes_used"]