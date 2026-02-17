"""
Decision Validator - Hard veto layer for LLM decisions.

The LLM proposes decisions. The Validator approves or vetoes.
This creates a fail-safe system where:
- Bad reasoning can't pass hard rules
- Missing conditions = automatic rejection
- Conflicts = automatic NO_TRADE

Every decision passes through here. No exceptions.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any

# Optional settings import - fallback to defaults if not available
try:
    from app.core.config import Settings, get_settings
    _HAS_SETTINGS = True
except ImportError:
    _HAS_SETTINGS = False
    Settings = None
    def get_settings():
        return None

from app.domain.decision import (
    ProposedDecision,
    ValidationResult,
    VetoReason,
    AgentDecision,
    TradeSetup
)
from app.domain.phase import MarketPhase


class DecisionValidator:
    """
    Hard gate for LLM decisions.
    
    The LLM proposes. The Validator approves or vetoes.
    This is NOT optional - every decision passes through here.
    
    Rules are based on ICT Rulebook:
    - Section 9: Invalidation Rules
    - Section 10: Execution Checklist
    """
    
    # Default settings if config not available
    DEFAULT_MAX_TRADES_PER_SESSION = 3
    
    def __init__(self, settings: Optional[Any] = None, max_trades_per_session: int = None):
        self.settings = settings or (get_settings() if _HAS_SETTINGS else None)
        
        # Get max trades from settings or use default
        if max_trades_per_session is not None:
            self.max_trades_per_session = max_trades_per_session
        elif self.settings and hasattr(self.settings, 'max_trades_per_session'):
            self.max_trades_per_session = self.settings.max_trades_per_session
        else:
            self.max_trades_per_session = self.DEFAULT_MAX_TRADES_PER_SESSION
    
    def validate(
        self,
        proposed: ProposedDecision,
        context: "MarketContext",
        observation_data: dict
    ) -> ValidationResult:
        """
        Validate a proposed decision against hard rules.
        
        Args:
            proposed: The decision proposed by the LLM
            context: Current market context
            observation_data: Raw observation data
            
        Returns:
            ValidationResult with approval status and any vetoes
        """
        
        veto_reasons: List[VetoReason] = []
        warnings: List[str] = []
        checks_passed: List[str] = []
        checks_failed: List[str] = []
        confidence_adjustment = 0.0
        
        # WAIT and NO_TRADE decisions pass through without validation
        if proposed.decision != "TRADE":
            return ValidationResult(
                approved=True,
                original_decision=proposed.decision,
                final_decision=proposed.decision,
                veto_reasons=[],
                warnings=[],
                original_confidence=proposed.confidence,
                adjusted_confidence=proposed.confidence,
                checks_passed=["Non-trade decision - no validation needed"],
                checks_failed=[]
            )
        
        # =====================================================================
        # HARD VETO RULES (Any one = rejection)
        # =====================================================================
        
        # Rule 1.1: HTF Bias must be clear
        htf_bias = context.bias.current_bias
        if htf_bias == "NEUTRAL":
            veto_reasons.append(VetoReason.NO_HTF_ALIGNMENT)
            checks_failed.append("HTF bias is NEUTRAL")
        else:
            checks_passed.append(f"HTF bias is {htf_bias}")
        
        # Rule 1.2: LTF must align with HTF
        ltf_aligned = context.structure.ltf_aligned
        has_mss = context.bias.last_mss is not None
        
        if not ltf_aligned and not has_mss:
            veto_reasons.append(VetoReason.BIAS_CONFLICT)
            checks_failed.append("LTF not aligned and no MSS")
        else:
            if ltf_aligned:
                checks_passed.append("LTF aligned with HTF")
            elif has_mss:
                checks_passed.append("MSS justifies entry direction")
        
        # Rule 8.1: Must be in valid session (killzone)
        if not context.session.in_killzone:
            veto_reasons.append(VetoReason.SESSION_INVALID)
            checks_failed.append(f"Not in killzone (session: {context.session.current_session})")
        else:
            checks_passed.append(f"In killzone: {context.session.killzone_name}")
        
        # Rule 3.4: Liquidity must be swept
        if not context.liquidity.has_recent_sweep(minutes=60):
            veto_reasons.append(VetoReason.LIQUIDITY_NOT_SWEPT)
            checks_failed.append("No liquidity sweep in last 60 minutes")
        else:
            checks_passed.append("Recent liquidity sweep detected")
        
        # Rule 2.3: Entry requires displacement
        displacements = observation_data.get("displacements", [])
        if not displacements:
            veto_reasons.append(VetoReason.NO_DISPLACEMENT)
            checks_failed.append("No displacement detected")
        else:
            checks_passed.append(f"{len(displacements)} displacement(s) detected")
        
        # Rule 5.1: Price must be in correct PD zone for direction
        if proposed.setup:
            zone = context.pd_arrays.current_zone
            direction = proposed.setup.direction
            
            zone_valid = self._validate_pd_zone(zone, direction)
            if not zone_valid:
                veto_reasons.append(VetoReason.PD_ZONE_WRONG)
                checks_failed.append(f"{direction} in {zone} zone is invalid")
            else:
                checks_passed.append(f"{direction} in {zone} zone is valid")
        
        # Rule 8.4: No trades during news cooldown
        if context.session.check_news_cooldown():
            veto_reasons.append(VetoReason.NEWS_COOLDOWN)
            checks_failed.append("Within news cooldown period")
        else:
            checks_passed.append("No news cooldown active")
        
        # Rule 9.3: Max trades per session
        if context.session.trades_this_session >= self.max_trades_per_session:
            veto_reasons.append(VetoReason.MAX_TRADES_REACHED)
            checks_failed.append(f"Max trades ({self.max_trades_per_session}) reached")
        else:
            checks_passed.append(f"Trade count: {context.session.trades_this_session}/{self.max_trades_per_session}")
        
        # Phase check: Entry should happen in DISTRIBUTION or EXPANSION
        current_phase = context.phase.current_phase
        if not current_phase.is_entry_valid():
            veto_reasons.append(VetoReason.PHASE_MISMATCH)
            checks_failed.append(f"Phase {current_phase.value} does not support entry")
        else:
            checks_passed.append(f"Phase {current_phase.value} supports entry")
        
        # =====================================================================
        # SOFT WARNINGS (Reduce confidence, don't veto)
        # =====================================================================
        
        # Low phase confidence
        if context.phase.phase_confidence < 0.6:
            warnings.append(f"Phase confidence low: {context.phase.phase_confidence:.0%}")
            confidence_adjustment -= 0.10
        
        # Few confluence elements
        confluence_count = self._count_confluence(context, observation_data)
        if confluence_count < 3:
            warnings.append(f"Limited confluence: {confluence_count} elements")
            confidence_adjustment -= 0.15
        elif confluence_count >= 5:
            # High confluence = confidence boost
            confidence_adjustment += 0.05
        
        # Low bias strength
        if context.bias.bias_strength < 0.5:
            warnings.append(f"Bias strength low: {context.bias.bias_strength:.0%}")
            confidence_adjustment -= 0.05
        
        # Many MSS today (choppy market)
        if context.bias.mss_count_today >= 3:
            warnings.append(f"Choppy market: {context.bias.mss_count_today} MSS today")
            confidence_adjustment -= 0.10
        
        # =====================================================================
        # FINAL DECISION
        # =====================================================================
        
        adjusted_confidence = max(0.0, min(1.0, proposed.confidence + confidence_adjustment))
        
        if veto_reasons:
            return ValidationResult(
                approved=False,
                original_decision="TRADE",
                final_decision="NO_TRADE",
                veto_reasons=veto_reasons,
                warnings=warnings,
                original_confidence=proposed.confidence,
                adjusted_confidence=0.0,  # Vetoed = 0 confidence
                checks_passed=checks_passed,
                checks_failed=checks_failed
            )
        
        return ValidationResult(
            approved=True,
            original_decision="TRADE",
            final_decision="TRADE",
            veto_reasons=[],
            warnings=warnings,
            original_confidence=proposed.confidence,
            adjusted_confidence=adjusted_confidence,
            checks_passed=checks_passed,
            checks_failed=checks_failed
        )
    
    def _validate_pd_zone(self, zone: str, direction: str) -> bool:
        """
        Rule 5.1: Validate price is in correct zone for direction.
        
        - LONG entries should be in DISCOUNT
        - SHORT entries should be in PREMIUM
        - EQUILIBRIUM is acceptable for both (with reduced confidence)
        """
        if zone == "EQUILIBRIUM":
            return True  # Acceptable but will get warning
        
        if direction == "LONG" and zone != "DISCOUNT":
            return False
        
        if direction == "SHORT" and zone != "PREMIUM":
            return False
        
        return True
    
    def _count_confluence(self, context: "MarketContext", observation_data: dict) -> int:
        """Count number of confluence elements present (Rule 10)."""
        count = 0
        
        # HTF bias clear
        if context.bias.current_bias != "NEUTRAL":
            count += 1
        
        # LTF aligned
        if context.structure.ltf_aligned:
            count += 1
        
        # MSS present
        if context.bias.last_mss:
            count += 1
        
        # Recent sweep
        if context.liquidity.has_recent_sweep():
            count += 1
        
        # Displacement
        if observation_data.get("displacements"):
            count += 1
        
        # Active FVG
        if context.pd_arrays.active_fvgs:
            count += 1
        
        # Active order block
        if context.pd_arrays.active_order_blocks:
            count += 1
        
        # In killzone
        if context.session.in_killzone:
            count += 1
        
        # OTE zone
        if context.pd_arrays.in_ote:
            count += 1
        
        # Correct phase
        if context.phase.current_phase.is_entry_valid():
            count += 1
        
        return count
    
    def create_final_decision(
        self,
        proposed: ProposedDecision,
        validation: ValidationResult,
        context: "MarketContext"
    ) -> AgentDecision:
        """
        Create the final AgentDecision from proposed + validation.
        """
        return AgentDecision(
            decision=validation.final_decision,
            confidence=validation.adjusted_confidence,
            reasoning=proposed.reasoning,
            brief_reason=proposed.brief_reason if validation.approved else self._format_veto_reason(validation),
            rule_citations=proposed.rule_citations,
            setup=proposed.setup if validation.approved else None,
            validation=validation,
            observation_hash=context.last_observation_hash,
            phase_at_decision=context.phase.current_phase.value,
            context_summary=context.to_narrative()[:500],  # Truncate for storage
            timestamp=datetime.utcnow(),
            total_latency_ms=proposed.llm_latency_ms  # Will be updated with validation time
        )
    
    def _format_veto_reason(self, validation: ValidationResult) -> str:
        """Format veto reasons as brief reason."""
        if not validation.veto_reasons:
            return "Unknown veto"
        
        reasons = [r.value.split("(")[0].strip() for r in validation.veto_reasons[:3]]
        return "VETOED: " + "; ".join(reasons)


# =============================================================================
# Singleton Instance
# =============================================================================

_validator: Optional[DecisionValidator] = None


def get_decision_validator() -> DecisionValidator:
    """Get or create the decision validator singleton."""
    global _validator
    if _validator is None:
        _validator = DecisionValidator()
    return _validator
