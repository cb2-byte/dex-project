"""
Order Manager
=============
Order management for production trading: placement, cancellation, retry logic,
partial fills, and order lifecycle management.
"""

from __future__ import annotations
import asyncio
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
from decimal import Decimal
from datetime import datetime
from collections import deque

from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote
from paper_engine.execution import PaperExecutionEngine, NetReturnResult
from paper_engine.live_execution_adapter import LiveExecutionAdapter, LiveOrder, OrderStatus, OrderType, OrderSide
from paper_engine.wallet_manager import WalletManager
from paper_engine.records import PaperTradeRecorder
from paper_engine.boundaries import get_boundary, assert_paper_mode


logger = logging.getLogger(__name__)


class OrderState(Enum):
    """Extended order states for production."""
    CREATED = "created"
    VALIDATING = "validating"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class OrderEvent(Enum):
    """Order lifecycle events."""
    CREATED = "created"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


@dataclass
class OrderEventRecord:
    """Record of an order event for audit trail."""
    event_id: str
    order_id: str
    event: OrderEvent
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Order:
    """Production order with full lifecycle tracking."""
    order_id: str
    strategy: str
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "market", "limit", "stop_loss", "take_profit"
    quantity: Decimal
    price: Optional[Decimal] = None  # For limit orders
    stop_price: Optional[Decimal] = None
    state: OrderState = OrderState.CREATED
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    remaining_quantity: Decimal = field(init=False)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    submitted_at: Optional[float] = None
    filled_at: Optional[float] = None
    cancelled_at: Optional[float] = None
    rejected_at: Optional[float] = None
    rejected_reason: Optional[str] = None
    signature: Optional[str] = None
    client_order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    strategy: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        self.remaining_quantity = self.quantity - self.filled_quantity

    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price else None,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "state": self.state.value,
            "filled_quantity": str(self.filled_quantity),
            "avg_fill_price": str(self.avg_fill_price) if self.avg_fill_price else None,
            "remaining_quantity": str(self.remaining_quantity),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "submitted_at": self.submitted_at,
            "filled_at": self.filled_at,
            "cancelled_at": self.cancelled_at,
            "rejected_at": self.rejected_at,
            "rejected_reason": self.rejected_reason,
            "signature": self.signature,
            "client_order_id": self.client_order_id,
            "strategy": self.strategy,
            "tags": self.tags,
            "events": self.events,
            "metadata": self.metadata,
        }


class OrderValidator:
    """Validates orders before submission."""

    def __init__(self, config: PaperConfig):
        self.config = config

    def validate(self, order: 'Order', quote: PriceQuote, balance: Decimal) -> tuple[bool, Optional[str]]:
        """Validate order before submission. Returns (is_valid, error_message)."""
        # Check quantity
        if order.quantity <= 0:
            return False, "Quantity must be positive"

        # Check price for limit orders
        if order.order_type == "limit" and order.price is None:
            return False, "Limit orders require a price"

        if order.order_type == "limit" and order.price <= 0:
            return False, "Limit price must be positive"

        # Check stop price for stop orders
        if order.order_type in ("stop_loss", "take_profit") and order.stop_price is None:
            return False, "Stop orders require a stop price"

        # Check quantity limits
        if order.quantity > self.config.max_position_usd:
            return False, f"Order quantity exceeds max position size: {order.quantity} > {self.config.max_position_usd}"

        # Check price sanity for limit orders
        if order.order_type == "limit" and order.price:
            # Price shouldn't be too far from market
            mid_price = quote.mid_price
            if mid_price > 0:
                deviation = abs(order.price - mid_price) / mid_price
                if deviation > 0.1:  # 10% max deviation
                    return False, f"Limit price deviates too far from market: {deviation:.2%}"

        return True, None


class RetryPolicy:
    """Configurable retry policy for order operations."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: float = 0.1,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)."""
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        # Add jitter
        jitter_range = delay * self.jitter
        return delay + (hash(str(time.time())) % 1000 / 1000 - 0.5) * 2 * jitter_range


