"""ICT Trading System Tools - Core analysis functions per ICT_Rulebook_V1.md."""
from typing import List, Tuple, Optional, Literal, Dict, Union
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP, getcontext
from src.models import OHLCV, EconomicEvent, BiasValue

# Set precision for financial calculations
getcontext().prec = 28

# Configurable constants
LOOKBACK_DEFAULT = 2
ATR_PERIOD = 14
ATR_MULTIPLIER_DEFAULT = Decimal("2.0")
OTE_RET_62 = Decimal("0.618")
OTE_RET_705 = Decimal("0.705")
OTE_RET_79 = Decimal("0.79")
PIP_VALUE_DEFAULT = Decimal("10.0")

# ============================================================================
# UTILITIES
# ============================================================================

def to_decimal(value: Union[float, int, str, Decimal]) -> Decimal:
    """Safely convert input to Decimal."""
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except Exception as e:
        raise ValueError(f"Could not convert {value} to Decimal: {e}")

# ============================================================================
# RULE 2.1: Swing Point Identification
# ============================================================================

def identify_swing_points(candles: List[OHLCV], lookback: int = LOOKBACK_DEFAULT) -> dict:
    """
    Identify swing highs and swing lows using fractal logic.
    Rule Ref: 2.1 - Market Structure

    Args:
        candles: List of OHLCV candles
        lookback: Number of candles on each side to confirm swing

    Returns:
        {"swing_highs": [(index, price)], "swing_lows": [(index, price)]}
    """
    if not candles:
        return {"swing_highs": [], "swing_lows": []}

    if len(candles) < (lookback * 2 + 1):
        return {"swing_highs": [], "swing_lows": []}

    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(candles) - lookback):
        current_candle = candles[i]
        high = current_candle.high
        low = current_candle.low

        # Check swing high
        is_swing_high = all(
            high >= candles[i - j].high and high >= candles[i + j].high
            for j in range(1, lookback + 1)
        )
        if is_swing_high:
            swing_highs.append((i, high))

        # Check swing low
        is_swing_low = all(
            low <= candles[i - j].low and low <= candles[i + j].low
            for j in range(1, lookback + 1)
        )
        if is_swing_low:
            swing_lows.append((i, low))

    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


# ============================================================================
# RULE 1.1: HTF Bias Determination
# ============================================================================

def get_market_structure(candles: List[OHLCV]) -> dict:
    """
    Analyze 1H structure to determine bias.
    Rule Ref: 1.1 - Higher Timeframe Bias

    Returns:
        {"bias": "BULLISH"/"BEARISH"/"NEUTRAL", "structure": "HH_HL"/"LH_LL"/"UNCLEAR"}
    """
    if not candles:
        return {"bias": BiasValue.NEUTRAL, "structure": "UNCLEAR", "rule_refs": ["1.1"]}

    swings = identify_swing_points(candles)
    highs = swings["swing_highs"]
    lows = swings["swing_lows"]

    # If we have at least 2 of each swing type, check for HH/HL or LH/LL
    if len(highs) >= 2 and len(lows) >= 2:
        # Get last two swing points
        last_two_highs = highs[-2:]
        last_two_lows = lows[-2:]

        # Check for HH/HL (Bullish)
        higher_high = last_two_highs[1][1] > last_two_highs[0][1]
        higher_low = last_two_lows[1][1] > last_two_lows[0][1]

        # Check for LH/LL (Bearish)
        lower_high = last_two_highs[1][1] < last_two_highs[0][1]
        lower_low = last_two_lows[1][1] < last_two_lows[0][1]

        if higher_high and higher_low:
            return {"bias": BiasValue.BULLISH, "structure": "HH_HL", "rule_refs": ["1.1", "1.1.1", "2.1"]}
        elif lower_high and lower_low:
            return {"bias": BiasValue.BEARISH, "structure": "LH_LL", "rule_refs": ["1.1", "1.1.1", "2.1"]}

    # Fallback: check price trajectory using first and last candles
    if len(candles) >= 5:
        start_zone = candles[:3]
        end_zone = candles[-3:]

        start_avg = sum((c.close for c in start_zone), Decimal("0")) / 3
        end_avg = sum((c.close for c in end_zone), Decimal("0")) / 3

        # Check for clear directional movement (>0.3% move)
        price_change_pct = (end_avg - start_avg) / start_avg * 100

        # Also check if highs/lows are generally increasing or decreasing
        if price_change_pct > Decimal("0.3"):
            # Bullish trend check
            mid_idx = len(candles) // 2
            first_half_low = min(c.low for c in candles[:mid_idx])
            second_half_low = min(c.low for c in candles[mid_idx:])
            first_half_high = max(c.high for c in candles[:mid_idx])
            second_half_high = max(c.high for c in candles[mid_idx:])

            if second_half_high > first_half_high and second_half_low > first_half_low:
                return {"bias": BiasValue.BULLISH, "structure": "HH_HL", "rule_refs": ["1.1", "1.1.1"]}

        elif price_change_pct < Decimal("-0.3"):
            # Bearish trend check
            mid_idx = len(candles) // 2
            first_half_low = min(c.low for c in candles[:mid_idx])
            second_half_low = min(c.low for c in candles[mid_idx:])
            first_half_high = max(c.high for c in candles[:mid_idx])
            second_half_high = max(c.high for c in candles[mid_idx:])

            if second_half_high < first_half_high and second_half_low < first_half_low:
                return {"bias": BiasValue.BEARISH, "structure": "LH_LL", "rule_refs": ["1.1", "1.1.1"]}

    return {"bias": BiasValue.NEUTRAL, "structure": "UNCLEAR", "rule_refs": ["1.1"]}


