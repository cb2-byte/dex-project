#!/usr/bin/env python3
"""Test Polymarket credentials using Python client"""

from py_clob_client_v2 import ClobClient
import json

PRIVATE_KEY = "0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b"
FUNDER = "0x7eBA28fCa6c899156e086797FeaF378db552ed66"

print("🔑 Creating API credentials via Python client...")
print("Signer:", "0x7eBA28fCa6c899156e086797FeaF378db552ed66")
print("")

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=PRIVATE_KEY,
    funder=FUNDER
)

try:
    # Try to derive first (in case key exists)
    print("Attempting to derive existing key (nonce=777816)...")
    creds = client.derive_api_key(nonce=777816)
    
    if creds and creds.apiKey:
        print("\n✅ Derived credentials:")
        print("API Key:   ", creds.apiKey)
        print("Secret:    ", creds.secret)
        print("Passphrase:", creds.passphrase)
        
        # Save to file
        with open('.polymarket-keys.json', 'w') as f:
            json.dump({
                'apiKey': creds.apiKey,
                'secret': creds.secret,
                'passphrase': creds.passphrase,
                'nonce': 777816
            }, f, indent=2)
        
        print("\n✅ Saved to .polymarket-keys.json")
        
        # Test balance
        print("\n--- Testing ---")
        balance = client.get_balance_allowance(asset_type="COLLATERAL")
        print("Balance:", balance.balance if hasattr(balance, 'balance') else balance, "USDC")
        print("\n🎉 WORKING!")
    else:
        print("❌ Derive returned no apiKey")
        print("Response:", creds)
        
except Exception as e:
    print(f"❌ Derive failed: {e}")
    print("\nTrying to create new key...")
    
    try:
        import random
        nonce = random.randint(100000, 999999)
        print(f"Using nonce: {nonce}")
        
        creds = client.create_api_key(nonce=nonce)
        
        print("\n✅ Created credentials:")
        print("API Key:   ", creds.apiKey if hasattr(creds, 'apiKey') else creds.get('apiKey'))
        print("Secret:    ", creds.secret if hasattr(creds, 'secret') else creds.get('secret'))
        print("Passphrase:", creds.passphrase if hasattr(creds, 'passphrase') else creds.get('passphrase'))
        print("Nonce:     ", nonce)
        
        api_key = creds.apiKey if hasattr(creds, 'apiKey') else creds.get('apiKey')
        secret = creds.secret if hasattr(creds, 'secret') else creds.get('secret')
        passphrase = creds.passphrase if hasattr(creds, 'passphrase') else creds.get('passphrase')
        
        with open('.polymarket-keys.json', 'w') as f:
            json.dump({
                'apiKey': api_key,
                'secret': secret,
                'passphrase': passphrase,
                'nonce': nonce
            }, f, indent=2)
        
        print("\n✅ Saved to .polymarket-keys.json")
        
    except Exception as e2:
        print(f"❌ Create also failed: {e2}")
        print("\nWe need to create credentials via Polymarket UI")
