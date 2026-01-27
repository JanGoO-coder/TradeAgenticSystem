"""
Session Observation Tools.

Analyzes time-based context including trading sessions, kill zones,
session ranges, and Power of Three. Pure observation - no trading signals.
"""
from datetime import datetime, time, timedelta
from typing import Optional


# Session definitions (in EST/New York time)
SESSIONS = {
    "Asia": {
        "start": time(18, 0),   # 6 PM EST (previous day)
        "end": time(3, 0),      # 3 AM EST
        "description": "Asian session - consolidation typical"
    },
    "London": {
        "start": time(3, 0),    # 3 AM EST
        "end": time(12, 0),     # 12 PM EST
        "description": "London session - high volatility"
    },
    "NY": {
        "start": time(8, 0),    # 8 AM EST
        "end": time(17, 0),     # 5 PM EST
        "description": "New York session - highest volume"
    }
}

# Kill zone definitions (in EST)
KILL_ZONES = {
    "London_KZ": {
        "start": time(2, 0),    # 2 AM EST
        "end": time(5, 0),      # 5 AM EST
        "description": "London Kill Zone - institutional activity"
    },
    "NY_KZ": {
        "start": time(7, 0),    # 7 AM EST
        "end": time(10, 0),     # 10 AM EST
        "description": "New York Kill Zone - highest probability setups"
    },
    "London_Close": {
        "start": time(10, 0),   # 10 AM EST
        "end": time(12, 0),     # 12 PM EST
        "description": "London Close - profit taking, reversals possible"
    }
}


def get_current_session(timestamp: Optional[datetime] = None) -> dict:
    """
    Determine the current trading session.

    Args:
        timestamp: Time to check (UTC). Defaults to now.

    Returns:
        {
            "session": "Asia" | "London" | "NY" | "Overlap",
            "session_start": datetime,
            "session_end": datetime,
            "time_in_session": str,  # HH:MM into session
            "time_remaining": str,   # HH:MM until session end
            "description": str,
            "observation": str
        }
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    # Convert UTC to EST (UTC - 5 hours, simplified)
    est_time = timestamp - timedelta(hours=5)
    current_time = est_time.time()

    active_sessions = []

    for session_name, times in SESSIONS.items():
        start = times["start"]
        end = times["end"]

        # Handle overnight sessions (Asia)
        if start > end:
            in_session = current_time >= start or current_time <= end
        else:
            in_session = start <= current_time <= end

        if in_session:
            active_sessions.append(session_name)

    # Determine primary session
    if "London" in active_sessions and "NY" in active_sessions:
        session = "Overlap"
        description = "London/NY Overlap - highest liquidity period"
    elif active_sessions:
        session = active_sessions[0]
        description = SESSIONS[session]["description"]
    else:
        session = "Off-Hours"
        description = "Between major sessions"

    return {
        "session": session,
        "est_time": est_time.strftime("%H:%M"),
        "utc_time": timestamp.strftime("%H:%M"),
        "active_sessions": active_sessions,
        "description": description,
        "observation": f"Current session: {session} (EST: {est_time.strftime('%H:%M')}). {description}"
    }


def check_killzone(timestamp: Optional[datetime] = None) -> dict:
    """
    Check if current time is within a Kill Zone.

    Kill Zones are specific time windows with higher probability
    of institutional activity and reliable setups.

    Args:
        timestamp: Time to check (UTC). Defaults to now.

    Returns:
        {
            "in_killzone": bool,
            "killzone": str | None,
            "killzone_start": str,
            "killzone_end": str,
            "time_remaining": str | None,  # Minutes remaining in KZ
            "description": str,
            "observation": str
        }
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    # Convert UTC to EST
    est_time = timestamp - timedelta(hours=5)
    current_time = est_time.time()

    active_kz = None
    kz_details = None

    for kz_name, times in KILL_ZONES.items():
        start = times["start"]
        end = times["end"]

        if start <= current_time <= end:
            active_kz = kz_name
            kz_details = times

            # Calculate time remaining
            end_dt = datetime.combine(est_time.date(), end)
            current_dt = datetime.combine(est_time.date(), current_time)
            remaining = end_dt - current_dt
            remaining_mins = int(remaining.total_seconds() / 60)

            return {
                "in_killzone": True,
                "killzone": kz_name,
                "killzone_start": start.strftime("%H:%M"),
                "killzone_end": end.strftime("%H:%M"),
                "time_remaining": f"{remaining_mins} minutes",
                "description": times["description"],
                "observation": (
                    f"ACTIVE: {kz_name} ({start.strftime('%H:%M')} - {end.strftime('%H:%M')} EST). "
                    f"{remaining_mins} minutes remaining. {times['description']}"
                )
            }

    # Find next kill zone
    next_kz = None
    min_wait = None

    for kz_name, times in KILL_ZONES.items():
        start = times["start"]

        if start > current_time:
            start_dt = datetime.combine(est_time.date(), start)
            current_dt = datetime.combine(est_time.date(), current_time)
            wait = start_dt - current_dt

            if min_wait is None or wait < min_wait:
                min_wait = wait
                next_kz = kz_name

    wait_str = f"{int(min_wait.total_seconds() / 60)} minutes" if min_wait else "tomorrow"

    return {
        "in_killzone": False,
        "killzone": None,
        "killzone_start": None,
        "killzone_end": None,
        "time_remaining": None,
        "next_killzone": next_kz,
        "time_until_next": wait_str,
        "description": "Outside Kill Zone",
        "observation": (
            f"Not in Kill Zone. Next: {next_kz} in {wait_str}. "
            f"Current EST: {current_time.strftime('%H:%M')}"
        )
    }


