"""
Market Context Manager - Persistent state tracking across analyses.

This is the MEMORY layer of the ICT Market Reasoning Engine.
It tracks:
- Bias evolution (not just current state)
- Structure timeline (structure breaks, MSS history)
- Liquidity sweeps log
- FVG/OB history and mitigation status
- Session history
- Phase state (Accumulation/Manipulation/Distribution/Expansion)

The context persists across multiple analysis cycles, allowing the
agent to maintain awareness of market evolution.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Deque
from collections import deque

from app.domain.events import MarketEvent, EventType, EventBatch
from app.domain.phase import MarketPhase, PhaseState
from app.domain.decision import AgentDecision


# =============================================================================
# State Components
# =============================================================================

@dataclass
class BiasState:
    """
    Tracks HTF bias with history.
    
    Not just "what is the bias now" but "how has it evolved".
    """
    
    current_bias: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    bias_since: Optional[datetime] = None
    bias_strength: float = 0.0  # 0.0 to 1.0
    
    # Historical bias changes (last 10)
    bias_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # MSS tracking for the day
    mss_count_today: int = 0
    last_mss: Optional[Dict[str, Any]] = None
    last_mss_time: Optional[datetime] = None
    
    def update_bias(self, new_bias: str, strength: float = 0.7, reason: str = ""):
        """Update bias with history tracking."""
        if new_bias != self.current_bias:
            # Record the change
            self.bias_history.append({
                "from": self.current_bias,
                "to": new_bias,
                "at": datetime.utcnow().isoformat(),
                "reason": reason
            })
            
            # Keep only last 10 changes
            if len(self.bias_history) > 10:
                self.bias_history = self.bias_history[-10:]
            
            self.current_bias = new_bias
            self.bias_since = datetime.utcnow()
        
        self.bias_strength = strength
    
    def record_mss(self, mss_data: Dict[str, Any]):
        """Record a market structure shift."""
        self.last_mss = mss_data
        self.last_mss_time = datetime.utcnow()
        self.mss_count_today += 1
    
    def get_bias_duration_minutes(self) -> int:
        """How long has current bias been active."""
        if not self.bias_since:
            return 0
        return int((datetime.utcnow() - self.bias_since).total_seconds() / 60)
    
    def to_narrative(self) -> str:
        """Generate natural language bias summary."""
        duration = self.get_bias_duration_minutes()
        lines = [
            f"**Bias**: {self.current_bias} (strength: {self.bias_strength:.0%})",
            f"**Duration**: {duration} minutes",
            f"**MSS Today**: {self.mss_count_today}",
        ]
        
        if self.bias_history:
            recent = self.bias_history[-3:]
            lines.append("**Recent Changes**:")
            for change in recent:
                lines.append(f"  - {change['from']} → {change['to']}")
        
        return "\n".join(lines)


@dataclass
class StructureState:
    """
    Tracks market structure evolution.
    """
    
    htf_structure: str = "UNKNOWN"  # HH_HL, LH_LL, RANGING
    ltf_structure: str = "UNKNOWN"
    ltf_aligned: bool = False
    
    # Swing points
    last_swing_high: Optional[Dict[str, Any]] = None
    last_swing_low: Optional[Dict[str, Any]] = None
    
    # Dealing range (Rule 2.4)
    dealing_range: Optional[Dict[str, float]] = None  # {high, low}
    
    # Structure breaks today
    structure_breaks_today: List[Dict[str, Any]] = field(default_factory=list)
    
    def record_structure_break(self, break_data: Dict[str, Any]):
        """Record a structure break."""
        self.structure_breaks_today.append({
            **break_data,
            "at": datetime.utcnow().isoformat()
        })
        # Keep last 20
        if len(self.structure_breaks_today) > 20:
            self.structure_breaks_today = self.structure_breaks_today[-20:]
    
    def set_dealing_range(self, high: float, low: float):
        """Set the current dealing range."""
        self.dealing_range = {"high": high, "low": low}
    
    def is_in_dealing_range(self, price: float) -> bool:
        """Check if price is inside dealing range."""
        if not self.dealing_range:
            return False
        return self.dealing_range["low"] <= price <= self.dealing_range["high"]


@dataclass
class LiquidityState:
    """
    Tracks liquidity events.
    """
    
    # Recent sweeps (circular buffer)
    recent_sweeps: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=15))
    
    # Known liquidity targets
    buy_side_targets: List[Dict[str, Any]] = field(default_factory=list)
    sell_side_targets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Equal highs/lows (liquidity pools)
    equal_highs: List[Dict[str, Any]] = field(default_factory=list)
    equal_lows: List[Dict[str, Any]] = field(default_factory=list)
    
    # Last significant sweep
    last_sweep: Optional[Dict[str, Any]] = None
    last_sweep_time: Optional[datetime] = None
    
    def record_sweep(self, sweep_data: Dict[str, Any]):
        """Record a liquidity sweep."""
        sweep_record = {
            **sweep_data,
            "at": datetime.utcnow().isoformat()
        }
        self.recent_sweeps.append(sweep_record)
        self.last_sweep = sweep_record
        self.last_sweep_time = datetime.utcnow()
    
    def get_sweeps_since(self, since: datetime) -> List[Dict[str, Any]]:
        """Get sweeps since a given time."""
        return [
            s for s in self.recent_sweeps
            if datetime.fromisoformat(s["at"]) > since
        ]
    
    def has_recent_sweep(self, minutes: int = 30) -> bool:
        """Check if there's been a sweep in the last N minutes."""
        if not self.last_sweep_time:
            return False
        return (datetime.utcnow() - self.last_sweep_time) < timedelta(minutes=minutes)


