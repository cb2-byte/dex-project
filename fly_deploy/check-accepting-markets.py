#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""Check which markets are actually accepting orders"""

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

accepting_count = 0
active_count = 0

for m in markets:
    if m.get('active'):
        active_count += 1
    if m.get('accepting_orders'):
        accepting_count += 1

print(f"\nTotal markets: {len(markets)}")
print(f"Active markets: {active_count}")
print(f"Accepting orders: {accepting_count}")

# Show some accepting markets
print("\n--- Markets accepting orders (first 10) ---")
shown = 0
for m in markets:
    if m.get('accepting_orders') and shown < 10:
        slug = m.get('market_slug', '') or m.get('slug', '')
        title = m.get('title', '') or m.get('question', '')
        tokens = m.get('tokens', [])
        token_ids = [t.get('token_id') if isinstance(t, dict) else t for t in tokens[:2]]
        print(f"\nSLUG: {slug}")
        print(f"TITLE: {title[:60]}")
        print(f"TOKENS: {token_ids}")
        shown += 1