# ============================================================================
# RULE 2.2: Displacement Detection
# ============================================================================

def detect_displacement(candles: List[OHLCV], atr_multiplier: Decimal = ATR_MULTIPLIER_DEFAULT) -> List[dict]:
    """
    Detect displacement candles (body size > ATR * multiplier).
    Rule Ref: 2.2 - Break in Market Structure

    Returns list of displacement candles with direction.
    """
    if len(candles) < ATR_PERIOD:
        return []

    # Calculate ATR
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i-1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if not true_ranges:
        return []

    atr = sum(true_ranges[-ATR_PERIOD:], Decimal("0")) / ATR_PERIOD

    displacements = []
    for i, candle in enumerate(candles):
        body_size = abs(candle.close - candle.open)
        if body_size > atr * atr_multiplier:
            direction = "BULLISH" if candle.close > candle.open else "BEARISH"
            displacements.append({
                "index": i,
                "direction": direction,
                "body_size": body_size,
                "atr": atr
            })

    return displacements


# ============================================================================
# RULE 5.2: Fair Value Gap Detection
# ============================================================================

def detect_fvg(candles: List[OHLCV]) -> List[dict]:
    """
    Detect Fair Value Gaps (3-candle imbalance).
    Rule Ref: 5.2 - Fair Value Gap

    Returns list of FVGs with type and price range.
    
    FVG Structure:
    - Candle 1: Sets the boundary
    - Candle 2: Momentum candle (creates the gap)
    - Candle 3: Confirms the gap
    """
    fvgs = []

    if len(candles) < 3:
        return []

    for i in range(2, len(candles)):
        candle_1 = candles[i - 2]  # First candle
        candle_2 = candles[i - 1]  # Middle candle (momentum)
        candle_3 = candles[i]       # Third candle

        # Middle candle direction for validation
        is_bullish_momentum = candle_2.close > candle_2.open
        momentum_body_size = abs(candle_2.close - candle_2.open)

        # Bullish FVG: candle_1 high < candle_3 low (gap to upside)
        # Validated by bullish momentum candle
        if candle_1.high < candle_3.low and is_bullish_momentum:
            fvgs.append({
                "type": "BULLISH_FVG",
                "index": i - 1,
                "top": candle_3.low,
                "bottom": candle_1.high,
                "midpoint": (candle_3.low + candle_1.high) / 2,
                "momentum_body_size": momentum_body_size,
                "rule_refs": ["5.2", "6.2"]
            })

        # Bearish FVG: candle_1 low > candle_3 high (gap to downside)
        # Validated by bearish momentum candle
        if candle_1.low > candle_3.high and not is_bullish_momentum:
            fvgs.append({
                "type": "BEARISH_FVG",
                "index": i - 1,
                "top": candle_1.low,
                "bottom": candle_3.high,
                "midpoint": (candle_1.low + candle_3.high) / 2,
                "momentum_body_size": momentum_body_size,
                "rule_refs": ["5.2", "6.2"]
            })

    return fvgs


