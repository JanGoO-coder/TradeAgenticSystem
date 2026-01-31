"""
Simple Breakout Strategy Tools.

Tools for the simple 5-minute candle breakout strategy:
- If 5-min candle breaks previous candle HIGH → Go SHORT
- If 5-min candle breaks previous candle LOW → Go LONG
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
import hashlib
import json


@dataclass
class BreakoutObservation:
    """
    Observation for the simple breakout strategy.

    Contains only the data needed for the breakout rule:
    - Previous and current 5-min candle data
    - Session context
    - Breakout detection
    """
    # Meta
    symbol: str
    timestamp: datetime
    current_price: float

    # Candle Data
    previous_candle: dict = field(default_factory=dict)  # {open, high, low, close, time}
    current_candle: dict = field(default_factory=dict)   # {open, high, low, close, time}

    # Breakout Detection
    breakout_detected: bool = False
    breakout_direction: Optional[str] = None  # "SHORT" if broke high, "LONG" if broke low
    breakout_level: Optional[float] = None    # The level that was broken

    # Session Context
    session: str = ""           # "ASIAN", "LONDON", "NEW_YORK", "OVERLAP"
    session_valid: bool = False # True for London/NY, False for Asian

    # State hash
    state_hash: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        parts = [
            f"## Breakout Analysis: {self.symbol}",
            f"**Time**: {self.timestamp.strftime('%Y-%m-%d %H:%M')} UTC",
            f"**Current Price**: {self.current_price:.5f}",
            "",
            "### Session Context",
            f"**Session**: {self.session}",
            f"**Valid for Trading**: {'YES' if self.session_valid else 'NO (Asian session - low volatility)'}",
            "",
            "### 5-Minute Candle Data",
        ]

        if self.previous_candle:
            parts.append("**Previous Candle**:")
            parts.append(f"  - High: {self.previous_candle.get('high', 'N/A'):.5f}")
            parts.append(f"  - Low: {self.previous_candle.get('low', 'N/A'):.5f}")
            parts.append(f"  - Close: {self.previous_candle.get('close', 'N/A'):.5f}")
        else:
            parts.append("**Previous Candle**: No data available")

        parts.append("")

        if self.current_candle:
            parts.append("**Current Candle**:")
            parts.append(f"  - Open: {self.current_candle.get('open', 'N/A'):.5f}")
            parts.append(f"  - High: {self.current_candle.get('high', 'N/A'):.5f}")
            parts.append(f"  - Low: {self.current_candle.get('low', 'N/A'):.5f}")
            parts.append(f"  - Close: {self.current_candle.get('close', 'N/A'):.5f}")
        else:
            parts.append("**Current Candle**: No data available (waiting for close)")

        parts.append("")
        parts.append("### Breakout Detection")

        if self.breakout_detected:
            if self.breakout_direction == "SHORT":
                parts.append(f"**BREAKOUT DETECTED**: Current candle BROKE ABOVE previous high ({self.breakout_level:.5f})")
                parts.append("**Signal**: Go SHORT (Rule 1.1)")
            else:
                parts.append(f"**BREAKOUT DETECTED**: Current candle BROKE BELOW previous low ({self.breakout_level:.5f})")
                parts.append("**Signal**: Go LONG (Rule 1.1)")
        else:
            if self.previous_candle and self.current_candle:
                prev_high = self.previous_candle.get('high', 0)
                prev_low = self.previous_candle.get('low', 0)
                curr_close = self.current_candle.get('close', 0)
                parts.append(f"**No Breakout**: Current close ({curr_close:.5f}) is within previous range ({prev_low:.5f} - {prev_high:.5f})")
            else:
                parts.append("**No Breakout**: Insufficient candle data")

        parts.append("")
        parts.append("### Trading Decision Factors")

        if not self.session_valid:
            parts.append("⚠️ **INVALID PERIOD**: Asian session - breakout strategy is not valid")
        elif self.breakout_detected:
            parts.append(f"✅ **VALID SETUP**: {self.breakout_direction} signal in {self.session} session")
        else:
            parts.append("⏳ **WAITING**: No breakout detected yet")

        return "\n".join(parts)


def get_session_from_time(dt: datetime) -> tuple[str, bool]:
    """
    Determine trading session from UTC time.

    Returns:
        Tuple of (session_name, is_valid_for_trading)

    Sessions (in UTC):
    - Asian: 00:00 - 07:00 UTC (invalid for breakout strategy)
    - London: 07:00 - 12:00 UTC (valid)
    - Overlap: 12:00 - 16:00 UTC (valid - NY overlaps with London)
    - New York: 16:00 - 21:00 UTC (valid)
    - After Hours: 21:00 - 00:00 UTC (invalid)
    """
    hour = dt.hour

    if 0 <= hour < 7:
        return "ASIAN", False
    elif 7 <= hour < 12:
        return "LONDON", True
    elif 12 <= hour < 16:
        return "LONDON_NY_OVERLAP", True
    elif 16 <= hour < 21:
        return "NEW_YORK", True
    else:
        return "AFTER_HOURS", False


def detect_breakout(prev_candle: dict, curr_candle: dict) -> tuple[bool, Optional[str], Optional[float]]:
    """
    Detect if current candle breaks previous candle's high or low.

    Args:
        prev_candle: Previous 5-min candle {open, high, low, close}
        curr_candle: Current 5-min candle {open, high, low, close}

    Returns:
        Tuple of (breakout_detected, direction, level)
        - direction: "SHORT" if broke high, "LONG" if broke low
        - level: The price level that was broken

    Logic:
        - If current candle CLOSES above previous high → SHORT signal
        - If current candle CLOSES below previous low → LONG signal
    """
    if not prev_candle or not curr_candle:
        return False, None, None

    prev_high = prev_candle.get('high')
    prev_low = prev_candle.get('low')
    curr_close = curr_candle.get('close')

    if prev_high is None or prev_low is None or curr_close is None:
        return False, None, None

    # Break of previous high → SHORT
    if curr_close > prev_high:
        return True, "SHORT", prev_high

    # Break of previous low → LONG
    if curr_close < prev_low:
        return True, "LONG", prev_low

    return False, None, None


def compute_breakout_state_hash(observation: BreakoutObservation) -> str:
    """Compute hash based on key observation elements for deduplication."""
    key_elements = {
        "prev_high": observation.previous_candle.get('high', 0),
        "prev_low": observation.previous_candle.get('low', 0),
        "curr_close": observation.current_candle.get('close', 0),
        "session": observation.session,
        "breakout": observation.breakout_detected,
        "direction": observation.breakout_direction
    }

    hash_input = json.dumps(key_elements, sort_keys=True)
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]


def run_breakout_observation(
    symbol: str,
    timestamp: datetime,
    current_price: float,
    candles_5m: List[dict]
) -> BreakoutObservation:
    """
    Run breakout observation on 5-minute candle data.

    Args:
        symbol: Trading symbol (e.g., "EURUSD")
        timestamp: Current timestamp
        current_price: Current market price
        candles_5m: List of 5-minute candles [{open, high, low, close, time}, ...]
                    Should be in chronological order, most recent last.

    Returns:
        BreakoutObservation with all analysis results
    """
    # Get session context
    session, session_valid = get_session_from_time(timestamp)

    # Get previous and current candle
    prev_candle = {}
    curr_candle = {}

    if candles_5m and len(candles_5m) >= 2:
        prev_candle = candles_5m[-2]
        curr_candle = candles_5m[-1]
    elif candles_5m and len(candles_5m) == 1:
        # Only current candle available
        curr_candle = candles_5m[-1]

    # Detect breakout
    breakout_detected, breakout_direction, breakout_level = detect_breakout(
        prev_candle, curr_candle
    )

    # Create observation
    observation = BreakoutObservation(
        symbol=symbol,
        timestamp=timestamp,
        current_price=current_price,
        previous_candle=prev_candle,
        current_candle=curr_candle,
        breakout_detected=breakout_detected,
        breakout_direction=breakout_direction,
        breakout_level=breakout_level,
        session=session,
        session_valid=session_valid
    )

    # Compute state hash
    observation.state_hash = compute_breakout_state_hash(observation)

    return observation


def get_breakout_entry_exit(
    direction: str,
    entry_price: float,
    prev_candle: dict,
    risk_reward: float = 1.0
) -> dict:
    """
    Calculate entry, stop loss, and take profit for a breakout trade.

    Args:
        direction: "LONG" or "SHORT"
        entry_price: Entry price
        prev_candle: Previous candle for stop loss reference
        risk_reward: Risk-reward ratio (default 1:1)

    Returns:
        Dict with entry, stop_loss, take_profit
    """
    if direction == "LONG":
        # For long: stop below breakout candle low
        stop_loss = prev_candle.get('low', entry_price * 0.999)
        risk = entry_price - stop_loss
        take_profit = entry_price + (risk * risk_reward)
    else:
        # For short: stop above breakout candle high
        stop_loss = prev_candle.get('high', entry_price * 1.001)
        risk = stop_loss - entry_price
        take_profit = entry_price - (risk * risk_reward)

    return {
        "direction": direction,
        "entry": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_pips": abs(entry_price - stop_loss) * 10000  # For forex pairs
    }
