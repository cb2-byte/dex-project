"""
Cross-Exchange Arbitrage Validator
===================================
Validates cross-exchange arbitrage opportunities with full cost model including transfers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from .config import PaperConfig
from .market_data import (
    MarketDataValidator, PriceQuote, ValidationResult, ValidationStatus,
    create_quote_from_cex
)
from .net_return import (
    NetReturnCalculator, NetReturnResult, RejectionReason, TransferPath
)


@dataclass
class ArbSignal:
    """Validated arbitrage signal with full audit trail."""
    strategy: str = "cross_exchange"
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
    transfer_path: str = "same_chain"

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
            "transfer_path": self.transfer_path,
        }


class CrossExchangeArbValidator:
    """
    Validates and scores cross-exchange arbitrage opportunities.
    Enforces: fresh prices, sufficient liquidity on both venues, transfer costs, positive net return.
    """

    def __init__(self, config: PaperConfig):
        self.config = config
        self.market_validator = MarketDataValidator(
            max_staleness_seconds=config.max_staleness_seconds,
            min_liquidity_usd=config.min_liquidity_usd
        )
        self.net_calculator = NetReturnCalculator(config)

    def determine_transfer_path(
        self,
        buy_quote: PriceQuote,
        sell_quote: PriceQuote,
    ) -> TransferPath:
        """
        Determine transfer path based on exchanges/chains.
        Simplified: if same source chain -> SAME_CHAIN, else WITHDRAW_DEPOSIT.
        Real implementation would check actual chain compatibility.
        """
        # Same source = same chain (e.g., both on Base via DEX)
        if buy_quote.source == sell_quote.source:
            return TransferPath.SAME_CHAIN

        # Both CEX -> withdraw/deposit
        cex_sources = {"coinbase", "kraken", "binance", "bybit", "okx"}
        if buy_quote.source in cex_sources and sell_quote.source in cex_sources:
            return TransferPath.WITHDRAW_DEPOSIT

        # Different chains -> bridge
        return TransferPath.BRIDGE

    def validate_and_score(
        self,
        quote_a: PriceQuote,        # First exchange quote
        quote_b: PriceQuote,        # Second exchange quote
        trade_size_usd: float,
        transfer_path: Optional[TransferPath] = None,
        bridge_name: Optional[str] = None,
    ) -> ArbSignal:
        """
        Full validation pipeline for cross-exchange arbitrage.
        Automatically determines buy/sell side from prices.
        """
        validation_details = {}

        # Step 1: Market data validation
        quotes = {"quote_a": quote_a, "quote_b": quote_b}

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

        # Step 2: Cross-exchange validation (same symbol, both fresh)
        cross_result = self.market_validator.validate_cross_exchange(quote_a, quote_b)
        validation_details["cross_exchange_validation"] = {
            "status": cross_result.status.value,
            "message": cross_result.message,
        }
        if not cross_result.is_valid:
            return ArbSignal(
                accepted=False,
                rejection_reason=cross_result.status.value,
                rejection_message=cross_result.message,
                trade_size_usd=trade_size_usd,
                quotes_used=quotes,
                validation_details=validation_details,
            )

        # Step 3: Determine buy/sell side from prices
        # Buy on cheaper, sell on more expensive
        price_a = quote_a.mid_price
        price_b = quote_b.mid_price

        if price_a < price_b:
            buy_quote, sell_quote = quote_a, quote_b
            buy_source, sell_source = quote_a.source, quote_b.source
        else:
            buy_quote, sell_quote = quote_b, quote_a
            buy_source, sell_source = quote_b.source, quote_a.source

        validation_details["side_determination"] = {
            "buy_exchange": buy_source,
            "sell_exchange": sell_source,
            "buy_price": buy_quote.mid_price,
            "sell_price": sell_quote.mid_price,
            "raw_discrepancy_pct": ((sell_quote.mid_price - buy_quote.mid_price) / buy_quote.mid_price) * 100,
        }

        # Step 4: Determine transfer path if not provided
        if transfer_path is None:
            transfer_path = self.determine_transfer_path(buy_quote, sell_quote)

        validation_details["transfer_path"] = transfer_path.value

        # Step 5: Net return calculation with full cost model
        net_result = self.net_calculator.cross_exchange_net_return(
            buy_quote=buy_quote,
            sell_quote=sell_quote,
            trade_size_usd=trade_size_usd,
            transfer_path=transfer_path,
            bridge_name=bridge_name,
        )

        validation_details["net_return"] = net_result.to_dict()

        # Step 6: Final accept/reject decision
        if net_result.passes_threshold:
            return ArbSignal(
                accepted=True,
                gross_return_pct=net_result.gross_return_pct,
                net_return_pct=net_result.net_return_pct,
                cost_breakdown=net_result.cost_breakdown.to_dict(),
                trade_size_usd=trade_size_usd,
                quotes_used=quotes,
                validation_details=validation_details,
                transfer_path=transfer_path.value,
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
                transfer_path=transfer_path.value,
            )

    def scan_exchange_pairs(
        self,
        exchange_quotes: Dict[str, Dict[str, PriceQuote]],
        trade_size_usd: float,
    ) -> List[ArbSignal]:
        """
        Scan multiple exchanges for cross-exchange arbitrage.
        exchange_quotes: {exchange_name: {symbol: PriceQuote}}
        Returns all viable signals across all symbol pairs.
        """
        signals = []
        exchanges = list(exchange_quotes.keys())

        # Compare each pair of exchanges
        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                ex_a, ex_b = exchanges[i], exchanges[j]
                quotes_a = exchange_quotes[ex_a]
                quotes_b = exchange_quotes[ex_b]

                # Find common symbols
                common_symbols = set(quotes_a.keys()) & set(quotes_b.keys())

                for symbol in common_symbols:
                    signal = self.validate_and_score(
                        quote_a=quotes_a[symbol],
                        quote_b=quotes_b[symbol],
                        trade_size_usd=trade_size_usd,
                    )
                    if signal.accepted:
                        signals.append(signal)

        return signals