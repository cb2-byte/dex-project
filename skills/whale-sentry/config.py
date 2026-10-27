"""
Configuration management for Whale Sentry skill.
"""
import os
from dataclasses import dataclass, field
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class WalletConfig:
    """Configuration for a monitored wallet."""
    chain: str  # ethereum, solana, base
    address: str
    label: str
    threshold_eth: float = 100.0
    threshold_sol: float = 5000.0
    threshold_usd: float = 100000.0
    enabled: bool = True


@dataclass
class Config:
    """Main configuration for Whale Sentry."""
    # API Keys
    etherscan_api_key: str = ""
    solscan_api_key: str = ""
    solana_fm_api_key: str = ""
    covalent_api_key: str = ""
    alchemy_api_key: str = ""
    
    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # NVIDIA
    nvidia_api_key: str = ""
    
    # Thresholds
    whale_threshold_eth: float = 100.0
    whale_threshold_sol: float = 5000.0
    whale_threshold_usd: float = 100000.0
    check_interval: int = 60
    
    # Monitored wallets
    wallets: List[WalletConfig] = field(default_factory=list)
    
    # Database
    database_path: str = "whale_sentry.db"
    
    # Monitoring
    enabled: bool = True
    check_interval_seconds: int = 60


def load_config() -> Config:
    """Load configuration from environment variables."""
    config = Config()
    
    # API Keys
    config.etherscan_api_key = os.getenv("ETHERSCAN_API_KEY", "")
    config.solscan_api_key = os.getenv("SOLSCAN_API_KEY", "")
    config.solana_fm_api_key = os.getenv("SOLANA_FM_API_KEY", "")
    config.covalent_api_key = os.getenv("COVALENT_API_KEY", "")
    config.alchemy_api_key = os.getenv("ALCHEMY_API_KEY", "")
    
    # Telegram
    config.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    config.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # NVIDIA
    config.nvidia_api_key = os.getenv("NVIDIA_API_KEY", "")
    
    # Thresholds
    config.whale_threshold_eth = float(os.getenv("WHALE_THRESHOLD_ETH", "100"))
    config.whale_threshold_sol = float(os.getenv("WHALE_THRESHOLD_SOL", "5000"))
    config.whale_threshold_usd = float(os.getenv("WHALE_THRESHOLD_USD", "100000"))
    config.check_interval = int(os.getenv("CHECK_INTERVAL", "60"))
    
    return config


def save_wallets(config: Config, path: str = "wallets.json"):
    """Save wallet configurations to JSON file."""
    import json
    data = [
        {
            "chain": w.chain,
            "address": w.address,
            "label": w.label,
            "threshold_eth": w.threshold_eth,
            "threshold_sol": w.threshold_sol,
            "threshold_usd": w.threshold_usd,
            "enabled": w.enabled
        }
        for w in config.wallets
    ]
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def load_wallets(config: Config, path: str = "wallets.json"):
    """Load wallet configurations from JSON file."""
    import json
    import os
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        data = json.load(f)
    config.wallets = [
        WalletConfig(
            chain=w["chain"],
            address=w["address"],
            label=w["label"],
            threshold_eth=w.get("threshold_eth", 100.0),
            threshold_sol=w.get("threshold_sol", 5000.0),
            threshold_usd=w.get("threshold_usd", 100000.0),
            enabled=w.get("enabled", True)
        )
        for w in data
    ]