"""
Market Structure Observation Tools.

Analyzes price action to identify swing points, structure, displacement,
and market structure shifts. Pure observation - no trading signals.
"""
from typing import List, Optional, Tuple


def get_swing_points(candles: List[dict], lookback: int = 2) -> dict:
    """
    Identify swing highs and swing lows using fractal logic.

    A swing high is a candle with highs lower on both sides.
    A swing low is a candle with lows higher on both sides.

    Args:
        candles: List of OHLCV candles [{open, high, low, close, time}, ...]
        lookback: Number of candles on each side to confirm swing (default 2)

    Returns:
        {
            "swing_highs": [{"index": int, "price": float, "time": str}, ...],
            "swing_lows": [{"index": int, "price": float, "time": str}, ...],
            "latest_swing_high": {"index", "price", "time"} | None,
            "latest_swing_low": {"index", "price", "time"} | None
        }
    """
    swing_highs = []
    swing_lows = []

    if len(candles) < (lookback * 2 + 1):
        return {
            "swing_highs": [],
            "swing_lows": [],
            "latest_swing_high": None,
            "latest_swing_low": None
        }

    for i in range(lookback, len(candles) - lookback):
        high = candles[i]["high"]
        low = candles[i]["low"]
        candle_time = candles[i].get("time", str(i))

        # Check swing high: higher than all neighbors
        is_swing_high = all(
            high >= candles[i - j]["high"] and high >= candles[i + j]["high"]
            for j in range(1, lookback + 1)
        )
        if is_swing_high:
            swing_highs.append({
                "index": i,
                "price": high,
                "time": candle_time
            })

        # Check swing low: lower than all neighbors
        is_swing_low = all(
            low <= candles[i - j]["low"] and low <= candles[i + j]["low"]
            for j in range(1, lookback + 1)
        )
        if is_swing_low:
            swing_lows.append({
                "index": i,
                "price": low,
                "time": candle_time
            })

    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "latest_swing_high": swing_highs[-1] if swing_highs else None,
        "latest_swing_low": swing_lows[-1] if swing_lows else None
    }


def get_market_structure(candles: List[dict], lookback: int = 2) -> dict:
    """
    Analyze market structure to identify trend characteristics.

    Looks for Higher Highs/Higher Lows (bullish) or Lower Highs/Lower Lows (bearish).

    Args:
        candles: List of OHLCV candles
        lookback: Swing detection lookback

    Returns:
        {
            "structure": "HH_HL" | "LH_LL" | "MIXED" | "UNCLEAR",
            "swing_sequence": [{"type": "HH"|"HL"|"LH"|"LL", "price": float}, ...],
            "last_two_highs": [price, price] | None,
            "last_two_lows": [price, price] | None,
            "observation": "Human-readable structure description"
        }
    """
    swings = get_swing_points(candles, lookback)
    highs = swings["swing_highs"]
    lows = swings["swing_lows"]

    result = {
        "structure": "UNCLEAR",
        "swing_sequence": [],
        "last_two_highs": None,
        "last_two_lows": None,
        "observation": ""
    }

    if len(highs) < 2 or len(lows) < 2:
        result["observation"] = f"Insufficient swings: {len(highs)} highs, {len(lows)} lows"
        return result

    # Get last two of each
    last_two_highs = [highs[-2]["price"], highs[-1]["price"]]
    last_two_lows = [lows[-2]["price"], lows[-1]["price"]]

    result["last_two_highs"] = last_two_highs
    result["last_two_lows"] = last_two_lows

    # Determine structure
    higher_high = last_two_highs[1] > last_two_highs[0]
    higher_low = last_two_lows[1] > last_two_lows[0]
    lower_high = last_two_highs[1] < last_two_highs[0]
    lower_low = last_two_lows[1] < last_two_lows[0]

    # Build swing sequence
    sequence = []
    if higher_high:
        sequence.append({"type": "HH", "price": last_two_highs[1]})
    elif lower_high:
        sequence.append({"type": "LH", "price": last_two_highs[1]})

    if higher_low:
        sequence.append({"type": "HL", "price": last_two_lows[1]})
    elif lower_low:
        sequence.append({"type": "LL", "price": last_two_lows[1]})

    result["swing_sequence"] = sequence

    # Classify structure
    if higher_high and higher_low:
        result["structure"] = "HH_HL"
        result["observation"] = (
            f"Bullish structure: Higher High at {last_two_highs[1]:.5f} "
            f"(prev {last_two_highs[0]:.5f}), Higher Low at {last_two_lows[1]:.5f} "
            f"(prev {last_two_lows[0]:.5f})"
        )
    elif lower_high and lower_low:
        result["structure"] = "LH_LL"
        result["observation"] = (
            f"Bearish structure: Lower High at {last_two_highs[1]:.5f} "
            f"(prev {last_two_highs[0]:.5f}), Lower Low at {last_two_lows[1]:.5f} "
            f"(prev {last_two_lows[0]:.5f})"
        )
    else:
        result["structure"] = "MIXED"
        result["observation"] = (
            f"Mixed structure: High moved {'up' if higher_high else 'down'}, "
            f"Low moved {'up' if higher_low else 'down'}"
        )

    return result


