#!/usr/bin/env python3
"""
Polymarket Chainlink Auto-Trading Bot (SILENT)
Monitors LINK price and auto-trades on Polymarket CLOB
Only alerts on successful executions
"""

import requests
import time
import json
import os
from datetime import datetime
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient

# Load API keys
KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(KEYS_FILE) as f:
    keys = json.load(f)

# Polymarket CLOB Client
creds = SimpleNamespace(
    api_key=keys['apiKey'],
    api_secret=keys['secret'],
    api_passphrase=keys['passphrase']
)

client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds
)

# Trading config
STAKE_USDC = 2
MIN_CHANGE = 0.15
CHECK_INTERVAL = 60

# Market discovery cache
link_market_cache = {"token_up": None, "token_down": None, "slug": None, "found_at": 0}

def get_binance_price(symbol='LINKUSDT'):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        resp = requests.get(url, timeout=5)
        return float(resp.json()['price'])
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None

def get_balance():
    try:
        result = client.get_balance_allowance()
        return float(result.get('balance', 0))
    except Exception as e:
        print(f"Balance check skipped: {e}")
        return 999999

def send_telegram_alert(message):
    try:
        token = '8527377021:AAFfUppTGj8EU8v4GBtMztAoOVbYVKNcQ4s'
        chat_id = '868123037'
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        requests.post(url, json={'chat_id': chat_id, 'text': message})
    except Exception as e:
        print(f"Telegram error: {e}")

def find_link_market(direction):
    try:
        # Check cache (valid 5 min)
        if link_market_cache["token_up"] and (time.time() - link_market_cache["found_at"]) < 300:
            return link_market_cache["token_up"] if direction == 'UP' else link_market_cache["token_down"], link_market_cache["slug"]
        
        result = client.get_sampling_simplified_markets()
        markets = result.get('data', []) if isinstance(result, dict) else result
        
        for m in markets:
            title = m.get('title', '').upper()
            if 'LINK' in title and 'UP' in title and 'DOWN' in title and '5M' in title:
                if m.get('active') and m.get('accepting_orders'):
                    outcomes = m.get('outcomes', [])
                    if len(outcomes) >= 2:
                        slug = m.get('slug', '')
                        link_market_cache["token_up"] = outcomes[0].get('token_id')
                        link_market_cache["token_down"] = outcomes[1].get('token_id')
                        link_market_cache["slug"] = slug
                        link_market_cache["found_at"] = time.time()
                        print(f"Found LINK market: {m.get('title')}")
                        return outcomes[0].get('token_id') if direction == 'UP' else outcomes[1].get('token_id'), slug
        
        return None, None
    except Exception as e:
        print(f"LINK market lookup error: {e}")
        return None, None

def place_trade(direction, change_pct, current_price):
    """AUTO-EXECUTE trade on Polymarket"""
    try:
        token_id, slug = find_link_market(direction)
        
        if not token_id:
            # No market available - don't alert, just log and return
            print(f"No active LINK market found for {direction}")
            return False
        
        # Price based on direction
        price = 0.65 if direction == 'UP' else 0.35
        
        # AUTO-EXECUTE ORDER
        order = client.create_and_post_order(
            {
                'tokenID': token_id,
                'price': price,
                'size': STAKE_USDC,
                'side': 0,
                'expiration': 0
            },
            {
                'tickSize': '0.01',
                'negRisk': False
            }
        )
        
        order_id = order.get('orderID', 'N/A')
        if isinstance(order_id, str):
            order_id = order_id[:8] + '...'
        
        # Send confirmation AFTER execution
        msg = f"🔗 LINK TRADE EXECUTED\n\n"
        msg += f"Direction: {direction}\n"
        msg += f"Change: {change_pct:+.2f}%\n"
        msg += f"Price: ${current_price:.2f}\n"
        msg += f"Stake: {STAKE_USDC} USDC\n"
        msg += f"Order: {order_id}\n\n"
        msg += f"Market: https://polymarket.com/event/{slug}"
        
        print(msg)
        send_telegram_alert(msg)
        return True
        
    except Exception as e:
        msg = f"❌ LINK trade failed: {str(e)[:150]}"
        print(msg)
        send_telegram_alert(msg)
        return False

def check_and_trade():
    print(f"[{datetime.now()}] Starting LINK auto-trader (SILENT MODE)...")
    send_telegram_alert("🔗 LINK bot started (Autonomous)\nAlerts on executions only")
    
    last_price = get_binance_price('LINKUSDT')
    if not last_price:
        print("Failed to get initial price")
        return
    
    print(f"Initial LINK price: ${last_price:.2f}")
    
    while True:
        time.sleep(CHECK_INTERVAL)
        current_price = get_binance_price('LINKUSDT')
        if not current_price:
            continue
        
        change_pct = ((current_price - last_price) / last_price) * 100
        
        if abs(change_pct) >= MIN_CHANGE:
            direction = 'UP' if change_pct > 0 else 'DOWN'
            print(f"[{datetime.now()}] SIGNAL: LINK {direction} {change_pct:+.2f}%")
            
            # AUTO-EXECUTE (no approval needed)
            if place_trade(direction, change_pct, current_price):
                last_price = current_price
        else:
            print(f"[{datetime.now()}] No signal ({change_pct:+.2f}%)")

if __name__ == '__main__':
    balance = get_balance()
    print(f"USDC Balance: {balance:.2f}")
    
    if balance < STAKE_USDC:
        print(f"Warning: Balance may be insufficient ({STAKE_USDC} USDC needed)")
        send_telegram_alert(f"⚠️ LINK bot started with low balance: {balance:.2f} USDC")
    
    check_and_trade()
