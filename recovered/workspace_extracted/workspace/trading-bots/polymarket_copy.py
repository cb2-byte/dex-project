#!/usr/bin/env python3
"""
Polymarket Copy Trading Bot - LIVE DATA VERSION

Fetches REAL market data from Polymarket APIs and shows what trades WOULD happen.
Uses your wallet: 0x98D9Dbd34d0156E6385D08d5263467601BE5e972

Usage:
    python3 polymarket_copy.py --live-test    # See real markets, no trades
    python3 polymarket_copy.py --check       # Show leaderboard
    python3 polymarket_copy.py --markets     # Show active markets
    python3 polymarket_copy.py --portfolio   # Show your portfolio
"""
import argparse
import sys
import os
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_utils import (
    load_config, load_state, save_state, setup_logging,
    format_money, send_telegram_alert
)

# Polymarket API endpoints
POLYMARKET_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

def get_polymarket_leaderboard():
    """Fetch real leaderboard from Polymarket"""
    try:
        # Try new Gamma API
        url = f"{GAMMA_API}/leaderboard"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            users = data.get('users', [])
            return [
                {
                    "address": u.get('address', ''),
                    "profit": u.get('profit', 0),
                    "volume": u.get('volume', 0),
                    "trades": u.get('numTrades', 0),
                    "win_rate": u.get('winRate', 0.5)
                }
                for u in users[:10]
            ]
        else:
            # Fallback to sample data with warning
            print("⚠️  Gamma API returned non-200, using sample data")
            return get_sample_traders()
            
    except Exception as e:
        print(f"⚠️  Couldn't fetch leaderboard: {e}")
        return get_sample_traders()

def get_sample_traders():
    """Sample data when API fails"""
    return [
        {"address": "0x742d35Cc6634C0532925a3b8D03C27F", "profit": 15000, "volume": 500000, "trades": 156, "win_rate": 0.62},
        {"address": "0x8ba1f109551bD432803012645Hac136", "profit": 8900, "volume": 320000, "trades": 89, "win_rate": 0.58},
        {"address": "0x71C7656EC7ab88b098defB751B7401B", "profit": 6200, "volume": 180000, "trades": 67, "win_rate": 0.71},
    ]

def get_user_portfolio(wallet_address):
    """Get portfolio for your specific wallet"""
    try:
        url = f"{GAMMA_API}/portfolio/{wallet_address}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"⚠️  Couldn't fetch portfolio: {e}")
        return None

def get_active_markets():
    """Get active prediction markets from Gamma API"""
    try:
        url = f"{GAMMA_API}/events"
        params = {
            "active": "true",
            "closed": "false",
            "order": "desc",
            "sort": "volume"
        }
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            events = response.json()
            
            markets = []
            for event in events.get('events', [])[:10]:
                # Get the best market (usually the first one)
                market = event.get('markets', [{}])[0]
                
                markets.append({
                    "id": event.get('id'),
                    "slug": event.get('slug'),
                    "title": event.get('title', 'Unknown'),
                    "description": event.get('description', '')[:100],
                    "category": event.get('category', 'General'),
                    "volume": event.get('volume', 0),
                    "liquidity": event.get('liquidity', 0),
                    "end_date": event.get('endDate'),
                    "yes_price": market.get('outcomePrices', {}).get('Yes', 0),
                    "no_price": market.get('outcomePrices', {}).get('No', 0),
                })
            
            return markets
        else:
            print(f"⚠️  Gamma API returned {response.status_code}")
            return get_sample_markets()
            
    except Exception as e:
        print(f"⚠️  Couldn't fetch markets: {e}")
        return get_sample_markets()

def get_sample_markets():
    """Sample markets when API fails"""
    return [
        {
            "id": "will-btc-hit-70k",
            "title": "Will BTC hit $70k by end of March?",
            "category": "Crypto",
            "volume": 250000,
            "yes_price": 0.35,
            "no_price": 0.65
        },
        {
            "id": "will-it-rain-london",
            "title": "Will it rain in London tomorrow?",
            "category": "Weather",
            "volume": 15000,
            "yes_price": 0.62,
            "no_price": 0.38
        },
        {
            "id": "fed-rate-cut",
            "title": "Will Fed cut rates in March?",
            "category": "Finance",
            "volume": 890000,
            "yes_price": 0.28,
            "no_price": 0.72
        }
    ]

def show_leaderboard(config):
    """Show real top traders"""
    print("\n🎯 POLYMARKET LIVE LEADERBOARD")
    print("=" * 70)
    
    traders = get_polymarket_leaderboard()
    
    print(f"📊 Top {len(traders)} traders (by profit):")
    print()
    
    for i, t in enumerate(traders, 1):
        print(f"{i}. {t['address'][:12]}...")
        print(f"   💰 Profit: {format_money(t['profit'])} USD")
        print(f"   📊 Volume: {format_money(t['volume'])} USD")
        print(f"   🎲 Win Rate: {t['win_rate']*100:.0f}%")
        print(f"   📈 Trades: {t['trades']}")
        print()

