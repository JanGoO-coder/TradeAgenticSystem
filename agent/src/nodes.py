"""LangGraph Nodes for ICT Trading System per system_plan.md."""
from typing import Dict, Any
from datetime import datetime

from src.models import (
    GraphState, HTFBias, LTFAlignment, TradeSetup, RiskParameters,
    ExecutionChecklist, BiasValue, AlignmentStatus, TradeStatus, EntryType
)
from src.tools import (
    get_market_structure, detect_displacement, detect_fvg,
    check_pd_array, calculate_ote_fib, scan_liquidity_sweeps,
    detect_mss, check_kill_zone, detect_session, fetch_news_impact,
    calc_position_size, calculate_rr, calculate_confluence_score,
    identify_swing_points
)


# ============================================================================
# NODE A: MACRO ANALYST (Bias Engine) - Rules 1.1, 1.1.1, 1.1.2
# ============================================================================

def macro_analyst_node(state: GraphState) -> GraphState:
    """
    Agent A: The "Macro Analyst" (Bias Engine)
    Role: Determines the 1H Directional Bias (Rule 1.1)
    Input: 1H OHLCV Data
    Output: BIAS: BULLISH, BIAS: BEARISH, or BIAS: NEUTRAL
    """
    state.nodes_triggered.append("Macro_Analyst")
    
    # Get 1H candle data
    htf_candles = state.snapshot.timeframe_bars.get("1H", [])
    
    if not htf_candles or len(htf_candles) < 10:
        state.htf_bias = HTFBias(
            value=BiasValue.NEUTRAL,
            rule_refs=["1.1", "9.2"]
        )
        state.reason_short = "Insufficient 1H data for bias determination"
        return state
    
    # Apply Rule 1.1: HTF Bias using structure
    structure_result = get_market_structure(htf_candles)
    
    # Check for displacement (Rule 2.2) to validate structure break
    displacements = detect_displacement(htf_candles)
    has_recent_displacement = any(
        d["index"] >= len(htf_candles) - 5 for d in displacements
    )
    
    # Per Rule 1.1.1: Trades allowed only when 1H structure is clean
    if structure_result["structure"] == "UNCLEAR":
        state.htf_bias = HTFBias(
            value=BiasValue.NEUTRAL,
            rule_refs=["1.1", "1.1.1"]
        )
        state.reason_short = "1H structure unclear - ranging or overlapping"
    else:
        state.htf_bias = HTFBias(
            value=structure_result["bias"],
            rule_refs=structure_result["rule_refs"]
        )
    
    return state


# ============================================================================
# NODE B: GATEKEEPER (Risk & Time) - Rules 8.1, 8.4, 9.2
# ============================================================================

def gatekeeper_node(state: GraphState) -> GraphState:
    """
    Agent B: The "Gatekeeper" (Risk & Time)
    Role: Enforces Rule 8 (Kill Zones) and Rule 8.4 (News)
    Input: Current Time, Economic Calendar
    Output: STATUS: GO or STATUS: WAIT
    """
    state.nodes_triggered.append("Gatekeeper")
    state.gatekeeper_failures = []
    
    # Parse timestamp
    try:
        timestamp = datetime.fromisoformat(state.snapshot.timestamp.replace('Z', '+00:00'))
    except:
        timestamp = datetime.now()
    
    # CHECK 1: HTF Bias must exist (Rule 1.1)
    if state.htf_bias is None or state.htf_bias.value == BiasValue.NEUTRAL:
        state.gatekeeper_failures.append("1.1: HTF bias unclear")
    
    # CHECK 2: Kill Zone (Rule 8.1)
    kz_result = check_kill_zone(timestamp)
    if not kz_result["in_kill_zone"]:
        state.gatekeeper_failures.append("8.1: Outside Kill Zone")
    
    # CHECK 3: Session detection
    session = state.snapshot.session or detect_session(timestamp)
    
    # CHECK 4: News Rules (Rule 8.4)
    news_result = fetch_news_impact(state.snapshot.economic_calendar, timestamp)
    if news_result["status"] == "BLOCKED":
        state.gatekeeper_failures.append(f"8.4: {news_result['reason']}")
    
    # Determine gatekeeper status
    if state.gatekeeper_failures:
        state.gatekeeper_status = "WAIT"
        state.final_status = TradeStatus.WAIT
        state.reason_short = f"Gatekeeper WAIT: {', '.join(state.gatekeeper_failures)}"
    else:
        state.gatekeeper_status = "GO"
    
    return state


