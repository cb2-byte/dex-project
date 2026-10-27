"""
Net Return Calculator
=====================
Calculates net returns for all strategies including fees, slippage, price impact, and transfer costs.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from enum import Enum
import math

from .config import FeeSchedule, SlippageModel, PaperConfig
from .market_data import PriceQuote, ValidationResult, ValidationStatus


class RejectionReason(Enum):
    """Reasons for rejecting a trade opportunity."""
    NEGATIVE_NET_RETURN = "negative_net_return"
    BELOW_THRESHOLD = "below_threshold"
    STALE_PRICE = "stale_price"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    MISSING_PAIR = "missing_pair"
    EXCESSIVE_SLIPPAGE = "excessive_slippage"
    TRANSFER_COST_EXCEEDS_EDGE = "transfer_cost_exceeds_edge"
    INVALID_QUOTE = "invalid_quote"


@dataclass
class CostBreakdown:
    """Detailed cost breakdown for a trade."""
    trading_fees_bps: float = 0.0
    slippage_bps: float = 0.0
    gas_usd: float = 0.0
    withdrawal_fees_usd: float = 0.0
    deposit_fees_usd: float = 0.0
    bridge_fees_bps: float = 0.0
    adverse_drift_bps: float = 0.0  # For meme sniper

    @property
    def total_cost_bps(self) -> float:
        return (self.trading_fees_bps + self.slippage_bps +
                self.bridge_fees_bps + self.adverse_drift_bps)

    @property
    def total_cost_usd(self) -> float:
        return self.gas_usd + self.withdrawal_fees_usd + self.deposit_fees_usd

    def to_dict(self) -> Dict:
        return {
            "trading_fees_bps": self.trading_fees_bps,
            "slippage_bps": self.slippage_bps,
            "gas_usd": self.gas_usd,
            "withdrawal_fees_usd": self.withdrawal_fees_usd,
            "deposit_fees_usd": self.deposit_fees_usd,
            "bridge_fees_bps": self.bridge_fees_bps,
            "adverse_drift_bps": self.adverse_drift_bps,
            "total_cost_bps": self.total_cost_bps,
            "total_cost_usd": self.total_cost_usd,
        }


@dataclass
class NetReturnResult:
    """Result of net return calculation."""
    gross_return_pct: float
    net_return_pct: float
    cost_breakdown: CostBreakdown
    passes_threshold: bool
    rejection_reason: Optional[RejectionReason] = None
    rejection_message: str = ""
    trade_size_usd: float = 0.0

    @property
    def is_profitable(self) -> bool:
        return self.net_return_pct > 0

    def to_dict(self) -> Dict:
        return {
            "gross_return_pct": self.gross_return_pct,
            "net_return_pct": self.net_return_pct,
            "cost_breakdown": self.cost_breakdown.to_dict(),
            "passes_threshold": self.passes_threshold,
            "rejection_reason": self.rejection_reason.value if self.rejection_reason else None,
            "rejection_message": self.rejection_message,
            "trade_size_usd": self.trade_size_usd,
            "is_profitable": self.is_profitable,
        }


class TransferPath(Enum):
    """Transfer path between exchanges/venues."""
    SAME_CHAIN = "same_chain"           # Same blockchain, just gas
    WITHDRAW_DEPOSIT = "withdraw_deposit"  # Withdraw from A, deposit to B
    BRIDGE = "bridge"                   # Cross-chain bridge


@dataclass
class NetReturnCalculator:
    """
    Calculates net returns for all strategy types.
    Applies fees, slippage, gas, transfer costs, and adverse drift.
    """
    config: PaperConfig

    def __post_init__(self):
        self.fee_schedule = self.config.fee_schedule
        self.slippage_model = self.config.slippage_model

    # ============================================================
    # Triangular Arbitrage: ETH -> SOL -> USDT -> ETH (or similar)
    # ============================================================
    def triangular_net_return(
        self,
        leg1_quote: PriceQuote,   # e.g., ETH/USDC (sell ETH, buy USDC)
        leg2_quote: PriceQuote,   # e.g., SOL/USDC (sell USDC, buy SOL)
        leg3_quote: PriceQuote,   # e.g., ETH/SOL (sell SOL, buy ETH)
        trade_size_usd: float,
        chain: str = "base",
    ) -> NetReturnResult:
        """
        Calculate net return for 3-leg triangular arbitrage.
        All legs on same chain (e.g., Base) -> only gas costs for transfers.
        """
        # Validate all quotes
        for label, quote in [("leg1", leg1_quote), ("leg2", leg2_quote), ("leg3", leg3_quote)]:
            if quote.price <= 0:
                return NetReturnResult(
                    gross_return_pct=0.0,
                    net_return_pct=0.0,
                    cost_breakdown=CostBreakdown(),
                    passes_threshold=False,
                    rejection_reason=RejectionReason.INVALID_QUOTE,
                    rejection_message=f"{label}: invalid price {quote.price}",
                    trade_size_usd=trade_size_usd,
                )

        # Calculate gross return from price cycle
        # Start with trade_size_usd of base asset (e.g., USDC)
        # Leg 1: USDC -> ETH (buy ETH at ask or mid)
        # Leg 2: ETH -> SOL (sell ETH, buy SOL)
        # Leg 3: SOL -> USDC (sell SOL, buy USDC)
        # Gross return = (final_usdc / initial_usdc - 1) * 100

        # Use mid prices for calculation
        p1 = leg1_quote.mid_price   # ETH per USDC (or USDC per ETH depending on convention)
        p2 = leg2_quote.mid_price   # SOL per USDC
        p3 = leg3_quote.mid_price   # ETH per SOL

        # Need to handle quote conventions carefully
        # Assume all quotes are in USDC terms for simplicity:
        # leg1: ETH/USDC -> price = USDC per ETH
        # leg2: SOL/USDC -> price = USDC per SOL
        # leg3: ETH/SOL -> price = SOL per ETH

        # Round trip: USDC -> ETH -> SOL -> USDC
        # USDC -> ETH: amount_eth = trade_size_usd / p1
        # ETH -> SOL: amount_sol = amount_eth * p3
        # SOL -> USDC: final_usdc = amount_sol * p2
        # Gross return = (final_usdc / trade_size_usd - 1) * 100

        try:
            amount_eth = trade_size_usd / p1
            amount_sol = amount_eth * p3
            final_usdc = amount_sol * p2
            gross_return_pct = (final_usdc / trade_size_usd - 1.0) * 100
        except (ZeroDivisionError, OverflowError):
            return NetReturnResult(
                gross_return_pct=0.0,
                net_return_pct=0.0,
                cost_breakdown=CostBreakdown(),
                passes_threshold=False,
                rejection_reason=RejectionReason.INVALID_QUOTE,
                rejection_message="Price calculation error (division by zero or overflow)",
                trade_size_usd=trade_size_usd,
            )

        # Calculate costs for 3 legs
        cost_breakdown = CostBreakdown()

        # Trading fees (3 legs)
        fee_bps_1 = self.fee_schedule.trading_fee_bps.get(leg1_quote.source, 30.0)
        fee_bps_2 = self.fee_schedule.trading_fee_bps.get(leg2_quote.source, 30.0)
        fee_bps_3 = self.fee_schedule.trading_fee_bps.get(leg3_quote.source, 30.0)
        cost_breakdown.trading_fees_bps = fee_bps_1 + fee_bps_2 + fee_bps_3

        # Slippage (3 legs)
        liq1 = leg1_quote.liquidity_usd or 1e9
        liq2 = leg2_quote.liquidity_usd or 1e9
        liq3 = leg3_quote.liquidity_usd or 1e9
        slip1 = self.slippage_model.estimate_slippage_bps(trade_size_usd, liq1)
        slip2 = self.slippage_model.estimate_slippage_bps(trade_size_usd, liq2)
        slip3 = self.slippage_model.estimate_slippage_bps(trade_size_usd, liq3)
        cost_breakdown.slippage_bps = slip1 + slip2 + slip3

        # Gas (3 transactions on same chain)
        gas_per_tx = self.fee_schedule.gas_estimate_usd.get(chain, 0.01)
        cost_breakdown.gas_usd = 3 * gas_per_tx

        # Total cost in percentage
        total_cost_bps = cost_breakdown.total_cost_bps
        total_cost_usd = cost_breakdown.total_cost_usd
        cost_pct = (total_cost_bps / 10000.0) * 100 + (total_cost_usd / trade_size_usd) * 100

        net_return_pct = gross_return_pct - cost_pct

        # Check thresholds
        passes = (net_return_pct >= self.config.min_net_edge_pct and
                  net_return_pct > 0)

        rejection = None
        message = ""
        if net_return_pct <= 0:
            rejection = RejectionReason.NEGATIVE_NET_RETURN
            message = f"Negative net return: {net_return_pct:.4f}%"
        elif not passes:
            rejection = RejectionReason.BELOW_THRESHOLD
            message = f"Net return {net_return_pct:.4f}% below threshold {self.config.min_net_edge_pct}%"

        return NetReturnResult(
            gross_return_pct=gross_return_pct,
            net_return_pct=net_return_pct,
            cost_breakdown=cost_breakdown,
            passes_threshold=passes,
            rejection_reason=rejection,
            rejection_message=message,
            trade_size_usd=trade_size_usd,
        )

    # ============================================================
    # Cross-Exchange Arbitrage: Buy on A, Sell on B
    # ============================================================
    def cross_exchange_net_return(
        self,
        buy_quote: PriceQuote,      # Cheaper exchange (buy here)
        sell_quote: PriceQuote,     # Expensive exchange (sell here)
        trade_size_usd: float,
        transfer_path: TransferPath = TransferPath.SAME_CHAIN,
        bridge_name: Optional[str] = None,
    ) -> NetReturnResult:
        """
        Calculate net return for cross-exchange arbitrage.
        Includes fees on both exchanges + transfer/settlement costs.
        """
        # Validate quotes
        for label, quote in [("buy", buy_quote), ("sell", sell_quote)]:
            if quote.price <= 0:
                return NetReturnResult(
                    gross_return_pct=0.0,
                    net_return_pct=0.0,
                    cost_breakdown=CostBreakdown(),
                    passes_threshold=False,
                    rejection_reason=RejectionReason.INVALID_QUOTE,
                    rejection_message=f"{label}: invalid price {quote.price}",
                    trade_size_usd=trade_size_usd,
                )

        # Gross return from price discrepancy
        # buy at buy_quote.price (or ask), sell at sell_quote.price (or bid)
        buy_price = buy_quote.ask or buy_quote.mid_price
        sell_price = sell_quote.bid or sell_quote.mid_price

        if sell_price <= buy_price:
            return NetReturnResult(
                gross_return_pct=0.0,
                net_return_pct=0.0,
                cost_breakdown=CostBreakdown(),
                passes_threshold=False,
                rejection_reason=RejectionReason.NEGATIVE_NET_RETURN,
                rejection_message=f"No price edge: buy {buy_price} >= sell {sell_price}",
                trade_size_usd=trade_size_usd,
            )

        gross_return_pct = ((sell_price - buy_price) / buy_price) * 100

        # Cost breakdown
        cost_breakdown = CostBreakdown()

        # Trading fees (2 legs)
        buy_fee_bps = self.fee_schedule.trading_fee_bps.get(buy_quote.source, 30.0)
        sell_fee_bps = self.fee_schedule.trading_fee_bps.get(sell_quote.source, 30.0)
        cost_breakdown.trading_fees_bps = buy_fee_bps + sell_fee_bps

        # Slippage (2 legs)
        buy_liq = buy_quote.liquidity_usd or 1e9
        sell_liq = sell_quote.liquidity_usd or 1e9
        buy_slip = self.slippage_model.estimate_slippage_bps(trade_size_usd, buy_liq)
        sell_slip = self.slippage_model.estimate_slippage_bps(trade_size_usd, sell_liq)
        cost_breakdown.slippage_bps = buy_slip + sell_slip

        # Transfer costs
        if transfer_path == TransferPath.SAME_CHAIN:
            # Just gas on source chain
            chain = buy_quote.source  # assume same chain
            cost_breakdown.gas_usd = self.fee_schedule.gas_estimate_usd.get(chain, 0.01)

        elif transfer_path == TransferPath.WITHDRAW_DEPOSIT:
            # Withdrawal from buy exchange + deposit to sell exchange + gas both
            cost_breakdown.withdrawal_fees_usd = self.fee_schedule.withdrawal_fee_usd.get(
                buy_quote.exchange or buy_quote.source, 0.0)
            cost_breakdown.deposit_fees_usd = self.fee_schedule.deposit_fee_usd.get(
                sell_quote.exchange or sell_quote.source, 0.0)
            # Gas for withdrawal + deposit
            cost_breakdown.gas_usd = (
                self.fee_schedule.gas_estimate_usd.get(buy_quote.source, 0.01) +
                self.fee_schedule.gas_estimate_usd.get(sell_quote.source, 0.01)
            )

        elif transfer_path == TransferPath.BRIDGE:
            # Bridge fee + gas on both chains
            bridge_fee_bps = self.fee_schedule.bridge_fee_bps.get(bridge_name or "hop", 5.0)
            cost_breakdown.bridge_fees_bps = bridge_fee_bps
            cost_breakdown.gas_usd = (
                self.fee_schedule.gas_estimate_usd.get(buy_quote.source, 0.01) +
                self.fee_schedule.gas_estimate_usd.get(sell_quote.source, 0.01)
            )

        # Total cost percentage
        total_cost_bps = cost_breakdown.total_cost_bps
        total_cost_usd = cost_breakdown.total_cost_usd
        cost_pct = (total_cost_bps / 10000.0) * 100 + (total_cost_usd / trade_size_usd) * 100

        net_return_pct = gross_return_pct - cost_pct

        # Check thresholds
        passes = (net_return_pct >= self.config.min_net_edge_pct and
                  net_return_pct > 0)

        rejection = None
        message = ""
        if net_return_pct <= 0:
            rejection = RejectionReason.NEGATIVE_NET_RETURN
            message = f"Negative net return after costs: {net_return_pct:.4f}%"
        elif cost_pct >= gross_return_pct:
            rejection = RejectionReason.TRANSFER_COST_EXCEEDS_EDGE
            message = f"Transfer costs ({cost_pct:.4f}%) exceed gross edge ({gross_return_pct:.4f}%)"
        elif not passes:
            rejection = RejectionReason.BELOW_THRESHOLD
            message = f"Net return {net_return_pct:.4f}% below threshold {self.config.min_net_edge_pct}%"

        return NetReturnResult(
            gross_return_pct=gross_return_pct,
            net_return_pct=net_return_pct,
            cost_breakdown=cost_breakdown,
            passes_threshold=passes,
            rejection_reason=rejection,
            rejection_message=message,
            trade_size_usd=trade_size_usd,
        )

    # ============================================================
    # Meme Sniper: Entry + Exit with adverse drift
    # ============================================================
    def meme_sniper_net_return(
        self,
        entry_quote: PriceQuote,
        exit_quote: PriceQuote,           # Projected exit price
        trade_size_usd: float,
        hold_seconds: float,
        momentum_signal_pct: float = 0.0,  # 24h price change as momentum
    ) -> NetReturnResult:
        """
        Calculate net return for meme sniper trade.
        Entry + exit costs + adverse drift risk adjustment.
        """
        if entry_quote.price <= 0 or exit_quote.price <= 0:
            return NetReturnResult(
                gross_return_pct=0.0,
                net_return_pct=0.0,
                cost_breakdown=CostBreakdown(),
                passes_threshold=False,
                rejection_reason=RejectionReason.INVALID_QUOTE,
                rejection_message="Invalid entry or exit price",
                trade_size_usd=trade_size_usd,
            )

        # Gross return from momentum
        # Cap momentum signal
        momentum_capped = min(momentum_signal_pct, self.config.meme_momentum_cap_pct)
        gross_return_pct = momentum_capped

        # Adverse drift during hold period
        hold_minutes = hold_seconds / 60.0
        adverse_drift_bps = self.config.meme_adverse_move_bps_per_min * hold_minutes
        adverse_drift_pct = adverse_drift_bps / 100.0

        # Risk-adjusted gross return
        risk_adjusted_gross = gross_return_pct - adverse_drift_pct

        # Cost breakdown
        cost_breakdown = CostBreakdown()
        cost_breakdown.adverse_drift_bps = adverse_drift_bps

        # Entry + exit fees (2 legs)
        entry_fee_bps = self.fee_schedule.trading_fee_bps.get(entry_quote.source, 30.0)
        exit_fee_bps = self.fee_schedule.trading_fee_bps.get(exit_quote.source, 30.0)
        cost_breakdown.trading_fees_bps = entry_fee_bps + exit_fee_bps

        # Entry + exit slippage
        entry_liq = entry_quote.liquidity_usd or 1e9
        exit_liq = exit_quote.liquidity_usd or 1e9
        entry_slip = self.slippage_model.estimate_slippage_bps(trade_size_usd, entry_liq)
        exit_slip = self.slippage_model.estimate_slippage_bps(trade_size_usd, exit_liq)
        cost_breakdown.slippage_bps = entry_slip + exit_slip

        # Gas (2 transactions)
        chain = entry_quote.source
        cost_breakdown.gas_usd = 2 * self.fee_schedule.gas_estimate_usd.get(chain, 0.01)

        # Total cost
        total_cost_bps = cost_breakdown.total_cost_bps
        total_cost_usd = cost_breakdown.total_cost_usd
        cost_pct = (total_cost_bps / 10000.0) * 100 + (total_cost_usd / trade_size_usd) * 100

        net_return_pct = risk_adjusted_gross - cost_pct

        # Check thresholds
        passes = (net_return_pct >= self.config.min_net_edge_pct and
                  net_return_pct > 0)

        rejection = None
        message = ""
        if net_return_pct <= 0:
            rejection = RejectionReason.NEGATIVE_NET_RETURN
            message = f"Negative risk-adjusted net return: {net_return_pct:.4f}%"
        elif risk_adjusted_gross <= 0:
            rejection = RejectionReason.NEGATIVE_NET_RETURN
            message = f"Adverse drift ({adverse_drift_pct:.4f}%) exceeds momentum ({gross_return_pct:.4f}%)"
        elif not passes:
            rejection = RejectionReason.BELOW_THRESHOLD
            message = f"Net return {net_return_pct:.4f}% below threshold {self.config.min_net_edge_pct}%"

        return NetReturnResult(
            gross_return_pct=gross_return_pct,
            net_return_pct=net_return_pct,
            cost_breakdown=cost_breakdown,
            passes_threshold=passes,
            rejection_reason=rejection,
            rejection_message=message,
            trade_size_usd=trade_size_usd,
        )