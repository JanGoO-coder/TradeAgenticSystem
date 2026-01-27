"""
Market Observer - Aggregates all observation tools.

Runs all analytical tools and produces a comprehensive market state
that the agent can reason over. Also computes state hashes for
selective analysis in backtesting.
"""
import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Any

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
    check_ltf_alignment,
    get_multi_timeframe_confluence
)


@dataclass
class MarketObservation:
    """
    Complete market observation at a point in time.

    This is the "eyes" output - everything the agent can see
    about the current market state.
    """
    # Meta
    symbol: str
    timestamp: datetime
    current_price: float

    # Bias & Structure
    htf_bias: dict = field(default_factory=dict)
    ltf_alignment: dict = field(default_factory=dict)
    confluence: dict = field(default_factory=dict)

    # Structure Details
    htf_structure: dict = field(default_factory=dict)
    ltf_structure: dict = field(default_factory=dict)
    htf_swings: dict = field(default_factory=dict)
    ltf_swings: dict = field(default_factory=dict)
    mss: Optional[dict] = None
    displacements: List[dict] = field(default_factory=list)

    # Liquidity
    sweeps: List[dict] = field(default_factory=list)
    equal_levels: dict = field(default_factory=dict)
    liquidity_pools: dict = field(default_factory=dict)

    # PD Arrays
    fvgs: List[dict] = field(default_factory=list)
    order_blocks: List[dict] = field(default_factory=list)
    premium_discount: dict = field(default_factory=dict)
    ote: Optional[dict] = None

    # Session Context
    session: dict = field(default_factory=dict)
    killzone: dict = field(default_factory=dict)
    power_of_three: dict = field(default_factory=dict)

    # State hash for selective analysis
    state_hash: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        parts = [
            f"## Market Observation: {self.symbol}",
            f"**Time**: {self.timestamp.strftime('%Y-%m-%d %H:%M')} UTC",
            f"**Price**: {self.current_price:.5f}",
            "",
            "### Bias & Structure",
            self.htf_bias.get("observation", "No HTF bias data"),
            self.ltf_alignment.get("observation", "No LTF alignment data"),
            "",
            "### Session Context",
            self.session.get("observation", "No session data"),
            self.killzone.get("observation", "No killzone data"),
        ]

        # Add MSS if detected
        if self.mss:
            parts.append("")
            parts.append("### Market Structure Shift")
            parts.append(self.mss.get("observation", "MSS detected"))

        # Add sweeps if present
        if self.sweeps:
            parts.append("")
            parts.append("### Liquidity Sweeps")
            for sweep in self.sweeps[-3:]:  # Last 3
                parts.append(f"- {sweep.get('observation', str(sweep))}")

        # Add FVGs if present
        unfilled_fvgs = [f for f in self.fvgs if not f.get("filled", True)]
        if unfilled_fvgs:
            parts.append("")
            parts.append("### Unfilled Fair Value Gaps")
            for fvg in unfilled_fvgs[-3:]:  # Last 3
                parts.append(f"- {fvg.get('observation', str(fvg))}")

        # Add PD zone
        if self.premium_discount:
            parts.append("")
            parts.append("### Premium/Discount")
            parts.append(self.premium_discount.get("observation", "No PD data"))

        # Add OTE if calculated
        if self.ote:
            parts.append("")
            parts.append("### OTE Zone")
            parts.append(self.ote.get("observation", "No OTE data"))

        # Add power of three
        if self.power_of_three.get("phase"):
            parts.append("")
            parts.append("### Power of Three")
            parts.append(self.power_of_three.get("observation", "No PO3 data"))

        # Confluence summary
        parts.append("")
        parts.append("### Confluence Summary")
        parts.append(self.confluence.get("observation", "No confluence data"))

        return "\n".join(parts)


