"""
Worker Agent Tools.

Computational functions for pattern detection and trade execution.
Zero strategic opinion - purely mechanical execution of analysis.
"""
from typing import List, Dict, Optional, Tuple, Any, Literal
from datetime import datetime, timedelta
import httpx

from ..state import (
    BiasDirection, OrderDirection, OrderType, TradeSetup,
    Position, ClosedTrade, TradeResult, MarketContext
)
from ..rules_config import RulesConfig, get_rules
from .models import FVGResult, SweepResult, MSSResult, OTEZone, PDZone, TurtleSoupResult


# =============================================================================
# Backend API Configuration
# =============================================================================

BACKEND_URL = "http://localhost:8000/api/v1"


# =============================================================================
# Swing Point Detection (Rule 2.1)
# =============================================================================

def find_swing_points(
    candles: List[Dict],
    lookback: int = 2
) -> Dict[str, List[Tuple[int, float]]]:
    """
    Identify swing highs and swing lows using fractal logic.
    Rule Ref: 2.1 - Market Structure
    """
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(candles) - lookback):
        high = candles[i]["high"]
        low = candles[i]["low"]

        is_swing_high = all(
            high >= candles[i - j]["high"] and high >= candles[i + j]["high"]
            for j in range(1, lookback + 1)
        )
        if is_swing_high:
            swing_highs.append((i, high))

        is_swing_low = all(
            low <= candles[i - j]["low"] and low <= candles[i + j]["low"]
            for j in range(1, lookback + 1)
        )
        if is_swing_low:
            swing_lows.append((i, low))

    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


# =============================================================================
# Displacement Detection (Rule 2.2)
# =============================================================================

def detect_displacement(
    candles: List[Dict],
    config: Optional[RulesConfig] = None
) -> List[Dict]:
    """
    Detect displacement candles (body > ATR * multiplier).
    Rule Ref: 2.2 - Break in Market Structure
    """
    if config is None:
        config = get_rules()

    atr_multiplier = config.displacement.atr_multiplier
    atr_period = config.displacement.atr_period

    if len(candles) < atr_period:
        return []

    # Calculate ATR
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    atr = sum(true_ranges[-atr_period:]) / atr_period

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


# =============================================================================
# Fair Value Gap Detection (Rule 5.2)
# =============================================================================

def find_fvg(candles: List[Dict]) -> List[FVGResult]:
    """
    Detect Fair Value Gaps (3-candle imbalance).
    Rule Ref: 5.2 - Fair Value Gap
    
    FVG Structure:
    - Candle 1: Sets the boundary
    - Candle 2: Momentum candle (creates the gap)
    - Candle 3: Confirms the gap
    """
    fvgs = []

    for i in range(2, len(candles)):
        candle_1 = candles[i - 2]
        candle_2 = candles[i - 1]  # Middle (momentum)
        candle_3 = candles[i]

        # Middle candle direction for validation
        is_bullish_momentum = candle_2["close"] > candle_2["open"]

        # Bullish FVG: candle_1 high < candle_3 low (validated by bullish momentum)
        if candle_1["high"] < candle_3["low"] and is_bullish_momentum:
            fvgs.append(FVGResult(
                type="BULLISH_FVG",
                index=i - 1,
                top=candle_3["low"],
                bottom=candle_1["high"],
                midpoint=(candle_3["low"] + candle_1["high"]) / 2
            ))

        # Bearish FVG: candle_1 low > candle_3 high (validated by bearish momentum)
        if candle_1["low"] > candle_3["high"] and not is_bullish_momentum:
            fvgs.append(FVGResult(
                type="BEARISH_FVG",
                index=i - 1,
                top=candle_1["low"],
                bottom=candle_3["high"],
                midpoint=(candle_1["low"] + candle_3["high"]) / 2
            ))

    return fvgs


# =============================================================================
# Liquidity Sweep Detection (Rule 3.4)
# =============================================================================

def find_liquidity_sweep(
    candles: List[Dict],
    swing_points: Dict[str, List[Tuple[int, float]]]
) -> List[SweepResult]:
    """
    Detect liquidity sweeps (wicks beyond swing points followed by rejection).
    Rule Ref: 3.1, 3.4 - Stop Hunt
    """
    sweeps = []
    recent_candles = candles[-5:]

    for idx, candle in enumerate(recent_candles):
        # Check sell-side sweep (wick below swing low)
        for swing_idx, swing_low in swing_points.get("swing_lows", [])[-3:]:
            if candle["low"] < swing_low and candle["close"] > swing_low:
                sweeps.append(SweepResult(
                    type="SELL_SIDE_SWEEP",
                    swing_price=swing_low,
                    sweep_price=candle["low"],
                    candle_index=len(candles) - 5 + idx
                ))

        # Check buy-side sweep (wick above swing high)
        for swing_idx, swing_high in swing_points.get("swing_highs", [])[-3:]:
            if candle["high"] > swing_high and candle["close"] < swing_high:
                sweeps.append(SweepResult(
                    type="BUY_SIDE_SWEEP",
                    swing_price=swing_high,
                    sweep_price=candle["high"],
                    candle_index=len(candles) - 5 + idx
                ))

    return sweeps


