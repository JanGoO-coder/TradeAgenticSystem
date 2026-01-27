"""
Deterministic Market Observers (The Eyes).
These functions process raw candle data and return objective facts.
NO opinions, NO signals, NO bias.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# =============================================================================
# 1. Fair Value Gaps (FVG)
# =============================================================================

def find_fvgs(candles: List[Dict]) -> List[Dict[str, Any]]:
    """
    Identify Fair Value Gaps (FVG) in the provided candles.
    A Bullish FVG is when Low[i] > High[i-2].
    A Bearish FVG is when High[i] < Low[i-2].
    
    Args:
        candles: List of OHLCV dicts (must be sorted by time)
        
    Returns:
        List of FVGs with {top, bottom, type, index, time}
    """
    fvgs = []
    if len(candles) < 3:
        return fvgs

    for i in range(2, len(candles)):
        curr = candles[i]
        prev_2 = candles[i-2]
        
        # Bullish FVG
        if curr["low"] > prev_2["high"]:
            fvgs.append({
                "type": "bullish",
                "top": curr["low"],
                "bottom": prev_2["high"],
                "index": i, # Index of the completed candle (3rd candle)
                "time": curr.get("timestamp") or curr.get("time"),
                "mitigated": False # Placeholder
            })
            
        # Bearish FVG
        elif curr["high"] < prev_2["low"]:
            fvgs.append({
                "type": "bearish",
                "top": prev_2["low"],
                "bottom": curr["high"],
                "index": i,
                "time": curr.get("timestamp") or curr.get("time"),
                "mitigated": False # Placeholder
            })
            
    return fvgs

# =============================================================================
# 2. Market Structure (Swings)
# =============================================================================

def get_market_structure(candles: List[Dict], lookback: int = 2) -> Dict[str, List[Dict]]:
    """
    Identify significant Swing Highs and Swing Lows (Fractals).
    
    Args:
        candles: List of candles
        lookback: Number of candles on each side required to form a swing
        
    Returns:
        Dict with "highs" and "lows" lists
    """
    swings = {"highs": [], "lows": []}
    
    if len(candles) < (lookback * 2 + 1):
        return swings

    for i in range(lookback, len(candles) - lookback):
        current = candles[i]
        
        # Check Swing High
        is_high = True
        for j in range(1, lookback + 1):
            if candles[i-j]["high"] > current["high"] or candles[i+j]["high"] > current["high"]:
                is_high = False
                break
        if is_high:
            swings["highs"].append({
                "price": current["high"],
                "index": i,
                "time": current.get("timestamp") or current.get("time")
            })

        # Check Swing Low
        is_low = True
        for j in range(1, lookback + 1):
            if candles[i-j]["low"] < current["low"] or candles[i+j]["low"] < current["low"]:
                is_low = False
                break
        if is_low:
            swings["lows"].append({
                "price": current["low"],
                "index": i,
                "time": current.get("timestamp") or current.get("time")
            })
            
    return swings

# =============================================================================
# 3. Session Status & Time Info
# =============================================================================

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

def get_session_status(timestamp: datetime) -> Dict[str, Any]:
    """
    Return purely objective time/session info.
    Uses 'America/New_York' for trading sessions.
    
    Session Definitions (Strict):
    - ASIA:     18:00 - 00:00 EST (Futures Open / Early Asia)
    - LONDON:   02:00 - 05:00 EST (London Open / KZ)
    - NEW_YORK: 07:00 - 10:00 EST (NY Open / KZ)
    
    Args:
        timestamp: UTC compliant datetime object (offset-aware preferred)
    """
    # Ensure timestamp is offset-aware UTC
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
    else:
        timestamp = timestamp.astimezone(ZoneInfo("UTC"))
        
    # Convert to Eastern Time
    est_tz = ZoneInfo("America/New_York")
    est_time = timestamp.astimezone(est_tz)
    
    est_hour = est_time.hour
    
    # Strict Session Logic (as per requirements)
    current_session = "OFF_HOURS"
    
    # ASIA: 18:00 - 00:00 (i.e., >= 18 or < 0, effectively 18-23:59)
    if est_hour >= 18:
        current_session = "ASIA"
    elif est_hour < 0: # Should not happen with .hour (0-23)
        pass 
        
    # LONDON: 02:00 - 05:00
    if 2 <= est_hour < 5:
        current_session = "LONDON"
        
    # NEW_YORK: 07:00 - 10:00
    if 7 <= est_hour < 10:
        current_session = "NEW_YORK"
        
    # Combined checks for checking overlap if needed, but for now strict return
    # If overlap, priority could be NY > London > Asia, but hours defined are disjoint except Asia wrap
    # Asia 18->24. London 2->5. NY 7->10. No overlap.
    
    # Killzones
    killzones = {
        "london": 2 <= est_hour < 5,
        "new_york": 7 <= est_hour < 10,
        "asia": est_hour >= 20 or est_hour < 0 # Simplified Asia KZ
    }

    return {
        "utc_time": timestamp.isoformat(),
        "est_time": est_time.isoformat(),
        "est_hour_int": est_hour,
        "day": est_time.strftime("%A"),
        "current_session": current_session,
        "killzones": killzones
    }

# =============================================================================
# 4. Liquidity Levels
# =============================================================================

def get_liquidity_levels(candles: List[Dict]) -> Dict[str, float]:
    """
    Get nearest significant liquidity levels (PDH, PDL, Session H/L).
    This function simply processes the provided candles to find max/min
    of specific time ranges if possible, or just significant points.
    
    For simplicity here, we return the global high/low of the analyzed range
    and the most recent swing points.
    """
    if not candles:
        return {}
        
    # Safely handle mixed dictionary keys if data source varies
    highs = []
    lows = []
    closes = []
    
    for c in candles:
        highs.append(c.get("high", c.get("h", 0)))
        lows.append(c.get("low", c.get("l", 0)))
        closes.append(c.get("close", c.get("c", 0)))
    
    if not highs: 
        return {}

    return {
        "range_high": max(highs),
        "range_low": min(lows),
        "current_price": closes[-1] if closes else 0
    }