# ============================================================================
# NODE C: SNIPER (Pattern Recognition) - Rules 6.1-6.7
# ============================================================================

def sniper_node(state: GraphState) -> GraphState:
    """
    Agent C: The "Sniper" (Pattern Recognition)
    Role: Scans 15M/5M for entry models (OTE, 2022 Model) matching Bias
    Input: 15M/5M Data + Bias from Agent A
    Output: SETUP_FOUND with entry details
    """
    state.nodes_triggered.append("Sniper")
    
    # Skip if gatekeeper failed
    if state.gatekeeper_status == "WAIT":
        return state
    
    bias = state.htf_bias.value if state.htf_bias else BiasValue.NEUTRAL
    
    # Get LTF candles
    ltf_candles_15m = state.snapshot.timeframe_bars.get("15M", [])
    ltf_candles_5m = state.snapshot.timeframe_bars.get("5M", [])
    
    # Use 15M as primary LTF
    ltf_candles = ltf_candles_15m if ltf_candles_15m else ltf_candles_5m
    ltf_timeframe = "15M" if ltf_candles_15m else "5M"
    
    if not ltf_candles or len(ltf_candles) < 10:
        state.ltf_alignment = LTFAlignment(
            timeframe=ltf_timeframe,
            alignment=AlignmentStatus.NOT_ALIGNED,
            rule_refs=["1.2"]
        )
        return state
    
    # Get swing points for LTF
    swing_points = identify_swing_points(ltf_candles)
    
    # Check LTF alignment with HTF (Rule 1.2)
    ltf_structure = get_market_structure(ltf_candles)
    ltf_aligned = (
        (bias == BiasValue.BULLISH and ltf_structure["bias"] == BiasValue.BULLISH) or
        (bias == BiasValue.BEARISH and ltf_structure["bias"] == BiasValue.BEARISH)
    )
    
    state.ltf_alignment = LTFAlignment(
        timeframe=ltf_timeframe,
        alignment=AlignmentStatus.ALIGNED if ltf_aligned else AlignmentStatus.NOT_ALIGNED,
        rule_refs=["1.2", "1.2.1"]
    )
    
    # Detect FVGs (Rule 5.2, 6.2)
    fvgs = detect_fvg(ltf_candles)
    
    # Detect liquidity sweeps (Rule 3.1, 3.4)
    sweeps = scan_liquidity_sweeps(ltf_candles, swing_points)
    
    # Detect MSS (Rule 2.3)
    mss = detect_mss(ltf_candles, swing_points)
    
    # Get current price and range
    current_price = ltf_candles[-1]["close"]
    range_high = max(c["high"] for c in ltf_candles[-20:])
    range_low = min(c["low"] for c in ltf_candles[-20:])
    
    # Check PD array (Rule 5.1)
    pd_result = check_pd_array(current_price, range_high, range_low, bias.value)
    
    # Calculate OTE zone (Rule 6.1)
    ote = calculate_ote_fib(range_high, range_low, bias.value)
    
    # BUILD SETUP based on bias
    rule_refs = []
    setup_name = ""
    setup_type = ""
    entry_price = None
    stop_loss = None
    take_profit = []
    invalidation = None
    is_counter_trend = False
    
    # Filter FVGs by bias direction
    aligned_fvgs = [f for f in fvgs if 
                   (bias == BiasValue.BULLISH and f["type"] == "BULLISH_FVG") or
                   (bias == BiasValue.BEARISH and f["type"] == "BEARISH_FVG")]
    
    if bias == BiasValue.BULLISH and ltf_aligned:
        # BULLISH SETUP OPTIONS
        
        if sweeps and any(s["type"] == "SELL_SIDE_SWEEP" for s in sweeps) and aligned_fvgs:
            # ICT 2022 Model (Rule 6.5) - Best setup: sweep + displacement + FVG
            setup_name = "Bullish ICT 2022"
            setup_type = "ICT_2022"
            rule_refs = ["6.5", "2.3", "3.4", "5.2"]
            
            sweep = next(s for s in sweeps if s["type"] == "SELL_SIDE_SWEEP")
            fvg = aligned_fvgs[-1]  # Most recent FVG
            
            entry_price = fvg["top"]  # Entry at top of FVG
            stop_loss = sweep["sweep_low"] - 0.0005  # Below sweep
            invalidation = stop_loss
            take_profit = [current_price + (current_price - stop_loss) * 2]  # 1:2 RR
            
        elif aligned_fvgs:
            # FVG Entry (Rule 6.2) - Entry on retrace into FVG
            fvg = aligned_fvgs[-1]  # Most recent aligned FVG
            setup_name = "Bullish FVG Entry"
            setup_type = "FVG"
            rule_refs = ["6.2", "5.2", "1.2"]
            
            entry_price = fvg["midpoint"]  # Entry at consequent encroachment (50%)
            stop_loss = fvg["bottom"] - 0.0005  # Below FVG
            invalidation = fvg["bottom"]
            # TP at next swing high + 1R extension
            take_profit = [range_high, range_high + (fvg["midpoint"] - fvg["bottom"])]
            
        elif pd_result["favorable"] and ote:
            # OTE Entry (Rule 6.1)
            setup_name = "Bullish OTE"
            setup_type = "OTE"
            rule_refs = ["6.1", "5.1", "1.2"]
            
            entry_price = ote["ote_zone_mid"]
            stop_loss = range_low - 0.0005
            invalidation = range_low
            take_profit = [range_high, range_high + (range_high - range_low)]
    
    elif bias == BiasValue.BEARISH and ltf_aligned:
        # BEARISH SETUP OPTIONS
        
        if sweeps and any(s["type"] == "BUY_SIDE_SWEEP" for s in sweeps) and aligned_fvgs:
            # ICT 2022 Model (Rule 6.5)
            setup_name = "Bearish ICT 2022"
            setup_type = "ICT_2022"
            rule_refs = ["6.5", "2.3", "3.4", "5.2"]
            
            sweep = next(s for s in sweeps if s["type"] == "BUY_SIDE_SWEEP")
            fvg = aligned_fvgs[-1]
            
            entry_price = fvg["bottom"]
            stop_loss = sweep["sweep_high"] + 0.0005
            invalidation = stop_loss
            take_profit = [current_price - (stop_loss - current_price) * 2]
            
        elif aligned_fvgs:
            # FVG Entry (Rule 6.2)
            fvg = aligned_fvgs[-1]
            setup_name = "Bearish FVG Entry"
            setup_type = "FVG"
            rule_refs = ["6.2", "5.2", "1.2"]
            
            entry_price = fvg["midpoint"]
            stop_loss = fvg["top"] + 0.0005
            invalidation = fvg["top"]
            take_profit = [range_low, range_low - (fvg["top"] - fvg["midpoint"])]
            
        elif pd_result["favorable"] and ote:
            # OTE Entry (Rule 6.1)
            setup_name = "Bearish OTE"
            setup_type = "OTE"
            rule_refs = ["6.1", "5.1", "1.2"]
            
            entry_price = ote["ote_zone_mid"]
            stop_loss = range_high + 0.0005
            invalidation = range_high
            take_profit = [range_low, range_low - (range_high - range_low)]
    
    # Check for counter-trend (Rule 1.2.2)
    if mss and not ltf_aligned:
        # Counter-trend requires 1H MSS confirmation
        htf_candles = state.snapshot.timeframe_bars.get("1H", [])
        if htf_candles:
            htf_swings = identify_swing_points(htf_candles)
            htf_mss = detect_mss(htf_candles, htf_swings)
            
            if htf_mss:
                is_counter_trend = True
                rule_refs.append("1.2.2")
            else:
                # Cannot take counter-trend without 1H MSS
                setup_name = ""
                state.reason_short = "Counter-trend blocked: No 1H MSS (Rule 1.2.2)"
    
    # Calculate confluence score
    confluence_checks = {
        "htf_bias_exists": bias != BiasValue.NEUTRAL,
        "ltf_aligned": ltf_aligned,
        "fvg_or_ob_present": len(aligned_fvgs) > 0,
        "liquidity_sweep": len(sweeps) > 0,
        "pd_favorable": pd_result.get("favorable", False),
        "session_ok": state.gatekeeper_status == "GO",
        "news_ok": "8.4" not in str(state.gatekeeper_failures)
    }
    confluence_score = calculate_confluence_score(confluence_checks)
    
    if setup_name and entry_price:
        state.detected_setup = TradeSetup(
            name=setup_name,
            type=setup_type,
            entry_price=round(entry_price, 5),
            entry_type=EntryType.LIMIT,
            stop_loss=round(stop_loss, 5) if stop_loss else None,
            take_profit=[round(tp, 5) for tp in take_profit] if take_profit else None,
            invalidation_point=round(invalidation, 5) if invalidation else None,
            is_counter_trend=is_counter_trend,
            confluence_score=confluence_score,
            rule_refs=rule_refs
        )
    else:
        state.final_status = TradeStatus.NO_TRADE
        if not state.reason_short:
            state.reason_short = "No valid setup found matching ICT criteria"
    
    return state


