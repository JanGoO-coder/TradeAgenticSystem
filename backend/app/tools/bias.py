"""
Bias Observation Tools.

Analyzes higher timeframe and lower timeframe data to determine
directional bias and alignment. Pure observation - no trading signals.
"""
from typing import List, Optional


def get_htf_bias(htf_candles: List[dict], lookback: int = 2) -> dict:
    """
    Determine Higher Timeframe (HTF) bias from structure analysis.

    HTF bias is the overall directional context from 1H or higher.
    This is the "narrative" - where is price likely going?

    Args:
        htf_candles: List of HTF OHLCV candles (typically 1H)
        lookback: Swing detection lookback

    Returns:
        {
            "bias": "BULLISH" | "BEARISH" | "NEUTRAL",
            "structure": "HH_HL" | "LH_LL" | "MIXED" | "UNCLEAR",
            "confidence": float,  # 0.0 to 1.0
            "key_levels": {
                "last_swing_high": float,
                "last_swing_low": float
            },
            "price_position": str,  # Description of where price is
            "observation": str
        }
    """
    from app.tools.structure import get_market_structure, get_swing_points

    if len(htf_candles) < 10:
        return {
            "bias": "NEUTRAL",
            "structure": "UNCLEAR",
            "confidence": 0.0,
            "key_levels": {},
            "price_position": "Insufficient data",
            "observation": "Insufficient HTF data for bias determination"
        }

    # Get structure
    structure = get_market_structure(htf_candles, lookback)
    swings = get_swing_points(htf_candles, lookback)

    current_price = htf_candles[-1]["close"]

    # Determine bias from structure
    if structure["structure"] == "HH_HL":
        bias = "BULLISH"
        confidence = 0.8
    elif structure["structure"] == "LH_LL":
        bias = "BEARISH"
        confidence = 0.8
    elif structure["structure"] == "MIXED":
        # Use price trajectory as tiebreaker
        first_close = htf_candles[0]["close"]
        price_change = (current_price - first_close) / first_close

        if price_change > 0.002:  # > 0.2% up
            bias = "BULLISH"
            confidence = 0.5
        elif price_change < -0.002:
            bias = "BEARISH"
            confidence = 0.5
        else:
            bias = "NEUTRAL"
            confidence = 0.3
    else:
        bias = "NEUTRAL"
        confidence = 0.2

    # Get key levels
    last_high = swings["latest_swing_high"]["price"] if swings["latest_swing_high"] else None
    last_low = swings["latest_swing_low"]["price"] if swings["latest_swing_low"] else None

    # Describe price position
    if last_high and last_low:
        range_size = last_high - last_low
        position = (current_price - last_low) / range_size if range_size > 0 else 0.5

        if position > 0.7:
            price_position = f"Near swing high ({position * 100:.0f}% of range)"
        elif position < 0.3:
            price_position = f"Near swing low ({position * 100:.0f}% of range)"
        else:
            price_position = f"Mid-range ({position * 100:.0f}% of range)"
    else:
        price_position = "Unable to determine"

    return {
        "bias": bias,
        "structure": structure["structure"],
        "confidence": confidence,
        "key_levels": {
            "last_swing_high": last_high,
            "last_swing_low": last_low
        },
        "price_position": price_position,
        "swing_sequence": structure.get("swing_sequence", []),
        "observation": (
            f"HTF Bias: {bias} (confidence: {confidence:.0%}). "
            f"Structure: {structure['structure']}. "
            f"{structure.get('observation', '')}"
        )
    }