# ============================================================================
# RULE 5.1: Premium/Discount Zone
# ============================================================================

def check_pd_array(current_price: Decimal, range_high: Decimal, range_low: Decimal, bias: str) -> dict:
    """
    Determine if price is in Premium or Discount zone.
    Rule Ref: 5.1 - Premium & Discount (PD Arrays)

    Note from rulebook:
    - Bullish: 0-0.5 = Discount, 0.5-1 = Premium
    - Bearish: 0-0.5 = Premium, 0.5-1 = Discount
    """
    current_price = to_decimal(current_price)
    range_high = to_decimal(range_high)
    range_low = to_decimal(range_low)

    if range_high == range_low:
        return {"zone": "EQUILIBRIUM", "level": Decimal("0.5"), "rule_refs": ["5.1"]}

    level = (current_price - range_low) / (range_high - range_low)

    if bias == "BULLISH":
        if level < Decimal("0.5"):
            zone = "DISCOUNT"  # Good for longs
        else:
            zone = "PREMIUM"
    else:  # BEARISH
        if level < Decimal("0.5"):
            zone = "PREMIUM"
        else:
            zone = "DISCOUNT"  # Good for shorts

    return {
        "zone": zone,
        "level": level.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
        "favorable": (bias == "BULLISH" and zone == "DISCOUNT") or
                    (bias == "BEARISH" and zone == "PREMIUM"),
        "rule_refs": ["5.1"]
    }


# ============================================================================
# RULE 6.1: OTE Zone Calculation
# ============================================================================

def calculate_ote_fib(swing_high: Decimal, swing_low: Decimal, direction: str) -> dict:
    """
    Calculate Optimal Trade Entry (OTE) Fibonacci levels.
    Rule Ref: 6.1 - Optimal Trade Entry

    OTE zone is 62%-79% retracement.
    """
    swing_high = to_decimal(swing_high)
    swing_low = to_decimal(swing_low)
    
    range_size = swing_high - swing_low

    if direction == "BULLISH":
        # Retracement from high to low for bullish OTE
        ote_62 = swing_high - (range_size * OTE_RET_62)
        ote_705 = swing_high - (range_size * OTE_RET_705)
        ote_79 = swing_high - (range_size * OTE_RET_79)
        return {
            "ote_zone_top": ote_62.quantize(Decimal("0.00001")),
            "ote_zone_mid": ote_705.quantize(Decimal("0.00001")),
            "ote_zone_bottom": ote_79.quantize(Decimal("0.00001")),
            "direction": "BULLISH",
            "rule_refs": ["6.1"]
        }
    else:
        # Retracement from low to high for bearish OTE
        ote_62 = swing_low + (range_size * OTE_RET_62)
        ote_705 = swing_low + (range_size * OTE_RET_705)
        ote_79 = swing_low + (range_size * OTE_RET_79)
        return {
            "ote_zone_top": ote_79.quantize(Decimal("0.00001")),
            "ote_zone_mid": ote_705.quantize(Decimal("0.00001")),
            "ote_zone_bottom": ote_62.quantize(Decimal("0.00001")),
            "direction": "BEARISH",
            "rule_refs": ["6.1"]
        }


# ============================================================================
# RULE 3.1-3.4: Liquidity Sweep Detection
# ============================================================================

