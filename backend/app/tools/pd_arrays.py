"""
PD Array Observation Tools.

Analyzes price action to identify Fair Value Gaps, Order Blocks, Breaker Blocks,
Premium/Discount zones, and OTE levels. Pure observation - no trading signals.
"""
from typing import List, Optional


def detect_fvg(candles: List[dict]) -> List[dict]:
    """
    Detect Fair Value Gaps (imbalances).

    A FVG is a 3-candle pattern where there's a gap between candle 1 and candle 3,
    indicating an imbalance that price may return to fill.

    Bullish FVG: candle_1.high < candle_3.low (gap up)
    Bearish FVG: candle_1.low > candle_3.high (gap down)

    Args:
        candles: List of OHLCV candles

    Returns:
        [
            {
                "type": "BULLISH_FVG" | "BEARISH_FVG",
                "index": int,  # Index of the middle candle
                "top": float,
                "bottom": float,
                "midpoint": float,
                "size": float,
                "filled": bool,
                "time": str,
                "observation": str
            },
            ...
        ]
    """
    fvgs = []

    if len(candles) < 3:
        return fvgs

    current_price = candles[-1]["close"]

    for i in range(2, len(candles)):
        candle_1 = candles[i - 2]
        candle_2 = candles[i - 1]
        candle_3 = candles[i]

        # Bullish FVG: gap up
        if candle_1["high"] < candle_3["low"]:
            top = candle_3["low"]
            bottom = candle_1["high"]
            midpoint = (top + bottom) / 2
            size = top - bottom

            # Check if FVG has been filled by subsequent price action
            filled = any(
                c["low"] <= midpoint
                for c in candles[i+1:]
            ) if i + 1 < len(candles) else False

            fvgs.append({
                "type": "BULLISH_FVG",
                "index": i - 1,
                "top": round(top, 5),
                "bottom": round(bottom, 5),
                "midpoint": round(midpoint, 5),
                "size": round(size, 5),
                "filled": filled,
                "time": candle_2.get("time", str(i - 1)),
                "observation": (
                    f"Bullish FVG at index {i-1}: {bottom:.5f} - {top:.5f} "
                    f"(size: {size:.5f}, {'filled' if filled else 'unfilled'})"
                )
            })

        # Bearish FVG: gap down
        if candle_1["low"] > candle_3["high"]:
            top = candle_1["low"]
            bottom = candle_3["high"]
            midpoint = (top + bottom) / 2
            size = top - bottom

            filled = any(
                c["high"] >= midpoint
                for c in candles[i+1:]
            ) if i + 1 < len(candles) else False

            fvgs.append({
                "type": "BEARISH_FVG",
                "index": i - 1,
                "top": round(top, 5),
                "bottom": round(bottom, 5),
                "midpoint": round(midpoint, 5),
                "size": round(size, 5),
                "filled": filled,
                "time": candle_2.get("time", str(i - 1)),
                "observation": (
                    f"Bearish FVG at index {i-1}: {bottom:.5f} - {top:.5f} "
                    f"(size: {size:.5f}, {'filled' if filled else 'unfilled'})"
                )
            })

    return fvgs


