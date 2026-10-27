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

print("=== Polymarket Aggressive Fill v5 ===")
print(f"Using Wallet: {FUNDER}")

# Initialize Client
client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=1,
    funder=FUNDER,
)

# Explicitly set API credentials for REST endpoints
if API_KEY and API_SECRET and API_PASSPHRASE:
    print("Setting API credentials...")
    try:
        client.set_api_creds(ApiCreds(api_key=API_KEY, api_secret=API_SECRET, api_passphrase=API_PASSPHRASE))
    except Exception as e:
        print(f"Warning: Could not set API creds: {e}")

token_id = "16748857912398914355191833003518205315915666088521477047521226979492030162264"
size = 5 
price = 0.999 # Adjusted to max allowed by API

try:
    # 1. Try to cancel existing open orders
    print("Checking for existing open orders...")
    try:
        open_orders = client.get_orders()
        for order in open_orders:
            token_id_val = getattr(order, 'tokenId', None) or order.get('tokenId') if isinstance(order, dict) else None
            if token_id_val == token_id:
                order_id = getattr(order, 'orderId', None) or order.get('orderId') if isinstance(order, dict) else None
                print(f"Cancelling pending order {order_id}...")
                client.cancel_order(order_id)
    except Exception as e:
        print(f"Note: Could not clear old orders ({e}). Proceeding to create new order...")

    # 2. Place aggressive fill order
    print(f"Placing aggressive fill order for {size} shares at ${price}...")
    args = OrderArgs(
        token_id=token_id,
        price=price,
        size=size,
        side="BUY"
    )
    
    result = client.create_order(args)
    print("\n✅ AGGRESSIVE ORDER PLACED SUCCESSFULLY")
    print(f"Bid price set to ${price} (max allowed).")

except Exception as e:
    print(f"\n❌ ACTION FAILED: {e}")
