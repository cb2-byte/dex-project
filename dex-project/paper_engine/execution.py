"""
Paper Execution Engine
=======================
Simulates trade execution with configurable capital, position sizing, fills, and P&L tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Tuple
from enum import Enum
import time
import uuid

from .config import PaperConfig
from .market_data import PriceQuote
from .net_return import NetReturnResult
from .boundaries import ExecutionBoundary, get_boundary


class FillStatus(Enum):
    """Status of a simulated fill."""
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"


@dataclass
class PaperFill:
    """Simulated fill result."""
    fill_id: str
    symbol: str
    side: Literal["buy", "sell"]
    requested_size_usd: float
    filled_size_usd: float
    fill_price: float
    slippage_bps: float
    fees_usd: float
    gas_usd: float
    timestamp: float
    status: FillStatus = FillStatus.FILLED
    rejection_reason: Optional[str] = None

    @property
    def total_cost_usd(self) -> float:
        return self.fees_usd + self.gas_usd

    def to_dict(self) -> Dict:
        return {
            "fill_id": self.fill_id,
            "symbol": self.symbol,
            "side": self.side,
            "requested_size_usd": self.requested_size_usd,
            "filled_size_usd": self.filled_size_usd,
            "fill_price": self.fill_price,
            "slippage_bps": self.slippage_bps,
            "fees_usd": self.fees_usd,
            "gas_usd": self.gas_usd,
            "total_cost_usd": self.total_cost_usd,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class PaperPosition:
    """Open paper trading position."""
    position_id: str
    symbol: str
    side: PositionSide
    entry_price: float
    size_usd: float
    entry_time: float
    entry_fill: PaperFill
    fees_paid_usd: float = 0.0
    unrealized_pnl_usd: float = 0.0
    realized_pnl_usd: float = 0.0
    exit_fill: Optional[PaperFill] = None
    exit_time: Optional[float] = None

    @property
    def is_open(self) -> bool:
        return self.exit_fill is None

    @property
    def current_value_usd(self) -> float:
        """Current position value (for long: size * current_price / entry_price)."""
        # This is updated by mark_to_market
        return self.size_usd + self.unrealized_pnl_usd

    def to_dict(self) -> Dict:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "size_usd": self.size_usd,
            "entry_time": self.entry_time,
            "fees_paid_usd": self.fees_paid_usd,
            "unrealized_pnl_usd": self.unrealized_pnl_usd,
            "realized_pnl_usd": self.realized_pnl_usd,
            "is_open": self.is_open,
            "exit_time": self.exit_time,
            "exit_fill": self.exit_fill.to_dict() if self.exit_fill else None,
        }


@dataclass
class PaperTrade:
    """Completed paper trade record."""
    trade_id: str
    strategy: str
    symbol: str
    side: str
    entry_time: float
    exit_time: float
    entry_price: float
    exit_price: float
    size_usd: float
    fees_usd: float
    slippage_usd: float
    gas_usd: float
    gross_pnl_usd: float
    net_pnl_usd: float
    hold_seconds: float
    return_pct: float

    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "side": self.side,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "size_usd": self.size_usd,
            "fees_usd": self.fees_usd,
            "slippage_usd": self.slippage_usd,
            "gas_usd": self.gas_usd,
            "gross_pnl_usd": self.gross_pnl_usd,
            "net_pnl_usd": self.net_pnl_usd,
            "hold_seconds": self.hold_seconds,
            "return_pct": self.return_pct,
        }


class PaperExecutionEngine:
    """
    Paper trading execution engine with risk management.
    Simulates fills, tracks positions, enforces limits, records P&L.
    """

    def __init__(self, config: PaperConfig, boundary: Optional[ExecutionBoundary] = None):
        self.config = config
        self.boundary = boundary or get_boundary(paper_mode=True)

        # Capital & risk state
        self.starting_capital_usd = config.starting_capital_usd
        self.cash_usd = config.starting_capital_usd
        self.max_position_usd = config.starting_capital_usd * config.max_position_pct
        self.max_daily_exposure_usd = config.starting_capital_usd * config.max_daily_exposure_pct
        self.max_drawdown_usd = config.starting_capital_usd * config.max_drawdown_pct

        # Position tracking
        self.positions: Dict[str, PaperPosition] = {}
        self.closed_trades: List[PaperTrade] = []
        self.fills: List[PaperFill] = []

        # Daily tracking
        self.daily_pnl_usd = 0.0
        self.daily_volume_usd = 0.0
        self.daily_trades = 0
        self.peak_equity = config.starting_capital_usd
        self.max_drawdown_pct = 0.0

        # Kill switch
        self.kill_switch_triggered = False
        self.kill_switch_reason = ""

    # ============================================================
    # Risk Checks
    # ============================================================
    def can_open_position(self, size_usd: float) -> Tuple[bool, str]:
        """Check if new position can be opened within risk limits."""
        if self.kill_switch_triggered:
            return False, f"Kill switch active: {self.kill_switch_reason}"

        # Check position size limit
        if size_usd > self.max_position_usd:
            return False, f"Position size ${size_usd:.2f} exceeds max ${self.max_position_usd:.2f}"

        # Check daily exposure limit
        if self.daily_volume_usd + size_usd > self.max_daily_exposure_usd:
            return False, f"Daily exposure would exceed limit: ${self.daily_volume_usd + size_usd:.2f} > ${self.max_daily_exposure_usd:.2f}"

        # Check available cash
        if size_usd > self.cash_usd:
            return False, f"Insufficient cash: ${self.cash_usd:.2f} < ${size_usd:.2f}"

        # Check drawdown
        current_equity = self.get_portfolio_value()
        drawdown_pct = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0
        if drawdown_pct >= self.config.max_drawdown_pct:
            self.kill_switch_triggered = True
            self.kill_switch_reason = f"Max drawdown reached: {drawdown_pct:.2%}"
            return False, self.kill_switch_reason

        return True, "OK"

    def check_kill_switch(self) -> bool:
        """Check and potentially trigger kill switch."""
        current_equity = self.get_portfolio_value()
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        drawdown_pct = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0
        self.max_drawdown_pct = max(self.max_drawdown_pct, drawdown_pct)

        if drawdown_pct >= self.config.max_drawdown_pct:
            self.kill_switch_triggered = True
            self.kill_switch_reason = f"Max drawdown reached: {drawdown_pct:.2%}"
            return True
        return False

    # ============================================================
    # Fill Simulation
    # ============================================================
    def simulate_fill(
        self,
        signal_side: Literal["buy", "sell"],  # From signal perspective
        quote: PriceQuote,
        size_usd: float,
        slippage_bps: float,
        fee_bps: float,
        gas_usd: float,
    ) -> PaperFill:
        """
        Simulate a fill with slippage and fees.
        signal_side: "buy" = going long, "sell" = going short
        """
        # Apply slippage to get fill price
        # Buy: pay more (ask + slippage), Sell: receive less (bid - slippage)
        mid = quote.mid_price
        slippage_pct = slippage_bps / 10000.0

        if signal_side == "buy":
            fill_price = mid * (1 + slippage_pct)
        else:
            fill_price = mid * (1 - slippage_pct)

        # Calculate fees
        fees_usd = size_usd * (fee_bps / 10000.0)

        # Create fill
        fill = PaperFill(
            fill_id=str(uuid.uuid4())[:8],
            symbol=quote.symbol,
            side=signal_side,
            requested_size_usd=size_usd,
            filled_size_usd=size_usd,  # Full fill in paper mode
            fill_price=fill_price,
            slippage_bps=slippage_bps,
            fees_usd=fees_usd,
            gas_usd=gas_usd,
            timestamp=time.time(),
        )

        self.fills.append(fill)
        return fill

    # ============================================================
    # Position Management
    # ============================================================
    def open_position(
        self,
        strategy: str,
        symbol: str,
        side: Literal["buy", "sell"],
        quote: PriceQuote,
        size_usd: float,
        net_return: NetReturnResult,
    ) -> Tuple[Optional[PaperPosition], Optional[str]]:
        """
        Open a new position from a validated signal.
        Returns (position, error_message).
        """
        # Risk check
        can_open, reason = self.can_open_position(size_usd)
        if not can_open:
            return None, reason

        # Determine position side
        pos_side = PositionSide.LONG if side == "buy" else PositionSide.SHORT

        # Simulate entry fill
        total_fee_bps = net_return.cost_breakdown.trading_fees_bps
        total_slippage_bps = net_return.cost_breakdown.slippage_bps
        total_gas_usd = net_return.cost_breakdown.gas_usd

        # Split costs across entry/exit (roughly half each)
        entry_fee_bps = total_fee_bps / 2
        entry_slippage_bps = total_slippage_bps / 2
        entry_gas_usd = total_gas_usd / 2

        entry_fill = self.simulate_fill(
            signal_side=side,
            quote=quote,
            size_usd=size_usd,
            slippage_bps=entry_slippage_bps,
            fee_bps=entry_fee_bps,
            gas_usd=entry_gas_usd,
        )

        # Create position
        position = PaperPosition(
            position_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            side=pos_side,
            entry_price=entry_fill.fill_price,
            size_usd=size_usd,
            entry_time=entry_fill.timestamp,
            entry_fill=entry_fill,
            fees_paid_usd=entry_fill.total_cost_usd,
        )

        # Update state
        self.positions[position.position_id] = position
        self.cash_usd -= size_usd + entry_fill.total_cost_usd
        self.daily_volume_usd += size_usd
        self.daily_trades += 1

        return position, None

    def mark_to_market(self, current_quotes: Dict[str, PriceQuote]):
        """Update unrealized P&L for all open positions."""
        for position in self.positions.values():
            if not position.is_open:
                continue

            quote = current_quotes.get(position.symbol)
            if not quote:
                continue

            current_price = quote.mid_price
            entry_price = position.entry_price

            if position.side == PositionSide.LONG:
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price

            position.unrealized_pnl_usd = position.size_usd * pnl_pct

        # Check kill switch
        self.check_kill_switch()

    def close_position(
        self,
        position_id: str,
        exit_quote: PriceQuote,
        net_return: NetReturnResult,
    ) -> Tuple[Optional[PaperTrade], Optional[str]]:
        """
        Close an existing position.
        Returns (trade_record, error_message).
        """
        position = self.positions.get(position_id)
        if not position:
            return None, f"Position {position_id} not found"

        if not position.is_open:
            return None, f"Position {position_id} already closed"

        # Simulate exit fill
        total_fee_bps = net_return.cost_breakdown.trading_fees_bps
        total_slippage_bps = net_return.cost_breakdown.slippage_bps
        total_gas_usd = net_return.cost_breakdown.gas_usd

        exit_fee_bps = total_fee_bps / 2
        exit_slippage_bps = total_slippage_bps / 2
        exit_gas_usd = total_gas_usd / 2

        exit_side = "sell" if position.side == PositionSide.LONG else "buy"
        exit_fill = self.simulate_fill(
            signal_side=exit_side,
            quote=exit_quote,
            size_usd=position.size_usd,
            slippage_bps=exit_slippage_bps,
            fee_bps=exit_fee_bps,
            gas_usd=exit_gas_usd,
        )

        # Calculate P&L
        if position.side == PositionSide.LONG:
            gross_pnl = position.size_usd * (exit_fill.fill_price - position.entry_price) / position.entry_price
        else:
            gross_pnl = position.size_usd * (position.entry_price - exit_fill.fill_price) / position.entry_price

        total_fees = position.fees_paid_usd + exit_fill.total_cost_usd
        net_pnl = gross_pnl - total_fees
        hold_seconds = exit_fill.timestamp - position.entry_time
        return_pct = (net_pnl / position.size_usd) * 100

        # Create trade record
        trade = PaperTrade(
            trade_id=str(uuid.uuid4())[:8],
            strategy="",  # Set by caller
            symbol=position.symbol,
            side=position.side.value,
            entry_time=position.entry_time,
            exit_time=exit_fill.timestamp,
            entry_price=position.entry_price,
            exit_price=exit_fill.fill_price,
            size_usd=position.size_usd,
            fees_usd=total_fees,
            slippage_usd=position.entry_fill.slippage_bps * position.size_usd / 10000.0 + exit_fill.slippage_bps * position.size_usd / 10000.0,
            gas_usd=position.entry_fill.gas_usd + exit_fill.gas_usd,
            gross_pnl_usd=gross_pnl,
            net_pnl_usd=net_pnl,
            hold_seconds=hold_seconds,
            return_pct=return_pct,
        )

        # Update position
        position.exit_fill = exit_fill
        position.exit_time = exit_fill.timestamp
        position.realized_pnl_usd = net_pnl
        position.unrealized_pnl_usd = 0.0
        position.fees_paid_usd = total_fees

        # Update state
        self.cash_usd += position.size_usd + net_pnl
        self.daily_pnl_usd += net_pnl
        self.closed_trades.append(trade)

        # Remove from open positions
        del self.positions[position_id]

        return trade, None

    # ============================================================
    # Portfolio Valuation
    # ============================================================
    def get_portfolio_value(self) -> float:
        """Total portfolio value = cash + unrealized P&L."""
        unrealized = sum(p.unrealized_pnl_usd for p in self.positions.values())
        return self.cash_usd + unrealized

    def get_total_return_pct(self) -> float:
        """Total return since start."""
        return ((self.get_portfolio_value() - self.starting_capital_usd) / self.starting_capital_usd) * 100

    def get_daily_pnl_pct(self) -> float:
        """Daily P&L as percentage of starting capital."""
        return (self.daily_pnl_usd / self.starting_capital_usd) * 100

    def reset_daily(self):
        """Reset daily counters (call at midnight)."""
        self.daily_pnl_usd = 0.0
        self.daily_volume_usd = 0.0
        self.daily_trades = 0

    # ============================================================
    # State Export
    # ============================================================
    def get_state(self) -> Dict:
        """Get full engine state for persistence."""
        return {
            "starting_capital_usd": self.starting_capital_usd,
            "cash_usd": self.cash_usd,
            "portfolio_value_usd": self.get_portfolio_value(),
            "total_return_pct": self.get_total_return_pct(),
            "daily_pnl_usd": self.daily_pnl_usd,
            "daily_pnl_pct": self.get_daily_pnl_pct(),
            "daily_volume_usd": self.daily_volume_usd,
            "daily_trades": self.daily_trades,
            "open_positions": len(self.positions),
            "closed_trades": len(self.closed_trades),
            "peak_equity": self.peak_equity,
            "max_drawdown_pct": self.max_drawdown_pct,
            "kill_switch_triggered": self.kill_switch_triggered,
            "kill_switch_reason": self.kill_switch_reason,
            "positions": {pid: pos.to_dict() for pid, pos in self.positions.items()},
            "recent_fills": [f.to_dict() for f in self.fills[-100:]],
            "recent_trades": [t.to_dict() for t in self.closed_trades[-100:]],
        }


from typing import Tuple, Dict, List, Optional, Literal

# Type imports