"""
Enhanced Prompts for Neuro-Symbolic Strategy Agent.

These prompts guide the LLM (brain) to interpret objective market facts
against natural-language trading strategies.
"""
from typing import Dict, Any, List, Optional


# =============================================================================
# System Prompt (LLM Role Definition)
# =============================================================================

SYSTEM_PROMPT = """You are an expert ICT (Inner Circle Trader) analyst acting as the decision-making brain of a trading system.

Your role is to interpret OBJECTIVE MARKET FACTS against a TRADING STRATEGY PLAYBOOK and determine:
1. The current market BIAS (directional tendency based on structure)
2. Whether conditions are suitable for a TRADE

## Your Analysis Framework

### Step 1: Assess Market Structure
Examine the swing point relationships across timeframes:
- Higher Highs + Higher Lows = Bullish structure
- Lower Highs + Lower Lows = Bearish structure
- Mixed, unclear, or no swing points = Ranging/Neutral

### Step 2: Check Time & Session
- Is the current time/session allowed by the strategy?
- Are we inside a valid trading window (Kill Zone, Silver Bullet)?
- Weekend or off-hours = NO TRADE

### Step 3: Identify Entry Conditions
Based on the strategy's requirements, check:
- Fair Value Gaps (FVGs) present and aligned with bias?
- Liquidity sweeps occurred (price rejected from swing levels)?
- Price in appropriate zone for the direction?

### Step 4: Make Decision
- All required conditions met = TRADE
- Some conditions met, monitoring = MONITOR
- Structure unclear, wrong session, or missing conditions = WAIT

## Output Format (JSON)
You MUST return valid JSON matching this schema:
{
    "bias": "BULLISH" | "BEARISH" | "NEUTRAL",
    "confidence": 0.0 to 1.0,
    "reasoning": "Step-by-step explanation of your analysis",
    "action": "TRADE" | "MONITOR" | "WAIT",
    "key_levels": {
        "entry_zone": [low_price, high_price] or null,
        "stop_loss": price or null,
        "target": price or null
    },
    "structure_assessment": "Brief summary of market structure",
    "session_assessment": "Brief summary of time/session validity",
    "entry_conditions_met": ["condition1", "condition2", ...],
    "blocking_factors": ["factor1", "factor2", ...] (only if action is WAIT)
}

## Critical Rules
1. If the strategy requires a specific session (e.g., "NY Silver Bullet 10-11 AM") and we are NOT in that session, you MUST return bias=NEUTRAL, action=WAIT.
2. Do NOT invent patterns that aren't supported by the factual data provided.
3. Be CONSERVATIVE - when in doubt, return action=WAIT.
4. Your reasoning must reference specific facts from the data provided.
5. The key_levels should only be populated if action=TRADE and you have sufficient data to suggest them.
"""


# =============================================================================
# Prompt Builder
# =============================================================================

def build_analysis_prompt(strategy_text: str, market_facts: Dict[str, Any]) -> str:
    """
    Construct a comprehensive prompt for LLM analysis.
    
    Formats the raw market facts into a human-readable structure
    that helps the LLM reason effectively.
    
    Args:
        strategy_text: Natural language strategy playbook
        market_facts: Dict from build_market_facts()
        
    Returns:
        Complete prompt string
    """
    
    # Format time/session section
    time_section = _format_time_facts(market_facts.get("time", {}))
    
    # Format structure section (multi-timeframe)
    structure_section = _format_structure_facts(market_facts.get("structure", {}))
    
    # Format imbalances (FVGs) section
    imbalance_section = _format_imbalance_facts(market_facts.get("imbalances", {}))
    
    # Format price position section
    position_section = _format_price_position(market_facts.get("price_position", {}))
    
    # Format sweep events section
    sweep_section = _format_sweep_facts(market_facts.get("sweep_events", {}))
    
    # Format liquidity levels
    liquidity_section = _format_liquidity_facts(market_facts.get("liquidity", {}))
    
    # Format Fibonacci if available
    fib_section = _format_fibonacci_facts(market_facts.get("fibonacci", {}))
    
    # Assemble full prompt
    prompt = f"""{SYSTEM_PROMPT}

================================================================================
ACTIVE TRADING STRATEGY (Your Playbook)
================================================================================
{strategy_text}

================================================================================
CURRENT MARKET FACTS (Objective Data)
================================================================================

{time_section}

{structure_section}

{imbalance_section}

{position_section}

{sweep_section}

{liquidity_section}

{fib_section}

================================================================================
YOUR TASK
================================================================================
Based on the STRATEGY PLAYBOOK and MARKET FACTS above, provide your analysis.

Remember:
- If the strategy's required session/time conditions are not met → action=WAIT
- If market structure is unclear → bias=NEUTRAL, action=WAIT
- Only suggest action=TRADE when ALL strategy conditions are satisfied
- Your reasoning must cite specific facts from the data above

Respond with valid JSON only.
"""
    return prompt