class OrderManager:
    """
    Production order manager handling order lifecycle:
    placement, validation, submission, partial fills, cancellations, retries.
    """

    def __init__(
        self,
        config: PaperConfig,
        execution_adapter: LiveExecutionAdapter,
        wallet_manager: WalletManager,
        recorder: Optional[PaperTradeRecorder] = None,
        validator: Optional[OrderValidator] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.config = config
        self.execution_adapter = execution_adapter
        self.wallet_manager = wallet_manager
        self.recorder = recorder
        self.validator = validator or OrderValidator(config)
        self.retry_policy = retry_policy or RetryPolicy()
        self.boundary = get_boundary()

        # Order storage
        self.orders: Dict[str, 'Order'] = {}
        self.orders_by_client_id: Dict[str, str] = {}  # client_order_id -> order_id
        self.active_orders: Dict[str, 'Order'] = {}
        self.order_history: List['Order'] = []

        # Event handlers
        self.on_order_created: Optional[Callable[['Order'], Awaitable[None]]] = None
        self.on_order_submitted: Optional[Callable[['Order'], Awaitable[None]]] = None
        self.on_order_filled: Optional[Callable[['Order'], Awaitable[None]]] = None
        self.on_order_partially_filled: Optional[Callable[['Order'], Awaitable[None]]] = None
        self.on_order_cancelled: Optional[Callable[['Order'], Awaitable[None]]] = None
        self.on_order_rejected: Optional[Callable[['Order'], Awaitable[None]]] = None
        self.on_order_failed: Optional[Callable[['Order', Exception], Awaitable[None]]] = None

        # State
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._retry_tasks: Dict[str, asyncio.Task] = {}

        # Event log
        self.event_log: deque = deque(maxlen=10000)

    # ============================================================
    # Order Creation
    # ============================================================

    def create_order(
        self,
        strategy: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict] = None,
    ) -> 'Order':
        """Create a new order."""
        order_id = str(uuid.uuid4())[:16]
        client_order_id = client_order_id or str(uuid.uuid4())[:16]

        order = Order(
            order_id=order_id,
            client_order_id=client_order_id,
            strategy=strategy,
            symbol=symbol,
            side=side.lower(),
            order_type=order_type.lower(),
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            strategy="",
            tags=tags or {},
            metadata={},
        )

        self._add_event(order, OrderEvent.CREATED, {"initial_state": "CREATED"})

        return order

    def create_market_order(
        self,
        strategy: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        client_order_id: Optional[str] = None,
    ) -> 'Order':
        """Create a market order."""
        return self.create_order(
            strategy=strategy,
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=quantity,
            client_order_id=client_order_id,
        )

    def create_limit_order(
        self,
        strategy: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: Optional[str] = None,
    ) -> 'Order':
        """Create a limit order."""
        return self.create_order(
            strategy=strategy,
            symbol=symbol,
            side=side,
            order_type="limit",
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )

    def create_stop_loss(
        self,
        strategy: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal,
        client_order_id: Optional[str] = None,
    ) -> 'Order':
        """Create a stop loss order."""
        return self.create_order(
            strategy=strategy,
            symbol=symbol,
            side=side,
            order_type="stop_loss",
            quantity=quantity,
            stop_price=stop_price,
            client_order_id=client_order_id,
        )

    def create_take_profit(
        self,
        strategy: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal,
        client_order_id: Optional[str] = None,
    ) -> 'Order':
        """Create a take profit order."""
        return self.create_order(
            strategy=strategy,
            symbol=symbol,
            side=side,
            order_type="take_profit",
            quantity=quantity,
            stop_price=stop_price,
            client_order_id=client_order_id,
        )

    # ============================================================
    # Order Validation & Submission
    # ============================================================

    def validate_order(self, order: 'Order', quote: PriceQuote, balance: Decimal) -> tuple[bool, Optional[str]]:
        """Validate order before submission."""
        return self.validator.validate(order, quote, balance)

    async def submit_order(
        self,
        order: 'Order',
        quote: PriceQuote,
        net_return: NetReturnResult,
    ) -> tuple[bool, Optional[str]]:
        """Submit order to execution adapter with retry logic."""
        self.boundary.assert_paper_mode(f"submit_order {order.order_id}")

        # Validate
        balance = self.execution_adapter.get_portfolio_value()
        is_valid, error = self.validator.validate(order, quote, Decimal(str(self.execution_adapter.get_portfolio_value())))
        if not is_valid:
            order.state = OrderState.REJECTED
            order.rejected_reason = error
            order.rejected_at = time.time()
            order.rejected_reason = error
            self._add_event(order, OrderEvent.REJECTED, {"reason": error})
            if self.on_order_rejected:
                await self.on_order_rejected(order)
            return False, error

        # Update state
        order.state = OrderState.VALIDATING
        self._add_event(order, OrderEvent.VALIDATED)

        # Submit with retry
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                order.state = OrderState.SUBMITTED
                order.submitted_at = time.time()
                order.updated_at = time.time()
                self._add_event(order, OrderEvent.SUBMITTED, {"attempt": attempt + 1})

                # Submit to execution adapter
                # This would call the live execution adapter
                # For now, we simulate
                success, error = await self._submit_to_execution(order)

                if success:
                    order.submitted_at = time.time()
                    self.active_orders[order.order_id] = order
                    self._add_event(order, OrderEvent.SUBMITTED, {"attempt": attempt + 1})
                    if self.on_order_submitted:
                        await self.on_order_submitted(order)
                    return True, None
                else:
                    logger.warning(f"Order {order.order_id} submission failed (attempt {attempt + 1}): {error}")

            except Exception as e:
                logger.warning(f"Order {order.order_id} submission error (attempt {attempt + 1}): {e}")

            # Wait before retry
            if attempt < self.retry_policy.max_retries:
                delay = self.retry_policy.get_delay(attempt)
                logger.info(f"Retrying order {order.order_id} in {delay:.1f}s")
                await asyncio.sleep(delay)

        # All retries failed
        order.state = OrderState.REJECTED
        order.rejected_reason = "Max retries exceeded"
        order.rejected_at = time.time()
        self._add_event(order, OrderEvent.REJECTED, {"reason": "max_retries_exceeded"})
        if self.on_order_rejected:
            await self.on_order_rejected(order)

        return False, "Max retries exceeded"

    async def _submit_to_execution(self, order: 'Order') -> tuple[bool, Optional[str]]:
        """Submit order to execution adapter (placeholder for actual implementation)."""
        # This would call the live_execution_adapter
        # For now, simulate success
        return True, None

    # ============================================================
    # Order Management
    # ============================================================

    def get_order(self, order_id: str) -> Optional['Order']:
        """Get order by ID."""
        return self.orders.get(order_id)

    def get_order_by_client_id(self, client_order_id: str) -> Optional['Order']:
        """Get order by client order ID."""
        order_id = self.orders_by_client_id.get(client_order_id)
        if order_id:
            return self.orders.get(order_id)
        return None

    def get_active_orders(self, strategy: Optional[str] = None) -> List['Order']:
        """Get all active orders, optionally filtered by strategy."""
        orders = list(self.active_orders.values())
        if strategy:
            return [o for o in orders if o.strategy == strategy]
        return list(self.active_orders.values())

    def get_order_history(self, strategy: Optional[str] = None, limit: int = 100) -> List['Order']:
        """Get order history."""
        history = self.order_history
        if strategy:
            history = [o for o in history if o.strategy == strategy]
        return history[-limit:]

    # ============================================================
    # Order Cancellation
    # ============================================================

    async def cancel_order(self, order_id: str, reason: str = "User cancelled") -> tuple[bool, Optional[str]]:
        """Cancel an active order."""
        order = self.orders.get(order_id)
        if not order:
            return False, "Order not found"

        if order.state not in (OrderState.CREATED, OrderState.VALIDATING, OrderState.SUBMITTED, OrderState.PARTIAL):
            return False, f"Cannot cancel order in state: {order.state.value}"

        order.state = OrderState.CANCELLING
        self._add_event(order, OrderEvent.CANCELLED, {"reason": reason})

        # For market orders already submitted, can't cancel
        if order.order_type == "market" and order.state == OrderState.SUBMITTED:
            order.state = OrderState.CANCELLED
            order.cancelled_at = time.time()
            self._add_event(order, OrderEvent.CANCELLED, {"reason": "Market order already submitted"})
            self._move_to_history(order)
            if self.on_order_cancelled:
                await self.on_order_cancelled(order)
            return True, None

        # For limit orders, would need to cancel via DEX
        # For now, mark as cancelled
        order.state = OrderState.CANCELLED
        order.cancelled_at = time.time()
        self._add_event(order, OrderEvent.CANCELLED, {"reason": reason})
        self._move_to_history(order)

        if self.on_order_cancelled:
            await self.on_order_cancelled(order)

        return True, None

    async def cancel_all_orders(self, strategy: Optional[str] = None) -> int:
        """Cancel all active orders, optionally filtered by strategy."""
        cancelled = 0
        orders_to_cancel = [
            o for o in self.active_orders.values()
            if strategy is None or o.strategy == strategy
        ]

        for order in orders_to_cancel:
            success, _ = await self.cancel_order(order.order_id, "Cancel all")
            if success:
                cancelled += 1

        return cancelled

    # ============================================================
    # Fill Handling
    # ============================================================

    def handle_fill(
        self,
        order_id: str,
        fill_quantity: Decimal,
        fill_price: Decimal,
        fee: Decimal = Decimal("0"),
        timestamp: Optional[float] = None,
    ) -> bool:
        """Process a fill (partial or full)."""
        order = self.orders.get(order_id)
        if not order:
            return False

        if order.state not in (OrderState.SUBMITTED, OrderState.PARTIAL):
            logger.warning(f"Fill for order {order_id} in invalid state: {order.state}")
            return False

        # Update fill info
        order.filled_quantity += fill_quantity
        order.remaining_quantity = order.quantity - order.filled_quantity

        # Calculate weighted average fill price
        if order.avg_fill_price is None:
            order.avg_fill_price = fill_price
        else:
            total_value = order.avg_fill_price * (order.filled_quantity - fill_quantity) + fill_price * fill_quantity
            order.avg_fill_price = total_value / order.filled_quantity

        order.updated_at = time.time() if timestamp is None else timestamp

        # Check if fully filled
        if order.filled_quantity >= order.quantity:
            order.state = OrderState.FILLED
            order.filled_at = time.time()
            order.avg_fill_price = fill_price
            self._add_event(order, OrderEvent.FILLED, {"fill_price": str(fill_price), "fill_quantity": str(fill_quantity)})
            self._move_to_history(order)
            if self.on_order_filled:
                asyncio.create_task(self.on_order_filled(order))
        else:
            order.state = OrderState.PARTIALLY_FILLED
            self._add_event(order, OrderEvent.PARTIALLY_FILLED, {"fill_price": str(fill_price), "fill_quantity": str(fill_quantity)})
            if self.on_order_partially_filled:
                asyncio.create_task(self.on_order_partially_filled(order))

        self.updated_at = time.time()
        return True

    # ============================================================
    # Event Handling
    # ============================================================

    def _add_event(self, order: 'Order', event: OrderEvent, details: Dict = None):
        """Add event to order's event log."""
        event_record = OrderEventRecord(
            event_id=str(uuid.uuid4())[:8],
            order_id=order.order_id,
            event=event,
            timestamp=time.time(),
            details=details or {},
        )
        order.events.append(event_record.to_dict())
        self.event_log.append(event_record)

    def _move_to_history(self, order: 'Order'):
        """Move order from active to history."""
        if order.order_id in self.active_orders:
            del self.active_orders[order.order_id]
        if order.client_order_id in self.orders_by_client_id:
            del self.orders_by_client_id[order.client_order_id]
        self.order_history.append(order)

    # ============================================================
    # Monitoring
    # ============================================================

    async def start_monitoring(self, interval: float = 5.0):
        """Start order monitoring loop."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval))

    async def stop_monitoring(self):
        """Stop order monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self, interval: float):
        """Monitor active orders for fills, timeouts, etc."""
        while self._running:
            try:
                for order in list(self.active_orders.values()):
                    # Check for timeout
                    if order.submitted_at and (time.time() - order.submitted_at) > 300:  # 5 min timeout
                        if order.state == OrderState.SUBMITTED:
                            await self.cancel_order(order.order_id, "Timeout")

                    # Check for expiry
                    if order.state == OrderState.CREATED and (time.time() - order.created_at) > 3600:  # 1 hour
                        order.state = OrderState.EXPIRED
                        self._add_event(order, OrderEvent.EXPIRED, {"reason": "Order expired"})
                        self._move_to_history(order)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(interval)

    # ============================================================
    # State Access
    # ============================================================

    def get_order(self, order_id: str) -> Optional['Order']:
        return self.orders.get(order_id)

    def get_active_orders(self) -> List['Order']:
        return list(self.active_orders.values())

    def get_orders_by_strategy(self, strategy: str) -> List['Order']:
        return [o for o in self.active_orders.values() if o.strategy == strategy]

    def get_order_stats(self) -> Dict:
        """Get order statistics."""
        total = len(self.orders)
        active = len(self.active_orders)
        filled = sum(1 for o in self.orders.values() if o.state == OrderState.FILLED)
        cancelled = sum(1 for o in self.orders.values() if o.state == OrderState.CANCELLED)
        rejected = sum(1 for o in self.orders.values() if o.state == OrderState.REJECTED)

        return {
            "total": total,
            "active": active,
            "filled": filled,
            "cancelled": cancelled,
            "rejected": rejected,
            "fill_rate": filled / total if total > 0 else 0,
        }


__all__ = [
    "OrderManager",
    "Order",
    "OrderState",
    "OrderEvent",
    "OrderValidator",
    "RetryPolicy",
    "OrderValidator",
    "RetryPolicy",
    "OrderEvent",
    "OrderEventRecord",
]