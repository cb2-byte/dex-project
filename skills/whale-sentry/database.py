"""
Database module for Whale Sentry - SQLite storage for alerts and history.
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from contextlib import contextmanager


@dataclass
class Alert:
    """Alert data class."""
    id: Optional[int] = None
    alert_type: str = ""
    chain: str = ""
    hash: str = ""
    from_address: str = ""
    to_address: str = ""
    value: float = 0.0
    value_usd: Optional[float] = None
    token_symbol: Optional[str] = None
    token_value: Optional[float] = None
    timestamp: Optional[datetime] = None
    block_number: Optional[int] = None
    slot: Optional[int] = None
    chain_name: str = ""
    wallet_label: str = ""
    wallet_address: str = ""
    threshold_triggered: str = ""
    analysis: Optional[str] = None
    created_at: Optional[datetime] = None


class Database:
    """SQLite database for storing alerts and wallet configurations."""

    def __init__(self, db_path: str = "whale_sentry.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database tables."""
        with self.get_conn() as conn:
            # Alerts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    value REAL NOT NULL,
                    value_usd REAL,
                    token_symbol TEXT,
                    token_value REAL,
                    timestamp TEXT,
                    block_number INTEGER,
                    slot INTEGER,
                    chain_name TEXT NOT NULL,
                    wallet_label TEXT,
                    wallet_address TEXT NOT NULL,
                    threshold_triggered TEXT,
                    analysis TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Wallet configurations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain TEXT NOT NULL,
                    address TEXT NOT NULL,
                    label TEXT NOT NULL,
                    threshold_eth REAL DEFAULT 100.0,
                    threshold_sol REAL DEFAULT 5000.0,
                    threshold_usd REAL DEFAULT 100000.0,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(chain, address)
                )
            """)

            # Price cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price_usd REAL NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol)
                )
            """)

            # Settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_chain ON alerts(chain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_wallet ON alerts(wallet_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wallets_chain ON wallets(chain)")

    # Alert methods
    def add_alert(self, alert: 'Alert') -> int:
        """Add a new alert."""
        with self.get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO alerts (
                    alert_type, chain, hash, from_address, to_address,
                    value, value_usd, token_symbol, token_value,
                    timestamp, block_number, slot, chain_name,
                    wallet_label, wallet_address, threshold_triggered, analysis
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_type, alert.chain, alert.hash, alert.from_address,
                alert.to_address, alert.value, alert.value_usd, alert.token_symbol,
                alert.token_value,
                alert.timestamp.isoformat() if alert.timestamp else None,
                alert.block_number, alert.slot, alert.chain_name,
                alert.wallet_label, alert.wallet_address,
                alert.threshold_triggered, alert.analysis
            ))
            return cursor.lastrowid

    def get_alerts(self, hours: int = 24, chain: Optional[str] = None,
                   wallet_address: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get recent alerts."""
        with self.get_conn() as conn:
            query = "SELECT * FROM alerts WHERE datetime(timestamp) >= datetime('now', ?)"
            params = [f"-{hours} hours"]

            if chain:
                query += " AND chain = ?"
                params.append(chain)
            if wallet_address:
                query += " AND wallet_address = ?"
                params.append(wallet_address)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_alert_count(self, hours: int = 24) -> int:
        """Get count of alerts in last N hours."""
        with self.get_conn() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE datetime(timestamp) >= datetime('now', ?)",
                (f"-{hours} hours",)
            )
            return cursor.fetchone()[0]

    # Wallet methods
    def add_wallet(self, chain: str, address: str, label: str,
                   threshold_eth: float = 100.0, threshold_sol: float = 5000.0,
                   threshold_usd: float = 100000.0, enabled: bool = True) -> int:
        """Add a wallet to monitor."""
        with self.get_conn() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO wallets
                (chain, address, label, threshold_eth, threshold_sol, threshold_usd, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chain, address.lower(), label, threshold_eth, threshold_sol,
                 threshold_usd, int(enabled)))
            return cursor.lastrowid

    def remove_wallet(self, chain: str, address: str) -> bool:
        """Remove a wallet from monitoring."""
        with self.get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM wallets WHERE chain = ? AND address = ?",
                (chain, address.lower())
            )
            return cursor.rowcount > 0

    def get_wallets(self, chain: Optional[str] = None, enabled_only: bool = True) -> List[Dict]:
        """Get all monitored wallets."""
        with self.get_conn() as conn:
            query = "SELECT * FROM wallets"
            params = []

            conditions = []
            if chain:
                conditions.append("chain = ?")
                params.append(chain)
            if enabled_only:
                conditions.append("enabled = 1")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY created_at DESC"

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_wallet(self, chain: str, address: str, **kwargs) -> bool:
        """Update wallet configuration."""
        allowed = {"label", "threshold_eth", "threshold_sol", "threshold_usd", "enabled"}
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                updates.append(f"{k} = ?")
                params.append(v)

        if not updates:
            return False

        params.extend([chain, address.lower()])

        with self.get_conn() as conn:
            cursor = conn.execute(
                f"UPDATE wallets SET {', '.join(updates)} WHERE chain = ? AND address = ?",
                params
            )
            return cursor.rowcount > 0

    # Price cache methods
    def set_price(self, symbol: str, price_usd: float):
        """Cache a token price."""
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO price_cache (symbol, price_usd, timestamp)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (symbol.upper(), price_usd))

    def get_price(self, symbol: str) -> Optional[float]:
        """Get cached token price."""
        with self.get_conn() as conn:
            cursor = conn.execute(
                "SELECT price_usd FROM price_cache WHERE symbol = ?",
                (symbol.upper(),)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    # Settings methods
    def set_setting(self, key: str, value: str):
        """Set a setting value."""
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))

    def get_setting(self, key: str, default: str = "") -> str:
        """Get a setting value."""
        with self.get_conn() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def get_stats(self) -> Dict:
        """Get database statistics."""
        with self.get_conn() as conn:
            stats = {}

            cursor = conn.execute("SELECT COUNT(*) FROM alerts")
            stats["total_alerts"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM wallets WHERE enabled = 1")
            stats["active_wallets"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM wallets WHERE enabled = 0")
            stats["disabled_wallets"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM price_cache")
            stats["cached_prices"] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT MAX(created_at) FROM alerts")
            stats["latest_alert"] = cursor.fetchone()[0]

            return stats