def detect_order_blocks(candles: List[dict], min_move_pips: float = 20.0) -> List[dict]:
    """
    Detect Order Blocks.

    An Order Block is the last opposing candle before a significant move.
    It represents where institutional orders were placed.

    Bullish OB: Last bearish candle before a strong bullish move
    Bearish OB: Last bullish candle before a strong bearish move

    Args:
        candles: List of OHLCV candles
        min_move_pips: Minimum move size to qualify as significant

    Returns:
        [
            {
                "type": "BULLISH_OB" | "BEARISH_OB",
                "index": int,
                "high": float,
                "low": float,
                "body_high": float,
                "body_low": float,
                "subsequent_move": float,
                "time": str,
                "observation": str
            },
            ...
        ]
    """
    order_blocks = []
    min_move = min_move_pips * 0.0001

    if len(candles) < 5:
        return order_blocks

    for i in range(len(candles) - 3):
        candle = candles[i]
        is_bullish = candle["close"] > candle["open"]
        is_bearish = candle["close"] < candle["open"]

        # Look at next 3 candles for significant move
        future_candles = candles[i + 1:i + 4]

        if is_bearish:
            # Check for bullish move after bearish candle
            highest_after = max(c["high"] for c in future_candles)
            move = highest_after - candle["high"]

            if move >= min_move:
                order_blocks.append({
                    "type": "BULLISH_OB",
                    "index": i,
                    "high": candle["high"],
                    "low": candle["low"],
                    "body_high": candle["open"],
                    "body_low": candle["close"],
                    "subsequent_move": round(move, 5),
                    "time": candle.get("time", str(i)),
                    "observation": (
                        f"Bullish Order Block at index {i}: "
                        f"{candle['low']:.5f} - {candle['high']:.5f}, "
                        f"followed by {move * 10000:.1f} pip move up"
                    )
                })

        elif is_bullish:
            # Check for bearish move after bullish candle
            lowest_after = min(c["low"] for c in future_candles)
            move = candle["low"] - lowest_after

            if move >= min_move:
                order_blocks.append({
                    "type": "BEARISH_OB",
                    "index": i,
                    "high": candle["high"],
                    "low": candle["low"],
                    "body_high": candle["close"],
                    "body_low": candle["open"],
                    "subsequent_move": round(move, 5),
                    "time": candle.get("time", str(i)),
                    "observation": (
                        f"Bearish Order Block at index {i}: "
                        f"{candle['low']:.5f} - {candle['high']:.5f}, "
                        f"followed by {move * 10000:.1f} pip move down"
                    )
                })

    return order_blocks


def detect_breaker_blocks(candles: List[dict]) -> List[dict]:
    """
    Detect Breaker Blocks.

    A Breaker Block is a failed Order Block - an OB that was broken through.
    The OB then becomes a level that may act as support/resistance from the other side.

    Args:
        candles: List of OHLCV candles

    Returns:
        [
            {
                "type": "BULLISH_BREAKER" | "BEARISH_BREAKER",
                "original_ob_index": int,
                "break_index": int,
                "zone_high": float,
                "zone_low": float,
                "observation": str
            },
            ...
        ]
    """
    breakers = []
    order_blocks = detect_order_blocks(candles)

    for ob in order_blocks:
        ob_idx = ob["index"]

        # Look for subsequent break of the OB
        for i in range(ob_idx + 3, len(candles)):
            candle = candles[i]

            if ob["type"] == "BULLISH_OB":
                # Bullish OB broken = price closes below OB low
                if candle["close"] < ob["low"]:
                    # This becomes a bearish breaker (resistance when retested)
                    breakers.append({
                        "type": "BEARISH_BREAKER",
                        "original_ob_index": ob_idx,
                        "break_index": i,
                        "zone_high": ob["high"],
                        "zone_low": ob["low"],
                        "observation": (
                            f"Bearish Breaker: Bullish OB at {ob_idx} broken at {i}, "
                            f"zone {ob['low']:.5f} - {ob['high']:.5f} now resistance"
                        )
                    })
                    break

            elif ob["type"] == "BEARISH_OB":
                # Bearish OB broken = price closes above OB high
                if candle["close"] > ob["high"]:
                    # This becomes a bullish breaker (support when retested)
                    breakers.append({
                        "type": "BULLISH_BREAKER",
                        "original_ob_index": ob_idx,
                        "break_index": i,
                        "zone_high": ob["high"],
                        "zone_low": ob["low"],
                        "observation": (
                            f"Bullish Breaker: Bearish OB at {ob_idx} broken at {i}, "
                            f"zone {ob['low']:.5f} - {ob['high']:.5f} now support"
                        )
                    })
                    break

    return breakers