@dataclass
class PDArrayState:
    """
    Tracks PD arrays and their status.
    """
    
    # Active (unfilled) FVGs
    active_fvgs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Mitigated FVGs (for pattern recognition)
    mitigated_fvgs: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=20))
    
    # Active order blocks
    active_order_blocks: List[Dict[str, Any]] = field(default_factory=list)
    
    # Breaker blocks
    breaker_blocks: List[Dict[str, Any]] = field(default_factory=list)
    
    # Current zone
    current_zone: str = "EQUILIBRIUM"  # PREMIUM, DISCOUNT, EQUILIBRIUM
    zone_percentage: float = 0.5  # 0.0 = full discount, 1.0 = full premium
    
    # OTE zone
    ote_zone: Optional[Dict[str, float]] = None  # {upper, lower}
    in_ote: bool = False
    
    def update_zone(self, zone: str, percentage: float):
        """Update current premium/discount zone."""
        self.current_zone = zone
        self.zone_percentage = percentage
    
    def update_fvgs(self, fvgs: List[Dict[str, Any]]):
        """Update FVG list, tracking mitigations."""
        new_active = []
        for fvg in fvgs:
            if fvg.get("filled", False):
                self.mitigated_fvgs.append({
                    **fvg,
                    "mitigated_at": datetime.utcnow().isoformat()
                })
            else:
                new_active.append(fvg)
        self.active_fvgs = new_active
    
    def get_nearest_fvg(self, price: float, direction: str) -> Optional[Dict[str, Any]]:
        """Get nearest FVG for entry in given direction."""
        relevant = [
            f for f in self.active_fvgs
            if (direction == "LONG" and f.get("type") == "bullish") or
               (direction == "SHORT" and f.get("type") == "bearish")
        ]
        
        if not relevant:
            return None
        
        # Sort by distance to price
        relevant.sort(key=lambda f: abs((f.get("high", 0) + f.get("low", 0)) / 2 - price))
        return relevant[0]


@dataclass
class SessionState:
    """
    Tracks session context.
    """
    
    current_session: str = "OFF_HOURS"  # ASIAN, LONDON, NEW_YORK, OFF_HOURS
    in_killzone: bool = False
    killzone_name: str = ""
    
    # Power of Three phase
    po3_phase: str = "UNKNOWN"  # ACCUMULATION, MANIPULATION, DISTRIBUTION
    
    # Session extremes
    session_high: Optional[float] = None
    session_low: Optional[float] = None
    session_open: Optional[float] = None
    
    # Trade count for session (Rule 9.3)
    trades_this_session: int = 0
    last_trade_time: Optional[datetime] = None
    
    # News handling (Rule 8.4)
    news_cooldown: bool = False
    news_cooldown_until: Optional[datetime] = None
    
    def enter_killzone(self, name: str):
        """Enter a killzone."""
        self.in_killzone = True
        self.killzone_name = name
    
    def exit_killzone(self):
        """Exit killzone."""
        self.in_killzone = False
        self.killzone_name = ""
    
    def start_news_cooldown(self, minutes: int = 30):
        """Start news cooldown period."""
        self.news_cooldown = True
        self.news_cooldown_until = datetime.utcnow() + timedelta(minutes=minutes)
    
    def check_news_cooldown(self) -> bool:
        """Check if still in news cooldown."""
        if not self.news_cooldown:
            return False
        if self.news_cooldown_until and datetime.utcnow() > self.news_cooldown_until:
            self.news_cooldown = False
            return False
        return True
    
    def record_trade(self):
        """Record a trade taken in this session."""
        self.trades_this_session += 1
        self.last_trade_time = datetime.utcnow()
    
    def reset_session(self, session_name: str, open_price: float):
        """Reset for new session."""
        self.current_session = session_name
        self.session_open = open_price
        self.session_high = open_price
        self.session_low = open_price
        self.trades_this_session = 0


