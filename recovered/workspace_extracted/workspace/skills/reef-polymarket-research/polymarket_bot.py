#!/usr/bin/env python3
"""
Polymarket Paper Trading Bot - Research Framework
Colin's prediction market research tool
"""
import json
import os
from datetime import datetime
from pathlib import Path

# Paths
SKILL_DIR = Path.home() / "workspace" / "skills" / "reef-polymarket-research"
JOURNAL_FILE = SKILL_DIR / "references" / "research_journal.md"
THESIS_FILE = SKILL_DIR / "references" / "thesis_library.md"

# Paper trading config
CONFIG = {
    "paper_balance": 10000.00,
    "max_position": 0.10,  # 10% max per trade
    "min_edge": 0.05,     # 5% minimum edge
    "fee_rate": 0.02      # 2% Polymarket fee
}

def calculate_edge(your_prob, market_price):
    """Calculate trading edge"""
    fee_adjusted = market_price + CONFIG["fee_rate"]
    edge = your_prob - fee_adjusted
    return edge

def kelly_size(your_prob, market_price, bankroll):
    """Kelly criterion for position sizing (quarter Kelly)"""
    if market_price <= 0:
        return 0
    
    odds = (1 / market_price) - 1  # Decimal odds
    
    # Full Kelly
    if odds <= 0:
        return 0
    
    f_star = (your_prob * (odds + 1) - 1) / odds
    
    # Quarter Kelly (conservative)
    quarter_kelly = f_star / 4
    
    # Cap at max position size
    max_size = bankroll * CONFIG["max_position"]
    kelly_amount = bankroll * max(0, quarter_kelly)
    
    return min(kelly_amount, max_size)

def log_trade(market, direction, entry, your_prob, edge, size, thesis):
    """Log a paper trade to the journal"""
    
    # Read current journal
    with open(JOURNAL_FILE, 'r') as f:
        content = f.read()
    
    # Find trade number
    trade_num = content.count("| # |") + 1
    
    # Create trade entry
    trade_entry = f"""
## Trade #{trade_num} - {datetime.now().strftime('%Y-%m-%d')}

**Market**: {market}
**Direction**: {direction}
**Entry Price**: ${entry:.2f}
**My Probability**: {your_prob*100:.1f}%
**Market Price**: ${entry:.2f}
**Edge**: {edge*100:.1f}%
**Position Size**: ${size:.2f}
**Status**: OPEN

### Thesis
{thesis}

### Key Factors
- [Add your research points here]

### What Would Change My Mind
- [Add falsification criteria]

### Expected Value
- Win: ${size * ((1/entry) - 1):.2f}
- Loss: ${size:.2f}
- Expected: ${size * (your_prob * ((1/entry) - 1) - (1 - your_prob)):.2f}

---
"""
    
    # Append to journal
    with open(JOURNAL_FILE, 'a') as f:
        f.write(trade_entry)
    
    print(f"✅ Trade #{trade_num} logged to research journal")
    return trade_num

def quick_analysis():
    """Quick market analysis helper"""
    print("\n" + "="*60)
    print("🎯 POLYMARKET RESEARCH BOT")
    print("="*60)
    
    print("\n📊 Paper Trading Config:")
    print(f"   Balance: ${CONFIG['paper_balance']:,.2f}")
    print(f"   Max position: {CONFIG['max_position']*100:.0f}%")
    print(f"   Min edge: {CONFIG['min_edge']*100:.0f}%")
    print(f"   Fee rate: {CONFIG['fee_rate']*100:.0f}%")
    
    print("\n💡 Quick Edge Calculator:")
    print("   (Press Enter with no input to skip)")
    
    while True:
        market = input("\n📝 Market name: ").strip()
        if not market:
            break
        
        try:
            market_price = float(input("💰 Market price (e.g., 0.65 for 65%): "))
            your_prob = float(input("🎯 Your probability (e.g., 0.72 for 72%): "))
            
            edge = calculate_edge(your_prob, market_price)
            
            print(f"\n📊 Analysis:")
            print(f"   Market price: ${market_price:.2f} ({market_price*100:.1f}%)")
            print(f"   Your estimate: {your_prob*100:.1f}%")
            print(f"   Fee-adjusted: ${market_price + CONFIG['fee_rate']:.2f}")
            print(f"   Edge: {edge*100:+.1f}%")
            
            if edge >= CONFIG['min_edge']:
                print(f"   ✅ Edge > {CONFIG['min_edge']*100:.0f}% - POTENTIAL TRADE!")
                
                # Calculate position size
                size = kelly_size(your_prob, market_price, CONFIG['paper_balance'])
                print(f"   💰 Suggested size: ${size:.2f}")
                
                log_it = input("\n📝 Log this trade? (y/n): ").lower()
                if log_it == 'y':
                    direction = "YES" if your_prob > market_price else "NO"
                    thesis = input("📝 Brief thesis (one line): ")
                    log_trade(market, direction, market_price, your_prob, edge, size, thesis)
                    
            elif edge > 0:
                print(f"   ⚠️  Edge positive but < {CONFIG['min_edge']*100:.0f}% - skip")
            else:
                print(f"   ❌ No edge - market is efficient or you disagree")
                
        except ValueError:
            print("   ⚠️  Invalid input, try again")

def show_journal():
    """Display current journal"""
    with open(JOURNAL_FILE, 'r') as f:
        print(f.read())

def main():
    """Main menu"""
    print("\n🎯 Polymarket Research Bot - Colin's Paper Trading")
    
    while True:
        print("\n" + "="*40)
        print("1. Quick Analysis (calculate edge)")
        print("2. View Journal")
        print("3. Exit")
        print("="*40)
        
        choice = input("\nChoose: ").strip()
        
        if choice == '1':
            quick_analysis()
        elif choice == '2':
            show_journal()
        elif choice == '3':
            print("\nGood luck with your research! 🎯")
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main()
