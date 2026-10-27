#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')

print("=== Polymarket Force Trade (post_order) ===")
print(f"Using Wallet: {FUNDER}")

client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=1,
    funder=FUNDER,
)

if API_KEY and API_SECRET and API_PASSPHRASE:
    try:
        client.set_api_creds(ApiCreds(api_key=API_KEY, api_secret=API_SECRET, api_passphrase=API_PASSPHRASE))
    except Exception as e:
        print(f"Creds error: {e}")

# Market: Will the price of Bitcoin be above $70,000 on May 29?
# Token ID for "Yes"
token_id = "101621467528934283632456704600301715153811143182972337673199813033850688585771"
size = 5 
price = 0.998 

try:
    print(f"Attempting post_order for {size} shares at ${price}...")
    
    # post_order typically takes the same arguments as the API endpoint
    # We'll pass them as keyword arguments.
    result = client.post_order(
        tokenId=token_id,
        price=price,
        size=size,
        side="BUY"
    )
    
    print("\n✅ POST_ORDER EXECUTED")
    print(json.dumps(result, indent=2))

except Exception as e:
    print(f"\n❌ POST_ORDER FAILED: {e}")