# =============================================================================
# Main Context Class
# =============================================================================

@dataclass
class MarketContext:
    """
    Complete persistent market context for a symbol.
    
    This is the MEMORY of the agent - tracking everything that has happened
    and the current state derived from that history.
    """
    
    symbol: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    # State components
    bias: BiasState = field(default_factory=BiasState)
    structure: StructureState = field(default_factory=StructureState)
    liquidity: LiquidityState = field(default_factory=LiquidityState)
    pd_arrays: PDArrayState = field(default_factory=PDArrayState)
    session: SessionState = field(default_factory=SessionState)
    phase: PhaseState = field(default_factory=PhaseState)
    
    # Analysis tracking
    analysis_count: int = 0
    last_observation_hash: str = ""
    
    # Decision history (last 20)
    decision_history: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=20))
    last_decision: Optional[str] = None
    last_decision_time: Optional[datetime] = None
    
    # Event log (last 50 events)
    event_log: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50))
    
    def record_analysis(self, observation_hash: str):
        """Record that an analysis was performed."""
        self.analysis_count += 1
        self.last_observation_hash = observation_hash
        self.last_updated = datetime.utcnow()
    
    def record_decision(self, decision: AgentDecision):
        """Record a trading decision."""
        self.decision_history.append({
            "decision": decision.decision,
            "confidence": decision.confidence,
            "timestamp": decision.timestamp.isoformat(),
            "brief_reason": decision.brief_reason,
            "was_vetoed": decision.was_vetoed
        })
        self.last_decision = decision.decision
        self.last_decision_time = decision.timestamp
        
        if decision.decision == "TRADE":
            self.session.record_trade()
    
    def record_events(self, events: List[MarketEvent]):
        """Record events from an observation."""
        for event in events:
            self.event_log.append(event.to_dict())
    
    def to_narrative(self) -> str:
        """
        Generate natural language context summary for prompt injection.
        
        This is what the LLM sees about the persistent context.
        """
        lines = [
            f"# Persistent Market Context: {self.symbol}",
            f"**Analysis Count**: {self.analysis_count}",
            f"**Last Updated**: {self.last_updated.strftime('%H:%M')} UTC",
            "",
            "## Bias State",
            self.bias.to_narrative(),
            "",
            "## Market Phase",
            self.phase.to_narrative(),
            "",
            "## Session State",
            f"**Session**: {self.session.current_session}",
            f"**Killzone**: {'✅ ' + self.session.killzone_name if self.session.in_killzone else '❌ Not in killzone'}",
            f"**Trades This Session**: {self.session.trades_this_session}",
            f"**News Cooldown**: {'⚠️ Active' if self.session.check_news_cooldown() else '✅ Clear'}",
            "",
            "## Liquidity State",
            f"**Recent Sweeps**: {len(self.liquidity.recent_sweeps)}",
            f"**Last Sweep**: {self.liquidity.last_sweep_time.strftime('%H:%M') if self.liquidity.last_sweep_time else 'None'}",
            "",
            "## PD Arrays",
            f"**Zone**: {self.pd_arrays.current_zone} ({self.pd_arrays.zone_percentage:.0%})",
            f"**Active FVGs**: {len(self.pd_arrays.active_fvgs)}",
            f"**In OTE**: {'✅' if self.pd_arrays.in_ote else '❌'}",
        ]
        
        # Recent decisions
        if self.decision_history:
            lines.extend([
                "",
                "## Recent Decisions",
            ])
            for dec in list(self.decision_history)[-5:]:
                vetoed = " (VETOED)" if dec.get("was_vetoed") else ""
                lines.append(f"- {dec['decision']}{vetoed}: {dec.get('brief_reason', '')[:50]}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "analysis_count": self.analysis_count,
            "last_updated": self.last_updated.isoformat(),
            "bias": {
                "current": self.bias.current_bias,
                "strength": self.bias.bias_strength,
                "mss_count_today": self.bias.mss_count_today
            },
            "phase": self.phase.to_dict(),
            "session": {
                "current": self.session.current_session,
                "in_killzone": self.session.in_killzone,
                "trades_this_session": self.session.trades_this_session,
                "news_cooldown": self.session.check_news_cooldown()
            },
            "pd_arrays": {
                "zone": self.pd_arrays.current_zone,
                "active_fvgs": len(self.pd_arrays.active_fvgs),
                "in_ote": self.pd_arrays.in_ote
            },
            "liquidity": {
                "recent_sweeps": len(self.liquidity.recent_sweeps),
                "has_recent_sweep": self.liquidity.has_recent_sweep()
            }
        }


