"""
Market Observers - Pure Fact Extraction (The Eyes)

These functions observe the market and return OBJECTIVE FACTS ONLY.
NO opinions, NO bias, NO trading signals, NO "favorable" judgments.

The LLM (brain) interprets these facts against strategy playbooks.

Design Principles:
1. Functions return only observable data
2. No decision-making or interpretation
3. No "good/bad", "bullish/bearish" labels on data
4. Only factual relationships: "higher", "lower", "equal"
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo


# =============================================================================
# 1. Price Structure Observation
# =============================================================================

def observe_price_structure(candles: List[Dict], lookback: int = 2) -> Dict[str, Any]:
    """
    Observe swing points and structural relationships.
    
    Returns raw swing points without bias interpretation.
    The LLM decides if this constitutes "bullish" or "bearish" structure.
    
    Args:
        candles: List of OHLCV dicts (must be sorted by time, oldest first)
        lookback: Number of candles on each side to confirm swing
        
    Returns:
        Dict with swing points and factual relationships
    """
    result = {
        "swing_highs": [],
        "swing_lows": [],
        "highest_high": None,
        "lowest_low": None,
        "latest_high_relation": "unknown",
        "latest_low_relation": "unknown",
        "candle_count": len(candles)
    }
    
    if len(candles) < (lookback * 2 + 1):
        return result
    
    # Find swing highs and lows using fractal logic
    for i in range(lookback, len(candles) - lookback):
        current = candles[i]
        high = current.get("high", current.get("h", 0))
        low = current.get("low", current.get("l", 0))
        time_val = current.get("timestamp") or current.get("time")
        
        # Check swing high
        is_swing_high = True
        for j in range(1, lookback + 1):
            left_high = candles[i - j].get("high", candles[i - j].get("h", 0))
            right_high = candles[i + j].get("high", candles[i + j].get("h", 0))
            if high < left_high or high < right_high:
                is_swing_high = False
                break
        
        if is_swing_high:
            result["swing_highs"].append({
                "index": i,
                "price": high,
                "time": str(time_val) if time_val else None
            })
        
        # Check swing low
        is_swing_low = True
        for j in range(1, lookback + 1):
            left_low = candles[i - j].get("low", candles[i - j].get("l", 0))
            right_low = candles[i + j].get("low", candles[i + j].get("l", 0))
            if low > left_low or low > right_low:
                is_swing_low = False
                break
        
        if is_swing_low:
            result["swing_lows"].append({
                "index": i,
                "price": low,
                "time": str(time_val) if time_val else None
            })
    
    # Calculate range extremes
    if candles:
        highs = [c.get("high", c.get("h", 0)) for c in candles]
        lows = [c.get("low", c.get("l", 0)) for c in candles]
        result["highest_high"] = max(highs) if highs else None
        result["lowest_low"] = min(lows) if lows else None
    
    # Determine latest swing relationships (factual, not opinion)
    swing_highs = result["swing_highs"]
    swing_lows = result["swing_lows"]
    
    if len(swing_highs) >= 2:
        last = swing_highs[-1]["price"]
        prev = swing_highs[-2]["price"]
        if last > prev:
            result["latest_high_relation"] = "higher"
        elif last < prev:
            result["latest_high_relation"] = "lower"
        else:
            result["latest_high_relation"] = "equal"
    
    if len(swing_lows) >= 2:
        last = swing_lows[-1]["price"]
        prev = swing_lows[-2]["price"]
        if last > prev:
            result["latest_low_relation"] = "higher"
        elif last < prev:
            result["latest_low_relation"] = "lower"
        else:
            result["latest_low_relation"] = "equal"
    
    return result


# =============================================================================
# 2. Imbalance (FVG) Observation
# =============================================================================

def observe_imbalances(candles: List[Dict]) -> Dict[str, Any]:
    """
    Find Fair Value Gaps (FVGs) - raw coordinates only.
    
    A bullish FVG: candle[i].low > candle[i-2].high
    A bearish FVG: candle[i].high < candle[i-2].low
    
    Returns coordinates without labeling them as "good entry" or "signal".
    
    Args:
        candles: List of OHLCV dicts (sorted by time)
        
    Returns:
        Dict with bullish and bearish FVG lists
    """
    result = {
        "bullish_fvgs": [],
        "bearish_fvgs": [],
        "total_fvgs": 0
    }
    
    if len(candles) < 3:
        return result
    
    for i in range(2, len(candles)):
        curr = candles[i]
        prev_2 = candles[i - 2]
        
        curr_low = curr.get("low", curr.get("l", 0))
        curr_high = curr.get("high", curr.get("h", 0))
        prev_2_high = prev_2.get("high", prev_2.get("h", 0))
        prev_2_low = prev_2.get("low", prev_2.get("l", 0))
        time_val = curr.get("timestamp") or curr.get("time")
        
        # Bullish FVG: gap up (current low > 2-bars-ago high)
        if curr_low > prev_2_high:
            result["bullish_fvgs"].append({
                "top": curr_low,
                "bottom": prev_2_high,
                "midpoint": (curr_low + prev_2_high) / 2,
                "size": curr_low - prev_2_high,
                "index": i,
                "time": str(time_val) if time_val else None
            })
        
        # Bearish FVG: gap down (current high < 2-bars-ago low)
        elif curr_high < prev_2_low:
            result["bearish_fvgs"].append({
                "top": prev_2_low,
                "bottom": curr_high,
                "midpoint": (prev_2_low + curr_high) / 2,
                "size": prev_2_low - curr_high,
                "index": i,
                "time": str(time_val) if time_val else None
            })
    
    result["total_fvgs"] = len(result["bullish_fvgs"]) + len(result["bearish_fvgs"])
    return result


# =============================================================================
# 3. Session Time Observation
# =============================================================================

def observe_session_time(timestamp: datetime) -> Dict[str, Any]:
    """
    Report current time context - no opinion on tradability.
    
    All session times are based on EST (America/New_York).
    
    Args:
        timestamp: UTC datetime (offset-aware preferred)
        
    Returns:
        Dict with time facts and session status
    """
    # Ensure timestamp is UTC
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
    else:
        timestamp = timestamp.astimezone(ZoneInfo("UTC"))
    
    # Convert to EST
    est_tz = ZoneInfo("America/New_York")
    est_time = timestamp.astimezone(est_tz)
    est_hour = est_time.hour
    est_minute = est_time.minute
    
    # Session definitions (EST)
    # Asia: 18:00 - 00:00 (Sunday evening through overnight)
    # London: 02:00 - 11:00
    # New York: 07:00 - 16:00
    
    asia_active = est_hour >= 18 or est_hour < 3
    london_active = 2 <= est_hour < 11
    new_york_active = 7 <= est_hour < 16
    
    # Kill Zone definitions (EST)
    london_kz = 2 <= est_hour < 5
    ny_kz = 7 <= est_hour < 10
    
    # Silver Bullet windows (EST)
    silver_bullet_am = est_hour == 10  # 10:00 - 11:00
    silver_bullet_pm = est_hour == 14  # 14:00 - 15:00
    
    return {
        "utc_time": timestamp.isoformat(),
        "est_time": est_time.isoformat(),
        "est_hour": est_hour,
        "est_minute": est_minute,
        "day_of_week": est_time.strftime("%A"),
        "is_weekend": est_time.weekday() >= 5,
        "sessions": {
            "asia": {
                "active": asia_active,
                "description": "18:00-03:00 EST"
            },
            "london": {
                "active": london_active,
                "description": "02:00-11:00 EST"
            },
            "new_york": {
                "active": new_york_active,
                "description": "07:00-16:00 EST"
            }
        },
        "killzones": {
            "london_kz": {
                "active": london_kz,
                "description": "02:00-05:00 EST"
            },
            "new_york_kz": {
                "active": ny_kz,
                "description": "07:00-10:00 EST"
            }
        },
        "special_windows": {
            "silver_bullet_am": {
                "active": silver_bullet_am,
                "description": "10:00-11:00 EST"
            },
            "silver_bullet_pm": {
                "active": silver_bullet_pm,
                "description": "14:00-15:00 EST"
            }
        }
    }


# =============================================================================
# 4. Liquidity Levels Observation
# =============================================================================

def observe_liquidity_levels(
    candles: List[Dict],
    structure: Optional[Dict] = None,
    days_back: int = 2
) -> Dict[str, Any]:
    """
    Report significant price levels - no opinion on importance.
    
    Args:
        candles: List of OHLCV dicts (should include multiple days)
        structure: Optional pre-computed structure from observe_price_structure
        days_back: How many days to look back for PDH/PDL
        
    Returns:
        Dict with key price levels
    """
    result = {
        "range_high": None,
        "range_low": None,
        "current_price": None,
        "pdh": None,  # Previous Day High
        "pdl": None,  # Previous Day Low
        "recent_swing_highs": [],
        "recent_swing_lows": []
    }
    
    if not candles:
        return result
    
    # Get overall range
    highs = [c.get("high", c.get("h", 0)) for c in candles]
    lows = [c.get("low", c.get("l", 0)) for c in candles]
    closes = [c.get("close", c.get("c", 0)) for c in candles]
    
    result["range_high"] = max(highs) if highs else None
    result["range_low"] = min(lows) if lows else None
    result["current_price"] = closes[-1] if closes else None
    
    # Extract swing levels from structure if provided
    if structure:
        swing_highs = structure.get("swing_highs", [])
        swing_lows = structure.get("swing_lows", [])
        
        result["recent_swing_highs"] = [s["price"] for s in swing_highs[-5:]]
        result["recent_swing_lows"] = [s["price"] for s in swing_lows[-5:]]
    
    # Try to identify PDH/PDL (requires timestamp parsing)
    # This is a simplified version - in production, proper date grouping needed
    if len(candles) > 24:  # Assuming hourly candles
        prev_day_candles = candles[-48:-24]  # Approximate previous day
        if prev_day_candles:
            prev_highs = [c.get("high", c.get("h", 0)) for c in prev_day_candles]
            prev_lows = [c.get("low", c.get("l", 0)) for c in prev_day_candles]
            result["pdh"] = max(prev_highs) if prev_highs else None
            result["pdl"] = min(prev_lows) if prev_lows else None
    
    return result


# =============================================================================
# 5. Price Position Observation
# =============================================================================

def observe_price_position(
    current_price: float,
    range_high: float,
    range_low: float
) -> Dict[str, Any]:
    """
    Report where price is in range - no premium/discount opinion.
    
    Args:
        current_price: Current market price
        range_high: Top of the range
        range_low: Bottom of the range
        
    Returns:
        Dict with position facts
    """
    if range_high == range_low:
        return {
            "current_price": current_price,
            "range_high": range_high,
            "range_low": range_low,
            "range_size": 0,
            "position_in_range": 0.5,
            "distance_to_high": 0,
            "distance_to_low": 0
        }
    
    range_size = range_high - range_low
    position = (current_price - range_low) / range_size
    
    return {
        "current_price": current_price,
        "range_high": range_high,
        "range_low": range_low,
        "range_size": range_size,
        "position_in_range": round(position, 4),  # 0.0 = at low, 1.0 = at high
        "distance_to_high": round(range_high - current_price, 6),
        "distance_to_low": round(current_price - range_low, 6)
    }


# =============================================================================
# 6. Candle Characteristics Observation
# =============================================================================

def observe_candle_characteristics(candles: List[Dict], count: int = 10) -> Dict[str, Any]:
    """
    Report candle properties - no displacement opinion.
    
    Args:
        candles: List of OHLCV dicts
        count: Number of recent candles to analyze
        
    Returns:
        Dict with candle characteristics
    """
    result = {
        "recent_candles": [],
        "average_body_size": 0,
        "average_range": 0,
        "largest_body_size": 0,
        "largest_body_index": None
    }
    
    if not candles:
        return result
    
    recent = candles[-count:] if len(candles) >= count else candles
    
    body_sizes = []
    ranges = []
    
    for i, c in enumerate(recent):
        open_p = c.get("open", c.get("o", 0))
        high_p = c.get("high", c.get("h", 0))
        low_p = c.get("low", c.get("l", 0))
        close_p = c.get("close", c.get("c", 0))
        
        body_size = abs(close_p - open_p)
        candle_range = high_p - low_p
        wick_upper = high_p - max(open_p, close_p)
        wick_lower = min(open_p, close_p) - low_p
        
        direction = "bullish" if close_p > open_p else ("bearish" if close_p < open_p else "doji")
        body_ratio = body_size / candle_range if candle_range > 0 else 0
        
        body_sizes.append(body_size)
        ranges.append(candle_range)
        
        result["recent_candles"].append({
            "body_size": round(body_size, 6),
            "candle_range": round(candle_range, 6),
            "wick_upper": round(wick_upper, 6),
            "wick_lower": round(wick_lower, 6),
            "direction": direction,
            "body_to_range_ratio": round(body_ratio, 3)
        })
    
    if body_sizes:
        result["average_body_size"] = round(sum(body_sizes) / len(body_sizes), 6)
        result["average_range"] = round(sum(ranges) / len(ranges), 6)
        result["largest_body_size"] = round(max(body_sizes), 6)
        result["largest_body_index"] = body_sizes.index(max(body_sizes))
    
    return result


# =============================================================================
# 7. Sweep Events Observation
# =============================================================================

def observe_sweep_events(
    candles: List[Dict],
    swing_points: Dict,
    lookback_candles: int = 10
) -> Dict[str, Any]:
    """
    Detect price exceeding then rejecting from levels - factual only.
    
    A sweep is when price wicks beyond a level but closes back inside.
    No opinion on whether this is a "good" or "bad" signal.
    
    Args:
        candles: List of OHLCV dicts
        swing_points: Pre-computed swing points from observe_price_structure
        lookback_candles: How many recent candles to check
        
    Returns:
        Dict with potential sweep events
    """
    result = {
        "potential_sweeps": [],
        "sweep_count": 0
    }
    
    if not candles or not swing_points:
        return result
    
    recent = candles[-lookback_candles:] if len(candles) >= lookback_candles else candles
    swing_highs = [s["price"] for s in swing_points.get("swing_highs", [])[-5:]]
    swing_lows = [s["price"] for s in swing_points.get("swing_lows", [])[-5:]]
    
    for i, c in enumerate(recent):
        high_p = c.get("high", c.get("h", 0))
        low_p = c.get("low", c.get("l", 0))
        close_p = c.get("close", c.get("c", 0))
        open_p = c.get("open", c.get("o", 0))
        time_val = c.get("timestamp") or c.get("time")
        
        # Check for sweeps above swing highs
        for sh in swing_highs:
            if high_p > sh and close_p < sh:
                result["potential_sweeps"].append({
                    "type": "above_swing_high",
                    "level_swept": sh,
                    "extreme_price": high_p,
                    "close_price": close_p,
                    "candle_index": len(candles) - lookback_candles + i,
                    "rejection_size": round(high_p - close_p, 6),
                    "time": str(time_val) if time_val else None
                })
        
        # Check for sweeps below swing lows
        for sl in swing_lows:
            if low_p < sl and close_p > sl:
                result["potential_sweeps"].append({
                    "type": "below_swing_low",
                    "level_swept": sl,
                    "extreme_price": low_p,
                    "close_price": close_p,
                    "candle_index": len(candles) - lookback_candles + i,
                    "rejection_size": round(close_p - low_p, 6),
                    "time": str(time_val) if time_val else None
                })
    
    result["sweep_count"] = len(result["potential_sweeps"])
    return result


# =============================================================================
# 8. Fibonacci Levels Observation
# =============================================================================

def observe_fibonacci_levels(
    swing_high: float,
    swing_low: float
) -> Dict[str, Any]:
    """
    Calculate Fibonacci retracement levels - raw numbers only.
    
    No opinion on which level is "optimal" for entry.
    
    Args:
        swing_high: The swing high price
        swing_low: The swing low price
        
    Returns:
        Dict with Fibonacci levels
    """
    range_size = swing_high - swing_low
    
    # Standard Fibonacci levels
    levels = {
        "0.0": swing_low,
        "0.236": swing_low + range_size * 0.236,
        "0.382": swing_low + range_size * 0.382,
        "0.5": swing_low + range_size * 0.5,
        "0.618": swing_low + range_size * 0.618,
        "0.705": swing_low + range_size * 0.705,
        "0.786": swing_low + range_size * 0.786,
        "1.0": swing_high,
        "-0.272": swing_high + range_size * 0.272,  # Extension
        "-0.618": swing_high + range_size * 0.618   # Extension
    }
    
    # Round all values
    levels = {k: round(v, 6) for k, v in levels.items()}
    
    return {
        "swing_high": swing_high,
        "swing_low": swing_low,
        "range_size": round(range_size, 6),
        "levels": levels,
        "ote_zone": {
            "top": levels["0.618"],
            "bottom": levels["0.786"],
            "midpoint": levels["0.705"]
        }
    }


# =============================================================================
# 9. Aggregate Market Facts Builder
# =============================================================================

def build_market_facts(
    timestamp: datetime,
    timeframe_bars: Dict[str, List[Dict]]
) -> Dict[str, Any]:
    """
    Build complete market facts from multiple timeframes.
    
    This is the main entry point for gathering all observations.
    
    Args:
        timestamp: Current market timestamp
        timeframe_bars: Dict of timeframe -> candle list
        
    Returns:
        Complete market facts dictionary
    """
    facts = {
        "time": observe_session_time(timestamp),
        "structure": {},
        "imbalances": {},
        "liquidity": None,
        "price_position": None,
        "candle_behavior": {},
        "sweep_events": {},
        "fibonacci": None
    }
    
    # Process each timeframe
    for tf, candles in timeframe_bars.items():
        if not candles:
            continue
            
        structure = observe_price_structure(candles)
        facts["structure"][tf] = structure
        facts["imbalances"][tf] = observe_imbalances(candles)
        facts["candle_behavior"][tf] = observe_candle_characteristics(candles, count=10)
        facts["sweep_events"][tf] = observe_sweep_events(candles, structure)
    
    # Use 1H for main liquidity levels (or first available)
    main_tf = "1H" if "1H" in timeframe_bars else list(timeframe_bars.keys())[0]
    main_candles = timeframe_bars.get(main_tf, [])
    main_structure = facts["structure"].get(main_tf, {})
    
    if main_candles:
        facts["liquidity"] = observe_liquidity_levels(main_candles, main_structure)
        
        if facts["liquidity"]["range_high"] and facts["liquidity"]["range_low"]:
            facts["price_position"] = observe_price_position(
                facts["liquidity"]["current_price"],
                facts["liquidity"]["range_high"],
                facts["liquidity"]["range_low"]
            )
            
            # Calculate Fibonacci for the range
            facts["fibonacci"] = observe_fibonacci_levels(
                facts["liquidity"]["range_high"],
                facts["liquidity"]["range_low"]
            )
    
    return facts
