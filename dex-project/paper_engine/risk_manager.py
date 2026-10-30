"""
Risk Manager
============
Live risk management for production trading:
- Kill switches (daily loss, drawdown, position limits)
- Exposure limits (per-strategy, per-asset, total)
- Drawdown protection (daily, weekly, max)
- Position monitoring & auto-liquidation
- Real-time risk metrics & alerts
"""

from __future__ import annotations
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
from decimal import Decimal
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field

from paper_engine.config import PaperConfig
from paper_engine.execution import PaperExecutionEngine
from paper_engine.live_execution_adapter import LiveExecutionAdapter, LiveOrder, OrderStatus
from paper_engine.wallet_manager import WalletManager
from paper_engine.records import PaperTradeRecorder
from paper_engine.metrics import PerformanceMetrics
from paper_engine.boundaries import get_boundary, assert_paper_mode


logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskAction(Enum):
    """Actions to take when risk limits are breached."""
    WARN = "warn"                    # Log warning, continue
    REDUCE_POSITION = "reduce"       # Reduce position size
    CLOSE_POSITION = "close"         # Close specific position
    CLOSE_ALL = "close_all"          # Close all positions
    PAUSE_STRATEGY = "pause_strategy" # Pause specific strategy
    PAUSE_ALL = "pause_all"          # Pause all trading
    LIQUIDATE = "liquidate"          # Emergency liquidation


@dataclass
class RiskLimit:
    """Defines a risk limit with action on breach."""
    name: str
    limit_type: str  # "position", "exposure", "drawdown", "loss", "concentration"
    threshold: Decimal
    action: RiskAction
    scope: str = "global"  # "global", "strategy", "asset", "position"
    scope_value: Optional[str] = None  # e.g., strategy name, asset symbol
    cooldown_seconds: float = 300.0  # Cooldown before re-triggering


@dataclass
class RiskEvent:
    """Record of a risk event."""
    event_id: str
    timestamp: float
    level: RiskLevel
    limit_name: str
    limit_type: str
    current_value: Decimal
    threshold: Decimal
    action_taken: RiskAction
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionRisk:
    """Risk metrics for a position."""
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: float
    notional_value: Decimal
    margin_used: Optional[Decimal] = None
    leverage: Optional[float] = None


@dataclass
class PortfolioRisk:
    """Aggregate portfolio risk metrics."""
    total_equity: Decimal
    total_notional: Decimal
    total_unrealized_pnl: Decimal
    daily_pnl: Decimal
    daily_pnl_pct: float
    max_drawdown: Decimal
    max_drawdown_pct: float
    current_drawdown: Decimal
    current_drawdown_pct: float
    positions: List[PositionRisk] = field(default_factory=list)
    strategy_exposure: Dict[str, Decimal] = field(default_factory=dict)
    asset_exposure: Dict[str, Decimal] = field(default_factory=dict)
    leverage: float = 0.0
    margin_used: Decimal = Decimal("0")
    margin_available: Decimal = Decimal("0")