# =============================================================================
# Context Manager
# =============================================================================

class MarketContextManager:
    """
    Manages persistent market context across analyses.
    
    This is the single source of truth for market state.
    Each symbol has its own context that persists across analysis cycles.
    """
    
    def __init__(self):
        self._contexts: Dict[str, MarketContext] = {}
    
    def get_context(self, symbol: str) -> MarketContext:
        """Get or create context for symbol."""
        if symbol not in self._contexts:
            self._contexts[symbol] = MarketContext(symbol=symbol)
        return self._contexts[symbol]
    
    def has_context(self, symbol: str) -> bool:
        """Check if context exists for symbol."""
        return symbol in self._contexts
    
    def update_from_observation(
        self,
        symbol: str,
        observation_data: Dict[str, Any],
        events: List[MarketEvent]
    ) -> MarketContext:
        """
        Update context with new observation data and events.
        
        This is called after each observation cycle.
        """
        ctx = self.get_context(symbol)
        
        # Record the analysis
        ctx.record_analysis(observation_data.get("state_hash", ""))
        
        # Record events
        ctx.record_events(events)
        
        # Update bias state
        htf_bias = observation_data.get("htf_bias", {})
        if htf_bias.get("bias"):
            ctx.bias.update_bias(
                htf_bias["bias"],
                strength=htf_bias.get("strength", 0.7),
                reason=htf_bias.get("observation", "")
            )
        
        # Update structure state
        ctx.structure.ltf_aligned = observation_data.get("ltf_alignment", {}).get("aligned", False)
        
        if observation_data.get("mss"):
            ctx.bias.record_mss(observation_data["mss"])
            ctx.structure.record_structure_break(observation_data["mss"])
        
        # Update liquidity state
        for sweep in observation_data.get("sweeps", []):
            ctx.liquidity.record_sweep(sweep)
        
        # Update PD arrays
        ctx.pd_arrays.update_fvgs(observation_data.get("fvgs", []))
        ctx.pd_arrays.active_order_blocks = observation_data.get("order_blocks", [])
        
        pd_zone = observation_data.get("premium_discount", {})
        if pd_zone.get("zone"):
            ctx.pd_arrays.update_zone(
                pd_zone["zone"],
                pd_zone.get("percentage", 0.5)
            )
        
        # Update OTE status
        if observation_data.get("ote"):
            ctx.pd_arrays.ote_zone = observation_data["ote"]
            current_price = observation_data.get("current_price", 0)
            ote = observation_data["ote"]
            ctx.pd_arrays.in_ote = ote.get("lower", 0) <= current_price <= ote.get("upper", 0)
        
        # Update session state
        session = observation_data.get("session", {})
        if session.get("session"):
            ctx.session.current_session = session["session"]
        
        killzone = observation_data.get("killzone", {})
        if killzone.get("in_killzone"):
            ctx.session.enter_killzone(killzone.get("session", ""))
        else:
            ctx.session.exit_killzone()
        
        # Update PO3 phase
        po3 = observation_data.get("power_of_three", {})
        if po3.get("phase"):
            ctx.session.po3_phase = po3["phase"]
        
        return ctx
    
    def update_phase(
        self,
        symbol: str,
        new_phase: MarketPhase,
        confidence: float,
        reason: str
    ):
        """Update the market phase for a symbol."""
        ctx = self.get_context(symbol)
        ctx.phase.transition_to(new_phase, reason, confidence)
    
    def record_decision(self, symbol: str, decision: AgentDecision):
        """Record a trading decision in context."""
        ctx = self.get_context(symbol)
        ctx.record_decision(decision)
    
    def reset_context(self, symbol: str):
        """Reset context for a symbol (e.g., new trading day)."""
        if symbol in self._contexts:
            del self._contexts[symbol]
    
    def get_all_symbols(self) -> List[str]:
        """Get list of all tracked symbols."""
        return list(self._contexts.keys())


# =============================================================================
# Singleton Instance
# =============================================================================

_context_manager: Optional[MarketContextManager] = None


def get_context_manager() -> MarketContextManager:
    """Get or create the context manager singleton."""
    global _context_manager
    if _context_manager is None:
        _context_manager = MarketContextManager()
    return _context_manager
