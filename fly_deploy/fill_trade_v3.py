#!/usr/local/bin/python3
import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

# Load config
BOT_DIR = '/Users/colinbrennan/.openclaw/workspace/bots'
load_dotenv(os.path.join(BOT_DIR, '.env'))

HOST = "https://clob.polymarket.com"
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
FUNDER = os.getenv('WALLET_ADDRESS')

print("=== Polymarket Aggressive Fill v3 ===")
print(f"Using Wallet: {FUNDER}")

client = ClobClient(
    HOST,
    key=PRIVATE_KEY,
    chain_id=137,
    signature_type=1,
    funder=FUNDER,
)

token_id = "16748857912398914355191833003518205315915666088521477047521226979492030162264"
size = 5 
price = 1.00 # Maximum possible price to force fill

try:
    # 1. Cancel existing open orders for this token to avoid doubles
    print("Checking for existing open orders...")
    open_orders = client.get_orders()
    for order in open_orders:
        token_id_val = getattr(order, 'tokenId', None) or order.get('tokenId') if isinstance(order, dict) else None
        if token_id_val == token_id:
            order_id = getattr(order, 'orderId', None) or order.get('orderId') if isinstance(order, dict) else None
            print(f"Cancelling pending order {order_id}...")
            client.cancel_order(order_id)

    # 2. Place a new order at $1.00
    print(f"Placing aggressive fill order for {size} shares at ${price}...")
    args = OrderArgs(
        token_id=token_id,
        price=price,
        size=size,
        side="BUY"
    )
    
    result = client.create_order(args)
    print("\n✅ AGGRESSIVE ORDER PLACED SUCCESSFULLY")
    print(f"Bid price set to ${price} to force immediate fill.")

except Exception as e:
    print(f"\n❌ ACTION FAILED: {e}")
