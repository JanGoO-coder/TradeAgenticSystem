"""
Strategy Agent Tools.

Pure analysis functions for the Strategy Agent.
These functions assess market context but do NOT find patterns or execute trades.
"""
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta

from ..state import (
    BiasDirection, TradingSession, EnvironmentStatus,
    BiasAssessment, SessionLevels, EnvironmentCheck,
    EconomicEvent
)
from ..rules_config import RulesConfig, get_rules


# =============================================================================
# Swing Point Detection (Rule 2.1)
# =============================================================================

def identify_swing_points(
    candles: List[Dict],
    lookback: int = 2
) -> Dict[str, List[Tuple[int, float]]]:
    """
    Identify swing highs and swing lows using fractal logic.
    Rule Ref: 2.1 - Market Structure

    Args:
        candles: List of OHLCV candles as dicts
        lookback: Number of candles on each side to confirm swing

    Returns:
        {"swing_highs": [(index, price)], "swing_lows": [(index, price)]}
    """
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(candles) - lookback):
        high = candles[i]["high"]
        low = candles[i]["low"]

        # Check swing high
        is_swing_high = all(
            high >= candles[i - j]["high"] and high >= candles[i + j]["high"]
            for j in range(1, lookback + 1)
        )
        if is_swing_high:
            swing_highs.append((i, high))

        # Check swing low
        is_swing_low = all(
            low <= candles[i - j]["low"] and low <= candles[i + j]["low"]
            for j in range(1, lookback + 1)
        )
        if is_swing_low:
            swing_lows.append((i, low))

    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


# =============================================================================
# HTF Bias Determination (Rule 1.1)
# =============================================================================

def analyze_htf_bias(
    candles: List[Dict],
    config: Optional[RulesConfig] = None
) -> BiasAssessment:
    """
    Analyze HTF (1H) structure to determine directional bias.
    Rule Ref: 1.1 - Higher Timeframe Bias

    Args:
        candles: 1H OHLCV candles
        config: Rules configuration

    Returns:
        BiasAssessment with direction, confidence, and rationale
    """
    if config is None:
        config = get_rules()

    min_candles = config.timeframes.min_candles_for_structure
    lookback = config.timeframes.swing_lookback

    if not candles or len(candles) < min_candles:
        return BiasAssessment(
            direction=BiasDirection.NEUTRAL,
            confidence=0.0,
            rationale=f"Insufficient data ({len(candles) if candles else 0}/{min_candles} candles)",
            rule_refs=["1.1", "9.2"]
        )

    swings = identify_swing_points(candles, lookback)
    highs = swings["swing_highs"]
    lows = swings["swing_lows"]

    # Check for HH/HL or LH/LL pattern
    if len(highs) >= 2 and len(lows) >= 2:
        last_two_highs = highs[-2:]
        last_two_lows = lows[-2:]

        higher_high = last_two_highs[1][1] > last_two_highs[0][1]
        higher_low = last_two_lows[1][1] > last_two_lows[0][1]
        lower_high = last_two_highs[1][1] < last_two_highs[0][1]
        lower_low = last_two_lows[1][1] < last_two_lows[0][1]

        if higher_high and higher_low:
            return BiasAssessment(
                direction=BiasDirection.BULLISH,
                confidence=0.85,
                rationale="1H showing HH/HL structure - bullish momentum",
                rule_refs=["1.1", "1.1.1", "2.1"]
            )
        elif lower_high and lower_low:
            return BiasAssessment(
                direction=BiasDirection.BEARISH,
                confidence=0.85,
                rationale="1H showing LH/LL structure - bearish momentum",
                rule_refs=["1.1", "1.1.1", "2.1"]
            )

    # Fallback: check price trajectory
    if len(candles) >= 5:
        start_zone = candles[:3]
        end_zone = candles[-3:]

        start_avg = sum(c["close"] for c in start_zone) / 3
        end_avg = sum(c["close"] for c in end_zone) / 3

        price_change_pct = (end_avg - start_avg) / start_avg * 100

        if price_change_pct > 0.3:
            return BiasAssessment(
                direction=BiasDirection.BULLISH,
                confidence=0.6,
                rationale=f"Price trending up {price_change_pct:.2f}% - weak bullish bias",
                rule_refs=["1.1"]
            )
        elif price_change_pct < -0.3:
            return BiasAssessment(
                direction=BiasDirection.BEARISH,
                confidence=0.6,
                rationale=f"Price trending down {abs(price_change_pct):.2f}% - weak bearish bias",
                rule_refs=["1.1"]
            )

    return BiasAssessment(
        direction=BiasDirection.NEUTRAL,
        confidence=0.3,
        rationale="1H structure unclear - ranging or overlapping",
        rule_refs=["1.1", "1.1.1"]
    )


