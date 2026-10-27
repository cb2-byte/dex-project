#!/usr/bin/env python3
import sys, json
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient

# Load keys
with open('.polymarket-keys.json') as f:
    keys = json.load(f)

creds = SimpleNamespace(api_key=keys['apiKey'], api_secret=keys['secret'], api_passphrase=keys['passphrase'])
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds
)

print("Fetching markets from Polymarket...")
result = client.get_sampling_simplified_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

print(f"Total markets: {len(markets)}\n")

# Debug: Check market statuses
print("=== MARKET STATUS ANALYSIS ===")
active_count = len([m for m in markets if m.get('active')])
accepting_count = len([m for m in markets if m.get('accepting_orders')])
both_count = len([m for m in markets if m.get('active') and m.get('accepting_orders')])
with_outcomes = len([m for m in markets if len(m.get('outcomes', [])) >= 2])
both_and_outcomes = len([m for m in markets if m.get('active') and m.get('accepting_orders') and len(m.get('outcomes', [])) >= 2])

print(f"Active: {active_count}/1000")
print(f"Accepting orders: {accepting_count}/1000")
print(f"Both active AND accepting: {both_count}/1000")
print(f"With 2+ outcomes: {with_outcomes}/1000")
print(f"ALL THREE criteria met: {both_and_outcomes}/1000")

print("\n=== SAMPLE MARKETS (first 10) ===")
for i, m in enumerate(markets[:10]):
    print(f"\nMarket {i}:")
    print(f"  active: {m.get('active')}")
    print(f"  accepting_orders: {m.get('accepting_orders')}")
    print(f"  outcomes: {len(m.get('outcomes', []))}")
    print(f"  condition_id: {m.get('condition_id')[:30]}..." if m.get('condition_id') else "  condition_id: None")

# Try to find ANY tradeable market with looser criteria
print("\n=== TRYING LOOSER CRITERIA ===")
market_relaxed = None
for m in markets:
    if m.get('active'):  # At least active
        outcomes = m.get('outcomes', [])
        if len(outcomes) >= 2:
            market_relaxed = m
            print(f"Found active market (not requiring accepting_orders):")
            print(f"  active: {m.get('active')}")
            print(f"  accepting_orders: {m.get('accepting_orders')}")
            print(f"  outcomes: {len(outcomes)}")
            break

if not market_relaxed:
    print("No active market with 2+ outcomes found either!")
    
    # Check if ANY market has outcomes
    any_outcomes = [m for m in markets if len(m.get('outcomes', [])) >= 2]
    print(f"\nMarkets with 2+ outcomes (regardless of status): {len(any_outcomes)}")
    if any_outcomes:
        m = any_outcomes[0]
        print(f"  First one: active={m.get('active')}, accepting={m.get('accepting_orders')}")
