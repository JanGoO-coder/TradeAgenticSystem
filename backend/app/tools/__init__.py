"""
Trading System - Observation Tools.

Pure observation functions that analyze market data and return factual observations.
These tools are the "eyes" of the agent - they observe and report, never decide.
"""
from app.tools.structure import (
    get_swing_points,
    get_market_structure,
    detect_displacement,
    detect_mss
)
from app.tools.liquidity import (
    find_sweeps,
    find_equal_highs_lows,
    identify_liquidity_pools
)
from app.tools.pd_arrays import (
    detect_fvg,
    detect_order_blocks,
    detect_breaker_blocks,
    check_premium_discount,
    calculate_ote
)
from app.tools.sessions import (
    get_current_session,
    check_killzone,
    get_session_range,
    check_power_of_three
)
from app.tools.bias import (
    get_htf_bias,
    check_ltf_alignment
)
from app.tools.observer import (
    run_all_observations,
    compute_state_hash,
    MarketObservation
)
from app.tools.breakout import (
    run_breakout_observation,
    BreakoutObservation,
    detect_breakout,
    get_breakout_entry_exit
)

__all__ = [
    # Structure
    "get_swing_points",
    "get_market_structure",
    "detect_displacement",
    "detect_mss",
    # Liquidity
    "find_sweeps",
    "find_equal_highs_lows",
    "identify_liquidity_pools",
    # PD Arrays
    "detect_fvg",
    "detect_order_blocks",
    "detect_breaker_blocks",
    "check_premium_discount",
    "calculate_ote",
    # Sessions
    "get_current_session",
    "check_killzone",
    "get_session_range",
    "check_power_of_three",
    # Bias
    "get_htf_bias",
    "check_ltf_alignment",
    # Aggregator
    "run_all_observations",
    "compute_state_hash",
    "MarketObservation",
    # Simple Breakout Strategy
    "run_breakout_observation",
    "BreakoutObservation",
    "detect_breakout",
    "get_breakout_entry_exit"
]
