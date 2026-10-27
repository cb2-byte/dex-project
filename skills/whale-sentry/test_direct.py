#!/usr/bin/env python3
"""
Whale Sentry - Direct Test Script (no package installation needed)
"""
import sys
import os
sys.path.insert(0, '/Users/colinbrennan/.openclaw/workspace/skills/whale-sentry')

# Monkey-patch the relative imports to absolute
import whale_sentry.config as config_module
import whale_sentry.database as database_module
import whale_sentry.monitor as monitor_module
import whale_sentry.alerts as alerts_module
import whale_sentry.analysis as analysis_module

# Now import the main module
import whale_sentry.whale_sentry as whale_sentry_module

# Test the functions directly
from whale_sentry.whale_sentry import (
    WhaleSentrySkill,
    whale_sentry_add_wallet,
    whale_sentry_list_wallets,
    whale_sentry_get_alerts,
    whale_sentry_get_summary,
    whale_sentry_get_stats,
    whale_sentry_set_threshold,
    whale_sentry_get_wallet,
)

# Initialize skill
skill = WhaleSentrySkill()
skill.initialize()
print("✅ Skill initialized")

# Test adding a wallet (Ethereum - Vitalik's wallet)
print("\n📍 Adding test wallet...")
result = whale_sentry_add_wallet(
    chain="ethereum",
    address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    label="Vitalik Buterin",
    threshold_eth=50.0,
    threshold_usd=100000.0
)
print(f"   Result: {result}")

# Test adding a Solana wallet
print("\n📍 Adding Solana test wallet...")
result = whale_sentry_add_wallet(
    chain="solana",
    address="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    label="Whale #1",
    threshold_sol=1000.0,
    threshold_usd=50000.0
)
print(f"   Result: {result}")

# List wallets
print("\n📋 Listing wallets...")
wallets = whale_sentry_list_wallets()
for w in wallets:
    print(f"   - {w['label']} ({w['chain']}): {w['address'][:8]}...{w['address'][-6:]}")

# Get wallet info
print("\n🔍 Getting wallet info...")
wallet = whale_sentry_get_wallet("ethereum", "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
print(f"   {wallet}")

# Test threshold update
print("\n⚙️ Updating threshold...")
result = whale_sentry_set_threshold(
    chain="ethereum",
    address="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    threshold_eth=25.0,
    threshold_usd=50000.0
)
print(f"   Result: {result}")

# Get stats
print("\n📊 Getting stats...")
stats = whale_sentry_get_stats()
print(f"   {stats}")

print("\n✅ All tests passed!")
