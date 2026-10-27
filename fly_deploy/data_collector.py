#!/Library/Frameworks/Python.framework/Versions/3.14/bin/python3
"""
Market Data Collector for Backtrader
Fetches historical OHLCV data from Binance to fuel the Verifier's backtests.
"""

import requests
import pandas as pd
import os
from datetime import datetime, timedelta

DATA_DIR = "trades/data"

def fetch_binance_history(symbol, interval='1h', days=30):
    print(f"Fetching {days} days of {interval} data for {symbol}...")
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    url = f"https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 1000
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_asset_volume', 'number_of_trades', 
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # Convert timestamp to readable date
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Save to CSV for Backtrader
        filename = f"{symbol.lower()}_{interval}.csv"
        filepath = os.path.join(DATA_DIR, filename)
        df.to_csv(filepath, index=False)
        print(f"Successfully saved to {filepath}")
        return filepath
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

if __name__ == "__main__":
    # We need data for the assets our bots trade
    symbols = ['ETHUSDT', 'BTCUSDT']
    for s in symbols:
        fetch_binance_history(s)
