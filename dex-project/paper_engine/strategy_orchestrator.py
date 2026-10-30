"""
Strategy Orchestrator
=====================
Main loop coordinating 3 strategies (triangular, cross-exchange, meme sniper),
signal prioritization, cooldown management, and strategy lifecycle.
"""

from __future__ import annotations
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
from dataclasses import field
from datetime import datetime
import uuid

from paper_engine.config import PaperConfig
from paper_engine.market_data import PriceQuote, MarketDataValidator
from paper_engine.net_return import NetReturnCalculator, NetReturnResult, TransferPath
from paper_engine.triangular import TriangularArbValidator
from paper_engine.cross_exchange import CrossExchangeArbValidator
from paper_engine.meme_sniper import MemeSniperValidator
from paper_engine.execution import PaperExecutionEngine, NetReturnResult
from paper_engine.live_execution_adapter import LiveExecutionAdapter, LiveOrder, OrderStatus
from paper_engine.wallet_manager import WalletManager
from paper_engine.records import PaperTradeRecorder
from paper_engine.metrics import PerformanceMetrics
from paper_engine.boundaries import get_boundary, assert_paper_mode


logger = logging.getLogger(__name__)


class StrategyState(Enum):
    """Strategy operational states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPING = "stopping"


class SignalPriority(Enum):
    """Signal priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class StrategySignal:
    """Unified signal from any strategy."""
    signal_id: str
    strategy: str  # "triangular", "cross_exchange", "meme_sniper"
    symbol: str
    side: str  # "buy" or "sell"
    timestamp: float
    gross_return_pct: float
    net_return_pct: float
    cost_breakdown: Dict
    rejection_reason: Optional[str]
    rejection_message: str
    trade_size_usd: float
    quotes: Dict
    validation_details: Dict
    priority: SignalPriority = SignalPriority.NORMAL
    metadata: Dict = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """Per-strategy configuration."""
    enabled: bool = True
    min_net_edge_pct: float = 0.2
    max_trade_size_usd: float = 100.0
    cooldown_seconds: float = 60.0
    max_concurrent_signals: int = 3
    priority: SignalPriority = SignalPriority.NORMAL
    custom_params: Dict = field(default_factory=dict)


@dataclass
class StrategyStateInfo:
    """Runtime state for a strategy."""
    state: StrategyState = StrategyState.STOPPED
    last_signal_time: float = 0
    signal_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    cooldown_until: float = 0
    active_signals: int = 0


