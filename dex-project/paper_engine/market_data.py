"""
Market Data Validation Layer
=============================
Shared validation for all strategies: timestamps, staleness, liquidity, pair existence.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from enum import Enum
import time


class ValidationStatus(Enum):
    """Validation result status."""
    VALID = "valid"
    STALE_PRICE = "stale_price"
    INVALID_PRICE = "invalid_price"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    PAIR_NOT_FOUND = "pair_not_found"
    MISSING_QUOTE = "missing_quote"
    SYMBOL_MISMATCH = "symbol_mismatch"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    status: ValidationStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID

    @classmethod
    def valid(cls, message: str = "") -> "ValidationResult":
        return cls(ValidationStatus.VALID, message)

    @classmethod
    def invalid(cls, status: ValidationStatus, message: str, **details) -> "ValidationResult":
        return cls(status, message, details)


@dataclass
class PriceQuote:
    """Validated price quote with metadata."""
    symbol: str                           # e.g., "ETH/USDC", "SOL/USDT"
    price: float                          # Mid price or last trade price
    source: str                           # "coingecko_demo", "coinbase", "kraken", "geckoterminal"
    timestamp: float                      # Unix epoch when fetched
    bid: Optional[float] = None           # Best bid
    ask: Optional[float] = None           # Best ask
    liquidity_usd: Optional[float] = None # Pool/orderbook liquidity
    volume_24h_usd: Optional[float] = None
    exchange: Optional[str] = None        # Venue identifier
    pair_address: Optional[str] = None    # On-chain pair address (DEX)
    fee_tier_bps: Optional[float] = None  # Fee tier in basis points (DEX)

    @property
    def spread_bps(self) -> Optional[float]:
        """Bid-ask spread in basis points."""
        if self.bid is not None and self.ask is not None and self.ask > 0:
            return ((self.ask - self.bid) / self.ask) * 10000
        return None

    @property
    def mid_price(self) -> float:
        """Mid price from bid/ask or fallback to price."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.price

    def age_seconds(self, now: Optional[float] = None) -> float:
        """Age of quote in seconds."""
        now = now or time.time()
        return now - self.timestamp

    def is_stale(self, max_staleness_seconds: float, now: Optional[float] = None) -> bool:
        """Check if quote exceeds staleness threshold."""
        return self.age_seconds(now) > max_staleness_seconds


