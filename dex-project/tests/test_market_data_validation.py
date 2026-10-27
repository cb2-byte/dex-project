"""
Tests for Market Data Validation Layer
======================================
Tests staleness, liquidity, invalid prices, and validation logic.
"""

import pytest
import time
from paper_engine.market_data import (
    MarketDataValidator,
    PriceQuote,
    ValidationResult,
    ValidationStatus,
    create_quote_from_coingecko,
    create_quote_from_cex,
    create_quote_from_geckoterminal,
)
from paper_engine.config import PaperConfig


class TestMarketDataValidator:
    """Test the MarketDataValidator class."""

    @pytest.fixture
    def config(self):
        return PaperConfig(
            max_staleness_seconds={
                "coingecko_demo": 60.0,
                "coinbase": 10.0,
                "kraken": 10.0,
                "geckoterminal": 60.0,
            },
            min_liquidity_usd=10_000.0,
        )

    @pytest.fixture
    def validator(self, config):
        return MarketDataValidator(
            max_staleness_seconds=config.max_staleness_seconds,
            min_liquidity_usd=config.min_liquidity_usd,
        )

    @pytest.fixture
    def fresh_quote(self):
        return PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            bid=2499.5,
            ask=2500.5,
            liquidity_usd=100_000.0,
        )

    @pytest.fixture
    def stale_quote(self):
        return PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time() - 100,  # 100 seconds ago
            liquidity_usd=100_000.0,
        )

    @pytest.fixture
    def low_liquidity_quote(self):
        return PriceQuote(
            symbol="MEME/USDC",
            price=0.001,
            source="geckoterminal",
            timestamp=time.time(),
            liquidity_usd=500.0,  # Below 10k minimum
        )

    @pytest.fixture
    def invalid_price_quote(self):
        return PriceQuote(
            symbol="ETH/USDC",
            price=-100.0,  # Invalid negative price
            source="coinbase",
            timestamp=time.time(),
        )

    def test_accepts_fresh_liquid_quote(self, validator, fresh_quote):
        """Fresh quote with sufficient liquidity should be valid."""
        result = validator.validate_quote(fresh_quote)
        assert result.is_valid
        assert result.status == ValidationStatus.VALID

    def test_rejects_stale_quote(self, validator, stale_quote):
        """Quote older than max_staleness should be rejected."""
        result = validator.validate_quote(stale_quote)
        assert not result.is_valid
        assert result.status == ValidationStatus.STALE_PRICE
        assert "stale" in result.message.lower()

    def test_rejects_low_liquidity(self, validator, low_liquidity_quote):
        """Quote with liquidity below minimum should be rejected."""
        result = validator.validate_quote(low_liquidity_quote)
        assert not result.is_valid
        assert result.status == ValidationStatus.INSUFFICIENT_LIQUIDITY
        assert "liquidity" in result.message.lower()

    def test_rejects_invalid_price(self, validator, invalid_price_quote):
        """Negative or zero price should be rejected."""
        result = validator.validate_quote(invalid_price_quote)
        assert not result.is_valid
        assert result.status == ValidationStatus.INVALID_PRICE

    def test_rejects_nan_price(self, validator):
        """NaN price should be rejected."""
        quote = PriceQuote(
            symbol="ETH/USDC",
            price=float('nan'),
            source="coinbase",
            timestamp=time.time(),
        )
        result = validator.validate_quote(quote)
        assert not result.is_valid
        assert result.status == ValidationStatus.INVALID_PRICE

    def test_rejects_infinite_price(self, validator):
        """Infinite price should be rejected."""
        quote = PriceQuote(
            symbol="ETH/USDC",
            price=float('inf'),
            source="coinbase",
            timestamp=time.time(),
        )
        result = validator.validate_quote(quote)
        assert not result.is_valid
        assert result.status == ValidationStatus.INVALID_PRICE

    def test_validates_triangle_all_present(self, validator, fresh_quote):
        """Triangle with all three quotes present should validate."""
        quotes = {
            "leg1": fresh_quote,
            "leg2": PriceQuote(
                symbol="SOL/USDC",
                price=100.0,
                source="coinbase",
                timestamp=time.time(),
                liquidity_usd=50_000.0,
            ),
            "leg3": PriceQuote(
                symbol="ETH/SOL",
                price=25.0,
                source="coinbase",
                timestamp=time.time(),
                liquidity_usd=50_000.0,
            ),
        }
        result = validator.validate_triangle(quotes, ["leg1", "leg2", "leg3"])
        assert result.is_valid

    def test_rejects_triangle_missing_leg(self, validator, fresh_quote):
        """Triangle missing a required leg should be rejected."""
        quotes = {"leg1": fresh_quote, "leg2": fresh_quote}
        result = validator.validate_triangle(quotes, ["leg1", "leg2", "leg3"])
        assert not result.is_valid
        assert result.status == ValidationStatus.MISSING_QUOTE

    def test_validates_cross_exchange_same_symbol(self, validator, fresh_quote):
        """Cross-exchange with same symbol should validate."""
        quote_b = PriceQuote(
            symbol="ETH/USDC",
            price=2501.0,
            source="kraken",
            timestamp=time.time(),
            liquidity_usd=80_000.0,
        )
        result = validator.validate_cross_exchange(fresh_quote, quote_b)
        assert result.is_valid

    def test_rejects_cross_exchange_symbol_mismatch(self, validator, fresh_quote):
        """Cross-exchange with different symbols should be rejected."""
        quote_b = PriceQuote(
            symbol="SOL/USDC",
            price=100.0,
            source="kraken",
            timestamp=time.time(),
        )
        result = validator.validate_cross_exchange(fresh_quote, quote_b)
        assert not result.is_valid
        assert result.status == ValidationStatus.SYMBOL_MISMATCH

    def test_staleness_per_source(self, validator):
        """Different sources have different staleness limits."""
        # Coinbase: 10s limit
        coinbase_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time() - 15,  # 15s ago - stale for coinbase
        )
        result = validator.validate_quote(coinbase_quote)
        assert not result.is_valid
        assert result.status == ValidationStatus.STALE_PRICE

        # CoinGecko: 60s limit
        cg_quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coingecko_demo",
            timestamp=time.time() - 30,  # 30s ago - fresh for coingecko
        )
        result = validator.validate_quote(cg_quote)
        assert result.is_valid


