#!/usr/bin/env python3
"""
3-Day Trading Bot Test Runner
Runs every 6 hours, logs all activity
"""
import subprocess
import os
from datetime import datetime

# Create test log
LOG_FILE = "bot_test_3day.log"

# Run the bot with all output
result = subprocess.run(
    ["python3", "-W", "ignore", "coinbase_dca.py", "--live-test"],
    capture_output=True,
    text=True,
    cwd=os.path.dirname(os.path.abspath(__file__))
)

# Log with timestamp
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

with open(LOG_FILE, "a") as f:
    f.write(f"\n{'='*60}\n")
    f.write(f"RUN: {timestamp}\n")
    f.write(f"{'='*60}\n")
    f.write(result.stdout)
    if result.stderr:
        f.write(f"\n[STDERR]: {result.stderr}\n")
    f.write(f"\nExit code: {result.returncode}\n")
    f.write(f"{'='*60}\n\n")

# Also print to console
print(f"Test logged at {timestamp}")
print(f"Check: tail -20 {LOG_FILE}")
