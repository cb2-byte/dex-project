#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""
Polymarket ETH Auto-Trading Bot with Frank-Wolfe Portfolio Optimization
UPGRADED TO LOOP ENGINEERING: Now PROPOSES trades instead of executing.
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

eth_market_cache = {"token_up": None, "token_down": None, "slug": None, "found_at": 0}

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

def find_eth_market(direction):
    try:
        if eth_market_cache["token_up"] and (time.time() - eth_market_cache["found_at"]) < 300:
            return eth_market_cache["token_up"] if direction == 'UP' else eth_market_cache["token_down"], eth_market_cache["slug"]
        
        # Try Gamma API first (finds markets before CLOB has them)
        try:
            import httpx
            r = httpx.get('https://gamma-api.polymarket.com/events?series=eth-up-or-down', timeout=10)
            if r.status_code == 200:
                data = r.json()
                events = data if isinstance(data, list) else [data]
                for event in events:
                    markets = event.get('markets', [])
                    for m in markets:
                        slug = m.get('slug', '')
                        active = m.get('active', False)
                        # Try to get token IDs from outcomes
                        outcomes = m.get('outcomes', [])
                        if active and 'updown' in slug.lower() and len(outcomes) >= 2:
                            # Get token IDs
                            token_yes = outcomes[0].get('token_id') if isinstance(outcomes[0], dict) else None
                            token_no = outcomes[1].get('token_id') if isinstance(outcomes[1], dict) else None
                            if token_yes and token_no:
                                # Verify via CLOB that we can trade
                                ob_check = httpx.get(f'https://clob.polymarket.com/orderbook?token_id={token_yes}', timeout=5)
                                if ob_check.status_code == 200:
                                    eth_market_cache["token_up"] = token_yes
                                    eth_market_cache["token_down"] = token_no
                                    eth_market_cache["slug"] = slug
                                    eth_market_cache["found_at"] = time.time()
                                    print(f"[GAMMA] Found ETH market: {slug}")
                                    return eth_market_cache["token_up"] if direction == 'UP' else eth_market_cache["token_down"], slug
        except Exception as e:
            print(f"[GAMMA] Error: {e}")
        
        # Fallback to CLOB API
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
                            eth_market_cache["token_up"] = token_up
                            eth_market_cache["token_down"] = token_down
                            eth_market_cache["slug"] = slug
                            eth_market_cache["found_at"] = time.time()
                            return eth_market_cache["token_up"] if direction == 'UP' else eth_market_cache["token_down"], slug
        
        return None, None
    except Exception as e:
        print(f"Market lookup error: {e}")
        return None, None

def propose_eth_trade(market_id, stake, direction, reasoning):
    """
    Replaces execute_eth_trade. Instead of calling the API, it writes a
    proposal to the pending directory for the Verifier to check.
    """
    try:
        if "," not in market_id:
            return None
        
        slug, token_id = market_id.split(",", 1)
        
        proposal = {
            "timestamp": datetime.now().isoformat(),
            "asset": "ETH",
            "direction": direction,
            "stake": stake,
            "token_id": token_id,
            "slug": slug,
            "reasoning": reasoning,
            "proposed_by": "eth_portfolio_trader",
            "status": "PENDING"
        }
        
        filename = f"proposal_{int(time.time())}_{token_id}.json"
        filepath = os.path.join("trades/pending", filename)
        
        with open(filepath, 'w') as f:
            json.dump(proposal, f, indent=4)
            
        return filename
        
    except Exception as e:
        print(f"[ERROR] Proposal failed: {e}")
        return None

def check_and_trade_portfolio():
    print(f"[{datetime.now()}] Starting ETH portfolio trader (PROPOSAL MODE)...")
    
    portfolio_trader.reset_daily_state()
    
    last_price = get_binance_price('ETHUSDT')
    if not last_price:
        return
    
    print(f"Initial ETH price: ${last_price:.2f}")
    
    signal_window = 120
    last_optimization = time.time()
    
    while True:
        time.sleep(CHECK_INTERVAL)
        
        current_price = get_binance_price('ETHUSDT')
        if not current_price:
            continue
        
        change_pct = ((current_price - last_price) / last_price) * 100
        
        if time.time() - last_optimization >= signal_window:
            if portfolio_trader.signals:
                print(f"[{datetime.now()}] Optimizing signals for proposal...")
                result = portfolio_trader.optimize()
                allocations = result.get('allocations', [])
                
                for alloc in allocations:
                    token_id, slug = find_eth_market(alloc['direction'])
                    if token_id:
                        # Construct reasoning for the verifier
                        reasoning = f"Signal detected {alloc['direction']} with edge {alloc['edge']:.4f}. Optimized allocation for portfolio."
                        proposal_file = propose_eth_trade(f"{slug},{token_id}", alloc['stake'], alloc['direction'], reasoning)
                        if proposal_file:
                            print(f"[PROPOSED] ETH {alloc['direction']} ${alloc['stake']} -> {proposal_file}")
                
                portfolio_trader.signals = []
            
            last_optimization = time.time()
        
        if abs(change_pct) >= MIN_CHANGE:
            direction = 'UP' if change_pct > 0 else 'DOWN'
            edge = max(0.05, min(abs(change_pct) / 100, 0.15))
            
            token_id, slug = find_eth_market(direction)
            if token_id:
                portfolio_trader.add_signal(
                    asset="ETH",
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
        import traceback
        traceback.print_exc()
