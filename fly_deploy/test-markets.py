#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""Test what markets are available"""

import json
import os
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

print("Fetching markets...")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

print(f"Found {len(markets)} markets\n")

# Find BTC, ETH, LINK, Weather markets
for m in markets[:50]:  # Check first 50
    slug = m.get('market_slug', '') or m.get('slug', '')
    title = m.get('title', '')
    active = m.get('active', False)
    accepting = m.get('accepting_orders', False)
    tokens = m.get('tokens', [])
    
    if any(x in slug.lower() or x in title.lower() for x in ['bitcoin', 'btc', 'ethereum', 'eth', 'link', 'weather', 'rain']):
        print(f"SLUG: {slug}")
        print(f"TITLE: {title}")
        print(f"ACTIVE: {active}, ACCEPTING: {accepting}")
        print(f"TOKENS: {tokens}")
        print(f"CONDITION ID: {m.get('condition_id', 'N/A')}")
        print("---")