def check_ltf_alignment(
    ltf_candles: List[dict],
    htf_bias: str,
    lookback: int = 2
) -> dict:
    """
    Check if Lower Timeframe (LTF) structure aligns with HTF bias.

    LTF alignment means the shorter timeframe is moving in the same
    direction as the HTF narrative.

    Args:
        ltf_candles: List of LTF OHLCV candles (typically 15M or 5M)
        htf_bias: The HTF bias ("BULLISH", "BEARISH", "NEUTRAL")
        lookback: Swing detection lookback

    Returns:
        {
            "aligned": bool,
            "ltf_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
            "ltf_structure": str,
            "alignment_type": "STRONG" | "WEAK" | "CONFLICTING" | "NEUTRAL",
            "mss_detected": dict | None,  # Market Structure Shift if present
            "observation": str
        }
    """
    from app.tools.structure import get_market_structure, detect_mss, get_swing_points

    if len(ltf_candles) < 10:
        return {
            "aligned": False,
            "ltf_bias": "NEUTRAL",
            "ltf_structure": "UNCLEAR",
            "alignment_type": "NEUTRAL",
            "mss_detected": None,
            "observation": "Insufficient LTF data for alignment check"
        }

    # Get LTF structure
    ltf_structure = get_market_structure(ltf_candles, lookback)
    swings = get_swing_points(ltf_candles, lookback)

    # Check for MSS
    mss = detect_mss(ltf_candles, swings)

    # Determine LTF bias
    if ltf_structure["structure"] == "HH_HL":
        ltf_bias = "BULLISH"
    elif ltf_structure["structure"] == "LH_LL":
        ltf_bias = "BEARISH"
    else:
        ltf_bias = "NEUTRAL"

    # Check alignment
    if htf_bias == "NEUTRAL" or ltf_bias == "NEUTRAL":
        aligned = False
        alignment_type = "NEUTRAL"
    elif htf_bias == ltf_bias:
        aligned = True
        # Check if MSS confirms the direction
        if mss:
            if (htf_bias == "BULLISH" and mss["type"] == "BULLISH_MSS") or \
               (htf_bias == "BEARISH" and mss["type"] == "BEARISH_MSS"):
                alignment_type = "STRONG"
            else:
                alignment_type = "WEAK"
        else:
            alignment_type = "WEAK"
    else:
        aligned = False
        alignment_type = "CONFLICTING"

    # Build observation
    if aligned:
        obs = (
            f"LTF ALIGNED with HTF {htf_bias} bias. "
            f"LTF structure: {ltf_structure['structure']}. "
            f"Alignment: {alignment_type}."
        )
        if mss:
            obs += f" MSS detected: {mss['type']}."
    else:
        obs = (
            f"LTF NOT aligned with HTF {htf_bias} bias. "
            f"LTF bias: {ltf_bias}, structure: {ltf_structure['structure']}."
        )
        if mss:
            obs += f" MSS detected: {mss['type']}."

    return {
        "aligned": aligned,
        "ltf_bias": ltf_bias,
        "ltf_structure": ltf_structure["structure"],
        "alignment_type": alignment_type,
        "mss_detected": mss,
        "observation": obs
    }


def get_multi_timeframe_confluence(
    htf_candles: List[dict],
    ltf_candles: List[dict],
    micro_candles: Optional[List[dict]] = None
) -> dict:
    """
    Analyze multiple timeframes for confluence.

    Checks alignment across HTF (1H), LTF (15M), and optionally Micro (5M)
    timeframes for stronger confirmation.

    Args:
        htf_candles: 1H candles
        ltf_candles: 15M candles
        micro_candles: 5M candles (optional)

    Returns:
        {
            "confluence_score": int,  # 0-3 (or 0-4 with micro)
            "htf_bias": dict,
            "ltf_alignment": dict,
            "micro_alignment": dict | None,
            "overall_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
            "trade_readiness": "HIGH" | "MEDIUM" | "LOW" | "NONE",
            "observation": str
        }
    """
    # Get HTF bias
    htf_bias = get_htf_bias(htf_candles)

    # Check LTF alignment
    ltf_alignment = check_ltf_alignment(ltf_candles, htf_bias["bias"])

    # Check micro alignment if provided
    micro_alignment = None
    if micro_candles:
        micro_alignment = check_ltf_alignment(micro_candles, htf_bias["bias"], lookback=1)

    # Calculate confluence score
    score = 0

    if htf_bias["bias"] != "NEUTRAL":
        score += 1
        if htf_bias["confidence"] >= 0.7:
            score += 1

    if ltf_alignment["aligned"]:
        score += 1
        if ltf_alignment["alignment_type"] == "STRONG":
            score += 1

    if micro_alignment and micro_alignment["aligned"]:
        score += 1

    # Determine overall bias
    if htf_bias["bias"] != "NEUTRAL" and ltf_alignment["aligned"]:
        overall_bias = htf_bias["bias"]
    elif htf_bias["bias"] != "NEUTRAL":
        overall_bias = htf_bias["bias"]
    else:
        overall_bias = "NEUTRAL"

    # Determine trade readiness
    max_score = 5 if micro_candles else 4

    if score >= max_score - 1:
        readiness = "HIGH"
    elif score >= max_score // 2:
        readiness = "MEDIUM"
    elif score >= 1:
        readiness = "LOW"
    else:
        readiness = "NONE"

    return {
        "confluence_score": score,
        "max_score": max_score,
        "htf_bias": htf_bias,
        "ltf_alignment": ltf_alignment,
        "micro_alignment": micro_alignment,
        "overall_bias": overall_bias,
        "trade_readiness": readiness,
        "observation": (
            f"Multi-TF Confluence: {score}/{max_score}. "
            f"Overall bias: {overall_bias}. "
            f"Trade readiness: {readiness}. "
            f"HTF: {htf_bias['bias']}, LTF aligned: {ltf_alignment['aligned']}"
            + (f", Micro aligned: {micro_alignment['aligned']}" if micro_alignment else "")
        )
    }
