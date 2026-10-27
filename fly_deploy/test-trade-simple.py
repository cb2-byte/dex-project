#!/usr/bin/env python3
"""Simplest possible test trade"""

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

PRIVATE_KEY = "0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b"
FUNDER = "0x98D9Dbd34d0156E6385D08d5263467601BE5e972"

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=PRIVATE_KEY,
    creds=creds,
    signature_type=1,
    funder=FUNDER
)

print(f"Wallet: {FUNDER}")
print(f"Key: {PRIVATE_KEY[:20]}...")

# Get markets
print("\n📋 Getting markets...")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result
print(f"  Found {len(markets)} markets")

# Find one with liquidity
for m in markets[:10]:
    if not m.get('accepting_orders'):
        continue
    tokens = m.get('tokens', [])
    if len(tokens) < 2:
        continue
    
    # Extract token IDs
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
    
    slug = m.get('slug', 'unknown')[:50]
    print(f"\n🎯 Testing: {slug}")
    print(f"   Token: {token_id}")
    
    # Get orderbook via client
    try:
        ob = client.get_orderbook(token_id)
        print(f"   Orderbook: {ob}")
        
        if ob.get('bids') and len(ob['bids']) > 0:
            price = float(ob['bids'][0]['price'])
            print(f"   Best bid: {price}")
            
            # Place order
            print(f"\n💰 Placing 0.01 @ {price}...")
            order = OrderArgsV2(
                token_id=token_id,
                price=price,
                size=0.01,
                side='BUY',
                expiration=0
            )
            
            signed = client.create_order(order)
            print(f"   Signed: {signed[:100] if signed else 'None'}...")
            
            resp = client.post_order(signed)
            print(f"   ✅ RESULT: {resp}")
            break
        else:
            print("   No bids")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n--- Done ---")
