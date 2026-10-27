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

print("=== Polymarket Immediate Fill v2 ===")
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

try:
    # 1. Get the current best ask price
    print(f"Fetching best ask price for token {token_id}...")
    orderbook = client.get_order_book(token_id)
    
    # The error showed that orderbook is an OrderBookSummary object, not a dict.
    # We access asks as an attribute: orderbook.asks
    asks = orderbook.asks
    if not asks:
        print("❌ No asks found in orderbook. Cannot fill immediately.")
        exit(1)
    
    # asks is a list of [price, size]
    best_ask = float(asks[0][0])
    print(f"Best ask price is ${best_ask}")

    # 2. Cancel existing open orders for this token to avoid doubles
    print("Checking for existing open orders...")
    open_orders = client.get_orders()
    for order in open_orders:
        # Handling potential object or dict types for order
        token_id_val = getattr(order, 'tokenId', None) or order.get('tokenId') if isinstance(order, dict) else None
        if token_id_val == token_id:
            order_id = getattr(order, 'orderId', None) or order.get('orderId') if isinstance(order, dict) else None
            print(f"Cancelling pending order {order_id}...")
            client.cancel_order(order_id)

    # 3. Place a new order at the best ask price
    print(f"Placing immediate fill order for {size} shares at ${best_ask}...")
    args = OrderArgs(
        token_id=token_id,
        price=best_ask,
        size=size,
        side="BUY"
    )
    
    result = client.create_order(args)
    print("\n✅ IMMEDIATE ORDER PLACED SUCCESSFULLY")
    print(f"Filled at ${best_ask}")

except Exception as e:
    print(f"\n❌ ACTION FAILED: {e}")