class TestPriceQuote:
    """Test PriceQuote properties and methods."""

    def test_mid_price_from_bid_ask(self):
        """Mid price calculated from bid/ask when available."""
        quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            bid=2499.0,
            ask=2501.0,
        )
        assert quote.mid_price == 2500.0

    def test_mid_price_fallback(self):
        """Mid price falls back to price when bid/ask not available."""
        quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coingecko_demo",
            timestamp=time.time(),
        )
        assert quote.mid_price == 2500.0

    def test_spread_bps(self):
        """Spread calculated correctly in basis points."""
        quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=time.time(),
            bid=2499.0,
            ask=2501.0,
        )
        # Spread = (2501 - 2499) / 2501 * 10000 ≈ 7.99 bps
        assert quote.spread_bps is not None
        assert 7.9 < quote.spread_bps < 8.1

    def test_age_seconds(self):
        """Age calculated correctly."""
        past_time = time.time() - 30
        quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=past_time,
        )
        age = quote.age_seconds(past_time + 30)
        assert 29.9 < age < 30.1

    def test_is_stale(self):
        """Staleness check works correctly."""
        past_time = time.time() - 100
        quote = PriceQuote(
            symbol="ETH/USDC",
            price=2500.0,
            source="coinbase",
            timestamp=past_time,
        )
        assert quote.is_stale(50, past_time + 100)  # 100s old, 50s limit
        assert not quote.is_stale(200, past_time + 100)  # 100s old, 200s limit


class TestQuoteFactories:
    """Test quote factory functions."""

    def test_create_quote_from_coingecko(self):
        quote = create_quote_from_coingecko("ETH/USDC", 2500.0)
        assert quote.symbol == "ETH/USDC"
        assert quote.price == 2500.0
        assert quote.source == "coingecko_demo"

    def test_create_quote_from_cex(self):
        quote = create_quote_from_cex("ETH/USDC", 2500.0, "coinbase", bid=2499.0, ask=2501.0)
        assert quote.symbol == "ETH/USDC"
        assert quote.price == 2500.0
        assert quote.source == "coinbase"
        assert quote.exchange == "coinbase"
        assert quote.bid == 2499.0
        assert quote.ask == 2501.0

    def test_create_quote_from_geckoterminal(self):
        quote = create_quote_from_geckoterminal(
            symbol="MEME/USDC",
            price=0.001,
            pair_address="0x123...",
            liquidity_usd=50_000.0,
            volume_24h_usd=100_000.0,
            fee_tier_bps=50.0,
        )
        assert quote.symbol == "MEME/USDC"
        assert quote.source == "geckoterminal"
        assert quote.pair_address == "0x123..."
        assert quote.liquidity_usd == 50_000.0
        assert quote.volume_24h_usd == 100_000.0
        assert quote.fee_tier_bps == 50.0