# =============================================================================
# Formatting Helpers
# =============================================================================

def _format_time_facts(time_data: Dict[str, Any]) -> str:
    """Format time and session information."""
    if not time_data:
        return "## Time & Session\n(No time data available)"
    
    sessions = time_data.get("sessions", {})
    killzones = time_data.get("killzones", {})
    special_windows = time_data.get("special_windows", {})
    
    # Determine active session name
    active_sessions = [name.upper() for name, data in sessions.items() if data.get("active")]
    active_killzones = [name.replace("_kz", "").upper() for name, data in killzones.items() if data.get("active")]
    active_windows = [name.upper() for name, data in special_windows.items() if data.get("active")]
    
    return f"""## Time & Session Facts

- **Current Time (EST):** {time_data.get('est_time', 'unknown')}
- **Day of Week:** {time_data.get('day_of_week', 'unknown')}
- **Is Weekend:** {'Yes' if time_data.get('is_weekend') else 'No'}

### Session Status
| Session | Active | Hours (EST) |
|---------|--------|-------------|
| Asia | {'✅ ACTIVE' if sessions.get('asia', {}).get('active') else '❌ Inactive'} | {sessions.get('asia', {}).get('description', '18:00-03:00')} |
| London | {'✅ ACTIVE' if sessions.get('london', {}).get('active') else '❌ Inactive'} | {sessions.get('london', {}).get('description', '02:00-11:00')} |
| New York | {'✅ ACTIVE' if sessions.get('new_york', {}).get('active') else '❌ Inactive'} | {sessions.get('new_york', {}).get('description', '07:00-16:00')} |

### Kill Zones
- London Kill Zone (02:00-05:00 EST): {'✅ ACTIVE' if killzones.get('london_kz', {}).get('active') else '❌ Inactive'}
- New York Kill Zone (07:00-10:00 EST): {'✅ ACTIVE' if killzones.get('new_york_kz', {}).get('active') else '❌ Inactive'}

### Special Windows
- Silver Bullet AM (10:00-11:00 EST): {'✅ ACTIVE' if special_windows.get('silver_bullet_am', {}).get('active') else '❌ Inactive'}
- Silver Bullet PM (14:00-15:00 EST): {'✅ ACTIVE' if special_windows.get('silver_bullet_pm', {}).get('active') else '❌ Inactive'}

**Summary:** Active Session(s): {', '.join(active_sessions) if active_sessions else 'None (Off-Hours)'}"""


def _format_structure_facts(structure_data: Dict[str, Any]) -> str:
    """Format market structure across timeframes."""
    if not structure_data:
        return "## Market Structure\n(No structure data available)"
    
    lines = ["## Market Structure\n"]
    
    for tf, data in structure_data.items():
        swing_highs = data.get("swing_highs", [])
        swing_lows = data.get("swing_lows", [])
        high_relation = data.get("latest_high_relation", "unknown")
        low_relation = data.get("latest_low_relation", "unknown")
        
        lines.append(f"### {tf} Timeframe")
        lines.append(f"- Swing Highs Identified: {len(swing_highs)}")
        lines.append(f"- Swing Lows Identified: {len(swing_lows)}")
        lines.append(f"- Latest High vs Previous: **{high_relation.upper()}**")
        lines.append(f"- Latest Low vs Previous: **{low_relation.upper()}**")
        
        if data.get("highest_high") and data.get("lowest_low"):
            lines.append(f"- Range: {data.get('lowest_low'):.5f} to {data.get('highest_high'):.5f}")
        
        # Provide structure interpretation hint
        if high_relation == "higher" and low_relation == "higher":
            lines.append("- Structure Pattern: HH/HL (Potential Bullish)")
        elif high_relation == "lower" and low_relation == "lower":
            lines.append("- Structure Pattern: LH/LL (Potential Bearish)")
        else:
            lines.append("- Structure Pattern: Mixed/Unclear")
        
        lines.append("")
    
    return "\n".join(lines)


