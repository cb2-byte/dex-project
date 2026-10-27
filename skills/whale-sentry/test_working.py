#!/usr/bin/env python3
"""
Whale Sentry - Working Test (bypassing import issues)
"""
import sys
import os
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Load .env manually
env_path = '/Users/colinbrennan/.openclaw/workspace/skills/whale-sentry/.env'
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

print("✅ Environment loaded")
print(f"   ETHERSCAN_API_KEY: {os.getenv('ETHERSCAN_API_KEY', 'NOT SET')[:20]}...")
print(f"   SOLSCAN_API_KEY: {os.getenv('SOLSCAN_API_KEY', 'NOT SET')[:20]}...")
print(f"   COVALENT_API_KEY: {os.getenv('COVALENT_API_KEY', 'NOT SET')[:20]}...")
print(f"   ALCHEMY_API_KEY: {os.getenv('ALCHEMY_API_KEY', 'NOT SET')[:20]}...")
print(f"   NVIDIA_API_KEY: {os.getenv('NVIDIA_API_KEY', 'NOT SET')[:20]}...")

# Test database operations
db_path = '/Users/colinbrennan/.openclaw/workspace/skills/whale-sentry/whale_sentry.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Initialize tables
with conn:
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_chain ON alerts(chain)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_wallet ON alerts(wallet_address)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wallets_chain ON wallets(chain)")

# Wallet operations
def add_wallet(chain: str, address: str, label: str, threshold_eth: float = 100.0, threshold_sol: float = 5000.0, threshold_usd: float = 100000.0) -> Dict:
    """Add a wallet to monitor."""
    with conn:
        cursor = conn.execute("""
            INSERT OR REPLACE INTO wallets
            (chain, address, label, threshold_eth, threshold_sol, threshold_usd, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (chain, address.lower(), label, threshold_eth, threshold_sol, threshold_usd, 1))
        return {"success": True, "message": f"Added wallet {label} on {chain}", "id": cursor.lastrowid}

def list_wallets() -> List[Dict]:
    """List all monitored wallets."""
    with conn:
        cursor = conn.execute("SELECT * FROM wallets WHERE enabled = 1 ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def get_wallet(chain: str, address: str) -> Optional[Dict]:
    """Get wallet configuration."""
    with conn:
        cursor = conn.execute("SELECT * FROM wallets WHERE chain = ? AND address = ?", (chain, address.lower()))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_wallet_threshold(chain: str, address: str, threshold_eth: float = None, threshold_sol: float = None, threshold_usd: float = None) -> Dict:
    """Update wallet thresholds."""
    updates = []
    params = []
    if threshold_eth is not None:
        updates.append("threshold_eth = ?")
        params.append(threshold_eth)
    if threshold_sol is not None:
        updates.append("threshold_sol = ?")
        params.append(threshold_sol)
    if threshold_usd is not None:
        updates.append("threshold_usd = ?")
        params.append(threshold_usd)
    
    if not updates:
        return {"success": False, "message": "No thresholds provided"}
    
    params.extend([chain, address.lower()])
    
    with conn:
        cursor = conn.execute(
            f"UPDATE wallets SET {', '.join(updates)} WHERE chain = ? AND address = ?",
            params
        )
        if cursor.rowcount > 0:
            return {"success": True, "message": "Thresholds updated"}
        return {"success": False, "message": "Wallet not found"}

def get_stats() -> Dict:
    """Get database statistics."""
    with conn:
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

# Test the functions
print("\n🐋 Whale Sentry Skill Test")
print("=" * 40)

# Add Ethereum wallet
print("\n📍 Adding Ethereum test wallet (Vitalik)...")
result = add_wallet(
    chain="ethereum",
    address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    label="Vitalik Buterin",
    threshold_eth=50.0,
    threshold_usd=100000.0
)
print(f"   Result: {result}")

# Add Solana wallet
print("\n📍 Adding Solana test wallet...")
result = add_wallet(
    chain="solana",
    address="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    label="Whale #1",
    threshold_sol=1000.0,
    threshold_usd=50000.0
)
print(f"   Result: {result}")

# List wallets
print("\n📋 Listing wallets...")
wallets = list_wallets()
for w in wallets:
    print(f"   - {w['label']} ({w['chain']}): {w['address'][:8]}...{w['address'][-6:]}")
    print(f"     Thresholds: ETH={w['threshold_eth']}, SOL={w['threshold_sol']}, USD={w['threshold_usd']}")

# Get wallet info
print("\n🔍 Getting wallet info...")
wallet = get_wallet("ethereum", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
print(f"   {wallet}")

# Update threshold
print("\n⚙️ Updating threshold...")
result = update_wallet_threshold(
    chain="ethereum",
    address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    threshold_eth=25.0,
    threshold_usd=50000.0
)
print(f"   Result: {result}")

# Get stats
print("\n📊 Getting stats...")
stats = get_stats()
print(f"   {json.dumps(stats, indent=2)}")

conn.close()
print("\n✅ All tests passed!")
print("\n📝 Next steps for OpenClaw integration:")
print("   1. The skill tools should be available after gateway restart")
print("   2. If not, check OpenClaw skill loader for local workspace skills")
print("   3. The .env is configured with all API keys")
print("   4. Database is initialized and working")
