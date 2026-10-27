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

print("Testing CLOB market info endpoints...\n")

# First get one market
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result
if not markets:
    print("No markets found!")
    sys.exit(1)

first_market = markets[0]
market_id = first_market.get('market_id')
condition_id = first_market.get('condition_id')

print(f"Sample market: {first_market.get('question', 'N/A')[:50]}")
print(f"Market ID: {market_id}")
print(f"Condition ID: {condition_id}\n")

# Try get_clob_market_info with market_id
if market_id:
    print(f"=== get_clob_market_info('{market_id}') ===")
    try:
        info = client.get_clob_market_info(market_id)
        print(f"Type: {type(info)}")
        if isinstance(info, dict):
            print(f"Keys: {list(info.keys())[:15]}")
            if 'outcomes' in info:
                print(f"Outcomes: {json.dumps(info['outcomes'], indent=2, default=str)[:300]}")
            if 'clob_tokens' in info:
                print(f"CLOB Tokens: {json.dumps(info['clob_tokens'], indent=2, default=str)[:300]}")
        else:
            print(f"Value: {str(info)[:200]}")
    except Exception as e:
        print(f"Error: {e}")

print("\n=== GOAL ===")
print("Need to find: outcome token IDs for trading")
print("Market endpoints don't have them - must use condition_id or other method")