def detect_displacement(candles: List[dict], atr_multiplier: float = 2.0) -> List[dict]:
    """
    Detect displacement candles (strong momentum moves).

    A displacement candle has a body size greater than ATR × multiplier,
    indicating aggressive buying or selling.

    Args:
        candles: List of OHLCV candles
        atr_multiplier: Body must be > ATR × this value (default 2.0)

    Returns:
        [
            {
                "index": int,
                "direction": "BULLISH" | "BEARISH",
                "body_size": float,
                "atr": float,
                "ratio": float,  # body_size / atr
                "time": str,
                "observation": str
            },
            ...
        ]
    """
    if len(candles) < 14:
        return []

    # Calculate ATR (14-period)
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    atr = sum(true_ranges[-14:]) / 14

    displacements = []
    for i, candle in enumerate(candles):
        body_size = abs(candle["close"] - candle["open"])

        if body_size > atr * atr_multiplier:
            direction = "BULLISH" if candle["close"] > candle["open"] else "BEARISH"
            ratio = body_size / atr if atr > 0 else 0

            displacements.append({
                "index": i,
                "direction": direction,
                "body_size": body_size,
                "atr": atr,
                "ratio": round(ratio, 2),
                "time": candle.get("time", str(i)),
                "observation": (
                    f"{direction} displacement at index {i}: "
                    f"body {body_size:.5f} = {ratio:.1f}x ATR"
                )
            })

    return displacements


def detect_mss(candles: List[dict], swing_points: Optional[dict] = None) -> Optional[dict]:
    """
    Detect Market Structure Shift.

    An MSS occurs when price closes beyond a previous swing point,
    indicating a potential trend reversal.

    Args:
        candles: List of OHLCV candles
        swing_points: Pre-computed swings (optional, will compute if not provided)

    Returns:
        {
            "detected": True,
            "type": "BULLISH_MSS" | "BEARISH_MSS",
            "break_level": float,
            "break_candle_index": int,
            "close_price": float,
            "observation": str
        } | None
    """
    if len(candles) < 5:
        return None

    if swing_points is None:
        swing_points = get_swing_points(candles)

    highs = swing_points.get("swing_highs", [])
    lows = swing_points.get("swing_lows", [])

    if not highs or not lows:
        return None

    recent_candle = candles[-1]
    last_swing_high = highs[-1]["price"]
    last_swing_low = lows[-1]["price"]

    # Bullish MSS: close above last swing high
    if recent_candle["close"] > last_swing_high:
        return {
            "detected": True,
            "type": "BULLISH_MSS",
            "break_level": last_swing_high,
            "break_candle_index": len(candles) - 1,
            "close_price": recent_candle["close"],
            "observation": (
                f"Bullish MSS: Price closed at {recent_candle['close']:.5f} "
                f"above swing high {last_swing_high:.5f}"
            )
        }

    # Bearish MSS: close below last swing low
    if recent_candle["close"] < last_swing_low:
        return {
            "detected": True,
            "type": "BEARISH_MSS",
            "break_level": last_swing_low,
            "break_candle_index": len(candles) - 1,
            "close_price": recent_candle["close"],
            "observation": (
                f"Bearish MSS: Price closed at {recent_candle['close']:.5f} "
                f"below swing low {last_swing_low:.5f}"
            )
        }

    return None
