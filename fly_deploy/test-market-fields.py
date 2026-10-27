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

# Get markets and dump full first market
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

if markets:
    print("=== FULL FIRST MARKET ===")
    m = markets[0]
    print(json.dumps(m, indent=2, default=str)[:2000])
    print("\n=== ALL KEYS ===")
    print(list(m.keys()))
