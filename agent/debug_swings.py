"""Debug script to test FVG and sweep detection."""
import sys
sys.path.insert(0, '.')

from src.tools import (
    identify_swing_points, get_market_structure, detect_fvg, 
    scan_liquidity_sweeps, check_pd_array, calculate_ote_fib
)
from main import create_sample_snapshot

snapshot = create_sample_snapshot()
candles_15m = snapshot["timeframe_bars"]["15M"]
bias = "BULLISH"

print(f"\n=== 15M Candles ({len(candles_15m)} total) ===")
for i, c in enumerate(candles_15m):
    print(f"{i}: O={c['open']:.5f} H={c['high']:.5f} L={c['low']:.5f} C={c['close']:.5f}")

print("\n=== Swing Points ===")
swings = identify_swing_points(candles_15m)
print(f"Swing Highs: {swings['swing_highs']}")
print(f"Swing Lows: {swings['swing_lows']}")

print("\n=== Market Structure ===")
result = get_market_structure(candles_15m)
print(f"Bias: {result['bias']}")
print(f"Structure: {result['structure']}")

print("\n=== FVG Detection ===")
fvgs = detect_fvg(candles_15m)
print(f"Found {len(fvgs)} FVGs:")
for fvg in fvgs:
    print(f"  {fvg['type']} at index {fvg['index']}: {fvg['bottom']:.5f} - {fvg['top']:.5f}")

print("\n=== Liquidity Sweeps ===")
sweeps = scan_liquidity_sweeps(candles_15m, swings)
print(f"Found {len(sweeps)} sweeps:")
for sweep in sweeps:
    print(f"  {sweep['type']} at swing {sweep['swing_price']:.5f}")

print("\n=== PD Array Check ===")
current_price = candles_15m[-1]["close"]
range_high = max(c["high"] for c in candles_15m[-20:])
range_low = min(c["low"] for c in candles_15m[-20:])
pd_result = check_pd_array(current_price, range_high, range_low, bias)
print(f"Zone: {pd_result['zone']}, Level: {pd_result['level']}, Favorable: {pd_result['favorable']}")

print("\n=== OTE Zone ===")
ote = calculate_ote_fib(range_high, range_low, bias)
print(f"OTE: {ote}")