def run_all_observations(
    htf_candles: List[dict],
    ltf_candles: List[dict],
    symbol: str,
    timestamp: Optional[datetime] = None,
    micro_candles: Optional[List[dict]] = None
) -> MarketObservation:
    """
    Run all observation tools and aggregate results.

    This is the main entry point for market analysis. It runs
    all tools and produces a complete MarketObservation.

    Args:
        htf_candles: Higher timeframe candles (1H)
        ltf_candles: Lower timeframe candles (15M)
        symbol: Trading symbol (e.g., "EURUSD")
        timestamp: Observation timestamp (defaults to now)
        micro_candles: Optional micro timeframe candles (5M)

    Returns:
        MarketObservation with all analysis results
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    current_price = ltf_candles[-1]["close"] if ltf_candles else 0

    # === Bias & Structure ===
    htf_bias = get_htf_bias(htf_candles)
    ltf_alignment = check_ltf_alignment(ltf_candles, htf_bias["bias"])
    confluence = get_multi_timeframe_confluence(htf_candles, ltf_candles, micro_candles)

    # === Structure Details ===
    htf_structure = get_market_structure(htf_candles)
    ltf_structure = get_market_structure(ltf_candles)
    htf_swings = get_swing_points(htf_candles)
    ltf_swings = get_swing_points(ltf_candles)
    mss = detect_mss(ltf_candles, ltf_swings)
    displacements = detect_displacement(ltf_candles)[-5:]  # Last 5

    # === Liquidity ===
    sweeps = find_sweeps(ltf_candles, ltf_swings)
    equal_levels = find_equal_highs_lows(ltf_candles)
    liquidity_pools = identify_liquidity_pools(ltf_candles)

    # === PD Arrays ===
    fvgs = detect_fvg(ltf_candles)[-10:]  # Last 10
    order_blocks = detect_order_blocks(ltf_candles)[-5:]  # Last 5

    # Premium/Discount using HTF range
    if htf_swings["latest_swing_high"] and htf_swings["latest_swing_low"]:
        premium_discount = check_premium_discount(
            current_price,
            htf_swings["latest_swing_high"]["price"],
            htf_swings["latest_swing_low"]["price"]
        )
    else:
        premium_discount = {"zone": "UNKNOWN", "observation": "Unable to determine PD zone"}

    # OTE calculation if we have bias and swings
    ote = None
    if htf_bias["bias"] != "NEUTRAL" and htf_swings["latest_swing_high"] and htf_swings["latest_swing_low"]:
        ote = calculate_ote(
            htf_swings["latest_swing_high"]["price"],
            htf_swings["latest_swing_low"]["price"],
            htf_bias["bias"]
        )

    # === Session Context ===
    session = get_current_session(timestamp)
    killzone = check_killzone(timestamp)
    power_of_three = check_power_of_three(ltf_candles, session.get("session", "NY"))

    # Create observation
    observation = MarketObservation(
        symbol=symbol,
        timestamp=timestamp,
        current_price=current_price,
        htf_bias=htf_bias,
        ltf_alignment=ltf_alignment,
        confluence=confluence,
        htf_structure=htf_structure,
        ltf_structure=ltf_structure,
        htf_swings=htf_swings,
        ltf_swings=ltf_swings,
        mss=mss,
        displacements=displacements,
        sweeps=sweeps,
        equal_levels=equal_levels,
        liquidity_pools=liquidity_pools,
        fvgs=fvgs,
        order_blocks=order_blocks,
        premium_discount=premium_discount,
        ote=ote,
        session=session,
        killzone=killzone,
        power_of_three=power_of_three
    )

    # Compute state hash
    observation.state_hash = compute_state_hash(observation)

    return observation


def compute_state_hash(observation: MarketObservation) -> str:
    """
    Compute a hash of the market state for change detection.

    Only includes elements that would trigger a new analysis:
    - Bias changes
    - Structure breaks (MSS)
    - New sweeps
    - Session/killzone changes
    - Significant FVG changes

    Args:
        observation: The market observation to hash

    Returns:
        MD5 hash string of significant state elements
    """
    significant_state = {
        "bias": observation.htf_bias.get("bias"),
        "structure": observation.htf_structure.get("structure"),
        "aligned": observation.ltf_alignment.get("aligned"),
        "mss": observation.mss.get("type") if observation.mss else None,
        "sweep_count": len(observation.sweeps),
        "last_sweep_type": observation.sweeps[-1]["type"] if observation.sweeps else None,
        "session": observation.session.get("session"),
        "in_killzone": observation.killzone.get("in_killzone"),
        "unfilled_fvg_count": len([f for f in observation.fvgs if not f.get("filled")]),
        "pd_zone": observation.premium_discount.get("zone")
    }

    state_str = json.dumps(significant_state, sort_keys=True)
    return hashlib.md5(state_str.encode()).hexdigest()[:12]
