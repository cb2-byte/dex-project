"""
Whale Sentry - Main Skill Entry Point
On-chain whale monitoring and alerting system using free APIs.
"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from .config import Config, load_config, load_wallets, save_wallets
from .database import Database, Alert
from .monitor import WhaleSentryMonitor, run_monitor
from .config import WalletConfig


class WhaleSentrySkill:
    """Main Whale Sentry skill class for OpenClaw integration."""

    def __init__(self, config: Config = None):
        self.config = config or load_config()
        self.database = Database(self.config.database_path)
        self.monitor = None
        self._monitor_task = None

    def initialize(self):
        """Initialize the skill - load wallets from storage."""
        load_wallets(self.config)
        return True

    def add_wallet(self, chain: str, address: str, label: str,
                   threshold_eth: float = 100.0, threshold_sol: float = 5000.0,
                   threshold_usd: float = 100000.0, enabled: bool = True) -> Dict:
        """Add a wallet to monitor."""
        wallet = WalletConfig(
            chain=chain,
            address=address,
            label=label,
            threshold_eth=threshold_eth,
            threshold_sol=threshold_sol,
            threshold_usd=threshold_usd,
            enabled=True
        )
        self.config.wallets.append(wallet)
        save_wallets(self.config)
        self.database.add_wallet(chain, address, label, threshold_eth, threshold_sol, threshold_usd, True)
        return {"success": True, "message": f"Added wallet {label} on {chain}"}

    def remove_wallet(self, chain: str, address: str) -> Dict:
        """Remove a wallet from monitoring."""
        success = self.database.remove_wallet(chain, address)
        if success:
            self.config.wallets = [w for w in self.config.wallets 
                                  if not (w.chain == chain and w.address.lower() == address.lower())]
            from .config import save_wallets
            save_wallets(self.config)
            return {"success": True, "message": f"Removed wallet {address} on {chain}"}
        return {"success": False, "message": "Wallet not found"}

    def list_wallets(self) -> List[Dict]:
        """List all monitored wallets."""
        return self.database.get_wallets()

    def start_monitoring(self) -> Dict:
        """Start the background monitoring daemon."""
        if self._monitor_task and not self._monitor_task.done():
            return {"success": False, "message": "Monitoring already running"}

        # Create monitor instance
        config = load_config()
        database = Database()
        monitor = WhaleSentryMonitor(load_config(), Database())

        async def run():
            monitor = WhaleSentryMonitor(load_config(), Database())
            await monitor.start()
            try:
                while True:
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                await monitor.stop()

        self._monitor_task = asyncio.create_task(run())
        return {"success": True, "message": "Monitoring started in background"}

    def stop_monitoring(self) -> Dict:
        """Stop the background monitoring daemon."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            return {"success": True, "message": "Monitoring stopped"}
        return {"success": False, "message": "Monitoring not running"}

    def get_alerts(self, hours: int = 24, chain: str = None, 
                   wallet_address: str = None, limit: int = 100) -> List[Dict]:
        """Get recent alerts."""
        db = Database()
        return db.get_alerts(hours, chain, wallet_address, 100)

    def get_summary(self, hours: int = 24) -> Dict:
        """Get alert summary for the last N hours."""
        from .database import Database
        from .alerts import AlertFormatter
        
        db = Database()
        alerts = db.get_alerts(hours)
        
        if not alerts:
            return {"summary": f"No alerts in last {hours} hours", "count": 0}
        
        # Group by chain
        by_chain = {}
        for alert in alerts:
            chain = alert.get("chain", "unknown")
            if chain not in by_chain:
                by_chain[chain] = []
            by_chain[chain].append(alert)
        
        summary = {
            "total_alerts": len(alerts),
            "by_chain": {},
            "top_alerts": []
        }
        
        for chain, chain_alerts in by_chain.items():
            total_usd = sum(a.get("value_usd", 0) or 0 for a in chain_alerts)
            summary["by_chain"][chain] = {
                "count": len(chain_alerts),
                "total_usd": total_usd
            }
        
        # Top 3 largest
        sorted_alerts = sorted(alerts, key=lambda x: x.get("value_usd", 0) or 0, reverse=True)
        summary["top_alerts"] = sorted_alerts[:3]
        
        return summary

    def check_wallet_now(self, chain: str, address: str) -> Dict:
        """Immediately check a specific wallet for activity."""
        # This would be implemented to do an immediate check
        return {"success": True, "message": "Check initiated"}

    def get_stats(self) -> Dict:
        """Get skill statistics."""
        db = Database()
        return db.get_stats()

    def set_wallet_threshold(self, chain: str, address: str, 
                            threshold_eth: float = None, 
                            threshold_sol: float = None, 
                            threshold_usd: float = None) -> Dict:
        """Update wallet thresholds."""
        updates = {}
        if threshold_eth is not None:
            updates["threshold_eth"] = threshold_eth
        if threshold_sol is not None:
            updates["threshold_sol"] = threshold_sol
        if threshold_usd is not None:
            updates["threshold_usd"] = threshold_usd
        
        if not updates:
            return {"success": False, "message": "No thresholds provided"}
        
        db = Database()
        success = db.update_wallet(chain, address, **updates)
        
        if success:
            # Update in-memory config
            for w in self.config.wallets:
                if w.chain == chain and w.address.lower() == address.lower():
                    for k, v in updates.items():
                        setattr(w, k, v)
                    break
            from .config import save_wallets
            save_wallets(self.config)
            return {"success": True, "message": "Thresholds updated"}
        return {"success": False, "message": "Wallet not found"}

    def get_wallet_info(self, chain: str, address: str) -> Optional[Dict]:
        """Get wallet configuration."""
        for w in self.config.wallets:
            if w.chain == chain and w.address.lower() == address.lower():
                return {
                    "chain": w.chain,
                    "address": w.address,
                    "label": w.label,
                    "threshold_eth": w.threshold_eth,
                    "threshold_sol": w.threshold_sol,
                    "threshold_usd": w.threshold_usd,
                    "enabled": w.enabled
                }
        return None