def get_session_range(candles: list[dict], session: str) -> dict:
    """
    Calculate the high/low range for a specific session's candles.

    Useful for identifying session highs/lows as liquidity targets.

    Args:
        candles: List of OHLCV candles with 'time' field
        session: "Asia", "London", or "NY"

    Returns:
        {
            "session": str,
            "high": float,
            "low": float,
            "range_size": float,
            "candle_count": int,
            "observation": str
        }
    """
    if session not in SESSIONS:
        return {
            "session": session,
            "error": f"Unknown session: {session}",
            "observation": f"Unknown session: {session}"
        }

    session_times = SESSIONS[session]
    start = session_times["start"]
    end = session_times["end"]

    session_candles = []

    for candle in candles:
        if "time" not in candle:
            continue

        try:
            # Parse candle time
            if isinstance(candle["time"], str):
                candle_dt = datetime.fromisoformat(candle["time"].replace("Z", "+00:00"))
            else:
                candle_dt = candle["time"]

            # Convert to EST
            est_dt = candle_dt - timedelta(hours=5)
            candle_time = est_dt.time()

            # Check if in session
            if start > end:  # Overnight session
                in_session = candle_time >= start or candle_time <= end
            else:
                in_session = start <= candle_time <= end

            if in_session:
                session_candles.append(candle)

        except (ValueError, TypeError):
            continue

    if not session_candles:
        return {
            "session": session,
            "high": None,
            "low": None,
            "range_size": None,
            "candle_count": 0,
            "observation": f"No {session} session candles found in data"
        }

    session_high = max(c["high"] for c in session_candles)
    session_low = min(c["low"] for c in session_candles)
    range_size = session_high - session_low

    return {
        "session": session,
        "high": round(session_high, 5),
        "low": round(session_low, 5),
        "range_size": round(range_size, 5),
        "candle_count": len(session_candles),
        "observation": (
            f"{session} session range: {session_low:.5f} - {session_high:.5f} "
            f"(size: {range_size * 10000:.1f} pips, {len(session_candles)} candles)"
        )
    }


def check_power_of_three(candles: list[dict], session: str = "NY") -> dict:
    """
    Check for Power of Three pattern within a session.

    Power of Three describes the typical institutional day:
    1. Accumulation - Early session range/consolidation
    2. Manipulation - False break of range to trap traders
    3. Distribution - True move in intended direction

    Args:
        candles: List of OHLCV candles
        session: Session to analyze

    Returns:
        {
            "phase": "ACCUMULATION" | "MANIPULATION" | "DISTRIBUTION" | "UNCLEAR",
            "session_range": dict,
            "early_range": dict,
            "observation": str
        }
    """
    session_range = get_session_range(candles, session)

    if session_range.get("candle_count", 0) < 6:
        return {
            "phase": "UNCLEAR",
            "session_range": session_range,
            "observation": "Insufficient session data for Power of Three analysis"
        }

    # Get session candles
    session_candles = candles[-session_range["candle_count"]:]

    # Divide into thirds
    third = len(session_candles) // 3

    early_candles = session_candles[:third]
    mid_candles = session_candles[third:2*third]
    late_candles = session_candles[2*third:]

    # Early range (Accumulation zone)
    early_high = max(c["high"] for c in early_candles)
    early_low = min(c["low"] for c in early_candles)

    # Check mid-session for manipulation
    mid_high = max(c["high"] for c in mid_candles)
    mid_low = min(c["low"] for c in mid_candles)

    broke_early_high = mid_high > early_high
    broke_early_low = mid_low < early_low

    # Check late session for distribution
    late_close = late_candles[-1]["close"] if late_candles else None

    # Determine phase
    if not broke_early_high and not broke_early_low:
        phase = "ACCUMULATION"
        obs = "Still in accumulation - no break of early range"
    elif broke_early_high and broke_early_low:
        phase = "MANIPULATION"
        obs = "Double manipulation - both sides swept"
    elif broke_early_high:
        if late_close and late_close < early_high:
            phase = "DISTRIBUTION"
            obs = "Buy-side manipulation, now distributing lower"
        else:
            phase = "MANIPULATION"
            obs = "Buy-side manipulation in progress"
    elif broke_early_low:
        if late_close and late_close > early_low:
            phase = "DISTRIBUTION"
            obs = "Sell-side manipulation, now distributing higher"
        else:
            phase = "MANIPULATION"
            obs = "Sell-side manipulation in progress"
    else:
        phase = "UNCLEAR"
        obs = "Pattern unclear"

    return {
        "phase": phase,
        "session_range": session_range,
        "early_range": {
            "high": round(early_high, 5),
            "low": round(early_low, 5)
        },
        "broke_high": broke_early_high,
        "broke_low": broke_early_low,
        "observation": f"Power of Three ({session}): {phase}. {obs}"
    }
