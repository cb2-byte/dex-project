"""
Fetch Coinbase historical data
Caches locally to save 5G data
"""
import requests
import json
from datetime import datetime, timedelta
from utils import save_cache, load_cache

COINBASE_API = "https://api.exchange.coinbase.com"
CACHE_FILE = "coinbase_btc_cache.json"

def fetch_candles(product="BTC-GBP", granularity=86400, days=90):
    """
    Fetch historical price data from Coinbase
    
    Args:
        product: Trading pair (BTC-GBP, ETH-GBP, etc.)
        granularity: Seconds per candle (86400 = 1 day)
        days: How many days of history
    
    Returns:
        List of candles: [timestamp, low, high, open, close, volume]
    """
    # Check cache first (saves 5G data!)
    cached = load_cache(CACHE_FILE.replace("btc", product.split("-")[0].lower()))
    if cached:
        return cached
    
    print(f"🌐 Fetching {product} data from Coinbase...")
    
    # Calculate start time
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    
    # Coinbase API endpoint
    url = f"{COINBASE_API}/products/{product}/candles"
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "granularity": granularity
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Save to cache
        cache_file = CACHE_FILE.replace("btc", product.split("-")[0].lower())
        save_cache(data, cache_file)
        
        print(f"✅ Got {len(data)} candles")
        return data
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return []

def get_sample_data():
    """
    Generate sample BTC data if offline
    Based on roughly realistic 2024-ish prices
    """
    print("📊 Using sample data (offline mode)")
    
    # Generate 90 days of sample data
    # Starting around £50k, with some volatility
    import random
    random.seed(42)  # Same results every time
    
    data = []
    price = 50000
    now = datetime.utcnow()
    
    for i in range(90):
        day = now - timedelta(days=90-i)
        timestamp = int(day.timestamp())
        
        # Random daily move (-3% to +3%)
        change = random.uniform(-0.03, 0.03)
        price = price * (1 + change)
        
        # Create candle: [time, low, high, open, close, volume]
        low = price * 0.98
        high = price * 1.02
        open_p = price * (1 + random.uniform(-0.01, 0.01))
        close = price
        volume = random.uniform(100, 500)
        
        data.append([timestamp, low, high, open_p, close, volume])
    
    return data

if __name__ == "__main__":
    print("🪙 Testing Coinbase data fetcher...")
    
    # Try real data first
    data = fetch_candles(days=30)
    
    # Fall back to sample if failed
    if not data:
        data = get_sample_data()
    
    # Show what we got
    if data:
        print(f"\nLast 5 candles:")
        for candle in data[-5:]:
            timestamp = datetime.fromtimestamp(candle[0])
            close = candle[4]
            print(f"  {timestamp.strftime('%Y-%m-%d')}: £{close:,.2f}")