def show_user_portfolio(wallet_address):
    """Show YOUR portfolio on Polymarket"""
    print("\n👤 YOUR POLYMARKET PORTFOLIO")
    print("=" * 70)
    print(f"Wallet: {wallet_address}")
    print()
    
    portfolio = get_user_portfolio(wallet_address)
    
    if portfolio:
        print(f"💰 Balance: {format_money(portfolio.get('balance', 0))}")
        print(f"📊 Positions: {len(portfolio.get('positions', []))}")
        print(f"💎 P/L: {format_money(portfolio.get('profit', 0))}")
        
        positions = portfolio.get('positions', [])
        if positions:
            print("\n📋 Open Positions:")
            for pos in positions[:5]:
                print(f"   • {pos.get('market', 'Unknown')[:40]}")
                print(f"     Size: {format_money(pos.get('size', 0))}")
    else:
        print("⚠️  Couldn't fetch portfolio data")
        print("   This is normal if the wallet hasn't traded yet")
        print("   Or if the API is temporarily unavailable")

def show_markets():
    """Show active prediction markets"""
    print("\n📊 ACTIVE POLYMARKET PREDICTIONS")
    print("=" * 70)
    
    markets = get_active_markets()
    
    for i, m in enumerate(markets[:5], 1):
        yes_price = float(m.get('yes_price', 0)) * 100
        
        print(f"{i}. {m['title'][:60]}")
        print(f"   Category: {m['category']} | Volume: {format_money(m.get('volume', 0))}")
        print(f"   📈 YES: {yes_price:.0f}% | 📉 NO: {100-yes_price:.0f}%")
        
        # Show end date if available
        end_date = m.get('end_date')
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                days_left = (end - datetime.now(end.tzinfo)).days
                print(f"   ⏰ Ends: {end.strftime('%Y-%m-%d')} ({days_left} days)")
            except:
                pass
        print()

def simulate_copy_trading(config, logger):
    """Simulate copy trading with live data"""
    print("\n🚀 POLYMARKET COPY TRADING SIMULATION")
    print("=" * 70)
    
    copy_config = config.get('copy_trading', {})
    mode = config.get('mode', 'alerts')
    
    print(f"🎯 Mode: {mode.upper()}")
    print(f"💰 Max copy size: {format_money(copy_config.get('max_trade_size', 10))}")
    print(f"📊 Min confidence: {copy_config.get('min_market_confidence', 0.55)*100:.0f}%")
    print(f"🎯 Max confidence: {copy_config.get('max_market_confidence', 0.85)*100:.0f}%")
    print()
    
    # Get top traders
    print("🔍 Fetching top traders...")
    traders = get_polymarket_leaderboard()
    
    # Filter by profit threshold
    min_profit = copy_config.get('min_wallet_profit', 1000)
    qualified = [t for t in traders if t['profit'] >= min_profit]
    
    print(f"✅ {len(qualified)} traders qualify (≥{format_money(min_profit)} profit)")
    print()
    
    if not qualified:
        print("⚠️  No traders qualify for your criteria")
        print("   Try lowering min_wallet_profit in config")
        return
    
    # Get active markets
    markets = get_active_markets()
    
    for t in qualified[:3]:
        print(f"👤 {t['address'][:15]}... ({format_money(t['profit'])} profit, {t['win_rate']*100:.0f}% WR)")
        
        # Simulate finding a good market
        for m in markets[:3]:
            yes_price = float(m.get('yes_price', 0.5))
            
            # Only copy if confidence is in sweet spot
            min_conf = copy_config.get('min_market_confidence', 0.55)
            max_conf = copy_config.get('max_market_confidence', 0.85)
            
            if min_conf <= yes_price <= max_conf:
                copy_pct = copy_config.get('copy_percentage', 0.05)
                max_copy = copy_config.get('max_trade_size', 10)
                copy_size = min(10 * copy_pct, max_copy)  # Assume £10 bet
                
                if mode == 'alerts':
                    print(f"   📢 ALERT: High-confidence market!")
                    print(f"      Market: {m['title'][:40]}...")
                    print(f"      Price: {yes_price*100:.0f}%")
                    print(f"      Suggested copy: {format_money(copy_size)}")
                else:
                    print(f"   🎯 WOULD COPY: {format_money(copy_size)}")
                break
        else:
            print(f"   ⏸️  No qualifying markets found")
        print()
    
    print("=" * 70)
    print("📝 This was a SIMULATION")
    print("   Set mode: 'auto' and dry_run: false for real trading")

def main():
    parser = argparse.ArgumentParser(description="Polymarket Bot - Live Data")
    parser.add_argument("--check", action="store_true", help="Show leaderboard")
    parser.add_argument("--markets", action="store_true", help="Show active markets")
    parser.add_argument("--portfolio", action="store_true", help="Show your portfolio")
    parser.add_argument("--live-test", action="store_true", help="Run simulation")
    args = parser.parse_args()
    
    full_config = load_config()
    config = full_config.get("polymarket", {})
    logger = setup_logging(full_config.get("logging", {}))
    
    wallet = config.get("wallet_address", "0x98D9Dbd34d0156E6385D08d5263467601BE5e972")
    
    if args.check:
        show_leaderboard(config)
        return
    
    if args.markets:
        show_markets()
        return
    
    if args.portfolio:
        show_user_portfolio(wallet)
        return
    
    if args.live_test:
        simulate_copy_trading(config, logger)
        return
    
    # Default: show everything
    show_leaderboard(config)
    show_markets()
    show_user_portfolio(wallet)

if __name__ == "__main__":
    main()
