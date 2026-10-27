#!/usr/bin/env python3
"""Test the new Polymarket credentials"""

from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import ApiCreds
import json

# Load saved credentials
with open('.polymarket-keys.json') as f:
    keys = json.load(f)

# Convert to ApiCreds object
creds = ApiCreds(
    api_key=keys['apiKey'],
    api_secret=keys['secret'],
    api_passphrase=keys['passphrase']
)

PRIVATE_KEY = "0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b"
FUNDER = "0x98D9Dbd34d0156E6385D08d5263467601BE5e972"  # Your profile wallet - where the funds are!

print("🧪 Testing Polymarket API credentials...")
print("API Key:", keys['apiKey'][:8] + "...")
print("")

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=PRIVATE_KEY,
    creds=creds,
    signature_type=2,  # GNOSIS_SAFE
    funder=FUNDER
)

try:
    # Check balance
    print("📊 Checking balance...")
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    balance = client.get_balance_allowance(params=params)
    
    # Handle both dict and object responses
    if isinstance(balance, dict):
        print(f"✅ USDC Balance: {balance.get('balance', 'unknown')} USDC")
        print(f"   Allowance: {balance.get('allowance', 'unknown')} USDC")
        print(f"   Raw response: {balance}")
    else:
        print(f"✅ USDC Balance: {balance.balance} USDC")
        print(f"   Allowance: {balance.allowance} USDC")
    print("")
    
    # Find a market
    print("🔍 Finding active market...")
    markets = client.get_markets(closed=False, archived=False, limit=5)
    print(f"   Found {len(markets)} markets\n")
    
    if len(markets) > 0:
        m = markets[0]
        print(f"   Market: {m.question or m.title or 'Unknown'}")
        print(f"   Token ID: {m.condition_id or m.id}")
    
    print("\n🎉 CREDENTIALS WORK!")
    print("Your bots are ready to trade.")
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
