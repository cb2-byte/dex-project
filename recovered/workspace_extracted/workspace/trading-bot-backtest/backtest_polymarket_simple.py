"""
Backtest simple Polymarket strategy

Since Polymarket doesn't have a public API for historical data,
this uses realistic sample data to teach the concepts.

Strategy: Only bet when confidence is > 60% (house edge simulation)
"""
import random
from datetime import datetime, timedelta
from utils import print_header, print_result, format_currency

def generate_polymarket_sample(days=90):
    """
    Generate sample Polymarket-like predictions
    
    In real Polymarket:
    - Prices = probability (0.50 = 50%)
    - You buy YES at price, win £1 if correct, lose if wrong
    - Or buy NO at (1-price), win £1 if correct
    """
    print("📊 Generating sample prediction market data...")
    
    random.seed(42)  # Same results every time
    events = []
    
    # Create some fake prediction events
    event_types = [
        "Will it rain in Jersey tomorrow?",
        "BTC price up this week?",
        "Will ETH break £2000?",
        "Will it snow in December?",
    ]
    
    start_date = datetime.now() - timedelta(days=days)
    
    for i in range(days):
        date = start_date + timedelta(days=i)
        
        # Pick random event type
        event_type = random.choice(event_types)
        
        # Market probability (0.10 to 0.90)
        # Higher = more likely to happen according to market
        market_prob = random.uniform(0.20, 0.80)
        
        # Actual outcome (random, but slightly correlated to probability)
        # This simulates "the market is kinda right but not always"
        actual_prob = market_prob + random.uniform(-0.15, 0.15)
        actual_prob = max(0, min(1, actual_prob))  # Clamp to 0-1
        outcome = random.random() < actual_prob
        
        events.append({
            "date": date,
            "event": event_type,
            "market_prob": market_prob,  # Price you can buy at
            "outcome": outcome,  # What actually happened
            "actual_prob": actual_prob  # True probability (hidden in real life)
        })
    
    return events

def backtest_polymarket_strategy(
    starting_bankroll=100,
    bet_size=5,
    min_confidence=0.60,  # Only bet if market says >60% likely
    days=90
):
    """
    Backtest a simple Polymarket strategy
    
    Strategy:
    - Only bet YES when market probability > min_confidence
    - Bet fixed amount each time
    - Win £1 per £1 invested if correct, lose all if wrong
    """
    print_header("Polymarket Strategy Backtest")
    print(f"💰 Starting bankroll: {format_currency(starting_bankroll)}")
    print(f"🎲 Bet size: {format_currency(bet_size)}")
    print(f"📊 Min confidence: {min_confidence*100:.0f}%")
    print(f"📅 Testing over: {days} days")
    print()
    
    # Generate sample data
    events = generate_polymarket_sample(days=days)
    
    # Run the strategy
    bankroll = starting_bankroll
    bets_made = 0
    bets_won = 0
    total_profit = 0
    
    print("📅 Sample of bets placed:")
    print("-" * 60)
    
    for event in events:
        market_prob = event["market_prob"]
        
        # Strategy: Only bet if market is confident
        if market_prob >= min_confidence:
            if bankroll < bet_size:
                print(f"💸 Out of money on {event['date'].strftime('%Y-%m-%d')}!")
                break
            
            # Place bet on YES (it'll happen)
            # Cost = bet_size, potential win = bet_size / market_prob (roughly £1 per share)
            # Simplified: you win £1 per share if correct
            shares = bet_size / market_prob
            cost = bet_size
            
            bankroll -= cost
            
            if event["outcome"]:
                # Won! Get £1 per share
                winnings = shares
                profit = winnings - cost
                bankroll += winnings
                bets_won += 1
                total_profit += profit
                result = "✅ WON"
            else:
                # Lost it all
                profit = -cost
                total_profit += profit
                result = "❌ LOST"
            
            bets_made += 1
            
            # Show some bets
            if bets_made <= 5 or (bets_made > 15 and bets_made <= 17):
                print(f"{event['date'].strftime('%Y-%m-%d')} | {event['event'][:25]:25} | "
                      f"Bet: {format_currency(cost)} at {market_prob*100:.0f}% | {result} | "
                      f"Bankroll: {format_currency(bankroll)}")
            elif bets_made == 6:
                print("...")
    
    print("-" * 60)
    
    # Calculate results
    win_rate = (bets_won / bets_made * 100) if bets_made > 0 else 0
    total_return = ((bankroll - starting_bankroll) / starting_bankroll) * 100
    
    print_header("RESULTS")
    print(f"💷 Starting bankroll: {format_currency(starting_bankroll)}")
    print(f"💎 Ending bankroll: {format_currency(bankroll)}")
    print(f"📊 Total profit/loss: {format_currency(bankroll - starting_bankroll)}")
    print(f"📈 Return: {total_return:+.1f}%")
    print()
    print(f"🎲 Bets placed: {bets_made}")
    print(f"✅ Bets won: {bets_won}")
    print(f"📉 Win rate: {win_rate:.1f}%")
    
    # Analysis
    print()
    print("📝 What this means:")
    if total_return > 0:
        print(f"   This strategy made money in this simulation!")
        print(f"   But remember: sample data ≠ real markets")
    else:
        print(f"   This strategy lost money in this simulation.")
        print(f"   Trying to be smarter than the market is hard!")
    
    print()
    print("⚠️  Real Polymarket notes:")
    print("   - Fees take 2% of winnings")
    print("   - You need to be RIGHT, not just confident")
    print("   - Markets are pretty efficient — hard to beat")
    
    return {
        "starting_bankroll": starting_bankroll,
        "ending_bankroll": bankroll,
        "profit": bankroll - starting_bankroll,
        "return_pct": total_return,
        "bets_made": bets_made,
        "bets_won": bets_won,
        "win_rate": win_rate
    }

if __name__ == "__main__":
    print("🎯 Polymarket Strategy Backtest")
    print("=" * 50)
    print()
    
    # Run the backtest
    results = backtest_polymarket_strategy(
        starting_bankroll=100,  # £100 starting
        bet_size=5,             # £5 per bet
        min_confidence=0.60,    # Only bet when >60% confident
        days=90                 # 90 days of events
    )
    
    print()
    print("🎓 Try changing the parameters:")
    print("   - What if min_confidence = 0.70? (Only bet on sure things)")
    print("   - What if bet_size = £10? (Bigger bets)")
    print("   - What if you bet on LOW confidence events? (Contrarian)")