# ============================================================================
# NODE D: RISK CALCULATOR - Rules 7.1, 7.2
# ============================================================================

def risk_calculator_node(state: GraphState) -> GraphState:
    """
    Agent D: Risk Calculator
    Role: Sizes the position per fixed percentage risk
    Rules: 7.1 (Fixed % Risk), 7.2 (R:R minimum 1:2)
    """
    state.nodes_triggered.append("Risk_Calculator")
    
    if not state.detected_setup or state.final_status in [TradeStatus.WAIT, TradeStatus.NO_TRADE]:
        return state
    
    setup = state.detected_setup
    
    # Calculate position size (Rule 7.1)
    if setup.entry_price and setup.stop_loss:
        size_result = calc_position_size(
            account_balance=state.snapshot.account_balance,
            risk_pct=state.snapshot.risk_pct,
            entry_price=setup.entry_price,
            stop_loss=setup.stop_loss
        )
        
        # Calculate R:R (Rule 7.2)
        rr = None
        rr_ok = False
        if setup.take_profit and len(setup.take_profit) > 0:
            rr_result = calculate_rr(
                setup.entry_price,
                setup.stop_loss,
                setup.take_profit[0]
            )
            rr = rr_result["rr"]
            rr_ok = rr_result["meets_minimum"]
        
        state.risk_params = RiskParameters(
            account_balance=state.snapshot.account_balance,
            risk_pct=state.snapshot.risk_pct,
            position_size=size_result["position_size"],
            rr=rr
        )
        
        # Reject if R:R doesn't meet minimum (Rule 7.2)
        if rr and not rr_ok:
            state.final_status = TradeStatus.NO_TRADE
            state.reason_short = f"R:R {rr} below minimum 1:2 (Rule 7.2)"
    
    return state