def scan_liquidity_sweeps(candles: List[OHLCV], swing_points: dict) -> List[dict]:
    """
    Detect liquidity sweeps (wicks beyond swing points followed by rejection).
    Rule Ref: 3.1 (Buy/Sell-Side Liquidity), 3.4 (Stop Hunt)
    """
    sweeps = []
    if len(candles) < 5:
        return sweeps
        
    recent_candles = candles[-5:]  # Check last 5 candles

    for idx, candle in enumerate(recent_candles):
        # Check sell-side sweep (wick below swing low)
        for swing_idx, swing_low in swing_points.get("swing_lows", [])[-3:]:
            if candle.low < swing_low and candle.close > swing_low:
                sweeps.append({
                    "type": "SELL_SIDE_SWEEP",
                    "swing_price": swing_low,
                    "sweep_low": candle.low,
                    "candle_index": len(candles) - 5 + idx,
                    "rule_refs": ["3.1", "3.4"]
                })

        # Check buy-side sweep (wick above swing high)
        for swing_idx, swing_high in swing_points.get("swing_highs", [])[-3:]:
            if candle.high > swing_high and candle.close < swing_high:
                sweeps.append({
                    "type": "BUY_SIDE_SWEEP",
                    "swing_price": swing_high,
                    "sweep_high": candle.high,
                    "candle_index": len(candles) - 5 + idx,
                    "rule_refs": ["3.1", "3.4"]
                })

    return sweeps


# ============================================================================
# RULE 2.3: Market Structure Shift Detection
# ============================================================================

def detect_mss(candles: List[OHLCV], swing_points: dict) -> Optional[dict]:
    """
    Detect Market Structure Shift.
    Rule Ref: 2.3 - Market Structure Shift (MSS)

    MSS = First break against previous trend AFTER liquidity is taken.
    """
    if len(candles) < 5:
        return None

    recent_candle = candles[-1]
    highs = swing_points.get("swing_highs", [])
    lows = swing_points.get("swing_lows", [])

    if len(highs) < 1 or len(lows) < 1:
        return None

    last_high = highs[-1][1]
    last_low = lows[-1][1]

    # Bullish MSS: body close above last swing high
    if recent_candle.close > last_high:
        return {
            "type": "BULLISH_MSS",
            "break_level": last_high,
            "close_price": recent_candle.close,
            "rule_refs": ["2.3", "2.2"]
        }

    # Bearish MSS: body close below last swing low
    if recent_candle.close < last_low:
        return {
            "type": "BEARISH_MSS",
            "break_level": last_low,
            "close_price": recent_candle.close,
            "rule_refs": ["2.3", "2.2"]
        }

    return None


# ============================================================================
# RULE 8.1: Kill Zone Check
# ============================================================================

def check_kill_zone(timestamp: datetime) -> dict:
    """
    Check if current time is within a Kill Zone.
    Rule Ref: 8.1 - Kill Zones

    London Kill Zone: 2:00 AM - 5:00 AM EST (07:00-10:00 UTC)
    NY Kill Zone: 7:00 AM - 10:00 AM EST (12:00-15:00 UTC)

    Note: Input is assumed to be UTC. We convert to EST (UTC-5).
    """
    # Simply extraction of hour/minute from UTC timestamp
    # Assuming timestamp is UTC aware or naive UTC
    
    # Adjust to EST (UTC - 5)
    # 07:00 UTC = 02:00 EST
    # 10:00 UTC = 05:00 EST
    # 12:00 UTC = 07:00 EST
    # 15:00 UTC = 10:00 EST
    
    hour = timestamp.hour
    
    # London KZ: 07:00 - 10:00 UTC
    london_kz = 7 <= hour < 10
    
    # NY KZ: 12:00 - 15:00 UTC
    ny_kz = 12 <= hour < 15

    if london_kz:
        return {"in_kill_zone": True, "session": "London", "rule_refs": ["8.1"]}
    elif ny_kz:
        return {"in_kill_zone": True, "session": "NY", "rule_refs": ["8.1"]}
    else:
        return {"in_kill_zone": False, "session": None, "rule_refs": ["8.1"]}


def detect_session(timestamp: datetime) -> str:
    """Auto-detect trading session from timestamp (UTC)."""
    # UTC hours mapping to sessions
    # Asia: 23:00 - 08:00 UTC
    # London: 08:00 - 16:00 UTC
    # NY: 13:00 - 21:00 UTC
    
    # NOTE: Simplified unique session assignment logic
    hour = timestamp.hour

    if 8 <= hour < 13:
        return "London"
    elif 13 <= hour < 21:
        return "NY"
    else:
        return "Asia"


# ============================================================================
# RULE 8.4: News Impact Check
# ============================================================================