# Skill metadata for OpenClaw
SKILL_METADATA = {
    "name": "whale-sentry",
    "version": "1.0.0",
    "description": "On-chain whale monitoring and alerting system using free APIs",
    "author": "penny",
    "tags": ["crypto", "monitoring", "whale-tracking", "defi", "telegram", "alerts"],
    "entry_point": "WhaleSentrySkill",
    "config_schema": {
        "type": "object",
        "properties": {
            "etherscan_api_key": {"type": "string", "description": "Etherscan API key (free)"},
            "solscan_api_key": {"type": "string", "description": "Solscan API key (free)"},
            "solana_fm_api_key": {"type": "string", "description": "Solana FM API key (free)"},
            "covalent_api_key": {"type": "string", "description": "Covalent API key (free: 1M calls/month)"},
            "alchemy_api_key": {"type": "string", "description": "Alchemy API key (free: 300M CU/month)"},
            "telegram_bot_token": {"type": "string", "description": "Telegram bot token for alerts"},
            "telegram_chat_id": {"type": "string", "description": "Telegram chat ID for alerts"},
            "nvidia_api_key": {"type": "string", "description": "NVIDIA API key for AI analysis"},
            "whale_threshold_eth": {"type": "number", "default": 100, "description": "ETH threshold for alerts"},
            "whale_threshold_sol": {"type": "number", "default": 5000, "description": "SOL threshold for alerts"},
            "whale_threshold_usd": {"type": "number", "default": 100000, "description": "USD threshold for alerts"},
            "check_interval": {"type": "integer", "default": 60, "description": "Check interval in seconds"}
        }
    }
}


def create_skill(config: dict = None):
    """Factory function for OpenClaw to create the skill instance."""
    config_obj = None
    if config:
        from .config import Config
        config_obj = Config(**config)
    return WhaleSentrySkill(config_obj)


# Tool functions for direct OpenClaw integration
def whale_sentry_add_wallet(chain: str, address: str, label: str,
                           threshold_eth: float = 100.0,
                           threshold_sol: float = 5000.0,
                           threshold_usd: float = 100000.0) -> Dict:
    """Add a wallet to monitor. Usage: whale_sentry_add_wallet(chain='ethereum', address='0x...', label='Whale #1')"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.add_wallet(chain, address, label, threshold_eth, threshold_sol, threshold_usd)


def whale_sentry_remove_wallet(chain: str, address: str) -> Dict:
    """Remove a wallet from monitoring. Usage: whale_sentry_remove_wallet(chain='ethereum', address='0x...')"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.remove_wallet(chain, address)


def whale_sentry_list_wallets() -> List[Dict]:
    """List all monitored wallets. Usage: whale_sentry_list_wallets()"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.list_wallets()


def whale_sentry_start_monitoring() -> Dict:
    """Start background monitoring. Usage: whale_sentry_start_monitoring()"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.start_monitoring()


def whale_sentry_stop_monitoring() -> Dict:
    """Stop background monitoring. Usage: whale_sentry_stop_monitoring()"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.stop_monitoring()


def whale_sentry_get_alerts(hours: int = 24, chain: str = None, 
                           wallet_address: str = None, limit: int = 100) -> List[Dict]:
    """Get recent alerts. Usage: whale_sentry_get_alerts(hours=24, chain='ethereum')"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.get_alerts(hours, chain, wallet_address)


def whale_sentry_get_summary(hours: int = 24) -> Dict:
    """Get alert summary. Usage: whale_sentry_get_summary(hours=24)"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.get_summary(hours)


def whale_sentry_get_stats() -> Dict:
    """Get skill statistics. Usage: whale_sentry_get_stats()"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.get_stats()


def whale_sentry_set_threshold(chain: str, address: str,
                              threshold_eth: float = None,
                              threshold_sol: float = None,
                              threshold_usd: float = None) -> Dict:
    """Set wallet thresholds. Usage: whale_sentry_set_threshold(chain='ethereum', address='0x...', threshold_eth=50)"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.set_wallet_threshold(chain, address, threshold_eth, threshold_sol, threshold_usd)


def whale_sentry_get_wallet(chain: str, address: str) -> Dict:
    """Get wallet configuration. Usage: whale_sentry_get_wallet(chain='ethereum', address='0x...')"""
    skill = WhaleSentrySkill()
    skill.initialize()
    return skill.get_wallet_info(chain, address)


# OpenClaw skill registration
def register_skill():
    """Register the skill with OpenClaw."""
    return {
        "name": "whale-sentry",
        "version": "1.0.0",
        "description": "On-chain whale monitoring and alerting system using free APIs",
        "entry_point": "WhaleSentrySkill",
        "tools": {
            "whale_sentry_add_wallet": whale_sentry_add_wallet,
            "whale_sentry_remove_wallet": whale_sentry_remove_wallet,
            "whale_sentry_list_wallets": whale_sentry_list_wallets,
            "whale_sentry_start_monitoring": whale_sentry_start_monitoring,
            "whale_sentry_stop_monitoring": whale_sentry_stop_monitoring,
            "whale_sentry_get_alerts": whale_sentry_get_alerts,
            "whale_sentry_get_summary": whale_sentry_get_summary,
            "whale_sentry_get_stats": whale_sentry_get_stats,
            "whale_sentry_set_threshold": whale_sentry_set_threshold,
            "whale_sentry_get_wallet": whale_sentry_get_wallet,
        }
    }