# ============================================================================
# NODE E: EXECUTOR (Checklist & Final Output) - Rule 10
# ============================================================================

def executor_node(state: GraphState) -> GraphState:
    """
    Agent E: Executor
    Role: Validates execution checklist and prepares final output
    Rule: 10 (Execution Checklist)
    
    Note: For this implementation, we DO NOT execute - only output setup.
    """
    state.nodes_triggered.append("Executor")
    
    # Build execution checklist (Rule 10)
    bias_exists = bool(state.htf_bias and state.htf_bias.value != BiasValue.NEUTRAL)
    ltf_mss = bool(state.ltf_alignment and state.ltf_alignment.alignment == AlignmentStatus.ALIGNED)
    has_sweep = bool(state.detected_setup is not None and "3.4" in state.detected_setup.rule_refs) if state.detected_setup else False
    rr_ok = bool(state.risk_params and state.risk_params.rr and state.risk_params.rr >= 2.0) if state.risk_params else False
    
    state.checklist = ExecutionChecklist(
        htf_bias_exists=bias_exists,
        ltf_mss=ltf_mss,
        pd_alignment=state.detected_setup is not None,
        liquidity_sweep_detected=has_sweep,
        session_ok=state.gatekeeper_status == "GO",
        news_ok="8.4" not in str(state.gatekeeper_failures),
        rr_minimum_met=rr_ok
    )
    
    # Determine final status
    if state.final_status is None:
        if state.detected_setup and all([
            state.checklist.htf_bias_exists,
            state.checklist.session_ok,
            state.checklist.news_ok
        ]):
            state.final_status = TradeStatus.TRADE_NOW
            state.reason_short = f"Valid {state.detected_setup.name} setup detected"
        elif state.gatekeeper_status == "WAIT":
            state.final_status = TradeStatus.WAIT
        else:
            state.final_status = TradeStatus.NO_TRADE
    
    # Calculate confidence
    if state.detected_setup:
        base_confidence = state.detected_setup.confluence_score / 10
        # Adjust for checklist items
        passed_checks = sum([
            state.checklist.htf_bias_exists,
            state.checklist.ltf_mss,
            state.checklist.pd_alignment,
            state.checklist.liquidity_sweep_detected,
            state.checklist.session_ok,
            state.checklist.news_ok,
            state.checklist.rr_minimum_met
        ])
        state.confidence = round(min((base_confidence + (passed_checks / 14)), 1.0), 2)
    else:
        state.confidence = 0.0
    
    # Build explanation
    state.explanation = build_explanation(state)
    
    return state


