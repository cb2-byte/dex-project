"""
Performance Metrics
====================
Calculates trading performance metrics from paper trade records.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import math
import statistics


@dataclass
class MetricsResult:
    """Complete performance metrics result."""
    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    # P&L
    net_pnl_usd: float = 0.0
    gross_pnl_usd: float = 0.0
    total_fees_usd: float = 0.0
    total_slippage_usd: float = 0.0
    total_gas_usd: float = 0.0

    # Returns
    total_return_pct: float = 0.0
    avg_return_pct: float = 0.0
    median_return_pct: float = 0.0
    std_return_pct: float = 0.0

    # Win rate & profit factor
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0

    # Risk
    max_drawdown_pct: float = 0.0
    max_drawdown_usd: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Trade stats
    avg_hold_seconds: float = 0.0
    median_hold_seconds: float = 0.0
    best_trade_pct: float = 0.0
    worst_trade_pct: float = 0.0
    best_trade_usd: float = 0.0
    worst_trade_usd: float = 0.0

    # Streaks
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # By strategy
    by_strategy: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items()}


class PerformanceMetrics:
    """
    Calculates comprehensive performance metrics from paper trades.
    """

    def __init__(self, risk_free_rate_annual: float = 0.02):
        self.risk_free_rate_annual = risk_free_rate_annual
        self.risk_free_rate_daily = risk_free_rate_annual / 252

    def calculate(self, trades: List[Dict]) -> MetricsResult:
        """
        Calculate all metrics from a list of trade dictionaries.
        Each trade dict should have: net_pnl_usd, gross_pnl_usd, fees_usd, slippage_usd, gas_usd,
        return_pct, hold_seconds, strategy, side, entry_time, exit_time
        """
        if not trades:
            return MetricsResult()

        result = MetricsResult()

        # Basic counts
        result.total_trades = len(trades)
        result.winning_trades = sum(1 for t in trades if t.get('net_pnl_usd', 0) > 0)
        result.losing_trades = sum(1 for t in trades if t.get('net_pnl_usd', 0) < 0)
        result.breakeven_trades = result.total_trades - result.winning_trades - result.losing_trades

        # P&L totals
        result.net_pnl_usd = sum(t.get('net_pnl_usd', 0) for t in trades)
        result.gross_pnl_usd = sum(t.get('gross_pnl_usd', 0) for t in trades)
        result.total_fees_usd = sum(t.get('fees_usd', 0) for t in trades)
        result.total_slippage_usd = sum(t.get('slippage_usd', 0) for t in trades)
        result.total_gas_usd = sum(t.get('gas_usd', 0) for t in trades)

        # Returns
        returns = [t.get('return_pct', 0) for t in trades]
        result.avg_return_pct = statistics.mean(returns) if returns else 0
        result.median_return_pct = statistics.median(returns) if returns else 0
        result.std_return_pct = statistics.stdev(returns) if len(returns) > 1 else 0

        # Win rate
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0

        # Profit factor
        gross_wins = sum(t.get('net_pnl_usd', 0) for t in trades if t.get('net_pnl_usd', 0) > 0)
        gross_losses = abs(sum(t.get('net_pnl_usd', 0) for t in trades if t.get('net_pnl_usd', 0) < 0))
        result.profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')

        # Avg win/loss
        wins = [t for t in trades if t.get('net_pnl_usd', 0) > 0]
        losses = [t for t in trades if t.get('net_pnl_usd', 0) < 0]
        result.avg_win_usd = statistics.mean([t['net_pnl_usd'] for t in wins]) if wins else 0
        result.avg_loss_usd = statistics.mean([t['net_pnl_usd'] for t in losses]) if losses else 0
        result.avg_win_pct = statistics.mean([t['return_pct'] for t in wins]) if wins else 0
        result.avg_loss_pct = statistics.mean([t['return_pct'] for t in losses]) if losses else 0

        # Best/worst
        result.best_trade_pct = max(returns) if returns else 0
        result.worst_trade_pct = min(returns) if returns else 0
        result.best_trade_usd = max(t.get('net_pnl_usd', 0) for t in trades) if trades else 0
        result.worst_trade_usd = min(t.get('net_pnl_usd', 0) for t in trades) if trades else 0

        # Hold times
        holds = [t.get('hold_seconds', 0) for t in trades]
        result.avg_hold_seconds = statistics.mean(holds) if holds else 0
        result.median_hold_seconds = statistics.median(holds) if holds else 0

        # Streaks
        result.max_consecutive_wins = self._max_consecutive(trades, lambda t: t.get('net_pnl_usd', 0) > 0)
        result.max_consecutive_losses = self._max_consecutive(trades, lambda t: t.get('net_pnl_usd', 0) < 0)

        # By strategy
        result.by_strategy = self._calculate_by_strategy(trades)

        return result

    def calculate_from_equity_curve(
        self,
        equity_curve: List[float],
        timestamps: List[float],
    ) -> Dict[str, float]:
        """
        Calculate drawdown and Sharpe from equity curve.
        equity_curve: portfolio values over time
        timestamps: corresponding unix timestamps
        """
        if len(equity_curve) < 2:
            return {
                "max_drawdown_pct": 0.0,
                "max_drawdown_usd": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
            }

        # Max drawdown
        peak = equity_curve[0]
        max_dd_pct = 0.0
        max_dd_usd = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value
            dd_usd = peak - value
            dd_pct = dd_usd / peak if peak > 0 else 0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_usd = dd_usd

        # Returns for Sharpe
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] > 0:
                ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                returns.append(ret)

        sharpe = 0.0
        sortino = 0.0
        if returns:
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 0
            downside_returns = [r for r in returns if r < 0]
            downside_std = statistics.stdev(downside_returns) if len(downside_returns) > 1 else 0

            # Annualize (assuming daily returns)
            periods_per_year = 252
            if std_return > 0:
                sharpe = (avg_return - self.risk_free_rate_daily) / std_return * math.sqrt(periods_per_year)
            if downside_std > 0:
                sortino = (avg_return - self.risk_free_rate_daily) / downside_std * math.sqrt(periods_per_year)

        # Calmar ratio
        calmar = 0.0
        if max_dd_pct > 0:
            annual_return = statistics.mean(returns) * periods_per_year if returns else 0
            calmar = annual_return / max_dd_pct

        return {
            "max_drawdown_pct": max_dd_pct * 100,
            "max_drawdown_usd": max_dd_usd,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
        }

    def _max_consecutive(self, trades: List[Dict], predicate) -> int:
        """Calculate maximum consecutive trades matching predicate."""
        max_streak = 0
        current = 0
        for t in trades:
            if predicate(t):
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    def _calculate_by_strategy(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Calculate metrics broken down by strategy."""
        by_strategy = {}
        strategies = set(t.get('strategy', 'unknown') for t in trades)

        for strat in strategies:
            strat_trades = [t for t in trades if t.get('strategy') == strat]
            if not strat_trades:
                continue

            wins = [t for t in strat_trades if t.get('net_pnl_usd', 0) > 0]
            losses = [t for t in strat_trades if t.get('net_pnl_usd', 0) < 0]

            by_strategy[strat] = {
                "total_trades": len(strat_trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate": len(wins) / len(strat_trades) if strat_trades else 0,
                "net_pnl_usd": sum(t.get('net_pnl_usd', 0) for t in strat_trades),
                "total_return_pct": sum(t.get('return_pct', 0) for t in strat_trades),
                "avg_return_pct": statistics.mean([t.get('return_pct', 0) for t in strat_trades]),
                "avg_hold_seconds": statistics.mean([t.get('hold_seconds', 0) for t in strat_trades]),
                "profit_factor": (
                    sum(t.get('net_pnl_usd', 0) for t in wins) /
                    abs(sum(t.get('net_pnl_usd', 0) for t in losses))
                    if losses else float('inf')
                ),
            }

        return by_strategy


def generate_performance_report(metrics: MetricsResult) -> str:
    """Generate a formatted performance report string."""
    lines = [
        "=" * 60,
        "PAPER TRADING PERFORMANCE REPORT",
        "=" * 60,
        f"Total Trades:        {metrics.total_trades}",
        f"  Winning:           {metrics.winning_trades}",
        f"  Losing:            {metrics.losing_trades}",
        f"  Breakeven:         {metrics.breakeven_trades}",
        f"Win Rate:            {metrics.win_rate:.2%}",
        "",
        f"Net P&L:             ${metrics.net_pnl_usd:,.2f}",
        f"Gross P&L:           ${metrics.gross_pnl_usd:,.2f}",
        f"Total Fees:          ${metrics.total_fees_usd:,.2f}",
        f"Total Slippage:      ${metrics.total_slippage_usd:,.2f}",
        f"Total Gas:           ${metrics.total_gas_usd:,.2f}",
        "",
        f"Avg Return:          {metrics.avg_return_pct:.4f}%",
        f"Median Return:       {metrics.median_return_pct:.4f}%",
        f"Return StdDev:       {metrics.std_return_pct:.4f}%",
        f"Profit Factor:       {metrics.profit_factor:.2f}",
        f"Avg Win:             ${metrics.avg_win_usd:,.2f} ({metrics.avg_win_pct:.4f}%)",
        f"Avg Loss:            ${metrics.avg_loss_usd:,.2f} ({metrics.avg_loss_pct:.4f}%)",
        "",
        f"Best Trade:          {metrics.best_trade_pct:.4f}% (${metrics.best_trade_usd:,.2f})",
        f"Worst Trade:         {metrics.worst_trade_pct:.4f}% (${metrics.worst_trade_usd:,.2f})",
        "",
        f"Max Drawdown:        {metrics.max_drawdown_pct:.2f}% (${metrics.max_drawdown_usd:,.2f})",
        f"Sharpe Ratio:        {metrics.sharpe_ratio:.2f}",
        f"Sortino Ratio:       {metrics.sortino_ratio:.2f}",
        f"Calmar Ratio:        {metrics.calmar_ratio:.2f}",
        "",
        f"Avg Hold Time:       {metrics.avg_hold_seconds:.0f}s",
        f"Median Hold Time:    {metrics.median_hold_seconds:.0f}s",
        f"Max Win Streak:      {metrics.max_consecutive_wins}",
        f"Max Loss Streak:     {metrics.max_consecutive_losses}",
        "",
        "By Strategy:",
    ]

    for strat, stats in metrics.by_strategy.items():
        lines.append(f"  {strat}:")
        lines.append(f"    Trades: {stats['total_trades']}, Win Rate: {stats['win_rate']:.2%}")
        lines.append(f"    Net P&L: ${stats['net_pnl_usd']:,.2f}, PF: {stats['profit_factor']:.2f}")

    lines.append("=" * 60)
    return "\n".join(lines)