#!/usr/bin/env python3
"""Debug what the Python client actually returns"""

from py_clob_client_v2 import ClobClient
import json

PRIVATE_KEY = "0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b"
FUNDER = "0x7eBA28fCa6c899156e086797FeaF378db552ed66"

print("🔑 Creating API credentials via Python client...")
print("")

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=PRIVATE_KEY,
    funder=FUNDER
)

try:
    import random
    nonce = random.randint(100000, 999999)
    print(f"Using nonce: {nonce}")
    
    creds = client.create_api_key(nonce=nonce)
    
    print("\n=== RAW CREDENTIALS OBJECT ===")
    print("Type:", type(creds))
    print("Dir:", dir(creds))
    print("")
    print("Str:", str(creds))
    print("Repr:", repr(creds))
    print("")
    
    # Try all possible attribute names
    for attr in ['apiKey', 'key', 'api_key', 'secret', 'passphrase', 'api_secret', 'api_passphrase']:
        try:
            val = getattr(creds, attr, None)
            print(f"{attr}: {val}")
        except:
            print(f"{attr}: <error accessing>")
    
    # Try dict access
    try:
        print("\nAs dict:", dict(creds))
    except:
        pass
    
    try:
        print("As JSON:", creds.__dict__)
    except:
        pass
    
except Exception as e:
    print(f"❌ Failed: {e}")
    import traceback
    traceback.print_exc()