def fetch_news_impact(events: List[EconomicEvent], current_time: datetime) -> dict:
    """
    Check for High Impact news in next 60 minutes.
    Rule Ref: 8.4 - News Rules

    High impact = No trades
    Medium/Low = Reduced risk
    """
    window_end = current_time + timedelta(minutes=60)

    high_impact_events = []
    medium_events = []

    for event in events:
        # Check if event is within the window (future only or imminent)
        if current_time <= event.time <= window_end:
            if event.impact == "HIGH":
                high_impact_events.append(event)
            elif event.impact == "MEDIUM":
                medium_events.append(event)

    if high_impact_events:
        return {
            "status": "BLOCKED",
            "reason": f"High impact news: {high_impact_events[0].event_name}",
            "events": high_impact_events,
            "rule_refs": ["8.4"]
        }
    elif medium_events:
        return {
            "status": "CAUTION",
            "reason": "Medium impact news in next 60 min",
            "events": medium_events,
            "rule_refs": ["8.4"]
        }
    else:
        return {
            "status": "CLEAR",
            "reason": "No significant news",
            "events": [],
            "rule_refs": ["8.4"]
        }


# ============================================================================
# RULE 7.1: Position Size Calculation
# ============================================================================

def calc_position_size(
    account_balance: Decimal,
    risk_pct: Decimal,
    entry_price: Decimal,
    stop_loss: Decimal,
    pip_value: Decimal = PIP_VALUE_DEFAULT
) -> dict:
    """
    Calculate position size based on fixed percentage risk.
    Rule Ref: 7.1 - Fixed Percentage Risk
    """
    account_balance = to_decimal(account_balance)
    risk_pct = to_decimal(risk_pct)
    entry_price = to_decimal(entry_price)
    stop_loss = to_decimal(stop_loss)
    
    risk_amount = account_balance * (risk_pct / Decimal("100"))
    stop_distance_pips = abs(entry_price - stop_loss) * Decimal("10000")  # For forex pairs

    if stop_distance_pips == Decimal("0"):
        return {"position_size": Decimal("0"), "risk_amount": Decimal("0"), "rule_refs": ["7.1"]}

    position_size = risk_amount / (stop_distance_pips * pip_value)

    return {
        "position_size": position_size.quantize(Decimal("0.01")),
        "risk_amount": risk_amount.quantize(Decimal("0.01")),
        "stop_distance_pips": stop_distance_pips.quantize(Decimal("0.1")),
        "rule_refs": ["7.1"]
    }


# ============================================================================
# RULE 7.2: Risk-Reward Calculation
# ============================================================================

def calculate_rr(entry_price: Decimal, stop_loss: Decimal, take_profit: Decimal) -> dict:
    """
    Calculate Risk:Reward ratio.
    Rule Ref: 7.2 - Risk-Reward & Targets

    Minimum acceptable R:R is 1:2 per rulebook.
    """
    entry_price = to_decimal(entry_price)
    stop_loss = to_decimal(stop_loss)
    take_profit = to_decimal(take_profit)
    
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)

    if risk == Decimal("0"):
        return {"rr": Decimal("0"), "meets_minimum": False, "rule_refs": ["7.2"]}

    rr = reward / risk

    return {
        "rr": rr.quantize(Decimal("0.01")),
        "meets_minimum": rr >= Decimal("2.0"),
        "rule_refs": ["7.2"]
    }


# ============================================================================
# CONFLUENCE SCORE CALCULATION
# ============================================================================

def calculate_confluence_score(checks: dict) -> int:
    """
    Calculate confluence score (0-10) based on passed checks.

    Points allocation:
    - HTF bias aligned: 2 points
    - LTF alignment: 1 point
    - FVG/OB presence: 2 points
    - Liquidity sweep: 2 points
    - PD alignment: 1 point
    - Session OK: 1 point
    - News OK: 1 point

    Total possible: 10 points
    """
    score = 0

    if checks.get("htf_bias_exists"):
        score += 2
    if checks.get("ltf_aligned"):
        score += 1
    if checks.get("fvg_or_ob_present"):
        score += 2
    if checks.get("liquidity_sweep"):
        score += 2
    if checks.get("pd_favorable"):
        score += 1
    if checks.get("session_ok"):
        score += 1
    if checks.get("news_ok"):
        score += 1

    return min(score, 10)