# =============================================================================
# Market Structure Shift Detection (Rule 2.3)
# =============================================================================

def detect_mss(
    candles: List[Dict],
    swing_points: Dict[str, List[Tuple[int, float]]]
) -> Optional[MSSResult]:
    """
    Detect Market Structure Shift.
    Rule Ref: 2.3 - MSS
    """
    if len(candles) < 5:
        return None

    recent_candle = candles[-1]
    highs = swing_points.get("swing_highs", [])
    lows = swing_points.get("swing_lows", [])

    if not highs or not lows:
        return None

    last_high = highs[-1][1]
    last_low = lows[-1][1]

    # Bullish MSS: close above last swing high
    if recent_candle["close"] > last_high:
        return MSSResult(
            type="BULLISH_MSS",
            break_level=last_high,
            close_price=recent_candle["close"]
        )

    # Bearish MSS: close below last swing low
    if recent_candle["close"] < last_low:
        return MSSResult(
            type="BEARISH_MSS",
            break_level=last_low,
            close_price=recent_candle["close"]
        )

    return None


# =============================================================================
# Turtle Soup Detection (Counter-Trend Reversal)
# =============================================================================

def find_turtle_soup(
    candles: List[Dict],
    swing_points: Dict[str, List[Tuple[int, float]]],
    lookback_min: int = 4,
    lookback_max: int = 20
) -> List[TurtleSoupResult]:
    """
    Detect Turtle Soup patterns (Linda Bradford Raschke).

    Turtle Soup pattern:
    1. Price takes out a swing high/low from 4-20 bars ago
    2. This is a "false breakout" or "stop run"
    3. Price then closes back inside the previous range
    4. Entry is taken on the failure of the breakout

    For LONG (Turtle Soup Long):
    - Price breaks below a recent swing low (4-20 bars)
    - Then closes back above that swing low
    - Enter long on the reversal

    For SHORT (Turtle Soup Short):
    - Price breaks above a recent swing high (4-20 bars)
    - Then closes back below that swing high
    - Enter short on the reversal

    Rule Refs:
    - 3.4: Liquidity sweep (stop hunt)
    - 2.3: MSS after sweep
    - 6.7: Turtle Soup entry model
    """
    turtle_soups = []

    if len(candles) < lookback_max + 2:
        return turtle_soups

    # Get the recent candle (the one that could complete the pattern)
    recent_idx = len(candles) - 1
    recent_candle = candles[recent_idx]
    prev_candle = candles[recent_idx - 1]

    # Look for Turtle Soup Long (failed breakdown)
    for swing_idx, swing_low in swing_points.get("swing_lows", []):
        bars_ago = recent_idx - swing_idx

        # Swing must be within lookback range
        if bars_ago < lookback_min or bars_ago > lookback_max:
            continue

        # Pattern: previous candle broke below swing low, current candle closed above
        if prev_candle["low"] < swing_low and recent_candle["close"] > swing_low:
            # Calculate reversal strength (how far price reversed)
            sweep_range = swing_low - prev_candle["low"]
            reversal_range = recent_candle["close"] - swing_low
            reversal_strength = min(reversal_range / max(sweep_range, 0.0001), 1.0)

            turtle_soups.append(TurtleSoupResult(
                type="TURTLE_SOUP_LONG",
                swing_taken=swing_low,
                sweep_extreme=prev_candle["low"],
                close_back=recent_candle["close"],
                candle_index=recent_idx,
                lookback_period=bars_ago,
                reversal_strength=round(reversal_strength, 3)
            ))

    # Look for Turtle Soup Short (failed breakout)
    for swing_idx, swing_high in swing_points.get("swing_highs", []):
        bars_ago = recent_idx - swing_idx

        # Swing must be within lookback range
        if bars_ago < lookback_min or bars_ago > lookback_max:
            continue

        # Pattern: previous candle broke above swing high, current candle closed below
        if prev_candle["high"] > swing_high and recent_candle["close"] < swing_high:
            # Calculate reversal strength
            sweep_range = prev_candle["high"] - swing_high
            reversal_range = swing_high - recent_candle["close"]
            reversal_strength = min(reversal_range / max(sweep_range, 0.0001), 1.0)

            turtle_soups.append(TurtleSoupResult(
                type="TURTLE_SOUP_SHORT",
                swing_taken=swing_high,
                sweep_extreme=prev_candle["high"],
                close_back=recent_candle["close"],
                candle_index=recent_idx,
                lookback_period=bars_ago,
                reversal_strength=round(reversal_strength, 3)
            ))

    # Sort by reversal strength (strongest first)
    turtle_soups.sort(key=lambda x: x.reversal_strength, reverse=True)

    return turtle_soups


# =============================================================================
# Premium/Discount Zone (Rule 5.1)
# =============================================================================