class StrategyOrchestrator:
    """
    Main orchestrator coordinating all strategies.
    Handles signal prioritization, cooldowns, deduplication, and execution.
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
        self.recorder = recorder or PaperTradeRecorder()
        self.boundary = get_boundary()

        # Strategy validators
        self.triangular_validator = TriangularArbValidator(config)
        self.cross_exchange_validator = CrossExchangeArbValidator(config)
        self.meme_sniper_validator = MemeSniperValidator(config)

        # Market data validator
        self.market_validator = MarketDataValidator(
            max_staleness_seconds=config.max_staleness_seconds,
            min_liquidity_usd=config.min_liquidity_usd,
        )

        # Strategy configurations
        self.strategy_configs: Dict[str, StrategyConfig] = {
            "triangular": StrategyConfig(
                enabled=True,
                min_net_edge_pct=config.min_net_edge_pct,
                max_trade_size_usd=100.0,
                cooldown_seconds=60.0,
                max_concurrent_signals=3,
                priority=SignalPriority.NORMAL,
            ),
            "cross_exchange": StrategyConfig(
                enabled=True,
                min_net_edge_pct=config.min_net_edge_pct,
                max_trade_size_usd=100.0,
                cooldown_seconds=30.0,
                max_concurrent_signals=2,
                priority=SignalPriority.HIGH,
            ),
            "meme_sniper": StrategyConfig(
                enabled=True,
                min_net_edge_pct=config.min_net_edge_pct,
                max_trade_size_usd=50.0,
                cooldown_seconds=300.0,
                max_concurrent_signals=5,
                priority=SignalPriority.NORMAL,
            ),
        }

        # Strategy states
        self.strategy_states: Dict[str, StrategyStateInfo] = {
            name: StrategyStateInfo() for name in self.strategy_configs
        }

        # Signal queue (priority queue)
        self._signal_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._signal_history: List[StrategySignal] = []
        self._signal_cache: Dict[str, float] = {}  # signal_hash -> timestamp

        # Control
        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_signal: Optional[Callable[[StrategySignal], Awaitable[None]]] = None
        self.on_execution: Optional[Callable[[LiveOrder], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[str, Exception], Awaitable[None]]] = None

    # ============================================================
    # Lifecycle
    # ============================================================

    async def start(self):
        """Start the orchestrator."""
        self.boundary.assert_paper_mode("start orchestrator")
        self._running = True
        self._main_task = asyncio.create_task(self._main_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Strategy orchestrator started")

    async def stop(self):
        """Stop the orchestrator gracefully."""
        self._running = False
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Strategy orchestrator stopped")

    async def pause(self):
        """Pause signal processing."""
        for state in self.strategy_states.values():
            if state.state == StrategyState.RUNNING:
                state.state = StrategyState.PAUSED

    async def resume(self):
        """Resume signal processing."""
        for state in self.strategy_states.values():
            if state.state == StrategyState.PAUSED:
                state.state = StrategyState.RUNNING

    # ============================================================
    # Main Loop
    # ============================================================

    async def _main_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                # Check cooldowns and update strategy states
                self._update_strategy_states()

                # Scan for signals from all strategies
                signals = await self._scan_all_strategies()

                # Queue valid signals
                for signal in signals:
                    await self._queue_signal(signal)

                # Process queued signals
                await self._process_signal_queue()

                # Wait before next iteration
                await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await self._handle_error("main_loop", e)
                await asyncio.sleep(5.0)

    async def _monitor_loop(self):
        """Monitor loop for health checks and order monitoring."""
        while self._running:
            try:
                # Monitor active orders
                await self.execution_adapter.monitor_orders()

                # Check kill switches
                if self.execution_adapter.kill_switch_triggered:
                    logger.warning("Kill switch triggered, pausing all strategies")
                    await self.pause()

                # Log portfolio status periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    state = self.execution_adapter.get_state()
                    logger.info(
                        f"Portfolio: ${state['portfolio_value_usd']:.2f} | "
                        f"Open: {state['open_positions']} | "
                        f"Daily P&L: ${state['daily_pnl_usd']:.2f} | "
                        f"Drawdown: {state['max_drawdown_pct']:.2f}%"
                    )

                await asyncio.sleep(10.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5.0)

    # ============================================================
    # Strategy Scanning
    # ============================================================

    async def _scan_all_strategies(self) -> List[StrategySignal]:
        """Scan all enabled strategies for signals."""
        signals = []

        # Triangular arbitrage
        if self.strategy_configs["triangular"].enabled:
            signals.extend(await self._scan_triangular())

        # Cross-exchange arbitrage
        if self.strategy_configs["cross_exchange"].enabled:
            signals.extend(await self._scan_cross_exchange())

        # Meme sniper
        if self.strategy_configs["meme_sniper"].enabled:
            signals.extend(await self._scan_meme_sniper())

        return signals

    async def _scan_triangular(self) -> List[StrategySignal]:
        """Scan for triangular arbitrage opportunities."""
        signals = []

        # This would fetch live market data in production
        # For now, we simulate with the validators
        # In production, you'd fetch live quotes from DEXs

        # Example: scan common triangular paths
        # ETH -> SOL -> USDC -> ETH
        # BTC -> ETH -> USDC -> BTC
        # etc.

        return []

    async def _scan_cross_exchange(self) -> List[StrategySignal]:
        """Scan for cross-exchange arbitrage."""
        signals = []

        # In production: fetch quotes from multiple exchanges
        # Compare prices, validate, calculate net return

        return []

    async def _scan_meme_sniper(self) -> List[StrategySignal]:
        """Scan for meme coin opportunities."""
        signals = []

        # In production: fetch new Pump.fun pools
        # Analyze momentum, liquidity, risk

        return []

    def _create_signal_from_validator(
        self,
        validator_name: str,
        validator_result: Any,
        quotes: Dict,
        trade_size_usd: float,
    ) -> Optional[StrategySignal]:
        """Create a StrategySignal from validator result."""
        # Check if already processed (deduplication)
        signal_hash = f"{validator_name}_{trade_size_usd}_{time.time() // 60}"
        if signal_hash in self._signal_cache:
            return None
        self._signal_cache[signal_hash] = time.time()

        # Clean old cache entries
        cutoff = time.time() - 300  # 5 minutes
        self._signal_cache = {
            k: v for k, v in self._signal_cache.items() if v > cutoff
        }

        # Determine priority
        priority = self.strategy_configs[validator_name].priority
        if net_return_pct > 1.0:
            priority = SignalPriority.HIGH
        elif net_return_pct > 0.5:
            priority = SignalPriority.NORMAL
        else:
            priority = SignalPriority.LOW

        return StrategySignal(
            signal_id=str(uuid.uuid4())[:8],
            strategy=validator_name,
            symbol="",  # Filled by caller
            side="buy",  # Filled by caller
            timestamp=time.time(),
            gross_return_pct=0,
            net_return_pct=0,
            cost_breakdown={},
            rejection_reason=None,
            rejection_message="",
            trade_size_usd=0,
            quotes={},
            validation_details={},
            priority=priority,
        )

    def _is_duplicate_signal(self, signal: StrategySignal) -> bool:
        """Check if signal is a duplicate."""
        key = f"{signal.strategy}_{signal.symbol}_{signal.side}"
        return key in self._signal_cache

    # ============================================================
    # Signal Queue Processing
    # ============================================================

    async def _queue_signal(self, signal: StrategySignal):
        """Queue a signal for processing."""
        # Check strategy cooldown
        state = self.strategy_states[signal.strategy]
        if state.cooldown_until > time.time():
            return

        # Check max concurrent signals
        if state.active_signals >= self.strategy_configs[signal.strategy].max_concurrent_signals:
            return

        # Check minimum net edge
        config = self.strategy_configs[signal.strategy]
        if signal.net_return_pct < config.min_net_edge_pct:
            return

        # Queue with priority (negative for max-heap)
        await self._signal_queue.put((-signal.priority.value, time.time(), signal))

    async def _process_signal_queue(self):
        """Process queued signals in priority order."""
        processed = 0
        max_per_cycle = 3

        while not self._signal_queue.empty() and processed < max_per_cycle:
            try:
                _, _, signal = self._signal_queue.get_nowait()

                # Re-validate before execution
                if not await self._validate_signal(signal):
                    continue

                # Check strategy state
                state = self.strategy_states[signal.strategy]
                if state.state != StrategyState.RUNNING:
                    continue

                # Check cooldown
                if state.cooldown_until > time.time():
                    # Re-queue
                    await self._signal_queue.put((
                        -signal.priority.value, time.time(), signal
                    ))
                    continue

                # Execute signal
                await self._execute_signal(signal)
                processed += 1

            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error processing signal: {e}")

    async def _validate_signal(self, signal: StrategySignal) -> bool:
        """Final validation before execution."""
        # Check if already executed similar signal recently
        key = f"{signal.strategy}_{signal.symbol}_{signal.side}"
        if key in self._signal_cache:
            return False

        # Check strategy state
        state = self.strategy_states[signal.strategy]
        if state.state != StrategyState.RUNNING:
            return False

        # Check cooldown
        if state.cooldown_until > time.time():
            return False

        # Check max concurrent
        if state.active_signals >= self.strategy_configs[signal.strategy].max_concurrent_signals:
            return False

        return True

    async def _execute_signal(self, signal: StrategySignal):
        """Execute a validated signal."""
        state = self.strategy_states[signal.strategy]
        state.active_signals += 1
        state.last_signal_time = time.time()
        state.signal_count += 1
        state.cooldown_until = time.time() + self.strategy_configs[signal.strategy].cooldown_seconds

        try:
            # Execute via live adapter
            # This is a placeholder - actual execution would use the live adapter
            logger.info(f"Executing signal: {signal.signal_id} - {signal.strategy} {signal.side} {signal.symbol}")

            # Record signal
            self._signal_history.append(signal)

            # Callback
            if self.on_signal:
                await self.on_signal(signal)

        except Exception as e:
            await self._handle_error(f"execute_signal_{signal.signal_id}", e)
        finally:
            state.active_signals -= 1

    def _update_strategy_states(self):
        """Update strategy states based on cooldowns and errors."""
        now = time.time()
        for name, state in self.strategy_states.items():
            # Check if cooldown expired
            if state.state == StrategyState.PAUSED and state.cooldown_until <= time.time():
                state.state = StrategyState.RUNNING

            # Check error count
            if state.error_count > 5:
                state.state = StrategyState.ERROR

    # ============================================================
    # Error Handling
    # ============================================================

    async def _handle_error(self, context: str, error: Exception):
        logger.error(f"Error in {context}: {error}")

        # Update error counts
        for state in self.strategy_states.values():
            state.error_count += 1
            state.last_error = str(error)

        if self.on_error:
            await self.on_error(context, error)

    # ============================================================
    # Configuration
    # ============================================================

    def update_strategy_config(self, strategy: str, config: StrategyConfig):
        """Update strategy configuration."""
        if strategy in self.strategy_configs:
            self.strategy_configs[strategy] = config

    def enable_strategy(self, strategy: str):
        if strategy in self.strategy_configs:
            self.strategy_configs[strategy].enabled = True
            self.strategy_states[strategy].state = StrategyState.RUNNING

    def disable_strategy(self, strategy: str):
        if strategy in self.strategy_configs:
            self.strategy_configs[strategy].enabled = False
            self.strategy_states[strategy].state = StrategyState.STOPPED

    def set_cooldown(self, strategy: str, seconds: float):
        if strategy in self.strategy_configs:
            self.strategy_configs[strategy].cooldown_seconds = seconds

    # ============================================================
    # Status & Metrics
    # ============================================================

    def get_status(self) -> Dict:
        """Get orchestrator status."""
        return {
            "running": self._running,
            "strategies": {
                name: {
                    "enabled": self.strategy_configs[name].enabled,
                    "state": state.state.value,
                    "signal_count": state.signal_count,
                    "error_count": state.error_count,
                    "active_signals": state.active_signals,
                    "cooldown_remaining": max(0, state.cooldown_until - time.time()),
                    "last_error": state.last_error,
                }
                for name, state in self.strategy_states.items()
            },
            "queue_size": self._signal_queue.qsize(),
            "total_signals": len(self._signal_history),
        }

    def get_metrics(self) -> Dict:
        """Get performance metrics."""
        if not self.recorder:
            return {}

        metrics_calc = PerformanceMetrics()
        trades = [t.to_dict() for t in self.recorder.closed_trades]
        return metrics_calc.calculate(trades)


__all__ = [
    "StrategyOrchestrator",
    "StrategyConfig",
    "StrategyState",
    "StrategyStateInfo",
    "StrategySignal",
    "SignalPriority",
    "SignalPriority",
]