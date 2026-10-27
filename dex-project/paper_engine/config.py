"""
Paper Trading Engine Configuration
===================================
Centralized configuration for all paper trading components.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import yaml
import os


@dataclass
class FeeSchedule:
    """Per-venue trading fee schedules (basis points)."""
    trading_fee_bps: Dict[str, float] = field(default_factory=lambda: {
        "coinbase": 30.0,
        "kraken": 26.0,
        "uniswap_v3_base": 5.0,
        "uniswap_v3_ethereum": 30.0,
    })
    withdrawal_fee_usd: Dict[str, float] = field(default_factory=lambda: {
        "coinbase": 0.0,
        "kraken": 2.5,
        "binance": 1.0,
    })
    deposit_fee_usd: Dict[str, float] = field(default_factory=lambda: {
        "coinbase": 0.0,
        "kraken": 0.0,
        "binance": 0.0,
    })
    gas_estimate_usd: Dict[str, float] = field(default_factory=lambda: {
        "base": 0.01,
        "ethereum": 5.0,
        "arbitrum": 0.10,
        "optimism": 0.10,
        "polygon": 0.01,
    })
    bridge_fee_bps: Dict[str, float] = field(default_factory=lambda: {
        "hop": 5.0,
        "across": 3.0,
        "wormhole": 8.0,
    })


@dataclass
class SlippageModel:
    """Price impact model: impact_bps = base_bps * (trade_size / liquidity)^alpha"""
    base_bps: float = 10.0
    alpha: float = 0.5
    max_slippage_bps: float = 500.0  # Cap at 5%

    def estimate_slippage_bps(self, trade_size_usd: float, liquidity_usd: float) -> float:
        if liquidity_usd <= 0:
            return self.max_slippage_bps
        ratio = trade_size_usd / liquidity_usd
        impact = self.base_bps * (ratio ** self.alpha)
        return min(impact, self.max_slippage_bps)


@dataclass
class PaperConfig:
    """Main paper trading configuration."""
    # Capital & risk limits
    starting_capital_usd: float = 1000.0
    max_position_pct: float = 0.10          # 10% per trade
    max_daily_exposure_pct: float = 0.50    # 50% daily
    max_drawdown_pct: float = 0.20          # 20% kill switch
    min_net_edge_pct: float = 0.20          # 0.2% minimum net return after all costs

    # Staleness limits per source (seconds)
    max_staleness_seconds: Dict[str, float] = field(default_factory=lambda: {
        "coingecko_demo": 60.0,
        "coinbase": 10.0,
        "kraken": 10.0,
        "geckoterminal": 60.0,
        "alchemy_rpc": 30.0,
    })

    # Liquidity requirements
    min_liquidity_usd: float = 10_000.0

    # Meme sniper specific
    meme_max_hold_seconds: float = 300.0
    meme_adverse_move_bps_per_min: float = 50.0
    meme_momentum_cap_pct: float = 5.0

    # Fee & slippage models
    fee_schedule: FeeSchedule = field(default_factory=FeeSchedule)
    slippage_model: SlippageModel = field(default_factory=SlippageModel)

    @classmethod
    def from_yaml(cls, path: str) -> "PaperConfig":
        """Load configuration from YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data.get('paper_engine', {}))

    @classmethod
    def from_dict(cls, data: dict) -> "PaperConfig":
        """Create config from dictionary."""
        fee_schedule = FeeSchedule(**data.get('fee_schedule', {}))
        slippage_model = SlippageModel(**data.get('slippage_model', {}))
        config_data = {k: v for k, v in data.items() 
                       if k not in ('fee_schedule', 'slippage_model')}
        config_data['fee_schedule'] = fee_schedule
        config_data['slippage_model'] = slippage_model
        return cls(**config_data)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'starting_capital_usd': self.starting_capital_usd,
            'max_position_pct': self.max_position_pct,
            'max_daily_exposure_pct': self.max_daily_exposure_pct,
            'max_drawdown_pct': self.max_drawdown_pct,
            'min_net_edge_pct': self.min_net_edge_pct,
            'max_staleness_seconds': self.max_staleness_seconds,
            'min_liquidity_usd': self.min_liquidity_usd,
            'meme_max_hold_seconds': self.meme_max_hold_seconds,
            'meme_adverse_move_bps_per_min': self.meme_adverse_move_bps_per_min,
            'meme_momentum_cap_pct': self.meme_momentum_cap_pct,
            'fee_schedule': {
                'trading_fee_bps': self.fee_schedule.trading_fee_bps,
                'withdrawal_fee_usd': self.fee_schedule.withdrawal_fee_usd,
                'deposit_fee_usd': self.fee_schedule.deposit_fee_usd,
                'gas_estimate_usd': self.fee_schedule.gas_estimate_usd,
                'bridge_fee_bps': self.fee_schedule.bridge_fee_bps,
            },
            'slippage_model': {
                'base_bps': self.slippage_model.base_bps,
                'alpha': self.slippage_model.alpha,
                'max_slippage_bps': self.slippage_model.max_slippage_bps,
            }
        }

    def save_yaml(self, path: str):
        """Save configuration to YAML file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump({'paper_engine': self.to_dict()}, f, default_flow_style=False)


# Default config instance
DEFAULT_CONFIG = PaperConfig()


def load_config(config_path: Optional[str] = None) -> PaperConfig:
    """Load config from file or return default."""
    if config_path and os.path.exists(config_path):
        return PaperConfig.from_yaml(config_path)
    return DEFAULT_CONFIG