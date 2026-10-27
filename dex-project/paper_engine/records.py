"""
Paper Trade Records & Persistence
==================================
Persistent audit logs, trade records, and performance snapshots.
"""

from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Dict, List, Optional, Any
import json
import os
import time
import uuid
from pathlib import Path
from datetime import datetime, date
import threading
from enum import Enum


def _serialize(value):
    """Convert supported Python objects into JSON-safe values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(
        f"Unsupported JSON serialization type: {type(value).__name__}"
    )


@dataclass
class AuditEvent:
    """Single audit log entry."""
    event_id: str
    event_type: str                    # signal, fill, trade, validation, risk, error
    strategy: str                      # triangular, cross_exchange, meme_sniper
    timestamp: float
    data: Dict[str, Any]
    session_id: str

    def to_jsonl(self) -> str:
        return json.dumps(_serialize(asdict(self)), separators=(',', ':'), allow_nan=False)


@dataclass
class PaperTradeRecord:
    """Complete paper trade record for persistence."""
    trade_id: str
    strategy: str
    symbol: str
    side: str                          # long/short
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
    entry_fill: Dict
    exit_fill: Dict
    validation_details: Dict
    session_id: str

    def to_jsonl(self) -> str:
        return json.dumps(_serialize(asdict(self)), separators=(',', ':'), allow_nan=False)


@dataclass
class SignalRecord:
    """Record of every signal (accepted or rejected)."""
    signal_id: str
    strategy: str
    symbol: str
    accepted: bool
    gross_return_pct: float
    net_return_pct: float
    rejection_reason: Optional[str]
    rejection_message: str
    trade_size_usd: float
    quotes: Dict
    validation_details: Dict
    timestamp: float
    session_id: str

    def to_jsonl(self) -> str:
        return json.dumps(_serialize(asdict(self)), separators=(',', ':'), allow_nan=False)


@dataclass
class DailySnapshot:
    """End-of-day portfolio snapshot."""
    date: str                          # YYYY-MM-DD
    session_id: str
    starting_capital_usd: float
    ending_equity_usd: float
    cash_usd: float
    daily_pnl_usd: float
    daily_pnl_pct: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    max_drawdown_pct: float
    peak_equity_usd: float
    open_positions: int
    timestamp: float

    def to_jsonl(self) -> str:
        return json.dumps(_serialize(asdict(self)), separators=(',', ':'), allow_nan=False)


class PaperTradeRecorder:
    """
    Persistent recorder for all paper trading activity.
    Writes JSONL files for audit trail, trades, signals, and daily snapshots.
    """

    def __init__(
        self,
        log_dir: str = "paper_trades",
        session_id: Optional[str] = None,
        rotate_daily: bool = True,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.rotate_daily = rotate_daily
        self._lock = threading.Lock()

        # File handles (lazy opened)
        self._audit_file: Optional[Any] = None
        self._trades_file: Optional[Any] = None
        self._signals_file: Optional[Any] = None
        self._snapshots_file: Optional[Any] = None
        self._current_date: Optional[str] = None

    def _get_date(self) -> str:
        return datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d")

    def _rotate_if_needed(self):
        """Rotate files if date changed."""
        if not self.rotate_daily:
            return

        current_date = self._get_date()
        if current_date != self._current_date:
            self._close_files()
            self._current_date = current_date
            self._open_files()

    def _open_files(self):
        """Open file handles for current date."""
        date_str = self._current_date or self._get_date()

        self._audit_file = open(
            self.log_dir / f"audit_{date_str}_{self.session_id}.jsonl", "a"
        )
        self._trades_file = open(
            self.log_dir / f"trades_{date_str}_{self.session_id}.jsonl", "a"
        )
        self._signals_file = open(
            self.log_dir / f"signals_{date_str}_{self.session_id}.jsonl", "a"
        )
        self._snapshots_file = open(
            self.log_dir / f"snapshots_{date_str}_{self.session_id}.jsonl", "a"
        )

    def _close_files(self):
        """Close all file handles."""
        for f in [self._audit_file, self._trades_file, self._signals_file, self._snapshots_file]:
            if f:
                f.close()
        self._audit_file = self._trades_file = self._signals_file = self._snapshots_file = None

    def _write(self, file_handle: Any, line: str):
        """Thread-safe write to file."""
        with self._lock:
            self._rotate_if_needed()
            if file_handle:
                file_handle.write(line + "\n")
                file_handle.flush()

    # ============================================================
    # Recording Methods
    # ============================================================
    def record_audit(self, event: AuditEvent):
        """Record an audit event."""
        self._rotate_if_needed()
        self._write(self._audit_file, event.to_jsonl())

    def record_trade(self, trade: PaperTradeRecord):
        """Record a completed trade."""
        self._rotate_if_needed()
        self._write(self._trades_file, trade.to_jsonl())

    def record_signal(self, signal: SignalRecord):
        """Record a signal (accepted or rejected)."""
        self._rotate_if_needed()
        self._write(self._signals_file, signal.to_jsonl())

    def record_snapshot(self, snapshot: DailySnapshot):
        """Record daily snapshot."""
        self._rotate_if_needed()
        self._write(self._snapshots_file, snapshot.to_jsonl())

    # ============================================================
    # Convenience Methods
    # ============================================================
    def log_signal(
        self,
        strategy: str,
        symbol: str,
        accepted: bool,
        gross_return_pct: float,
        net_return_pct: float,
        rejection_reason: Optional[str],
        rejection_message: str,
        trade_size_usd: float,
        quotes: Dict,
        validation_details: Dict,
    ):
        """Log a signal decision."""
        signal = SignalRecord(
            signal_id=str(uuid.uuid4())[:12],
            strategy=strategy,
            symbol=symbol,
            accepted=accepted,
            gross_return_pct=gross_return_pct,
            net_return_pct=net_return_pct,
            rejection_reason=rejection_reason,
            rejection_message=rejection_message,
            trade_size_usd=trade_size_usd,
            quotes={k: v.__dict__ if hasattr(v, '__dict__') else v for k, v in quotes.items()},
            validation_details=validation_details,
            timestamp=time.time(),
            session_id=self.session_id,
        )
        self.record_signal(signal)
        self.log_audit("signal", strategy, {
            "signal_id": signal.signal_id,
            "symbol": symbol,
            "accepted": accepted,
            "net_return_pct": net_return_pct,
        })

    def log_fill(self, strategy: str, fill_data: Dict):
        """Log a simulated fill."""
        self.log_audit("fill", strategy, fill_data)

    def log_trade(
        self,
        strategy: str,
        symbol: str,
        side: str,
        entry_time: float,
        exit_time: float,
        entry_price: float,
        exit_price: float,
        size_usd: float,
        fees_usd: float,
        slippage_usd: float,
        gas_usd: float,
        gross_pnl_usd: float,
        net_pnl_usd: float,
        hold_seconds: float,
        return_pct: float,
        entry_fill: Dict,
        exit_fill: Dict,
        validation_details: Dict,
    ):
        """Log a completed trade."""
        trade = PaperTradeRecord(
            trade_id=str(uuid.uuid4())[:12],
            strategy=strategy,
            symbol=symbol,
            side=side,
            entry_time=entry_time,
            exit_time=exit_time,
            entry_price=entry_price,
            exit_price=exit_price,
            size_usd=size_usd,
            fees_usd=fees_usd,
            slippage_usd=slippage_usd,
            gas_usd=gas_usd,
            gross_pnl_usd=gross_pnl_usd,
            net_pnl_usd=net_pnl_usd,
            hold_seconds=hold_seconds,
            return_pct=return_pct,
            entry_fill=entry_fill,
            exit_fill=exit_fill,
            validation_details=validation_details,
            session_id=self.session_id,
        )
        self.record_trade(trade)
        self.log_audit("trade", strategy, {
            "trade_id": trade.trade_id,
            "symbol": symbol,
            "net_pnl_usd": net_pnl_usd,
            "return_pct": return_pct,
        })

    def log_validation(self, strategy: str, signal_type: str, details: Dict):
        """Log a validation event."""
        self.log_audit("validation", strategy, {
            "signal_type": signal_type,
            **details
        })

    def log_risk_event(self, strategy: str, event_type: str, details: Dict):
        """Log a risk management event (kill switch, limit hit, etc.)."""
        self.log_audit("risk", strategy, {
            "event_type": event_type,
            **details
        })

    def log_error(self, strategy: str, error: str, context: Dict):
        """Log an error."""
        self.log_audit("error", strategy, {
            "error": error,
            **context
        })

    def log_audit(self, event_type: str, strategy: str, data: Dict):
        """Generic audit log entry."""
        event = AuditEvent(
            event_id=str(uuid.uuid4())[:12],
            event_type=event_type,
            strategy=strategy,
            timestamp=time.time(),
            data=data,
            session_id=self.session_id,
        )
        self.record_audit(event)

    def log_daily_snapshot(self, engine_state: Dict):
        """Log end-of-day snapshot from engine state."""
        snapshot = DailySnapshot(
            date=self._get_date(),
            session_id=self.session_id,
            starting_capital_usd=engine_state.get("starting_capital_usd", 0),
            ending_equity_usd=engine_state.get("portfolio_value_usd", 0),
            cash_usd=engine_state.get("cash_usd", 0),
            daily_pnl_usd=engine_state.get("daily_pnl_usd", 0),
            daily_pnl_pct=engine_state.get("daily_pnl_pct", 0),
            total_return_pct=engine_state.get("total_return_pct", 0),
            total_trades=engine_state.get("closed_trades", 0),
            winning_trades=engine_state.get("winning_trades", 0),
            losing_trades=engine_state.get("losing_trades", 0),
            max_drawdown_pct=engine_state.get("max_drawdown_pct", 0),
            peak_equity_usd=engine_state.get("peak_equity", 0),
            open_positions=engine_state.get("open_positions", 0),
            timestamp=time.time(),
        )
        self.record_snapshot(snapshot)

    def close(self):
        """Close all file handles."""
        self._close_files()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def load_trades_from_jsonl(filepath: str) -> List[PaperTradeRecord]:
    """Load trades from JSONL file."""
    trades = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                trades.append(PaperTradeRecord(**data))
    return trades


def load_signals_from_jsonl(filepath: str) -> List[SignalRecord]:
    """Load signals from JSONL file."""
    signals = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                signals.append(SignalRecord(**data))
    return signals


def load_snapshots_from_jsonl(filepath: str) -> List[DailySnapshot]:
    """Load daily snapshots from JSONL file."""
    snapshots = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                snapshots.append(DailySnapshot(**data))
    return snapshots