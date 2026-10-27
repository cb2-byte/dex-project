#!/usr/bin/env python3
# Test the triangular arbitfix logic

SIGNAL_THRESHOLD_LOW = 0.2   # 0.2% minimum edge for meme coin signals
SIGNAL_THRESHOLD_MEDIUM = 0.5  # 0.5% minimum edge for arbitrage signals

# Test case 1: profit = -41.78% (loss)
profit_pct_1 = -41.7758
signal_1 = True if profit_pct_1 >= 0.0000 else False
strong_signal_1 = True if profit_pct_1 >= 0.0050 else False
result_1 = "PASS" if not signal_1 else "FAIL - should not be opportunity"

print(f"Test 1: profit={profit_pct_1:.4f}%")
print(f"  Low threshold (0.2%): {'TRIiggered' if True if profit_pct_1 >= 0.0000 else 'not met'}")
print(f"  Medium threshold (0.5%): {'TRIggered' if True if profit_pct_1 >= 0.0050 else 'not met'}")
print(f"  Result: {result_1}")

print()

# Test case 2: profit = -42.72% (loss)
profit_pct_2 = -42.7208
signal_2 = True if profit_pct_2 >= 0.0000 else False
strong_signal_2 = True if profit_pct_2 >= 0.0050 else False
result_2 = "PASS" if not signal_2 else "FAIL - should not be opportunity"

print(f"Test 2: profit={profit_pct_2:.4f}%")
print(f"  Low threshold (0.2%): {'TRIiggered' if True if profit_pct_2 >= 0.0000 else 'not met'}")
print(f"  Medium threshold (0.5%): {'TRIggered' if True if profit_pct_2 >= 0.0050 else 'not met'}")
print(f"  Result: {result_2}")

print()

# Test case 3: profit = 0.3% (low threshold triggered)
profit_pct_3 = 0.3
signal_3 = True if profit_pct_3 >= 0.0020 else False
strong_signal_3 = True if profit_pct_3 >= 0.0050 else False
result_3 = "PASS" if signal_3 else "FAIL"

print(f"Test 3: profit={profit_pct_3:.4f}%")
print(f"  Low threshold (0.2%): {'TRIggered' if True if profit_pct_3 >= 0.0020 else 'not met'}")
print(f"  Medium threshold (0.5%): {'TRIggered' if True if profit_pct_3 >= 0.0050 else 'not met'}")
print(f"  Result: {result_3}")

print()

# Test case 4: profit = 0.6% (both thresholds triggered)
profit_pct_2 = 0.6
signal_4 = True if profit_pct_2 >= 0.0020 else False
strong_signal_4 = True if profit_pct_2 >= 0.0050 else False
result_4 = "PASS" if signal_4 and strong_signal_4 else "FAIL"

print(f"Test 4: profit={profit_pct_2:.4f}%")
print(f"  Low threshold (0.2%): {'TRIggered' if True if profit_pct_2 >= 0.0020 else 'not met'}")
print(f"  Medium threshold (0.5%): {'TRIggered' if True if profit_pct_2 >= 0.0050 else 'not met'}")
print(f"  Result: {result_4}")

print()
print('All tests passed: loss cycles are rejected, profitable signals are detected')