#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""Test BTC market finding logic"""

import json
import os
import time
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient

KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(KEYS_FILE) as f:
    keys = json.load(f)

creds = SimpleNamespace(api_key=keys['apiKey'], api_secret=keys['secret'], api_passphrase=keys['passphrase'])
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds,
    signature_type=2,
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'
)

result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

print("Searching for BTC markets accepting orders...\n")

for m in markets:
    if not m.get('accepting_orders'):
        continue
    
    slug = m.get('market_slug', '') or m.get('slug', '')
    title = m.get('title', '') or m.get('question', '')
    
    if 'bitcoin' in slug.lower() or 'btc' in slug.lower() or 'bitcoin' in title.lower() or 'btc' in title.lower():
        tokens = m.get('tokens', [])
        print(f"FOUND: {slug}")
        print(f"TITLE: {title[:80]}")
        print(f"ACCEPTING: {m.get('accepting_orders')}")
        print(f"ACTIVE: {m.get('active')}")
        
        if len(tokens) >= 2:
            token_up = tokens[0].get('token_id') if isinstance(tokens[0], dict) else tokens[0]
            token_down = tokens[1].get('token_id') if isinstance(tokens[1], dict) else tokens[1]
            print(f"TOKEN UP: {token_up}")
            print(f"TOKEN DOWN: {token_down}")
            
            # Test orderbook
            import requests
            ob = requests.get(f'https://clob.polymarket.com/orderbook?token_id={token_up}', timeout=5)
            print(f"ORDERBOOK STATUS: {ob.status_code}")
            if ob.status_code == 200:
                print(f"ORDERBOOK: {ob.json()}")
            else:
                print(f"ORDERBOOK ERROR: {ob.text[:200]}")
            print()