def check_premium_discount(
    current_price: float,
    range_high: float,
    range_low: float
) -> dict:
    """
    Determine if price is in Premium or Discount zone.

    The dealing range is split at equilibrium (50%):
    - Premium: Upper half (50-100%)
    - Discount: Lower half (0-50%)

    Smart money buys in discount, sells in premium.

    Args:
        current_price: Current market price
        range_high: High of the dealing range
        range_low: Low of the dealing range

    Returns:
        {
            "zone": "PREMIUM" | "DISCOUNT" | "EQUILIBRIUM",
            "level": float,  # 0.0 to 1.0
            "equilibrium": float,  # Price at 50%
            "distance_from_eq": float,
            "observation": str
        }
    """
    if range_high == range_low:
        return {
            "zone": "EQUILIBRIUM",
            "level": 0.5,
            "equilibrium": range_high,
            "distance_from_eq": 0,
            "observation": "Range has no size (high = low)"
        }

    range_size = range_high - range_low
    level = (current_price - range_low) / range_size
    equilibrium = (range_high + range_low) / 2
    distance_from_eq = current_price - equilibrium

    if level > 0.52:
        zone = "PREMIUM"
    elif level < 0.48:
        zone = "DISCOUNT"
    else:
        zone = "EQUILIBRIUM"

    return {
        "zone": zone,
        "level": round(level, 3),
        "equilibrium": round(equilibrium, 5),
        "distance_from_eq": round(distance_from_eq, 5),
        "observation": (
            f"Price at {level * 100:.1f}% of range ({zone}). "
            f"Equilibrium: {equilibrium:.5f}, "
            f"{'above' if distance_from_eq > 0 else 'below'} by {abs(distance_from_eq):.5f}"
        )
    }


def calculate_ote(swing_high: float, swing_low: float, direction: str) -> dict:
    """
    Calculate Optimal Trade Entry (OTE) Fibonacci levels.

    OTE is the 62%-79% retracement zone, considered optimal for entries
    in the direction of the trend.

    Args:
        swing_high: The swing high price
        swing_low: The swing low price
        direction: "BULLISH" (retracement down for long) or "BEARISH" (retracement up for short)

    Returns:
        {
            "direction": str,
            "ote_zone": {"top": float, "mid": float, "bottom": float},
            "fib_levels": {
                "0.0": float,
                "0.382": float,
                "0.5": float,
                "0.618": float,
                "0.705": float,
                "0.79": float,
                "1.0": float
            },
            "observation": str
        }
    """
    range_size = swing_high - swing_low

    fib_levels = {
        "0.0": swing_low if direction == "BULLISH" else swing_high,
        "0.382": swing_high - (range_size * 0.382) if direction == "BULLISH" else swing_low + (range_size * 0.382),
        "0.5": (swing_high + swing_low) / 2,
        "0.618": swing_high - (range_size * 0.618) if direction == "BULLISH" else swing_low + (range_size * 0.618),
        "0.705": swing_high - (range_size * 0.705) if direction == "BULLISH" else swing_low + (range_size * 0.705),
        "0.79": swing_high - (range_size * 0.79) if direction == "BULLISH" else swing_low + (range_size * 0.79),
        "1.0": swing_high if direction == "BULLISH" else swing_low
    }

    # Round all levels
    fib_levels = {k: round(v, 5) for k, v in fib_levels.items()}

    if direction == "BULLISH":
        ote_zone = {
            "top": fib_levels["0.618"],
            "mid": fib_levels["0.705"],
            "bottom": fib_levels["0.79"]
        }
    else:
        ote_zone = {
            "top": fib_levels["0.79"],
            "mid": fib_levels["0.705"],
            "bottom": fib_levels["0.618"]
        }

    return {
        "direction": direction,
        "ote_zone": ote_zone,
        "fib_levels": fib_levels,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "observation": (
            f"{direction} OTE zone: {ote_zone['bottom']:.5f} - {ote_zone['top']:.5f} "
            f"(midpoint: {ote_zone['mid']:.5f})"
        )
    }
