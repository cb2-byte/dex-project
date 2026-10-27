"""
Triangular Arbitrage Validator
===============================
Validates triangular arbitrage opportunities with full cost model.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from .config import PaperConfig
from .market_data import (
    MarketDataValidator, PriceQuote, ValidationResult, ValidationStatus,
    create_quote_from_geckoterminal
)
from .net_return import (
    NetReturnCalculator, NetReturnResult, RejectionReason, TransferPath
)


@dataclass
class ArbSignal:
    """Validated arbitrage signal with full audit trail."""
    strategy: str = "triangular"
    accepted: bool = False
    gross_return_pct: float = 0.0
    net_return_pct: float = 0.0
    cost_breakdown: Dict = field(default_factory=dict)
    rejection_reason: Optional[str] = None
    rejection_message: str = ""
    trade_size_usd: float = 0.0
    quotes_used: Dict[str, PriceQuote] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    validation_details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "strategy": self.strategy,
            "accepted": self.accepted,
            "gross_return_pct": self.gross_return_pct,
            "net_return_pct": self.net_return_pct,
            "cost_breakdown": self.cost_breakdown,
            "rejection_reason": self.rejection_reason,
            "rejection_message": self.rejection_message,
            "trade_size_usd": self.trade_size_usd,
            "quotes_used": {k: v.__dict__ for k, v in self.quotes_used.items()},
            "timestamp": self.timestamp,
            "validation_details": self.validation_details,
        }


class TriangularArbValidator:
    """
    Validates and scores triangular arbitrage opportunities.
    Enforces: fresh prices, sufficient liquidity, pair existence, positive net return.
    """

    def __init__(self, config: PaperConfig):
        self.config = config
        self.market_validator = MarketDataValidator(
            max_staleness_seconds=config.max_staleness_seconds,
            min_liquidity_usd=config.min_liquidity_usd
        )
        self.net_calculator = NetReturnCalculator(config)

    def validate_and_score(
        self,
        leg1_quote: PriceQuote,   # e.g., ETH/USDC
        leg2_quote: PriceQuote,   # e.g., SOL/USDC
        leg3_quote: PriceQuote,   # e.g., ETH/SOL
        trade_size_usd: float,
        chain: str = "base",
    ) -> ArbSignal:
        """
        Full validation pipeline for triangular arbitrage.
        Returns ArbSignal with accept/reject decision and full audit trail.
        """
        validation_details = {}

        # Step 1: Market data validation
        quotes = {
            "leg1": leg1_quote,
            "leg2": leg2_quote,
            "leg3": leg3_quote,
        }

        # Validate each quote individually
        for label, quote in quotes.items():
            result = self.market_validator.validate_quote(quote)
            validation_details[f"{label}_validation"] = {
                "status": result.status.value,
                "message": result.message,
                "details": result.details
            }
            if not result.is_valid:
                return ArbSignal(
                    accepted=False,
                    rejection_reason=result.status.value,
                    rejection_message=f"{label}: {result.message}",
                    trade_size_usd=trade_size_usd,
                    quotes_used=quotes,
                    validation_details=validation_details,
                )

        # Step 2: Verify pair existence on target DEX (GeckoTerminal)
        # Check that all three pairs have on-chain pool addresses
        for label, quote in quotes.items():
            if quote.source == "geckoterminal" and not quote.pair_address:
                validation_details[f"{label}_pair_check"] = {
                    "status": ValidationStatus.PAIR_NOT_FOUND.value,
                    "message": "Missing pair address for DEX quote"
                }
                return ArbSignal(
                    accepted=False,
                    rejection_reason=ValidationStatus.PAIR_NOT_FOUND.value,
                    rejection_message=f"{label}: missing pair address on DEX",
                    trade_size_usd=trade_size_usd,
                    quotes_used=quotes,
                    validation_details=validation_details,
                )

        # Step 3: Net return calculation with full cost model
        net_result = self.net_calculator.triangular_net_return(
            leg1_quote=leg1_quote,
            leg2_quote=leg2_quote,
            leg3_quote=leg3_quote,
            trade_size_usd=trade_size_usd,
            chain=chain,
        )

        validation_details["net_return"] = net_result.to_dict()

        # Step 4: Final accept/reject decision
        if net_result.passes_threshold:
            return ArbSignal(
                accepted=True,
                gross_return_pct=net_result.gross_return_pct,
                net_return_pct=net_result.net_return_pct,
                cost_breakdown=net_result.cost_breakdown.to_dict(),
                trade_size_usd=trade_size_usd,
                quotes_used=quotes,
                validation_details=validation_details,
            )
        else:
            return ArbSignal(
                accepted=False,
                gross_return_pct=net_result.gross_return_pct,
                net_return_pct=net_result.net_return_pct,
                cost_breakdown=net_result.cost_breakdown.to_dict(),
                rejection_reason=net_result.rejection_reason.value if net_result.rejection_reason else "unknown",
                rejection_message=net_result.rejection_message,
                trade_size_usd=trade_size_usd,
                quotes_used=quotes,
                validation_details=validation_details,
            )

    def validate_from_geckoterminal_pools(
        self,
        pools: List[Dict],
        trade_size_usd: float,
        chain: str = "base",
    ) -> List[ArbSignal]:
        """
        Scan GeckoTerminal pools for triangular arbitrage opportunities.
        Expects pools with token relationships to form triangles.
        """
        signals = []

        # Group pools by tokens to find triangles
        # This is a simplified version - real implementation would need
        # proper triangle detection from pool graph
        token_pools = {}
        for pool in pools:
            attrs = pool.get("attributes", {})
            base_token = attrs.get("base_token_symbol", "")
            quote_token = attrs.get("quote_token_symbol", "")
            if base_token and quote_token:
                pair_key = f"{base_token}/{quote_token}"
                token_pools[pair_key] = pool

        # Look for common triangles (e.g., ETH/USDC, SOL/USDC, ETH/SOL)
        common_triangles = [
            ("ETH/USDC", "SOL/USDC", "ETH/SOL"),
            ("WETH/USDC", "SOL/USDC", "WETH/SOL"),
            ("ETH/USDC", "WBTC/USDC", "ETH/WBTC"),
        ]

        for leg1_sym, leg2_sym, leg3_sym in common_triangles:
            if all(sym in token_pools for sym in [leg1_sym, leg2_sym, leg3_sym]):
                # Create quotes from pool data
                quotes = {}
                for label, sym in [("leg1", leg1_sym), ("leg2", leg2_sym), ("leg3", leg3_sym)]:
                    pool = token_pools[sym]
                    attrs = pool.get("attributes", {})
                    quotes[label] = create_quote_from_geckoterminal(
                        symbol=sym,
                        price=attrs.get("price_usd", 0),
                        pair_address=pool.get("id", ""),
                        liquidity_usd=attrs.get("reserve_in_usd", 0),
                        volume_24h_usd=attrs.get("volume_usd", {}).get("h24", 0),
                        fee_tier_bps=attrs.get("fee", 0) * 100,  # Convert to bps
                    )

                signal = self.validate_and_score(
                    leg1_quote=quotes["leg1"],
                    leg2_quote=quotes["leg2"],
                    leg3_quote=quotes["leg3"],
                    trade_size_usd=trade_size_usd,
                    chain=chain,
                )
                signals.append(signal)

        return signals