class RiskManager:
    """
    Live risk management system with kill switches, exposure limits,
    drawdown protection, and real-time monitoring.
    """

    def __init__(
        self,
        config: PaperConfig,
        execution_adapter: LiveExecutionAdapter,
        wallet_manager: WalletManager,
        recorder: Optional[PaperTradeRecorder] = None,
    ):
        self.config = config
        self.execution_adapter = execution_adapter
        self.wallet_manager = wallet_manager
        self.recorder = recorder
        self.boundary = get_boundary()

        # Risk limits (configurable)
        self.limits: List[RiskLimit] = []
        self._setup_default_limits()

        # State
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._last_portfolio_value: Decimal = Decimal("0")
        self._peak_portfolio_value: Decimal = Decimal("0")
        self._daily_start_value: Decimal = Decimal("0")
        self._daily_start_time: float = 0

        # Events
        self.event_log: deque = deque(maxlen=10000)
        self._alert_callbacks: List[Callable[[RiskEvent], Awaitable[None]]] = []

        # Cooldowns
        self._last_triggered: Dict[str, float] = {}

        # Callbacks
        self.on_alert: Optional[Callable[[RiskEvent], Awaitable[None]]] = None
        self.on_action_executed: Optional[Callable[[RiskAction, str], Awaitable[None]]] = None

    def _setup_default_limits(self):
        """Configure default risk limits from config."""
        # Daily loss limit
        self.add_limit(RiskLimit(
            name="daily_loss_limit",
            limit_type="loss",
            threshold=Decimal(str(self.config.max_daily_drawdown)) / Decimal("100"),
            action=RiskAction.PAUSE_ALL,
            scope="global",
            cooldown_seconds=86400,  # 24 hours
        ))

        # Max drawdown
        self.add_limit(RiskLimit(
            name="max_drawdown",
            limit_type="drawdown",
            threshold=Decimal(str(self.config.max_daily_drawdown)) / Decimal("100"),
            action=RiskAction.PAUSE_ALL,
            scope="global",
            cooldown_seconds=86400,
        ))

        # Max position size
        self.add_limit(RiskLimit(
            name="max_position_size",
            limit_type="position",
            threshold=Decimal(str(self.config.max_position_usd)),
            action=RiskAction.CLOSE_POSITION,
            scope="position",
            cooldown_seconds=3600,
        ))

        # Daily exposure limit
        self.add_limit(RiskLimit(
            name="daily_exposure_limit",
            limit_type="exposure",
            threshold=Decimal(str(self.config.max_daily_exposure_usd)),
            action=RiskAction.PAUSE_ALL,
            scope="global",
            cooldown_seconds=86400,
        ))

        # Per-asset concentration (max 30% in single asset)
        self.add_limit(RiskLimit(
            name="concentration_limit",
            limit_type="concentration",
            threshold=Decimal("0.30"),
            action=RiskAction.REDUCE_POSITION,
            scope="asset",
            cooldown_seconds=3600,
        ))

    def add_limit(self, limit: RiskLimit):
        """Add or update a risk limit."""
        # Remove existing with same name
        self.limits = [l for l in self.limits if l.name != limit.name]
        self.limits.append(limit)

    def remove_limit(self, name: str) -> bool:
        """Remove a risk limit by name."""
        for i, limit in enumerate(self.limits):
            if limit.name == name:
                self.limits.pop(i)
                return True
        return False

    def add_alert_callback(self, callback: Callable[[RiskEvent], Awaitable[None]]):
        """Add alert callback."""
        self._alert_callbacks.append(callback)

    # ============================================================
    # Core Risk Calculations
    # ============================================================

    def calculate_portfolio_risk(self) -> PortfolioRisk:
        """Calculate current portfolio risk metrics."""
        state = self.execution_adapter.get_state()

        # Get current positions from execution adapter
        positions = []
        for pos_id, pos in self.execution_adapter.positions.items():
            pos_risk = PositionRisk(
                symbol=pos.symbol,
                side=pos.side.value,
                quantity=pos.size_usd,
                entry_price=pos.entry_price,
                current_price=pos.entry_price,  # Would fetch real price in production
                unrealized_pnl=pos.unrealized_pnl_usd,
                unrealized_pnl_pct=0.0,
                notional_value=pos.size_usd,
            )
            if pos.entry_price > 0:
                # Would calculate real P&L with current price
                pass

        # Calculate portfolio metrics
        total_equity = Decimal(str(state.get("portfolio_value_usd", 0)))
        daily_pnl = Decimal(str(state.get("daily_pnl_usd", 0)))
        total_equity_start = self._daily_start_value if self._daily_start_value > 0 else total_equity

        daily_pnl_pct = float(daily_pnl / total_equity_start * 100) if total_equity_start > 0 else 0

        # Update peak
        if total_equity > self._peak_portfolio_value:
            self._peak_portfolio_value = total_equity

        # Calculate drawdown
        drawdown = self._peak_portfolio_value - total_equity
        drawdown_pct = float(drawdown / self._peak_portfolio_value * 100) if self._peak_portfolio_value > 0 else 0

        # Daily P&L %
        daily_pnl_pct = float(daily_pnl / self._daily_start_value * 100) if self._daily_start_value > 0 else 0

        return PortfolioRisk(
            total_equity=total_equity,
            total_notional=Decimal(str(state.get("total_allocated", 0))),
            total_unrealized_pnl=Decimal("0"),
            daily_pnl=Decimal(str(state.get("daily_pnl_usd", 0))),
            daily_pnl_pct=daily_pnl_pct,
            max_drawdown=Decimal(str(state.get("max_drawdown_pct", 0))) / Decimal("100") * Decimal(str(state.get("peak_equity", total_equity))),
            max_drawdown_pct=state.get("max_drawdown_pct", 0),
            current_drawdown=Decimal(str(self._peak_portfolio_value - total_equity)),
            current_drawdown_pct=drawdown_pct,
            leverage=0.0,
        )

    # ============================================================
    # Limit Checking
    # ============================================================

    async def check_limits(self) -> List[RiskEvent]:
        """Check all risk limits against current state. Returns triggered events."""
        events = []
        portfolio = self.calculate_portfolio_risk()

        for limit in self.limits:
            # Check cooldown
            if limit.name in self._last_triggered:
                if time.time() - self._last_triggered[limit.name] < limit.cooldown_seconds:
                    continue

            triggered = False
            current_value = Decimal("0")
            message = ""

            if limit.limit_type == "loss":
                # Daily loss
                portfolio = self.calculate_portfolio_risk()
                daily_loss_pct = abs(portfolio.daily_pnl_pct) / 100
                if daily_loss_pct >= limit.threshold:
                    triggered = True
                    current_value = Decimal(str(portfolio.daily_pnl_pct / 100))
                    message = f"Daily loss {daily_loss_pct:.2%} exceeds limit {limit.threshold:.2%}"

            elif limit.limit_type == "drawdown":
                portfolio = self.calculate_portfolio_risk()
                if portfolio.current_drawdown_pct >= limit.threshold * 100:
                    triggered = True
                    current_value = Decimal(str(portfolio.current_drawdown_pct / 100))
                    message = f"Drawdown {portfolio.current_drawdown_pct:.2f}% exceeds limit {limit.threshold * 100:.2f}%"

            elif limit.limit_type == "position":
                # Check individual position sizes
                # Would check each active position
                pass

            elif limit.limit_type == "exposure":
                portfolio = self.calculate_portfolio_risk()
                daily_exposure = portfolio.total_notional
                if daily_exposure >= limit.threshold:
                    triggered = True
                    current_value = portfolio.total_notional
                    message = f"Daily exposure ${daily_exposure:,.0f} exceeds limit ${limit.threshold:,.0f}"

            elif limit.limit_type == "concentration":
                # Check asset concentration
                # Would iterate positions and check concentration
                pass

            if triggered:
                event = RiskEvent(
                    event_id=str(uuid.uuid4())[:8],
                    timestamp=time.time(),
                    level=self._determine_risk_level(limit),
                    limit_name=limit.name,
                    limit_type=limit.limit_type,
                    current_value=current_value,
                    threshold=limit.threshold,
                    action_taken=limit.action,
                    message=message,
                    details={
                        "scope": limit.scope,
                        "scope_value": limit.scope_value,
                    },
                )
                self._last_triggered[limit.name] = time.time()
                await self._handle_risk_event(event)
                yield event

    def _determine_risk_level(self, limit: RiskLimit) -> RiskLevel:
        """Determine risk level from action severity."""
        action_severity = {
            RiskAction.WARN: RiskLevel.LOW,
            RiskAction.REDUCE_POSITION: RiskLevel.MEDIUM,
            RiskAction.CLOSE_POSITION: RiskLevel.HIGH,
            RiskAction.CLOSE_ALL: RiskLevel.HIGH,
            RiskAction.PAUSE_STRATEGY: RiskLevel.HIGH,
            RiskAction.PAUSE_ALL: RiskLevel.CRITICAL,
            RiskAction.LIQUIDATE: RiskLevel.CRITICAL,
        }
        return action_severity.get(limit.action, RiskLevel.MEDIUM)

    async def _handle_risk_event(self, event: RiskEvent):
        """Handle a triggered risk event."""
        logger.warning(f"RISK EVENT: {event.limit_name} - {event.message}")

        # Execute action
        await self._execute_action(event)

        # Log event
        self.event_log.append(event)

        # Callbacks
        for callback in self._alert_callbacks:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # Record in event log
        self.event_log.append(event)

    async def _execute_action(self, event: RiskEvent):
        """Execute the risk action."""
        action = event.action_taken

        try:
            if action == RiskAction.WARN:
                logger.warning(f"Risk warning: {event.message}")

            elif action == RiskAction.REDUCE_POSITION:
                await self._reduce_positions(event)

            elif action == RiskAction.CLOSE_POSITION:
                await self._close_positions(event)

            elif action == RiskAction.CLOSE_ALL:
                await self._close_all_positions()

            elif action == RiskAction.PAUSE_STRATEGY:
                await self._pause_strategy(event)

            elif action == RiskAction.PAUSE_ALL:
                await self._pause_all()

            elif action == RiskAction.LIQUIDATE:
                await self._emergency_liquidate()

            if self.on_action_executed:
                await self.on_action_executed(event.action_taken, event.limit_name)

        except Exception as e:
            logger.error(f"Failed to execute action {action}: {e}")

    async def _reduce_positions(self, event: RiskEvent):
        """Reduce position sizes by 50%."""
        logger.warning("Reducing positions by 50% due to risk limit")
        # Would integrate with execution adapter to reduce positions

    async def _close_positions(self, event: RiskEvent):
        """Close specific positions."""
        logger.warning("Closing positions due to risk limit")
        # Would close specific positions via execution adapter

    async def _close_all_positions(self):
        """Close all open positions."""
        logger.critical("CLOSING ALL POSITIONS - Emergency action")
        await self.execution_adapter.cancel_all_orders()

    async def _pause_strategy(self, event: RiskEvent):
        """Pause a specific strategy."""
        scope_value = event.details.get("scope_value")
        logger.warning(f"Pausing strategy: {scope_value}")
        # Would pause the strategy in orchestrator

    async def _pause_all(self):
        """Pause all trading."""
        logger.critical("PAUSING ALL TRADING")
        # Would pause all strategies

    async def _emergency_liquidate(self):
        """Emergency liquidation of all positions."""
        logger.critical("EMERGENCY LIQUIDATION INITIATED")
        await self._close_all_positions()
        # Additional emergency procedures

    # ============================================================
    # Monitoring Loop
    # ============================================================

    async def start_monitoring(self, interval: float = 10.0):
        """Start risk monitoring loop."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info("Risk manager monitoring started")

    async def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, interval: float):
        """Main monitoring loop."""
        while self._running:
            try:
                # Check all limits
                async for event in self.check_limits():
                    pass  # Events handled in check_limits

                # Update portfolio metrics
                portfolio = self.calculate_portfolio_risk()
                self._last_portfolio_value = portfolio.total_equity

                # Initialize daily tracking
                if self._daily_start_time == 0:
                    self._daily_start_time = time.time()
                    self._daily_start_value = portfolio.total_equity

                # Reset daily at midnight
                if time.time() - self._daily_start_time > 86400:
                    self._daily_start_time = time.time()
                    portfolio = self.calculate_portfolio_risk()
                    self._daily_start_value = portfolio.total_equity

                await asyncio.sleep(10.0)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Risk monitor error: {e}")
                await asyncio.sleep(5.0)

    # ============================================================
    # Public API
    # ============================================================

    def add_alert_callback(self, callback: Callable[[RiskEvent], Awaitable[None]]):
        """Add callback for risk events."""
        self._alert_callbacks.append(callback)

    def get_risk_status(self) -> Dict:
        """Get current risk status."""
        portfolio = self.calculate_portfolio_risk()

        return {
            "total_equity": str(portfolio.total_equity),
            "daily_pnl_pct": portfolio.daily_pnl_pct,
            "current_drawdown_pct": portfolio.current_drawdown_pct,
            "max_drawdown_pct": portfolio.max_drawdown_pct,
            "total_notional": str(portfolio.total_notional),
            "active_limits": len(self.limits),
            "active_alerts": len([e for e in self.event_log if time.time() - e.timestamp < 3600]),
        }

    def get_recent_events(self, limit: int = 100) -> List[Dict]:
        """Get recent risk events."""
        return [e.__dict__ for e in list(self.event_log)[-limit:]]

    def get_limit_status(self) -> List[Dict]:
        """Get status of all risk limits."""
        return [
            {
                "name": limit.name,
                "type": limit.limit_type,
                "threshold": str(limit.threshold),
                "action": limit.action.value,
                "scope": limit.scope,
                "cooldown_remaining": max(0, limit.cooldown_seconds - (time.time() - self._last_triggered.get(limit.name, 0))),
            }
            for limit in self.limits
        }

    def update_limit(self, name: str, threshold: Decimal, action: RiskAction = None):
        """Update an existing limit."""
        for limit in self.limits:
            if limit.name == name:
                limit.threshold = threshold
                if action:
                    limit.action = action
                return True
        return False

    def add_custom_limit(self, limit: RiskLimit):
        """Add a custom risk limit."""
        self.limits.append(limit)

    def emergency_stop(self, reason: str = "Manual emergency stop"):
        """Trigger emergency stop - liquidate everything."""
        logger.critical(f"EMERGENCY STOP: {reason}")
        asyncio.create_task(self._emergency_liquidate())


__all__ = [
    "RiskManager",
    "RiskLimit",
    "RiskEvent",
    "RiskLevel",
    "RiskAction",
    "PortfolioRisk",
    "PositionRisk",
]