# =============================================================================
# Kill Zone Detection (Rule 8.1)
# =============================================================================

def check_killzone(
    timestamp: datetime,
    config: Optional[RulesConfig] = None
) -> Dict[str, Any]:
    """
    Check if current time is within an active Kill Zone.
    Rule Ref: 8.1 - Kill Zones

    Args:
        timestamp: Current UTC timestamp
        config: Rules configuration

    Returns:
        Dict with killzone status and details
    """
    if config is None:
        config = get_rules()

    # Convert UTC to EST (UTC-5)
    est_hour = (timestamp.hour - 5) % 24
    est_minute = timestamp.minute

    kz_config = config.killzones

    # Check London KZ
    if kz_config.london.enabled:
        start_h = kz_config.london.start_hour
        end_h = kz_config.london.end_hour
        if start_h <= est_hour < end_h:
            return {
                "active": True,
                "name": "london",
                "session": TradingSession.LONDON,
                "rule_refs": ["8.1"]
            }

    # Check NY KZ
    if kz_config.new_york.enabled:
        start_h = kz_config.new_york.start_hour
        end_h = kz_config.new_york.end_hour
        if start_h <= est_hour < end_h:
            return {
                "active": True,
                "name": "new_york",
                "session": TradingSession.NEW_YORK,
                "rule_refs": ["8.1"]
            }

    # Check Asia KZ
    if kz_config.asia.enabled:
        start_h = kz_config.asia.start_hour
        end_h = kz_config.asia.end_hour
        # Handle overnight session (e.g., 20:00-00:00)
        if start_h > end_h:
            if est_hour >= start_h or est_hour < end_h:
                return {
                    "active": True,
                    "name": "asia",
                    "session": TradingSession.ASIA,
                    "rule_refs": ["8.1"]
                }
        elif start_h <= est_hour < end_h:
            return {
                "active": True,
                "name": "asia",
                "session": TradingSession.ASIA,
                "rule_refs": ["8.1"]
            }

    return {
        "active": False,
        "name": None,
        "session": TradingSession.OFF_HOURS,
        "rule_refs": ["8.1"]
    }


def detect_session(timestamp: datetime) -> TradingSession:
    """
    Auto-detect current trading session from timestamp.

    Args:
        timestamp: Current UTC timestamp

    Returns:
        TradingSession enum value
    """
    # Convert to EST
    est_hour = (timestamp.hour - 5) % 24

    # Session definitions (EST)
    # Asia: 18:00 - 03:00
    # London: 03:00 - 12:00
    # NY: 08:00 - 17:00

    if 3 <= est_hour < 8:
        return TradingSession.LONDON
    elif 8 <= est_hour < 17:
        return TradingSession.NEW_YORK
    elif est_hour >= 18 or est_hour < 3:
        return TradingSession.ASIA
    else:
        return TradingSession.OFF_HOURS


# =============================================================================
# Silverbullet Window Detection (Rule 6.6)
# =============================================================================

def check_silverbullet(
    timestamp: datetime,
    config: Optional[RulesConfig] = None
) -> Dict[str, Any]:
    """
    Check if current time is within a Silverbullet window.
    Rule Ref: 6.6 - Silverbullet Entry

    Default windows: 10-11 AM EST, 2-3 PM EST

    Returns:
        Dict with silverbullet status and window details
    """
    if config is None:
        config = get_rules()

    if not config.silverbullet.enabled:
        return {"active": False, "reason": "Silverbullet disabled in config"}

    # Convert UTC to EST
    est_hour = (timestamp.hour - 5) % 24
    est_minute = timestamp.minute

    for window in config.silverbullet.windows:
        start_h = int(window.start_est.split(":")[0])
        start_m = int(window.start_est.split(":")[1])
        end_h = int(window.end_est.split(":")[0])
        end_m = int(window.end_est.split(":")[1])

        # Check if within window
        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m
        current_total = est_hour * 60 + est_minute

        if start_total <= current_total < end_total:
            return {
                "active": True,
                "window": f"{window.start_est}-{window.end_est} EST",
                "rule_refs": ["6.6"]
            }

    return {"active": False, "reason": "Outside Silverbullet windows"}


# =============================================================================
# News Filter (Rule 8.4)
# =============================================================================

