#!/usr/bin/env python3
"""Check Polymarket balance with new pUSD system"""

from py_clob_client_v2 import ClobClient
from py_clob_client_v2.clob_types import ApiCreds
import json

# Load credentials
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
    signature_type=2,
    funder=FUNDER
)

print("📊 Checking Polymarket balance...")
print("Wallet:", FUNDER)
print("")

# Try different balance methods
try:
    # Method 1: Simple balance (no params)
    print("Trying get_balance_allowance()...")
    balance = client.get_balance_allowance()
    print(f"✅ Balance: {balance}")
except Exception as e1:
    print(f"❌ Method 1 failed: {e1}")
    
    try:
        # Method 2: With params
        print("\nTrying with AssetType.COLLATERAL...")
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        balance = client.get_balance_allowance(params=params)
        print(f"✅ Balance: {balance}")
    except Exception as e2:
        print(f"❌ Method 2 failed: {e2}")
        
        try:
            # Method 3: Raw endpoint
            print("\nTrying raw API call...")
            import requests
            from py_clob_client_v2.headers.headers import create_level_2_headers
            from py_clob_client_v2.signing.signer import create_signer
            
            signer = create_signer(PRIVATE_KEY)
            timestamp = int(time.time() * 1000)
            
            headers = create_level_2_headers(
                signer, creds, 
                {'method': 'GET', 'requestPath': '/balance-allowance'},
                timestamp=timestamp
            )
            
            resp = requests.get(
                'https://clob.polymarket.com/balance-allowance',
                headers=headers
            )
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.json()}")
        except Exception as e3:
            print(f"❌ Method 3 failed: {e3}")

print("\n--- Alternative: Check via public API ---")
try:
    import requests
    resp = requests.get(f'https://clob.polymarket.com/user/balance?user={FUNDER}')
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
except Exception as e:
    print(f"❌ Public API failed: {e}")
