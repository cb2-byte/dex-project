#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, ApiCreds

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
API_PASSPHRASE = os.getenv('API_PASSPHRASE')

print("=== Polymarket Sanity Trade ===")
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
# Outcome: Yes (Token ID 101621467528934283632456704600301715153811143182972337673199813033850688585771)
token_id = "101621467528934283632456704600301715153811143182972337673199813033850688585771"
size = 5 
price = 0.998 # Best ask was 0.997, so 0.998 is an aggressive fill

try:
    # Cancel any existing orders for this token
    print("Cleaning up existing orders...")
    try:
        open_orders = client.get_orders()
        for order in open_orders:
            t_id = getattr(order, 'tokenId', None) or order.get('tokenId') if isinstance(order, dict) else None
            if t_id == token_id:
                o_id = getattr(order, 'orderId', None) or order.get('orderId') if isinstance(order, dict) else None
                client.cancel_order(o_id)
    except Exception as e:
        print(f"Note: Order cleanup failed ({e}), proceeding anyway...")

    print(f"Placing immediate fill order for {size} shares at ${price}...")
    args = OrderArgs(
        token_id=token_id,
        price=price,
        size=size,
        side="BUY"
    )
    
    result = client.create_order(args)
    print("\n✅ ORDER PLACED SUCCESSFULLY")
    print(f"Filled at ${price} for token {token_id}")

except Exception as e:
    print(f"\n❌ ACTION FAILED: {e}")
