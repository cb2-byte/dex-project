#!/usr/bin/env python3
"""Force-fill trade: Bypasses orderbook checks to test pure API execution"""

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
    signature_type=1,  # POLY_PROXY for email accounts
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'
)

print("🚀 FORCE-FILL TRADE TEST")
print(f"Wallet: 0x98D9Dbd...\n")

# 1. Verify connectivity and balance
print("📊 Checking balance...")
try:
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    balance = client.get_balance_allowance(params=params)
    print(f"   Balance: {balance}")
except Exception as e:
    print(f"   Balance check failed: {e}")

# 2. Find any market that is simply "accepting orders"
print("\n🔍 Finding a market that accepts orders (skipping orderbook check)...")
result = client.get_markets()
markets = result.get('data', []) if isinstance(result, dict) else result

target_token = None
target_name = ""

for m in markets[:100]:
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
    
    if token_id:
        target_token = token_id
        target_name = m.get('question', 'Unknown Market')[:60]
        break

if not target_token:
    print("❌ No markets found that are accepting orders.")
    exit(1)

print(f"   Target Market: {target_name}")
print(f"   Token ID: {target_token}")

# 3. Place a 'Force-Fill' order
# Price 0.99 for a BUY is almost guaranteed to fill if the market is open
print(f"\n💰 Attempting Force-Fill: BUY $0.50 @ 0.99...")
try:
    order = OrderArgsV2(
        token_id=target_token,
        price=0.99,
        size=0.50,
        side='BUY',
        expiration=0
    )
    
    print("   Signing order...")
    signed = client.create_order(order)
    print(f"   Signed ✅")
    
    print("   Posting to CLOB...")
    resp = client.post_order(signed)
    
    print(f"\n🎉 RESULT:")
    print(f"   {resp}")
    
except Exception as e:
    print(f"\n❌ EXECUTION FAILED:")
    print(f"   {e}")
    import traceback
    traceback.print_exc()

print("\n--- Done ---")