def _format_imbalance_facts(imbalance_data: Dict[str, Any]) -> str:
    """Format Fair Value Gap information."""
    if not imbalance_data:
        return "## Fair Value Gaps (FVGs)\n(No FVG data available)"
    
    lines = ["## Fair Value Gaps (FVGs)\n"]
    
    for tf, data in imbalance_data.items():
        bullish = data.get("bullish_fvgs", [])
        bearish = data.get("bearish_fvgs", [])
        
        lines.append(f"### {tf} Timeframe")
        lines.append(f"- Bullish FVGs: {len(bullish)}")
        
        for i, fvg in enumerate(bullish[-3:]):  # Show last 3
            lines.append(f"  - FVG {i+1}: {fvg.get('bottom', 0):.5f} to {fvg.get('top', 0):.5f} (mid: {fvg.get('midpoint', 0):.5f})")
        
        lines.append(f"- Bearish FVGs: {len(bearish)}")
        
        for i, fvg in enumerate(bearish[-3:]):
            lines.append(f"  - FVG {i+1}: {fvg.get('bottom', 0):.5f} to {fvg.get('top', 0):.5f} (mid: {fvg.get('midpoint', 0):.5f})")
        
        lines.append("")
    
    return "\n".join(lines)


def _format_price_position(position_data: Dict[str, Any]) -> str:
    """Format current price position."""
    if not position_data:
        return "## Price Position\n(No price position data available)"
    
    position_pct = position_data.get("position_in_range", 0.5) * 100
    zone = "Upper Half" if position_pct > 50 else "Lower Half"
    
    return f"""## Current Price Position

- **Current Price:** {position_data.get('current_price', 0):.5f}
- **Range High:** {position_data.get('range_high', 0):.5f}
- **Range Low:** {position_data.get('range_low', 0):.5f}
- **Position in Range:** {position_pct:.1f}% (0% = at low, 100% = at high)
- **Zone:** {zone}
- **Distance to High:** {position_data.get('distance_to_high', 0):.5f}
- **Distance to Low:** {position_data.get('distance_to_low', 0):.5f}"""


def _format_sweep_facts(sweep_data: Dict[str, Any]) -> str:
    """Format liquidity sweep events."""
    if not sweep_data:
        return "## Liquidity Sweep Events\n(No sweep data available)"
    
    lines = ["## Liquidity Sweep Events\n"]
    
    for tf, data in sweep_data.items():
        sweeps = data.get("potential_sweeps", [])
        
        lines.append(f"### {tf} Timeframe")
        lines.append(f"- Total Sweeps Detected: {len(sweeps)}")
        
        if sweeps:
            for i, sweep in enumerate(sweeps[-5:]):  # Show last 5
                sweep_type = sweep.get("type", "unknown")
                level = sweep.get("level_swept", 0)
                rejection = sweep.get("rejection_size", 0)
                
                direction = "above swing high (buy-side)" if "above" in sweep_type else "below swing low (sell-side)"
                lines.append(f"  - Sweep {i+1}: Price swept {direction} at {level:.5f}, rejected {rejection:.5f}")
        else:
            lines.append("  - No sweeps detected in recent candles")
        
        lines.append("")
    
    return "\n".join(lines)


def _format_liquidity_facts(liquidity_data: Dict[str, Any]) -> str:
    """Format key liquidity levels."""
    if not liquidity_data:
        return "## Key Liquidity Levels\n(No liquidity data available)"
    
    return f"""## Key Liquidity Levels

- **Range High:** {liquidity_data.get('range_high', 'N/A')}
- **Range Low:** {liquidity_data.get('range_low', 'N/A')}
- **Current Price:** {liquidity_data.get('current_price', 'N/A')}
- **Previous Day High (PDH):** {liquidity_data.get('pdh', 'N/A')}
- **Previous Day Low (PDL):** {liquidity_data.get('pdl', 'N/A')}
- **Recent Swing Highs:** {liquidity_data.get('recent_swing_highs', [])}
- **Recent Swing Lows:** {liquidity_data.get('recent_swing_lows', [])}"""


def _format_fibonacci_facts(fib_data: Dict[str, Any]) -> str:
    """Format Fibonacci retracement levels."""
    if not fib_data or not fib_data.get("levels"):
        return "## Fibonacci Levels\n(No Fibonacci data available)"
    
    levels = fib_data.get("levels", {})
    ote = fib_data.get("ote_zone", {})
    
    return f"""## Fibonacci Levels (Based on Range)

| Level | Price |
|-------|-------|
| 0% (Low) | {levels.get('0.0', 'N/A')} |
| 23.6% | {levels.get('0.236', 'N/A')} |
| 38.2% | {levels.get('0.382', 'N/A')} |
| 50% | {levels.get('0.5', 'N/A')} |
| 61.8% | {levels.get('0.618', 'N/A')} |
| 70.5% (OTE Sweet Spot) | {levels.get('0.705', 'N/A')} |
| 78.6% | {levels.get('0.786', 'N/A')} |
| 100% (High) | {levels.get('1.0', 'N/A')} |

**OTE Zone:** {ote.get('bottom', 'N/A')} to {ote.get('top', 'N/A')} (midpoint: {ote.get('midpoint', 'N/A')})"""

