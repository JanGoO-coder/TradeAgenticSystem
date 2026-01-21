"""ICT Trading System Tools - Core analysis functions per ICT_Rulebook_V1.md."""
from typing import List, Tuple, Optional, Literal
from datetime import datetime, time, timedelta
from src.models import OHLCV, EconomicEvent, BiasValue


# ============================================================================
# RULE 2.1: Swing Point Identification
# ============================================================================

def identify_swing_points(candles: List[dict], lookback: int = 2) -> dict:
    """
    Identify swing highs and swing lows using fractal logic.
    Rule Ref: 2.1 - Market Structure
    
    Args:
        candles: List of OHLCV candles
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


# ============================================================================
# RULE 1.1: HTF Bias Determination
# ============================================================================

def get_market_structure(candles: List[dict]) -> dict:
    """
    Analyze 1H structure to determine bias.
    Rule Ref: 1.1 - Higher Timeframe Bias
    
    Returns:
        {"bias": "BULLISH"/"BEARISH"/"NEUTRAL", "structure": "HH_HL"/"LH_LL"/"UNCLEAR"}
    """
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
        
        start_avg = sum(c["close"] for c in start_zone) / 3
        end_avg = sum(c["close"] for c in end_zone) / 3
        
        # Check for clear directional movement (>0.5% move)
        price_change_pct = (end_avg - start_avg) / start_avg * 100
        
        # Also check if highs/lows are generally increasing or decreasing
        if price_change_pct > 0.3:
            # Bullish trend
            first_half_low = min(c["low"] for c in candles[:len(candles)//2])
            second_half_low = min(c["low"] for c in candles[len(candles)//2:])
            first_half_high = max(c["high"] for c in candles[:len(candles)//2])
            second_half_high = max(c["high"] for c in candles[len(candles)//2:])
            
            if second_half_high > first_half_high and second_half_low > first_half_low:
                return {"bias": BiasValue.BULLISH, "structure": "HH_HL", "rule_refs": ["1.1", "1.1.1"]}
        
        elif price_change_pct < -0.3:
            # Bearish trend
            first_half_low = min(c["low"] for c in candles[:len(candles)//2])
            second_half_low = min(c["low"] for c in candles[len(candles)//2:])
            first_half_high = max(c["high"] for c in candles[:len(candles)//2])
            second_half_high = max(c["high"] for c in candles[len(candles)//2:])
            
            if second_half_high < first_half_high and second_half_low < first_half_low:
                return {"bias": BiasValue.BEARISH, "structure": "LH_LL", "rule_refs": ["1.1", "1.1.1"]}
    
    return {"bias": BiasValue.NEUTRAL, "structure": "UNCLEAR", "rule_refs": ["1.1"]}


# ============================================================================
# RULE 2.2: Displacement Detection
# ============================================================================

def detect_displacement(candles: List[dict], atr_multiplier: float = 2.0) -> List[dict]:
    """
    Detect displacement candles (body size > ATR * multiplier).
    Rule Ref: 2.2 - Break in Market Structure
    
    Returns list of displacement candles with direction.
    """
    if len(candles) < 14:
        return []
    
    # Calculate ATR
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    
    atr = sum(true_ranges[-14:]) / 14
    
    displacements = []
    for i, candle in enumerate(candles):
        body_size = abs(candle["close"] - candle["open"])
        if body_size > atr * atr_multiplier:
            direction = "BULLISH" if candle["close"] > candle["open"] else "BEARISH"
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

def detect_fvg(candles: List[dict]) -> List[dict]:
    """
    Detect Fair Value Gaps (3-candle imbalance).
    Rule Ref: 5.2 - Fair Value Gap
    
    Returns list of FVGs with type and price range.
    """
    fvgs = []
    
    for i in range(2, len(candles)):
        candle_1 = candles[i - 2]  # First candle
        candle_2 = candles[i - 1]  # Middle candle (momentum)
        candle_3 = candles[i]       # Third candle
        
        # Bullish FVG: candle_1 high < candle_3 low
        if candle_1["high"] < candle_3["low"]:
            fvgs.append({
                "type": "BULLISH_FVG",
                "index": i - 1,
                "top": candle_3["low"],
                "bottom": candle_1["high"],
                "midpoint": (candle_3["low"] + candle_1["high"]) / 2,
                "rule_refs": ["5.2", "6.2"]
            })
        
        # Bearish FVG: candle_1 low > candle_3 high
        if candle_1["low"] > candle_3["high"]:
            fvgs.append({
                "type": "BEARISH_FVG",
                "index": i - 1,
                "top": candle_1["low"],
                "bottom": candle_3["high"],
                "midpoint": (candle_1["low"] + candle_3["high"]) / 2,
                "rule_refs": ["5.2", "6.2"]
            })
    
    return fvgs


# ============================================================================
# RULE 5.1: Premium/Discount Zone
# ============================================================================

def check_pd_array(current_price: float, range_high: float, range_low: float, bias: str) -> dict:
    """
    Determine if price is in Premium or Discount zone.
    Rule Ref: 5.1 - Premium & Discount (PD Arrays)
    
    Note from rulebook: 
    - Bullish: 0-0.5 = Discount, 0.5-1 = Premium
    - Bearish: 0-0.5 = Premium, 0.5-1 = Discount
    """
    if range_high == range_low:
        return {"zone": "EQUILIBRIUM", "level": 0.5, "rule_refs": ["5.1"]}
    
    level = (current_price - range_low) / (range_high - range_low)
    
    if bias == "BULLISH":
        if level < 0.5:
            zone = "DISCOUNT"  # Good for longs
        else:
            zone = "PREMIUM"
    else:  # BEARISH
        if level < 0.5:
            zone = "PREMIUM"
        else:
            zone = "DISCOUNT"  # Good for shorts
    
    return {
        "zone": zone,
        "level": round(level, 3),
        "favorable": (bias == "BULLISH" and zone == "DISCOUNT") or 
                    (bias == "BEARISH" and zone == "PREMIUM"),
        "rule_refs": ["5.1"]
    }


# ============================================================================
# RULE 6.1: OTE Zone Calculation
# ============================================================================

def calculate_ote_fib(swing_high: float, swing_low: float, direction: str) -> dict:
    """
    Calculate Optimal Trade Entry (OTE) Fibonacci levels.
    Rule Ref: 6.1 - Optimal Trade Entry
    
    OTE zone is 62%-79% retracement.
    """
    range_size = swing_high - swing_low
    
    if direction == "BULLISH":
        # Retracement from high to low for bullish OTE
        ote_62 = swing_high - (range_size * 0.618)
        ote_705 = swing_high - (range_size * 0.705)
        ote_79 = swing_high - (range_size * 0.79)
        return {
            "ote_zone_top": round(ote_62, 5),
            "ote_zone_mid": round(ote_705, 5),
            "ote_zone_bottom": round(ote_79, 5),
            "direction": "BULLISH",
            "rule_refs": ["6.1"]
        }
    else:
        # Retracement from low to high for bearish OTE
        ote_62 = swing_low + (range_size * 0.618)
        ote_705 = swing_low + (range_size * 0.705)
        ote_79 = swing_low + (range_size * 0.79)
        return {
            "ote_zone_top": round(ote_79, 5),
            "ote_zone_mid": round(ote_705, 5),
            "ote_zone_bottom": round(ote_62, 5),
            "direction": "BEARISH",
            "rule_refs": ["6.1"]
        }


# ============================================================================
# RULE 3.1-3.4: Liquidity Sweep Detection
# ============================================================================

def scan_liquidity_sweeps(candles: List[dict], swing_points: dict) -> List[dict]:
    """
    Detect liquidity sweeps (wicks beyond swing points followed by rejection).
    Rule Ref: 3.1 (Buy/Sell-Side Liquidity), 3.4 (Stop Hunt)
    """
    sweeps = []
    recent_candles = candles[-5:]  # Check last 5 candles
    
    for idx, candle in enumerate(recent_candles):
        # Check sell-side sweep (wick below swing low)
        for swing_idx, swing_low in swing_points.get("swing_lows", [])[-3:]:
            if candle["low"] < swing_low and candle["close"] > swing_low:
                sweeps.append({
                    "type": "SELL_SIDE_SWEEP",
                    "swing_price": swing_low,
                    "sweep_low": candle["low"],
                    "candle_index": len(candles) - 5 + idx,
                    "rule_refs": ["3.1", "3.4"]
                })
        
        # Check buy-side sweep (wick above swing high)
        for swing_idx, swing_high in swing_points.get("swing_highs", [])[-3:]:
            if candle["high"] > swing_high and candle["close"] < swing_high:
                sweeps.append({
                    "type": "BUY_SIDE_SWEEP",
                    "swing_price": swing_high,
                    "sweep_high": candle["high"],
                    "candle_index": len(candles) - 5 + idx,
                    "rule_refs": ["3.1", "3.4"]
                })
    
    return sweeps


# ============================================================================
# RULE 2.3: Market Structure Shift Detection
# ============================================================================

def detect_mss(candles: List[dict], swing_points: dict) -> Optional[dict]:
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
    if recent_candle["close"] > last_high:
        return {
            "type": "BULLISH_MSS",
            "break_level": last_high,
            "close_price": recent_candle["close"],
            "rule_refs": ["2.3", "2.2"]
        }
    
    # Bearish MSS: body close below last swing low
    if recent_candle["close"] < last_low:
        return {
            "type": "BEARISH_MSS",
            "break_level": last_low,
            "close_price": recent_candle["close"],
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
    # Convert UTC to EST (subtract 5 hours)
    est_hour = (timestamp.hour - 5) % 24
    
    # London KZ: 2-5 AM EST = 7-10 UTC
    london_kz = 2 <= est_hour <= 5
    
    # NY KZ: 7-10 AM EST = 12-15 UTC
    ny_kz = 7 <= est_hour <= 10
    
    if london_kz:
        return {"in_kill_zone": True, "session": "London", "rule_refs": ["8.1"]}
    elif ny_kz:
        return {"in_kill_zone": True, "session": "NY", "rule_refs": ["8.1"]}
    else:
        return {"in_kill_zone": False, "session": None, "rule_refs": ["8.1"]}


def detect_session(timestamp: datetime) -> str:
    """Auto-detect trading session from timestamp."""
    hour = timestamp.hour
    
    # Asia: 18:00 - 03:00 EST
    # London: 03:00 - 12:00 EST  
    # NY: 08:00 - 17:00 EST
    
    if 3 <= hour < 8:
        return "London"
    elif 8 <= hour < 17:
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
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    pip_value: float = 10.0  # Standard for 1 lot on majors
) -> dict:
    """
    Calculate position size based on fixed percentage risk.
    Rule Ref: 7.1 - Fixed Percentage Risk
    """
    risk_amount = account_balance * (risk_pct / 100)
    stop_distance_pips = abs(entry_price - stop_loss) * 10000  # For forex pairs
    
    if stop_distance_pips == 0:
        return {"position_size": 0, "risk_amount": 0, "rule_refs": ["7.1"]}
    
    position_size = risk_amount / (stop_distance_pips * pip_value)
    
    return {
        "position_size": round(position_size, 2),
        "risk_amount": round(risk_amount, 2),
        "stop_distance_pips": round(stop_distance_pips, 1),
        "rule_refs": ["7.1"]
    }


# ============================================================================
# RULE 7.2: Risk-Reward Calculation
# ============================================================================

def calculate_rr(entry_price: float, stop_loss: float, take_profit: float) -> dict:
    """
    Calculate Risk:Reward ratio.
    Rule Ref: 7.2 - Risk-Reward & Targets
    
    Minimum acceptable R:R is 1:2 per rulebook.
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    
    if risk == 0:
        return {"rr": 0, "meets_minimum": False, "rule_refs": ["7.2"]}
    
    rr = reward / risk
    
    return {
        "rr": round(rr, 2),
        "meets_minimum": rr >= 2.0,
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
