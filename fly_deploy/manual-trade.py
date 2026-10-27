#!/usr/bin/env python3
"""Manual test trade"""

import json
from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, OrderArgsV2

with open('.polymarket-keys.json') as f:
    keys = json.load(f)

creds = ApiCreds(
    api_key=keys['apiKey'],
    api_secret=keys['secret'],
    api_passphrase=keys['passphrase']
)

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds,
    signature_type=1,
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'
)

print("🧪 MANUAL TEST TRADE")
print(f"Wallet: 0x98D9Dbd...\n")

# Check balance
print("📊 Balance...")
try:
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    balance = client.get_balance_allowance(params=params)
    print(f"   {balance}\n")
except Exception as e:
    print(f"   Error: {e}\n")

# Get markets
print("🔍 Markets...")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result
print(f"   Found {len(markets)} markets\n")

# Find first market accepting orders
for i, m in enumerate(markets[:50]):
    if not m.get('accepting_orders'):
        continue
    
    tokens = m.get('tokens', [])
    if len(tokens) < 2:
        continue
    
    token_id = None
    for t in tokens:
        if isinstance(t, dict):
            token_id = t.get('token_id')
        else:
            token_id = t
        if token_id:
            break
    
    if not token_id:
        continue
    
    slug = m.get('slug', 'unknown')[:40]
    print(f"[{i}] {slug}")
    print(f"    Token: {token_id}")
    
    # Try to place order
    print(f"    Placing $0.50 @ 0.50...")
    try:
        order = OrderArgsV2(
            token_id=token_id,
            price=0.50,
            size=0.50,
            side='BUY',
            expiration=0
        )
        
        signed = client.create_order(order)
        resp = client.post_order(signed)
        
        print(f"\n✅ TRADE EXECUTED!")
        print(f"   {resp}")
        exit(0)
        
    except Exception as e:
        err = str(e)
        if 'orderbook' in err.lower() or 'does not exist' in err.lower():
            print(f"    ❌ No orderbook")
        else:
            print(f"    ❌ {err[:80]}")
    
    print()

print("❌ No trades executed")