def calculate_premium_discount(
    current_price: float,
    range_high: float,
    range_low: float,
    bias: BiasDirection
) -> PDZone:
    """
    Determine if price is in Premium or Discount zone.
    Rule Ref: 5.1 - PD Arrays
    """
    if range_high == range_low:
        return PDZone(zone="EQUILIBRIUM", level=0.5, favorable=False)

    level = (current_price - range_low) / (range_high - range_low)

    if bias == BiasDirection.BULLISH:
        zone = "DISCOUNT" if level < 0.5 else "PREMIUM"
        favorable = zone == "DISCOUNT"
    else:
        zone = "PREMIUM" if level < 0.5 else "DISCOUNT"
        favorable = zone == "PREMIUM"

    return PDZone(zone=zone, level=round(level, 3), favorable=favorable)


# =============================================================================
# OTE Zone Calculation (Rule 6.1)
# =============================================================================

def calculate_ote_zone(
    swing_high: float,
    swing_low: float,
    direction: BiasDirection
) -> OTEZone:
    """
    Calculate Optimal Trade Entry (OTE) Fibonacci levels.
    Rule Ref: 6.1 - OTE Zone (62%-79%)
    """
    range_size = swing_high - swing_low

    if direction == BiasDirection.BULLISH:
        # Retracement from high for bullish entry
        ote_62 = swing_high - (range_size * 0.618)
        ote_705 = swing_high - (range_size * 0.705)
        ote_79 = swing_high - (range_size * 0.79)
        return OTEZone(
            direction=OrderDirection.LONG,
            zone_top=round(ote_62, 5),
            zone_mid=round(ote_705, 5),
            zone_bottom=round(ote_79, 5)
        )
    else:
        # Retracement from low for bearish entry
        ote_62 = swing_low + (range_size * 0.618)
        ote_705 = swing_low + (range_size * 0.705)
        ote_79 = swing_low + (range_size * 0.79)
        return OTEZone(
            direction=OrderDirection.SHORT,
            zone_top=round(ote_79, 5),
            zone_mid=round(ote_705, 5),
            zone_bottom=round(ote_62, 5)
        )


# =============================================================================
# Risk Calculations (Rule 7.1, 7.2)
# =============================================================================

def calculate_position_size(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    pip_value: float = 10.0
) -> Dict[str, float]:
    """
    Calculate position size based on fixed percentage risk.
    Rule Ref: 7.1 - Fixed Percentage Risk
    """
    risk_amount = account_balance * (risk_pct / 100)
    stop_distance_pips = abs(entry_price - stop_loss) * 10000

    if stop_distance_pips == 0:
        return {"position_size": 0, "risk_amount": 0, "stop_pips": 0}

    position_size = risk_amount / (stop_distance_pips * pip_value)

    return {
        "position_size": round(position_size, 2),
        "risk_amount": round(risk_amount, 2),
        "stop_pips": round(stop_distance_pips, 1)
    }


def calculate_risk_reward(
    entry_price: float,
    stop_loss: float,
    take_profit: float
) -> Dict[str, Any]:
    """
    Calculate Risk:Reward ratio.
    Rule Ref: 7.2 - Minimum 1:2 R:R
    """
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)

    if risk == 0:
        return {"rr": 0, "meets_minimum": False}

    rr = reward / risk

    return {
        "rr": round(rr, 2),
        "meets_minimum": rr >= 2.0,
        "risk_pips": round(risk * 10000, 1),
        "reward_pips": round(reward * 10000, 1)
    }


# =============================================================================
# Confluence Score Calculation
# =============================================================================

def calculate_confluence_score(
    checks: Dict[str, bool],
    config: Optional[RulesConfig] = None
) -> int:
    """
    Calculate confluence score (0-10) based on passed checks.
    """
    if config is None:
        config = get_rules()

    weights = config.confluence_weights
    score = 0

    if checks.get("htf_bias_exists"):
        score += weights.htf_bias_exists
    if checks.get("ltf_aligned"):
        score += weights.ltf_aligned
    if checks.get("fvg_or_ob_present"):
        score += weights.fvg_or_ob_present
    if checks.get("liquidity_sweep"):
        score += weights.liquidity_sweep
    if checks.get("pd_favorable"):
        score += weights.pd_favorable
    if checks.get("session_ok"):
        score += weights.session_ok
    if checks.get("news_ok"):
        score += weights.news_ok

    return min(score, 10)


# =============================================================================
# Backtest Execution Tools
# =============================================================================

def execute_backtest_trade(
    direction: Literal["LONG", "SHORT"],
    entry_price: float,
    stop_loss: float,
    take_profit: Optional[float] = None,
    setup_name: str = "Agent Trade",
    risk_reward: Optional[float] = None
) -> Dict[str, Any]:
    """
    Execute a trade in the backtest simulation.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{BACKEND_URL}/backtest/trade/open",
                json={
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "setup_name": setup_name,
                    "risk_reward": risk_reward,
                    "auto_calculate": True
                }
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
) -> Dict[str, Any]:
    """
    Close an open position in the backtest simulation.
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
                return {"success": False, "error": f"HTTP {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_backtest_positions() -> Dict[str, Any]:
    """
    Get all open positions in the backtest simulation.
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


def step_backtest_forward(bars: int = 1) -> Dict[str, Any]:
    """
    Advance the backtest simulation by N bars.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
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
                    "auto_closed_trades": result.get("auto_closed_trades", [])
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}
