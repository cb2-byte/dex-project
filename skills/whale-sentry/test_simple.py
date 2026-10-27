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

# Test database directly
db_path = '/Users/colinbrennan/.openclaw/workspace/skills/whale-sentry/whale_sentry.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Check tables
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables:", tables)

# Check wallets table
cursor = conn.execute("SELECT * FROM wallets")
wallets = [dict(row) for row in cursor.fetchall()]
print("\nWallets in DB:", wallets)

# Check alerts table
cursor = conn.execute("SELECT * FROM alerts LIMIT 5")
alerts = [dict(row) for row in cursor.fetchall()]
print("\nAlerts in DB:", alerts)

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