# ============================================================================
# BACKTEST TRADE EXECUTION TOOLS
# ============================================================================

import httpx
from typing import Literal

BACKEND_URL = "http://localhost:8000/api/v1"


def execute_backtest_trade(
    direction: Literal["LONG", "SHORT"],
    entry_price: Decimal,
    stop_loss: Decimal,
    take_profit: Optional[Decimal] = None,
    setup_name: str = "Agent Trade",
    risk_reward: Optional[Decimal] = None
) -> dict:
    """
    Execute a trade in the backtest simulation.

    Used by the agent to place trades when auto-execute is enabled.

    Args:
        direction: "LONG" or "SHORT"
        entry_price: Entry price for the trade
        stop_loss: Stop loss price
        take_profit: Take profit price (auto-calculated if None)
        setup_name: Name of the ICT setup that triggered this trade
        risk_reward: Custom R:R ratio for TP calculation

    Returns:
        Dict with trade result including position ID if successful
    """
    try:
        # Convert Decimals to string/float for JSON serialization
        payload = {
            "direction": direction,
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit) if take_profit else None,
            "setup_name": setup_name,
            "risk_reward": float(risk_reward) if risk_reward else None,
            "auto_calculate": True
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BACKEND_URL}/backtest/trade/open",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": result.get("success", False),
                    "position_id": result.get("position", {}).get("id"),
                    "entry_price": result.get("position", {}).get("entry_price"),
                    "volume": result.get("calculated_volume"),
                    "take_profit": result.get("calculated_tp"),
                    "message": result.get("message")
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def close_backtest_position(
    position_id: str,
    reason: str = "MANUAL"
) -> dict:
    """
    Close an open position in the backtest simulation.

    Args:
        position_id: ID of the position to close
        reason: Reason for closing (MANUAL, TP_HIT, SL_HIT, etc.)

    Returns:
        Dict with trade result including P&L
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BACKEND_URL}/backtest/trade/close",
                json={
                    "position_id": position_id,
                    "reason": reason
                }
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": result.get("success", False),
                    "pnl_pips": result.get("trade", {}).get("pnl_pips"),
                    "pnl_usd": result.get("trade", {}).get("pnl_usd"),
                    "pnl_rr": result.get("trade", {}).get("pnl_rr"),
                    "message": result.get("message")
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_backtest_positions() -> dict:
    """
    Get all open positions in the backtest simulation.

    Returns:
        Dict with list of open positions
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{BACKEND_URL}/backtest/positions")

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "count": result.get("count", 0),
                    "positions": result.get("positions", [])
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_backtest_state() -> dict:
    """
    Get current backtest state including balance and statistics.

    Returns:
        Dict with current backtest state
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            # Get current bar info
            bar_response = client.get(f"{BACKEND_URL}/backtest/current-bar")
            stats_response = client.get(f"{BACKEND_URL}/backtest/statistics")
            risk_response = client.get(f"{BACKEND_URL}/backtest/risk-settings")

            state = {
                "success": True,
                "current_bar": bar_response.json() if bar_response.status_code == 200 else None,
                "statistics": stats_response.json() if stats_response.status_code == 200 else None,
                "risk_settings": risk_response.json() if risk_response.status_code == 200 else None
            }

            return state

    except Exception as e:
        return {"success": False, "error": str(e)}


def step_backtest_forward(bars: int = 1) -> dict:
    """
    Advance the backtest simulation by N bars.

    Args:
        bars: Number of bars to advance

    Returns:
        Dict with step result including any auto-closed trades
    """
    try:
        with httpx.Client(timeout=30.0) as client:  # Longer timeout for tick replay
            response = client.post(
                f"{BACKEND_URL}/backtest/step",
                params={"bars": bars}
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "current_index": result.get("current_index"),
                    "progress": result.get("progress"),
                    "has_more": result.get("has_more"),
                    "auto_closed_trades": result.get("auto_closed_trades", []),
                    "tick_replay": result.get("tick_replay")
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}
