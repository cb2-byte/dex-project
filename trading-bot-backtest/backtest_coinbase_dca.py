"""
Backtest DCA (Dollar Cost Average) strategy on Coinbase

Strategy: Buy £10 of BTC every week, no matter the price
"""
from fetch_coinbase_data import fetch_candles, get_sample_data
from utils import print_header, print_result, format_currency

def backtest_dca(investment_per_week=10, weeks=12, product="BTC-GBP"):
    """
    Backtest DCA strategy
    
    Args:
        investment_per_week: How much GBP to invest each week
        weeks: How many weeks to simulate
        product: Trading pair to use
    """
    print_header(f"DCA Backtest: {product}")
    print(f"💰 Investment: {format_currency(investment_per_week)}/week for {weeks} weeks")
    print(f"📊 Total invested: {format_currency(investment_per_week * weeks)}")
    print()
    
    # Get price data
    data = fetch_candles(product=product, days=weeks*7)
    if not data:
        print("⚠️  Using sample data for demo...")
        data = get_sample_data()
    
    # Coinbase candles: [time, low, high, open, close, volume]
    # We want weekly data, so take every 7th candle (assuming daily data)
    weekly_prices = data[::7][:weeks]
    
    if len(weekly_prices) < weeks:
        print(f"⚠️  Only got {len(weekly_prices)} weeks of data, adjusting...")
        weeks = len(weekly_prices)
    
    # Run the strategy
    total_invested = 0
    total_btc = 0
    
    print("📅 Week-by-week breakdown:")
    print("-" * 50)
    
    for i, candle in enumerate(weekly_prices):
        timestamp = candle[0]
        price = candle[4]  # Close price
        
        # Buy £10 worth of BTC
        btc_bought = investment_per_week / price
        total_btc += btc_bought
        total_invested += investment_per_week
        
        from datetime import datetime
        date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
        
        if i < 5 or i >= weeks - 2:  # Show first 5 and last 2
            print(f"Week {i+1:2d} ({date}): £{price:,.0f}/BTC → bought {btc_bought:.6f} BTC")
        elif i == 5:
            print("...")
    
    print("-" * 50)
    
    # Calculate final value
    final_price = weekly_prices[-1][4]
    final_value = total_btc * final_price
    profit = final_value - total_invested
    profit_pct = (profit / total_invested) * 100
    
    # Show results
    print_header("RESULTS")
    print(f"💷 Total invested: {format_currency(total_invested)}")
    print(f"🪙 Total BTC owned: {total_btc:.6f}")
    print(f"📈 Final BTC price: {format_currency(final_price)}")
    print(f"💎 Portfolio value: {format_currency(final_value)}")
    print(f"📊 Profit/Loss: {format_currency(profit)} ({profit_pct:+.1f}%)")
    print(f"📉 Average buy price: {format_currency(total_invested / total_btc)}")
    
    # What if you lump-summed?
    lump_btc = total_invested / weekly_prices[0][4]
    lump_value = lump_btc * final_price
    lump_profit = lump_value - total_invested
    
    print(f"\n🎲 Comparison: Lump sum on day 1")
    print(f"   Would have: {format_currency(lump_value)} ({format_currency(lump_profit)} profit)")
    
    if profit > lump_profit:
        print("\n✅ DCA won! Smooths out volatility.")
    else:
        print("\n⚠️  Lump sum won this time — but DCA reduces risk!")
    
    return {
        "total_invested": total_invested,
        "final_value": final_value,
        "profit": profit,
        "profit_pct": profit_pct,
        "total_btc": total_btc
    }

if __name__ == "__main__":
    # Test with £10/week for 12 weeks
    # In real use, try 52 weeks (1 year) to see longer trends
    
    print("🪙 Coinbase DCA Backtest")
    print("=" * 50)
    print()
    
    # Run the backtest
    results = backtest_dca(
        investment_per_week=10,  # £10 per week
        weeks=12               # 12 weeks
    )
    
    print()
    print("📝 Notes:")
    print("- This uses historical data — past performance ≠ future results")
    print("- Real trading has fees (Coinbase ~0.5-1%)")
    print("- Try different time periods to see how DCA performs")
