"""
Paper Engine Package
====================
Safe paper-trading engine for DEX strategies with full risk controls.
"""

from .config import (
    PaperConfig,
    FeeSchedule,
    SlippageModel,
    DEFAULT_CONFIG,
    load_config,
)

from .boundaries import (
    ExecutionBoundary,
    get_boundary,
    set_paper_mode,
    paper_only,
    assert_paper_mode,
    FORBIDDEN_PATTERNS,
    FORBIDDEN_IMPORTS,
)

from .market_data import (
    MarketDataValidator,
    PriceQuote,
    ValidationResult,
    ValidationStatus,
    create_quote_from_coingecko,
    create_quote_from_cex,
    create_quote_from_geckoterminal,
)

from .net_return import (
    NetReturnCalculator,
    NetReturnResult,
    CostBreakdown,
    RejectionReason,
    TransferPath,
)

from .triangular import (
    TriangularArbValidator,
    ArbSignal as TriangularArbSignal,
)

from .cross_exchange import (
    CrossExchangeArbValidator,
    ArbSignal as CrossExchangeArbSignal,
)

from .meme_sniper import (
    MemeSniperValidator,
    MemeSignal,
)

from .execution import (
    PaperExecutionEngine,
    PaperPosition,
    PaperTrade,
    PaperFill,
    FillStatus,
    PositionSide,
)

from .records import (
    PaperTradeRecorder,
    PaperTradeRecord,
    SignalRecord,
    DailySnapshot,
    AuditEvent,
    load_trades_from_jsonl,
    load_signals_from_jsonl,
    load_snapshots_from_jsonl,
    _serialize,
)

from .metrics import (
    PerformanceMetrics,
    MetricsResult,
    generate_performance_report,
)

__all__ = [
    # Config
    "PaperConfig",
    "FeeSchedule",
    "SlippageModel",
    "DEFAULT_CONFIG",
    "load_config",
    # Boundaries
    "ExecutionBoundary",
    "get_boundary",
    "set_paper_mode",
    "paper_only",
    "assert_paper_mode",
    "FORBIDDEN_PATTERNS",
    "FORBIDDEN_IMPORTS",
    # Market Data
    "MarketDataValidator",
    "PriceQuote",
    "ValidationResult",
    "ValidationStatus",
    "create_quote_from_coingecko",
    "create_quote_from_cex",
    "create_quote_from_geckoterminal",
    # Net Return
    "NetReturnCalculator",
    "NetReturnResult",
    "CostBreakdown",
    "RejectionReason",
    "TransferPath",
    # Triangular
    "TriangularArbValidator",
    "TriangularArbSignal",
    # Cross Exchange
    "CrossExchangeArbValidator",
    "CrossExchangeArbSignal",
    # Meme Sniper
    "MemeSniperValidator",
    "MemeSignal",
    # Execution
    "PaperExecutionEngine",
    "PaperPosition",
    "PaperTrade",
    "PaperFill",
    "FillStatus",
    "PositionSide",
    # Records
    "PaperTradeRecorder",
    "PaperTradeRecord",
    "SignalRecord",
    "DailySnapshot",
    "AuditEvent",
    "load_trades_from_jsonl",
    "load_signals_from_jsonl",
    "load_snapshots_from_jsonl",
    # Metrics
    "PerformanceMetrics",
    "MetricsResult",
    "generate_performance_report",
]

__version__ = "0.1.0"