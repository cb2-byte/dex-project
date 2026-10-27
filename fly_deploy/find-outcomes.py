#!/usr/bin/env python3
import json
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient

with open('.polymarket-keys.json') as f:
    keys = json.load(f)

creds = SimpleNamespace(api_key=keys['apiKey'], api_secret=keys['secret'], api_passphrase=keys['passphrase'])
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds
)

# Get markets
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

if not markets:
    print("No markets")
    exit(1)

# Find market with question matching ETH
eth_market = None
for m in markets:
    q = m.get('question', '').lower()
    if 'eth' in q or 'ethereum' in q:
        eth_market = m
        break

if not eth_market:
    eth_market = markets[0]

print(f"Market: {eth_market.get('question', 'N/A')[:60]}")
print(f"Slug: {eth_market.get('slug', 'N/A')}")
print(f"Condition ID: {eth_market.get('condition_id', 'N/A')}")

slug = eth_market.get('slug')
condition_id = eth_market.get('condition_id')

# Try get_clob_market_info with slug
if slug:
    print(f"\n=== Trying get_clob_market_info('{slug}') ===")
    try:
        result = client.get_clob_market_info(slug)
        print(f"Result type: {type(result)}")
        if isinstance(result, dict):
            print(f"Keys: {list(result.keys())[:20]}")
            if 'clob_tokens' in result:
                print(f"CLOB tokens: {json.dumps(result['clob_tokens'], default=str)[:500]}")
            if 'outcomes' in result:
                print(f"Outcomes: {json.dumps(result['outcomes'], default=str)[:500]}")
        else:
            print(f"Result: {str(result)[:300]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

# Also try with condition_id
if condition_id:
    print(f"\n=== Trying get_clob_market_info('{condition_id}') ===")
    try:
        result = client.get_clob_market_info(condition_id)
        print(f"Result type: {type(result)}")
        if isinstance(result, dict):
            print(f"Keys: {list(result.keys())[:20]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

print("\n=== NEXT: Try get_market(slug) ===")
if slug:
    try:
        result = client.get_market(slug)
        print(f"Result type: {type(result)}")
        if isinstance(result, dict):
            print(f"Keys: {list(result.keys())[:20]}")
            if 'clob_tokens' in result:
                print(f"CLOB tokens: {json.dumps(result['clob_tokens'], default=str)[:500]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
