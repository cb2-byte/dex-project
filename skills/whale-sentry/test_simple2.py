#!/usr/bin/env python3
"""
Whale Sentry - Simple Test without imports
"""
import sys
import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

# Read .env manually
env_path = '/Users/colinbrennan/.openclaw/workspace/skills/whale-sentry/.env'
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

# Test database initialization directly
db_path = '/Users/colinbrennan/.openclaw/workspace/skills/whale-sentry/whale_sentry.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Initialize tables
with conn:
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

# Check tables
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables:", tables)

# Add a test wallet
cursor = conn.execute("""
    INSERT OR REPLACE INTO wallets
    (chain, address, label, threshold_eth, threshold_sol, threshold_usd, enabled)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", ("ethereum", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "Vitalik Buterin", 50.0, 5000.0, 100000.0, 1))

# Add a Solana test wallet
cursor = conn.execute("""
    INSERT OR REPLACE INTO wallets
    (chain, address, label, threshold_eth, threshold_sol, threshold_usd, enabled)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", ("solana", "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "Whale #1", 100.0, 1000.0, 50000.0, 1))

conn.commit()

# Check wallets table
cursor = conn.execute("SELECT * FROM wallets")
wallets = [dict(row) for row in cursor.fetchall()]
print("\nWallets in DB:", json.dumps(wallets, indent=2))

# Get stats
cursor = conn.execute("SELECT COUNT(*) FROM alerts")
total_alerts = cursor.fetchone()[0]
cursor = conn.execute("SELECT COUNT(*) FROM wallets WHERE enabled = 1")
active_wallets = cursor.fetchone()[0]
cursor = conn.execute("SELECT COUNT(*) FROM wallets WHERE enabled = 0")
disabled_wallets = cursor.fetchone()[0]
cursor = conn.execute("SELECT COUNT(*) FROM price_cache")
cached_prices = cursor.fetchone()[0]
cursor = conn.execute("SELECT MAX(created_at) FROM alerts")
latest_alert = cursor.fetchone()[0]

print(f"\nStats:")
print(f"  Total alerts: {total_alerts}")
print(f"  Active wallets: {active_wallets}")
print(f"  Disabled wallets: {disabled_wallets}")
print(f"  Cached prices: {cached_prices}")
print(f"  Latest alert: {latest_alert}")

conn.close()
print("\n✅ Database test passed!")
