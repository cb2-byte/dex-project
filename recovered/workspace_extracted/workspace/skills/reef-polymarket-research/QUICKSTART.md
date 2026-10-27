# Polymarket Research Skill

Research framework for finding edge in prediction markets.

## Setup

1. Create research journal:
```bash
cd ~/workspace/skills/reef-polymarket-research/references
touch research_journal.md thesis_library.md strategy_evolution.md
```

2. Configure paper trading:
```json
{
  "paper_balance": 10000,
  "max_position": 0.10,
  "min_edge": 0.05
}
```

## Key Commands

- Research market: Follow framework in SKILL.md
- Log trade: Update research_journal.md
- Check calibration: Review past trades vs outcomes
- Telegram update: Send to Rick (or yourself) every 4-6 hours

## Edge Formula

```
Expected Value = (Your Probability × Payout) - (Loss Probability × Stake)
```

Profit when: Your estimate > Market price + fees

## References

- research_journal.md - Trade logs
- thesis_library.md - Active/past theses  
- strategy_evolution.md - Method improvements
- source_quality.md - Rated sources
- calibration_log.md - Probability tracking