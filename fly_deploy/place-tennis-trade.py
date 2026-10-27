#!/usr/bin/env python3
"""Place trade on live tennis market"""

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

print("🎾 LIVE TENNIS TRADE")
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

# Try to find ATP/tennis markets
print("🔍 Finding tennis markets...\n")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

tennis_markets = []
for m in markets[:500]:
    slug = m.get('slug', '').lower()
    if 'atp' in slug or 'wta' in slug or 'tennis' in slug:
        if m.get('accepting_orders'):
            tokens = m.get('tokens', [])
            if len(tokens) >= 2:
                token_id = None
                for t in tokens:
                    if isinstance(t, dict):
                        token_id = t.get('token_id')
                    else:
                        token_id = t
                    if token_id:
                        break
                
                if token_id:
                    tennis_markets.append({
                        'token': token_id,
                        'slug': m.get('slug', 'unknown')[:50],
                        'question': m.get('question', '')[:60]
                    })

if not tennis_markets:
    print("❌ No tennis markets found")
    exit(1)

print(f"✅ Found {len(tennis_markets)} tennis markets:\n")
for i, m in enumerate(tennis_markets[:5]):
    print(f"[{i+1}] {m['question']}")
    print(f"    Token: {m['token']}\n")

# Pick first one and place order
m = tennis_markets[0]
print(f"💰 Placing $2.00 BUY @ 0.50 on: {m['question'][:50]}...\n")

try:
    order = OrderArgsV2(
        token_id=m['token'],
        price=0.50,
        size=2.0,
        side='BUY',
        expiration=0
    )
    
    print("   Creating order...")
    signed = client.create_order(order)
    print(f"   Order signed ✅")
    
    print("   Submitting to Polymarket...")
    resp = client.post_order(signed)
    
    print(f"\n🎉 TRADE EXECUTED!")
    print(f"   {resp}")
    print(f"\nCheck your Polymarket account!")
    
except Exception as e:
    print(f"\n❌ TRADE FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Done ---")
