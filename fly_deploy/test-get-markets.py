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

print("Testing different market endpoints...\n")

# Try get_markets
print("=== get_markets() ===")
try:
    result = client.get_markets()
    markets = result.get('data', []) if isinstance(result, dict) else result
    print(f"Returned: {len(markets)} markets")
    if markets:
        m = markets[0]
        print(f"First market keys: {list(m.keys())[:10]}")
        print(f"Has outcomes? {len(m.get('outcomes', [])) if 'outcomes' in m else 'NO outcomes key'}")
        if 'outcomes' in m and len(m['outcomes']) > 0:
            print(f"Sample outcome: {json.dumps(m['outcomes'][0], indent=2, default=str)[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Try get_simplified_markets
print("\n=== get_simplified_markets() ===")
try:
    result = client.get_simplified_markets()
    markets = result.get('data', []) if isinstance(result, dict) else result
    print(f"Returned: {len(markets)} markets")
    if markets:
        m = markets[0]
        print(f"First market keys: {list(m.keys())[:10]}")
        print(f"Has outcomes? {len(m.get('outcomes', [])) if 'outcomes' in m else 'NO outcomes key'}")
except Exception as e:
    print(f"Error: {e}")

# Try get_sampling_markets
print("\n=== get_sampling_markets() ===")
try:
    result = client.get_sampling_markets()
    markets = result.get('data', []) if isinstance(result, dict) else result
    print(f"Returned: {len(markets)} markets")
    if markets:
        m = markets[0]
        print(f"First market keys: {list(m.keys())[:10]}")
        print(f"Has outcomes? {len(m.get('outcomes', [])) if 'outcomes' in m else 'NO outcomes key'}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== SUMMARY ===")
print("Looking for: markets with 2+ outcomes and token_id data")