@dataclass
class MarketDataValidator:
    """
    Validates market data for all strategies.
    Enforces staleness limits, liquidity minimums, and pair existence.
    """
    max_staleness_seconds: Dict[str, float] = field(default_factory=lambda: {
        "coingecko_demo": 60.0,
        "coinbase": 10.0,
        "kraken": 10.0,
        "geckoterminal": 60.0,
        "alchemy_rpc": 30.0,
    })
    min_liquidity_usd: float = 10_000.0
    default_max_staleness: float = 30.0

    def get_max_staleness(self, source: str) -> float:
        """Get staleness limit for a source."""
        return self.max_staleness_seconds.get(source, self.default_max_staleness)

    def validate_quote(self, quote: PriceQuote, now: Optional[float] = None) -> ValidationResult:
        """Validate a single price quote."""
        now = now or time.time()

        # Check price validity
        import math
        if quote.price <= 0 or not isinstance(quote.price, (int, float)) or quote.price != quote.price or math.isinf(quote.price):
            return ValidationResult.invalid(
                ValidationStatus.INVALID_PRICE,
                f"Invalid price: {quote.price}",
                price=quote.price, symbol=quote.symbol
            )

        # Check staleness
        max_stale = self.get_max_staleness(quote.source)
        if quote.is_stale(max_stale, now):
            return ValidationResult.invalid(
                ValidationStatus.STALE_PRICE,
                f"Quote stale: {quote.age_seconds(now):.1f}s > {max_stale}s limit",
                age_seconds=quote.age_seconds(now),
                max_staleness=max_stale,
                source=quote.source,
                symbol=quote.symbol
            )

        # Check liquidity if available
        if quote.liquidity_usd is not None and quote.liquidity_usd < self.min_liquidity_usd:
            return ValidationResult.invalid(
                ValidationStatus.INSUFFICIENT_LIQUIDITY,
                f"Insufficient liquidity: ${quote.liquidity_usd:,.0f} < ${self.min_liquidity_usd:,.0f}",
                liquidity_usd=quote.liquidity_usd,
                min_liquidity_usd=self.min_liquidity_usd,
                symbol=quote.symbol
            )

        return ValidationResult.valid(f"Quote valid: {quote.symbol} @ {quote.price}")

    def validate_triangle(
        self,
        quotes: Dict[str, PriceQuote],
        required_symbols: List[str],
        now: Optional[float] = None
    ) -> ValidationResult:
        """
        Validate all three legs of a triangular arbitrage.
        required_symbols: e.g., ["ETH/USDC", "SOL/USDC", "ETH/SOL"] or equivalent
        """
        now = now or time.time()

        # Check all required quotes present
        for symbol in required_symbols:
            if symbol not in quotes:
                return ValidationResult.invalid(
                    ValidationStatus.MISSING_QUOTE,
                    f"Missing required quote: {symbol}",
                    missing_symbol=symbol,
                    available=list(quotes.keys())
                )

        # Validate each quote
        for symbol in required_symbols:
            quote = quotes[symbol]
            result = self.validate_quote(quote, now)
            if not result.is_valid:
                return ValidationResult.invalid(
                    result.status,
                    f"Triangle leg {symbol}: {result.message}",
                    **result.details
                )

        return ValidationResult.valid(f"Triangle validated: {required_symbols}")

    def validate_cross_exchange(
        self,
        quote_a: PriceQuote,
        quote_b: PriceQuote,
        now: Optional[float] = None
    ) -> ValidationResult:
        """Validate two quotes for cross-exchange arbitrage (same symbol)."""
        now = now or time.time()

        # Check symbol match
        if quote_a.symbol != quote_b.symbol:
            return ValidationResult.invalid(
                ValidationStatus.SYMBOL_MISMATCH,
                f"Symbol mismatch: {quote_a.symbol} vs {quote_b.symbol}",
                symbol_a=quote_a.symbol,
                symbol_b=quote_b.symbol
            )

        # Validate both quotes
        for label, quote in [("A", quote_a), ("B", quote_b)]:
            result = self.validate_quote(quote, now)
            if not result.is_valid:
                return ValidationResult.invalid(
                    result.status,
                    f"Cross-exchange leg {label} ({quote.source}): {result.message}",
                    **result.details
                )

        return ValidationResult.valid(f"Cross-exchange validated: {quote_a.symbol} on {quote_a.source} vs {quote_b.source}")

    def validate_meme_pool(
        self,
        quote: PriceQuote,
        pool_data: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None
    ) -> ValidationResult:
        """Validate a meme coin pool quote."""
        now = now or time.time()

        # Basic quote validation
        result = self.validate_quote(quote, now)
        if not result.is_valid:
            return result

        # Additional pool checks if data provided
        if pool_data:
            # Check pool exists on-chain
            if not pool_data.get("pair_address"):
                return ValidationResult.invalid(
                    ValidationStatus.PAIR_NOT_FOUND,
                    "No pair address in pool data",
                    pool_data=pool_data
                )

            # Check liquidity from pool data
            pool_liquidity = pool_data.get("liquidity_usd", 0)
            if pool_liquidity < self.min_liquidity_usd:
                return ValidationResult.invalid(
                    ValidationStatus.INSUFFICIENT_LIQUIDITY,
                    f"Pool liquidity too low: ${pool_liquidity:,.0f}",
                    pool_liquidity=pool_liquidity,
                    min_liquidity=self.min_liquidity_usd
                )

        return ValidationResult.valid(f"Meme pool validated: {quote.symbol}")


def create_quote_from_coingecko(
    symbol: str,
    price: float,
    source: str = "coingecko_demo",
    **kwargs
) -> PriceQuote:
    """Factory for CoinGecko quotes."""
    return PriceQuote(
        symbol=symbol,
        price=price,
        source=source,
        timestamp=time.time(),
        **kwargs
    )


def create_quote_from_cex(
    symbol: str,
    price: float,
    exchange: str,
    bid: Optional[float] = None,
    ask: Optional[float] = None,
    **kwargs
) -> PriceQuote:
    """Factory for CEX quotes (Coinbase, Kraken, etc.)."""
    return PriceQuote(
        symbol=symbol,
        price=price,
        source=exchange.lower(),
        timestamp=time.time(),
        exchange=exchange.lower(),
        bid=bid,
        ask=ask,
        **kwargs
    )


def create_quote_from_geckoterminal(
    symbol: str,
    price: float,
    pair_address: str,
    liquidity_usd: float,
    volume_24h_usd: float,
    fee_tier_bps: float,
    **kwargs
) -> PriceQuote:
    """Factory for GeckoTerminal DEX quotes."""
    return PriceQuote(
        symbol=symbol,
        price=price,
        source="geckoterminal",
        timestamp=time.time(),
        pair_address=pair_address,
        liquidity_usd=liquidity_usd,
        volume_24h_usd=volume_24h_usd,
        fee_tier_bps=fee_tier_bps,
        **kwargs
    )