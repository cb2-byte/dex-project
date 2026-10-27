#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""
Polymarket LINK Auto-Trading Bot
"""

import sys
sys.stdout.flush()

import requests
import time
import json
import os
from datetime import datetime
from types import SimpleNamespace
from py_clob_client_v2 import ClobClient, OrderArgsV2

from portfolio_trader import PortfolioTrader, PortfolioConfig

KEYS_FILE = os.path.join(os.path.dirname(__file__), '.polymarket-keys.json')
with open(KEYS_FILE) as f:
    keys = json.load(f)

creds = SimpleNamespace(api_key=keys['apiKey'], api_secret=keys['secret'], api_passphrase=keys['passphrase'])
client = ClobClient(
    host='https://clob.polymarket.com',
    chain_id=137,
    key='0xd2aad0f4a95a4e2b8d5090613fb95c278fcddb506616096d49df5d4c39859a3b',
    creds=creds,
    signature_type=1,  # POLY_PROXY for email-login accounts
    funder='0x98D9Dbd34d0156E6385D08d5263467601BE5e972'  # Your Polymarket wallet
)

CHECK_INTERVAL = 60
MIN_CHANGE = 0.001

link_market_cache = {"token_up": None, "token_down": None, "slug": None, "found_at": 0}

portfolio_config = PortfolioConfig(
    total_budget=100.0,
    max_daily_exposure=100.0,
    max_per_trade=50.0,
    max_bankroll_pct=0.30,
    paper_mode=False
)
portfolio_trader = PortfolioTrader(portfolio_config)

def get_binance_price(symbol):
    try:
        resp = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}', timeout=5)
        if resp.status_code == 200:
            return float(resp.json()['price'])
    except:
        pass
    return None

def find_link_market(direction):
    try:
        if link_market_cache["token_up"] and (time.time() - link_market_cache["found_at"]) < 300:
            return link_market_cache["token_up"] if direction == 'UP' else link_market_cache["token_down"], link_market_cache["slug"]
        
        result = client.get_markets()
        markets = result.get('data', []) if isinstance(result, dict) else result
        
        # Crypto/finance keywords
        keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'token', 'fed', 'rate', 'fdv', 'launch', 'binance', 'coinbase', 'defi']
        
        for m in markets:
            if m.get('accepting_orders'):
                slug = m.get('market_slug', '') or m.get('slug', '')
                title = (m.get('title', '') or m.get('question', '')).lower()
                
                # Check if market matches crypto/finance keywords
                if not any(kw in slug.lower() or kw in title for kw in keywords):
                    continue
                
                tokens = m.get('tokens', [])
                if len(tokens) >= 2:
                    if slug:
                        token_up = tokens[0].get('token_id') if isinstance(tokens[0], dict) else tokens[0]
                        token_down = tokens[1].get('token_id') if isinstance(tokens[1], dict) else tokens[1]
                        if token_up and token_down:
                            link_market_cache["token_up"] = token_up
                            link_market_cache["token_down"] = token_down
                            link_market_cache["slug"] = slug
                            link_market_cache["found_at"] = time.time()
                            return link_market_cache["token_up"] if direction == 'UP' else link_market_cache["token_down"], slug
        
        return None, None
    except Exception as e:
        return None, None

def execute_link_trade(market_id, stake, direction):
    try:
        if "," not in market_id:
            return None, None
        
        slug, token_id = market_id.split(",", 1)
        if not token_id:
            return None, None
        
        # Verify orderbook exists before placing order
        import requests
        ob_resp = requests.get(f'https://clob.polymarket.com/orderbook?token_id={token_id}', timeout=5)
        if ob_resp.status_code != 200:
            # Orderbook doesn't exist - invalidate cache
            link_market_cache["token_up"] = None
            link_market_cache["token_down"] = None
            link_market_cache["found_at"] = 0
            print(f"[WARN] Orderbook not found for {token_id}, cache invalidated")
            return None, None
        
        price = 0.65 if direction == 'UP' else 0.35
        
        order_args = OrderArgsV2(
            token_id=token_id,
            price=price,
            size=stake,
            side='BUY'
        )
        
        result = client.create_and_post_order(order_args, {})
        return result, slug
        
    except Exception as e:
        return None, None

def check_and_trade_portfolio():
    print(f"[{datetime.now()}] Starting LINK portfolio trader...")
    
    portfolio_trader.reset_daily_state()
    
    last_price = get_binance_price('LINKUSDT')
    if not last_price:
        return
    
    print(f"Initial LINK price: ${last_price:.2f}")
    
    signal_window = 120
    last_optimization = time.time()
    
    while True:
        time.sleep(CHECK_INTERVAL)
        
        current_price = get_binance_price('LINKUSDT')
        if not current_price:
            continue
        
        change_pct = ((current_price - last_price) / last_price) * 100
        
        if time.time() - last_optimization >= signal_window:
            if portfolio_trader.signals:
                print(f"[{datetime.now()}] Optimizing...")
                result = portfolio_trader.optimize()
                allocations = result.get('allocations', [])
                
                for alloc in allocations:
                    token_id, slug = find_link_market(alloc['direction'])
                    if token_id:
                        order_id, _ = execute_link_trade(f"{slug},{token_id}", alloc['stake'], alloc['direction'])
                        if order_id:
                            print(f"[EXECUTED] LINK {alloc['direction']} ${alloc['stake']}")
                
                portfolio_trader.signals = []
            
            last_optimization = time.time()
        
        if abs(change_pct) >= MIN_CHANGE:
            direction = 'UP' if change_pct > 0 else 'DOWN'
            edge = max(0.05, min(abs(change_pct) / 100, 0.15))
            
            token_id, slug = find_link_market(direction)
            if token_id:
                portfolio_trader.add_signal(
                    asset="LINK",
                    direction=direction,
                    edge=edge,
                    confidence=0.75,
                    market_id=f"{slug},{token_id}"
                )
            
            last_price = current_price

if __name__ == "__main__":
    try:
        check_and_trade_portfolio()
    except KeyboardInterrupt:
        print("\nStopped")
    except Exception as e:
        print(f"Fatal error: {e}")