def check_news_impact(
    events: List[EconomicEvent],
    current_time: datetime,
    config: Optional[RulesConfig] = None
) -> Dict[str, Any]:
    """
    Check for high impact news in the configured window.
    Rule Ref: 8.4 - News Rules

    Returns:
        Dict with news status and any blocking events
    """
    if config is None:
        config = get_rules()

    window_minutes = config.news.high_impact_window_minutes
    window_end = current_time + timedelta(minutes=window_minutes)

    high_impact = []
    medium_impact = []

    for event in events:
        if current_time <= event.time <= window_end:
            if event.impact == "HIGH":
                high_impact.append(event)
            elif event.impact == "MEDIUM":
                medium_impact.append(event)

    if high_impact:
        action = config.news.high_impact_action
        return {
            "clear": False,
            "status": action,
            "reason": f"High impact news in {window_minutes}min: {high_impact[0].event_name}",
            "events": high_impact,
            "rule_refs": ["8.4"]
        }
    elif medium_impact and config.news.medium_impact_action == "BLOCK":
        return {
            "clear": False,
            "status": "CAUTION",
            "reason": f"Medium impact news: {medium_impact[0].event_name}",
            "events": medium_impact,
            "rule_refs": ["8.4"]
        }

    return {
        "clear": True,
        "status": "CLEAR",
        "reason": "No significant news",
        "events": [],
        "rule_refs": ["8.4"]
    }


# =============================================================================
# Session Levels Tracking (Rule 3.1)
# =============================================================================

def calculate_session_levels(
    candles: List[Dict],
    timestamp: datetime,
    previous_levels: Optional[SessionLevels] = None
) -> SessionLevels:
    """
    Calculate key session levels: PDH/PDL, Asian H/L, London H/L, etc.
    Rule Ref: 3.1 - Previous Day High/Low

    Args:
        candles: Historical candles (should include previous day)
        timestamp: Current timestamp
        previous_levels: Previously calculated levels (for continuity)

    Returns:
        SessionLevels with all tracked levels
    """
    levels = SessionLevels()

    if not candles:
        return levels

    # Get current date in EST
    est_offset = timedelta(hours=-5)
    current_est = timestamp + est_offset
    today = current_est.date()
    yesterday = today - timedelta(days=1)

    # Filter candles by date
    today_candles = []
    yesterday_candles = []

    for c in candles:
        candle_time = c.get("timestamp") or datetime.fromisoformat(str(c.get("time", "")))
        if hasattr(candle_time, "date"):
            candle_date = (candle_time + est_offset).date()
            if candle_date == today:
                today_candles.append(c)
            elif candle_date == yesterday:
                yesterday_candles.append(c)

    # PDH/PDL from yesterday's candles
    if yesterday_candles:
        levels.pdh = max(c["high"] for c in yesterday_candles)
        levels.pdl = min(c["low"] for c in yesterday_candles)

    # Today's session levels
    if today_candles:
        # Find midnight open (first candle of the day)
        levels.midnight_open = today_candles[0]["open"]

        # Session breakdowns (simplified - would need timestamp parsing)
        # For now, use overall today high/low as approximation
        levels.ny_high = max(c["high"] for c in today_candles)
        levels.ny_low = min(c["low"] for c in today_candles)

    # Carry forward previous levels if not calculated
    if previous_levels:
        if levels.pdh is None:
            levels.pdh = previous_levels.pdh
        if levels.pdl is None:
            levels.pdl = previous_levels.pdl
        if levels.asian_high is None:
            levels.asian_high = previous_levels.asian_high
        if levels.asian_low is None:
            levels.asian_low = previous_levels.asian_low
        if levels.london_high is None:
            levels.london_high = previous_levels.london_high
        if levels.london_low is None:
            levels.london_low = previous_levels.london_low

    return levels


def update_killzone_levels(
    candles: List[Dict],
    killzone_name: str,
    current_levels: SessionLevels
) -> SessionLevels:
    """
    Update killzone high/low from candles during active killzone.

    Args:
        candles: Candles from current killzone period
        killzone_name: Name of active killzone
        current_levels: Current session levels

    Returns:
        Updated SessionLevels
    """
    if not candles:
        return current_levels

    kz_high = max(c["high"] for c in candles)
    kz_low = min(c["low"] for c in candles)

    current_levels.killzone_high = kz_high
    current_levels.killzone_low = kz_low

    # Also update session-specific levels
    if killzone_name == "asia":
        current_levels.asian_high = kz_high
        current_levels.asian_low = kz_low
    elif killzone_name == "london":
        current_levels.london_high = kz_high
        current_levels.london_low = kz_low
    elif killzone_name == "new_york":
        current_levels.ny_high = kz_high
        current_levels.ny_low = kz_low

    return current_levels