def build_explanation(state: GraphState) -> str:
    """Build human-readable explanation mapping outputs to rules."""
    parts = []
    
    if state.htf_bias:
        parts.append(
            f"HTF Bias: {state.htf_bias.value.value} per Rules {', '.join(state.htf_bias.rule_refs)}"
        )
    
    if state.ltf_alignment:
        parts.append(
            f"LTF ({state.ltf_alignment.timeframe}): {state.ltf_alignment.alignment.value} "
            f"per Rules {', '.join(state.ltf_alignment.rule_refs)}"
        )
    
    if state.detected_setup:
        parts.append(
            f"Setup: {state.detected_setup.name} ({state.detected_setup.type}) "
            f"with confluence score {state.detected_setup.confluence_score}/10 "
            f"per Rules {', '.join(state.detected_setup.rule_refs)}"
        )
        
        if state.detected_setup.is_counter_trend:
            parts.append("Counter-trend validated with 1H MSS per Rule 1.2.2")
    
    if state.risk_params:
        parts.append(
            f"Risk: {state.risk_params.risk_pct}% of ${state.risk_params.account_balance} = "
            f"{state.risk_params.position_size} lots, R:R {state.risk_params.rr} per Rules 7.1, 7.2"
        )
    
    if state.gatekeeper_failures:
        parts.append(f"Gatekeeper blocks: {', '.join(state.gatekeeper_failures)}")
    
    return " | ".join(parts)
