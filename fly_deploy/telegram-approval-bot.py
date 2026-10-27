#!/usr/bin/env python3
"""
Telegram Bot for Trade Approvals
Listens for /approve and /deny commands
"""

import requests
import time
import json
import os
from datetime import datetime
from py_clob_client_v2 import ClobClient
from types import SimpleNamespace

# Config
TELEGRAM_TOKEN = '8527377021:AAGGB02Cr9OjdZIxjnrdkixWBLBEsyUf5qQ'
CHAT_ID = '868123037'

# Load API keys
KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(KEYS_FILE) as f:
    poly_keys = json.load(f)

# Pending trades file
PENDING_TRADES_FILE = os.path.join(os.path.dirname(__file__), 'pending-trades.json')

def load_pending_trades():
    if os.path.exists(PENDING_TRADES_FILE):
        try:
            with open(PENDING_TRADES_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}

def remove_pending_trade(trade_id):
    trades = load_pending_trades()
    if trade_id in trades:
        del trades[trade_id]
        with open(PENDING_TRADES_FILE, 'w') as f:
            json.dump(trades, f, indent=2)
        return trades.get(trade_id)
    return None

def execute_trade(trade_data):
    """Execute the approved trade via Polymarket API"""
    try:
        creds = SimpleNamespace(
            api_key=poly_keys['apiKey'],
            api_secret=poly_keys['secret'],
            api_passphrase=poly_keys['passphrase']
        )
        
        client = ClobClient(
            host='https://clob.polymarket.com',
            chain_id=137,
            key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
            creds=creds
        )
        
        order = client.create_and_post_order(
            {
                'tokenID': trade_data['token_id'],
                'price': trade_data['price'],
                'size': trade_data['size'],
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
        
        return True, order_id
        
    except Exception as e:
        return False, str(e)

def send_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    requests.post(url, json={'chat_id': CHAT_ID, 'text': text})

def get_updates(offset=0):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates'
    params = {'offset': offset, 'timeout': 30}
    resp = requests.get(url, params=params, timeout=35)
    return resp.json()

def process_command(cmd_text):
    """Process /approve or /deny command"""
    parts = cmd_text.split()
    if len(parts) < 2:
        send_message("Usage: /approve <trade_id> or /deny <trade_id>")
        return
    
    try:
        trade_id = int(parts[1])
    except:
        send_message("Invalid trade ID. Use a number.")
        return
    
    # Load pending trades
    pending = load_pending_trades()
    
    if trade_id not in pending:
        send_message(f"Trade #{trade_id} not found or already processed.")
        return
    
    trade_data = pending[trade_id]
    
    if parts[0] == '/approve':
        # Execute the trade
        success, result = execute_trade(trade_data)
        
        if success:
            msg = f"✅ Trade #{trade_id} APPROVED & EXECUTED!\n"
            msg += f"Order ID: {result}\n"
            msg += f"Direction: {trade_data['direction']}\n"
            msg += f"Stake: {trade_data['size']} USDC"
        else:
            msg = f"❌ Trade #{trade_id} execution failed:\n{result}"
        
        remove_pending_trade(trade_id)
        send_message(msg)
        
    elif parts[0] == '/deny':
        msg = f"❌ Trade #{trade_id} DENIED"
        remove_pending_trade(trade_id)
        send_message(msg)
        
    else:
        send_message("Unknown command. Use /approve or /deny")

def run_bot():
    print(f"[{datetime.now()}] Starting Telegram approval bot...")
    send_message("🤖 Approval bot started\nSend /approve <id> or /deny <id> to manage trades")
    
    last_update_id = 0
    
    while True:
        try:
            result = get_updates(offset=last_update_id + 1)
            
            if result.get('ok') and result.get('result'):
                for update in result['result']:
                    last_update_id = update['update_id']
                    
                    # Check for message with command
                    if 'message' in update:
                        msg = update['message']
                        if msg.get('text') and msg.get('text').startswith('/'):
                            cmd = msg['text'].split()[0]
                            if cmd in ['/approve', '/deny']:
                                process_command(msg['text'])
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
        
        time.sleep(1)

if __name__ == '__main__':
    run_bot()
