"""
Phase Detector - Detects current market phase from events and context.

ICT setups are phase-dependent. This detector analyzes:
- Recent events (sweeps, structure breaks, displacements)
- Current context state
- To determine which PO3 phase we're in

Phases:
- ACCUMULATION: Range building, orders being placed
- MANIPULATION: False move to sweep liquidity
- DISTRIBUTION: Real directional move begins
- EXPANSION: Trend continuation
"""
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from app.domain.events import MarketEvent, EventType
from app.domain.phase import MarketPhase, PhaseState, is_valid_transition


class PhaseDetector:
    """
    Detects current market phase from events and context.
    
    The phase determines whether entries are valid:
    - ACCUMULATION: No entries (building range)
    - MANIPULATION: Prepare for entry (sweep happening)
    - DISTRIBUTION: Valid entries (real move starting)
    - EXPANSION: Valid entries (trend continuation)
    """
    
    def __init__(self, lookback_minutes: int = 60):
        self.lookback_minutes = lookback_minutes
    
    def detect_phase(
        self,
        context: "MarketContext",
        recent_events: List[MarketEvent]
    ) -> Tuple[MarketPhase, float, str]:
        """
        Detect current phase based on context and recent events.
        
        Returns: (phase, confidence, reason)
        """
        
        # Filter to recent events only
        cutoff = datetime.utcnow() - timedelta(minutes=self.lookback_minutes)
        events = [e for e in recent_events if e.timestamp > cutoff]
        
        # Categorize events
        sweep_events = [e for e in events if e.type in [
            EventType.LIQUIDITY_SWEEP_BUYSIDE,
            EventType.LIQUIDITY_SWEEP_SELLSIDE,
            EventType.STOP_HUNT
        ]]
        
        displacement_events = [e for e in events if e.type in [
            EventType.DISPLACEMENT_BULLISH,
            EventType.DISPLACEMENT_BEARISH
        ]]
        
        structure_events = [e for e in events if e.type in [
            EventType.BOS_BULLISH,
            EventType.BOS_BEARISH,
            EventType.MSS_BULLISH,
            EventType.MSS_BEARISH
        ]]
        
        fvg_events = [e for e in events if e.type in [
            EventType.FVG_BULLISH_FORMED,
            EventType.FVG_BEARISH_FORMED
        ]]
        
        # =================================================================
        # DISTRIBUTION Detection (Highest Priority)
        # Condition: Sweep + Displacement + FVG = Distribution starting
        # =================================================================
        if sweep_events and displacement_events and fvg_events:
            # Check sequence: sweep → displacement → FVG
            last_sweep = max(sweep_events, key=lambda e: e.timestamp)
            last_disp = max(displacement_events, key=lambda e: e.timestamp)
            last_fvg = max(fvg_events, key=lambda e: e.timestamp)
            
            # Correct sequence: sweep first, then displacement, then FVG
            if last_sweep.timestamp <= last_disp.timestamp <= last_fvg.timestamp:
                return (
                    MarketPhase.DISTRIBUTION,
                    0.85,
                    "Sweep → Displacement → FVG sequence detected (ICT 2022 model)"
                )
        
        # =================================================================
        # MANIPULATION Detection
        # Condition: Recent sweep without displacement follow-through
        # =================================================================
        if sweep_events and not displacement_events:
            last_sweep = max(sweep_events, key=lambda e: e.timestamp)
            time_since_sweep = (datetime.utcnow() - last_sweep.timestamp).total_seconds() / 60
            
            # Sweep within last 15 minutes without displacement = manipulation
            if time_since_sweep < 15:
                return (
                    MarketPhase.MANIPULATION,
                    0.80,
                    f"Liquidity sweep {time_since_sweep:.0f}m ago without displacement"
                )
        
        # =================================================================
        # EXPANSION Detection
        # Condition: Multiple structure breaks in same direction
        # =================================================================
        if len(structure_events) >= 2:
            bullish_breaks = [e for e in structure_events if "BULLISH" in e.type.value.upper()]
            bearish_breaks = [e for e in structure_events if "BEARISH" in e.type.value.upper()]
            
            # Consistent direction = expansion
            if len(bullish_breaks) >= 2 and not bearish_breaks:
                return (
                    MarketPhase.EXPANSION,
                    0.75,
                    f"{len(bullish_breaks)} bullish structure breaks - expansion phase"
                )
            
            if len(bearish_breaks) >= 2 and not bullish_breaks:
                return (
                    MarketPhase.EXPANSION,
                    0.75,
                    f"{len(bearish_breaks)} bearish structure breaks - expansion phase"
                )
        
        # =================================================================
        # ACCUMULATION Detection
        # Condition: Dealing range present, no decisive breaks
        # =================================================================
        if context.structure.dealing_range:
            # Check if price is still in range
            # (Would need current price to fully validate)
            if not structure_events:  # No breaks = still in range
                return (
                    MarketPhase.ACCUMULATION,
                    0.70,
                    "Price contained within dealing range"
                )
        
        # =================================================================
        # RE-ACCUMULATION / RE-DISTRIBUTION Detection
        # Condition: Existing bias with consolidation
        # =================================================================
        if context.bias.current_bias == "BULLISH":
            # Bullish bias but no recent expansion = reaccumulation
            if not displacement_events and context.session.po3_phase == "ACCUMULATION":
                return (
                    MarketPhase.REACCUMULATION,
                    0.60,
                    "Bullish bias with consolidation pattern"
                )
        
        if context.bias.current_bias == "BEARISH":
            if not displacement_events and context.session.po3_phase == "ACCUMULATION":
                return (
                    MarketPhase.REDISTRIBUTION,
                    0.60,
                    "Bearish bias with consolidation pattern"
                )
        
        # =================================================================
        # RANGING Detection
        # Condition: No clear directional events
        # =================================================================
        if not sweep_events and not displacement_events and not structure_events:
            return (
                MarketPhase.RANGING,
                0.40,
                "No significant events - market ranging"
            )
        
        # =================================================================
        # UNKNOWN (Default)
        # =================================================================
        return (
            MarketPhase.UNKNOWN,
            0.30,
            "Insufficient data to determine phase"
        )
    
    def update_context_phase(
        self,
        context: "MarketContext",
        recent_events: List[MarketEvent]
    ) -> bool:
        """
        Detect and update the phase in context.
        
        Returns: True if phase changed, False otherwise.
        """
        new_phase, confidence, reason = self.detect_phase(context, recent_events)
        
        current_phase = context.phase.current_phase
        
        # Check if this is a valid transition
        if not is_valid_transition(current_phase, new_phase):
            # Invalid transition - keep current unless confidence is very high
            if confidence < 0.85:
                return False
        
        # Only transition if phase is different
        if new_phase != current_phase:
            context.phase.transition_to(new_phase, reason, confidence)
            return True
        
        # Update confidence even if phase is same
        context.phase.phase_confidence = confidence
        return False


# =============================================================================
# Singleton Instance
# =============================================================================

_phase_detector: Optional[PhaseDetector] = None


def get_phase_detector() -> PhaseDetector:
    """Get or create the phase detector singleton."""
    global _phase_detector
    if _phase_detector is None:
        _phase_detector = PhaseDetector()
    return _phase_detector
