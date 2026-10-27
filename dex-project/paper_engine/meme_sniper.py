"""
Meme Sniper Validator
======================
Validates meme coin trading opportunities with proper edge calculation including costs and risk.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .config import PaperConfig
from .market_data import (
    MarketDataValidator, PriceQuote, ValidationResult, ValidationStatus,
    create_quote_from_geckoterminal
)
from .net_return import (
    NetReturnCalculator, NetReturnResult, RejectionReason
)


@dataclass
class MemeSignal:
    """Validated meme sniper signal with full audit trail."""
    strategy: str = "meme_sniper"
    accepted: bool = False
    gross_return_pct: float = 0.0
    net_return_pct: float = 0.0
    cost_breakdown: Dict = field(default_factory=dict)
    rejection_reason: Optional[str] = None
    rejection_message: str = ""
    trade_size_usd: float = 0.0
    quotes_used: Dict[str, PriceQuote] = field(default_factory=dict)
    pool_data: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    validation_details: Dict = field(default_factory=dict)
    momentum_signal_pct: float = 0.0
    adverse_drift_pct: float = 0.0
    hold_seconds: float = 0.0

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
            "pool_data": self.pool_data,
            "timestamp": self.timestamp,
            "validation_details": self.validation_details,
            "momentum_signal_pct": self.momentum_signal_pct,
            "adverse_drift_pct": self.adverse_drift_pct,
            "hold_seconds": self.hold_seconds,
        }


class MemeSniperValidator:
    """
    Validates and scores meme coin trading opportunities.
    Converts 24h momentum into risk-adjusted net return after all costs.
    Enforces: fresh prices, pool existence, liquidity, positive risk-adjusted net return.
    """

    def __init__(self, config: PaperConfig):
        self.config = config
        self.market_validator = MarketDataValidator(
            max_staleness_seconds=config.max_staleness_seconds,
            min_liquidity_usd=config.min_liquidity_usd
        )
        self.net_calculator = NetReturnCalculator(config)

    def estimate_momentum_signal(self, pool_data: Dict) -> float:
        """
        Extract momentum signal from pool data.
        Uses 24h price change as base signal, capped at config.meme_momentum_cap_pct.
        """
        attrs = pool_data.get("attributes", {})
        price_change = attrs.get("price_change_percentage", {}).get("h24", 0)
        # Cap the momentum signal
        return min(abs(price_change), self.config.meme_momentum_cap_pct)

    def estimate_hold_time(self, pool_data: Dict) -> float:
        """
        Estimate optimal hold time based on pool characteristics.
        Higher volume/shorter timeframe -> shorter hold.
        Simplified: use fixed max hold time from config.
        """
        return self.config.meme_max_hold_seconds

    def validate_and_score(
        self,
        pool_data: Dict,
        entry_quote: PriceQuote,
        exit_quote: PriceQuote,
        trade_size_usd: float,
    ) -> MemeSignal:
        """
        Full validation pipeline for meme sniper.
        """
        validation_details = {}
        now = __import__('time').time()

        # Step 1: Validate pool data and quote
        pool_validation = self.market_validator.validate_meme_pool(entry_quote, pool_data, now)
        validation_details["pool_validation"] = {
            "status": pool_validation.status.value,
            "message": pool_validation.message,
            "details": pool_validation.details
        }
        if not pool_validation.is_valid:
            return MemeSignal(
                accepted=False,
                rejection_reason=pool_validation.status.value,
                rejection_message=f"Pool: {pool_validation.message}",
                trade_size_usd=trade_size_usd,
                quotes_used={"entry": entry_quote, "exit": exit_quote},
                pool_data=pool_data,
                validation_details=validation_details,
            )

        # Step 2: Validate exit quote
        exit_validation = self.market_validator.validate_quote(exit_quote, now)
        validation_details["exit_validation"] = {
            "status": exit_validation.status.value,
            "message": exit_validation.message,
            "details": exit_validation.details
        }
        if not exit_validation.is_valid:
            return MemeSignal(
                accepted=False,
                rejection_reason=exit_validation.status.value,
                rejection_message=f"Exit quote: {exit_validation.message}",
                trade_size_usd=trade_size_usd,
                quotes_used={"entry": entry_quote, "exit": exit_quote},
                pool_data=pool_data,
                validation_details=validation_details,
            )

        # Step 3: Extract momentum signal
        momentum_signal = self.estimate_momentum_signal(pool_data)
        hold_seconds = self.estimate_hold_time(pool_data)
        adverse_drift_bps = self.config.meme_adverse_move_bps_per_min * (hold_seconds / 60.0)
        adverse_drift_pct = adverse_drift_bps / 100.0

        validation_details["signal_estimation"] = {
            "momentum_signal_pct": momentum_signal,
            "hold_seconds": hold_seconds,
            "adverse_drift_bps": adverse_drift_bps,
            "adverse_drift_pct": adverse_drift_pct,
            "risk_adjusted_gross_pct": momentum_signal - adverse_drift_pct,
        }

        # Step 4: Net return calculation with full cost model
        net_result = self.net_calculator.meme_sniper_net_return(
            entry_quote=entry_quote,
            exit_quote=exit_quote,
            trade_size_usd=trade_size_usd,
            hold_seconds=hold_seconds,
            momentum_signal_pct=momentum_signal,
        )

        validation_details["net_return"] = net_result.to_dict()

        # Step 5: Final accept/reject decision
        if net_result.passes_threshold:
            return MemeSignal(
                accepted=True,
                gross_return_pct=net_result.gross_return_pct,
                net_return_pct=net_result.net_return_pct,
                cost_breakdown=net_result.cost_breakdown.to_dict(),
                trade_size_usd=trade_size_usd,
                quotes_used={"entry": entry_quote, "exit": exit_quote},
                pool_data=pool_data,
                validation_details=validation_details,
                momentum_signal_pct=momentum_signal,
                adverse_drift_pct=adverse_drift_pct,
                hold_seconds=hold_seconds,
            )
        else:
            return MemeSignal(
                accepted=False,
                gross_return_pct=net_result.gross_return_pct,
                net_return_pct=net_result.net_return_pct,
                cost_breakdown=net_result.cost_breakdown.to_dict(),
                rejection_reason=net_result.rejection_reason.value if net_result.rejection_reason else "unknown",
                rejection_message=net_result.rejection_message,
                trade_size_usd=trade_size_usd,
                quotes_used={"entry": entry_quote, "exit": exit_quote},
                pool_data=pool_data,
                validation_details=validation_details,
                momentum_signal_pct=momentum_signal,
                adverse_drift_pct=adverse_drift_pct,
                hold_seconds=hold_seconds,
            )

    def scan_geckoterminal_pools(
        self,
        pools: List[Dict],
        trade_size_usd: float,
    ) -> List[MemeSignal]:
        """
        Scan GeckoTerminal pools for meme sniper opportunities.
        """
        signals = []

        for pool in pools:
            attrs = pool.get("attributes", {})

            # Extract token info
            base_token = attrs.get("base_token_symbol", "")
            quote_token = attrs.get("quote_token_symbol", "")
            if not base_token or not quote_token:
                continue

            symbol = f"{base_token}/{quote_token}"

            # Create entry quote from pool
            entry_quote = create_quote_from_geckoterminal(
                symbol=symbol,
                price=attrs.get("price_usd", 0),
                pair_address=pool.get("id", ""),
                liquidity_usd=attrs.get("reserve_in_usd", 0),
                volume_24h_usd=attrs.get("volume_usd", {}).get("h24", 0),
                fee_tier_bps=attrs.get("fee", 0) * 100,
            )

            # Exit quote: projected price after momentum
            momentum = self.estimate_momentum_signal(pool)
            exit_price = entry_quote.price * (1 + momentum / 100.0)
            exit_quote = PriceQuote(
                symbol=symbol,
                price=exit_price,
                source="geckoterminal_projected",
                timestamp=__import__('time').time(),
                liquidity_usd=entry_quote.liquidity_usd,
            )

            signal = self.validate_and_score(
                pool_data=pool,
                entry_quote=entry_quote,
                exit_quote=exit_quote,
                trade_size_usd=trade_size_usd,
            )
            if signal.accepted:
                signals.append(signal)

        return signals