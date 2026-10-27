"""
Utils - helper functions for backtesting
Don't need to understand this, just import it
"""
import json
import os
from datetime import datetime, timedelta

def save_cache(data, filename):
    """Save data to cache file (saves bandwidth on 5G)"""
    with open(filename, 'w') as f:
        json.dump(data, f)
    print(f"💾 Cached data to {filename}")

def load_cache(filename, max_age_hours=24):
    """Load data from cache if it exists and isn't too old"""
    if not os.path.exists(filename):
        return None
    
    # Check age
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(filename))
    if age > timedelta(hours=max_age_hours):
        print(f"⚠️  Cache too old ({age.days} days), fetching fresh data...")
        return None
    
    with open(filename, 'r') as f:
        print(f"📂 Using cached data ({filename})")
        return json.load(f)

def format_currency(amount):
    """Show money nicely"""
    return f"£{amount:,.2f}"

def format_percent(amount):
    """Show percentage nicely"""
    return f"{amount:+.2f}%"

def print_header(text):
    """Make headers look nice"""
    print(f"\n{'='*50}")
    print(f"  {text}")
    print(f"{'='*50}")

def print_result(label, value, good_if_positive=True):
    """Print results with color hints (well, emoji hints)"""
    emoji = "✅" if (value >= 0 and good_if_positive) else "⚠️ "
    print(f"{emoji} {label}: {value}")
