#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""Find active markets for BTC, ETH, LINK, Weather"""

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

print("Fetching all markets...")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

print(f"Total markets: {len(markets)}\n")

# Search for relevant keywords in all markets
keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'link', 'chainlink', 'weather', 'rain', 'temperature']
found = []

for i, m in enumerate(markets):
    slug = m.get('market_slug', '') or m.get('slug', '')
    title = m.get('title', '')
    active = m.get('active', False)
    accepting = m.get('accepting_orders', False)
    tokens = m.get('tokens', [])
    condition_id = m.get('condition_id', '')
    
    # Check if any keyword matches
    text = f"{slug} {title}".lower()
    if any(kw in text for kw in keywords):
        found.append({
            'index': i,
            'slug': slug,
            'title': title[:80],
            'active': active,
            'accepting': accepting,
            'tokens': tokens,
            'condition_id': condition_id
        })

print(f"Found {len(found)} relevant markets:\n")
for m in found[:10]:  # Show first 10
    print(f"IDX: {m['index']}")
    print(f"SLUG: {m['slug']}")
    print(f"TITLE: {m['title']}")
    print(f"ACTIVE: {m['active']}, ACCEPTING: {m['accepting']}")
    print(f"CONDITION_ID: {m['condition_id']}")
    print(f"TOKENS: {json.dumps(m['tokens'])}")
    print("---\n")
