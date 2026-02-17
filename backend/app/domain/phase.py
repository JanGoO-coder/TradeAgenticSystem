"""
Market Phase - ICT Power of Three State Machine.

Tracks the current market phase (Accumulation, Manipulation, Distribution, etc.)
and provides phase detection logic.

ICT setups are phase-dependent:
- Liquidity sweep during Accumulation ≠ entry signal
- Liquidity sweep during Manipulation → potential entry
- Same event, different phase = different meaning
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class MarketPhase(Enum):
    """ICT Power of Three + Extended Phases."""
    
    # Core PO3 Phases
    ACCUMULATION = "accumulation"       # Range building, orders placed
    MANIPULATION = "manipulation"       # False move to sweep liquidity
    DISTRIBUTION = "distribution"       # Real directional move begins
    
    # Extended Phases
    EXPANSION = "expansion"             # Trend continuation after distribution
    REACCUMULATION = "reaccumulation"   # Pause within bullish trend
    REDISTRIBUTION = "redistribution"   # Pause within bearish trend
    
    # Edge Cases
    RANGING = "ranging"                 # No clear phase
    UNKNOWN = "unknown"                 # Insufficient data
    
    def is_entry_valid(self) -> bool:
        """Check if this phase supports trade entry."""
        return self in [MarketPhase.DISTRIBUTION, MarketPhase.EXPANSION]
    
    def is_accumulating(self) -> bool:
        """Check if market is in an accumulation phase."""
        return self in [MarketPhase.ACCUMULATION, MarketPhase.REACCUMULATION, MarketPhase.REDISTRIBUTION]


@dataclass
class PhaseTransition:
    """Record of a phase transition."""
    
    from_phase: MarketPhase
    to_phase: MarketPhase
    timestamp: datetime
    reason: str
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_phase.value,
            "to": self.to_phase.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "confidence": self.confidence
        }


@dataclass
class PhaseState:
    """
    Tracks current market phase with history.
    
    This is part of the persistent context layer.
    """
    
    current_phase: MarketPhase = MarketPhase.UNKNOWN
    phase_since: Optional[datetime] = None
    phase_confidence: float = 0.0  # 0.0 to 1.0
    
    # Phase history for pattern recognition
    phase_history: List[PhaseTransition] = field(default_factory=list)
    
    # Phase transition triggers
    last_transition_reason: str = ""
    
    # Phase-specific tracking
    accumulation_range: Optional[Dict[str, float]] = None  # {high, low}
    manipulation_direction: Optional[str] = None  # "up" or "down"
    distribution_target: Optional[float] = None
    
    def transition_to(
        self,
        new_phase: MarketPhase,
        reason: str,
        confidence: float = 0.7
    ):
        """Record phase transition."""
        if self.current_phase != new_phase:
            # Record transition
            transition = PhaseTransition(
                from_phase=self.current_phase,
                to_phase=new_phase,
                timestamp=datetime.utcnow(),
                reason=reason,
                confidence=confidence
            )
            self.phase_history.append(transition)
            
            # Keep only last 20 transitions
            if len(self.phase_history) > 20:
                self.phase_history = self.phase_history[-20:]
            
            # Update current state
            self.current_phase = new_phase
            self.phase_since = datetime.utcnow()
            self.phase_confidence = confidence
            self.last_transition_reason = reason
    
    def get_phase_duration_minutes(self) -> int:
        """Get how long we've been in current phase."""
        if not self.phase_since:
            return 0
        delta = datetime.utcnow() - self.phase_since
        return int(delta.total_seconds() / 60)
    
    def get_recent_transitions(self, count: int = 5) -> List[PhaseTransition]:
        """Get last N phase transitions."""
        return self.phase_history[-count:]
    
    def to_narrative(self) -> str:
        """Generate natural language phase summary."""
        duration = self.get_phase_duration_minutes()
        
        lines = [
            f"**Current Phase**: {self.current_phase.value.upper()}",
            f"**Duration**: {duration} minutes",
            f"**Confidence**: {self.phase_confidence:.0%}",
        ]
        
        if self.last_transition_reason:
            lines.append(f"**Reason**: {self.last_transition_reason}")
        
        if self.current_phase == MarketPhase.ACCUMULATION and self.accumulation_range:
            lines.append(f"**Range**: {self.accumulation_range.get('low'):.5f} - {self.accumulation_range.get('high'):.5f}")
        
        if self.current_phase == MarketPhase.MANIPULATION:
            lines.append(f"**Direction**: {self.manipulation_direction or 'unknown'}")
        
        # Entry validity
        if self.current_phase.is_entry_valid():
            lines.append("**Entry Status**: ✅ Phase supports entry")
        else:
            lines.append("**Entry Status**: ❌ Phase does NOT support entry")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_phase": self.current_phase.value,
            "phase_since": self.phase_since.isoformat() if self.phase_since else None,
            "phase_confidence": self.phase_confidence,
            "duration_minutes": self.get_phase_duration_minutes(),
            "last_transition_reason": self.last_transition_reason,
            "entry_valid": self.current_phase.is_entry_valid(),
            "recent_transitions": [t.to_dict() for t in self.get_recent_transitions()]
        }


# Valid phase transitions (state machine rules)
VALID_TRANSITIONS = {
    MarketPhase.UNKNOWN: [MarketPhase.ACCUMULATION, MarketPhase.RANGING, MarketPhase.EXPANSION],
    MarketPhase.ACCUMULATION: [MarketPhase.MANIPULATION, MarketPhase.RANGING],
    MarketPhase.MANIPULATION: [MarketPhase.DISTRIBUTION, MarketPhase.ACCUMULATION],
    MarketPhase.DISTRIBUTION: [MarketPhase.EXPANSION, MarketPhase.REACCUMULATION, MarketPhase.REDISTRIBUTION],
    MarketPhase.EXPANSION: [MarketPhase.REACCUMULATION, MarketPhase.REDISTRIBUTION, MarketPhase.ACCUMULATION],
    MarketPhase.REACCUMULATION: [MarketPhase.MANIPULATION, MarketPhase.EXPANSION],
    MarketPhase.REDISTRIBUTION: [MarketPhase.MANIPULATION, MarketPhase.EXPANSION],
    MarketPhase.RANGING: [MarketPhase.ACCUMULATION, MarketPhase.MANIPULATION],
}


def is_valid_transition(from_phase: MarketPhase, to_phase: MarketPhase) -> bool:
    """Check if a phase transition is valid according to ICT logic."""
    return to_phase in VALID_TRANSITIONS.get(from_phase, [])
