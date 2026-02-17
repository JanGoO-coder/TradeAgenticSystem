"""
Decision Models - Proposed decisions and validation results.

The LLM proposes decisions. The Validator approves or vetoes.
This creates a fail-safe system where:
- Bad reasoning can't pass hard rules
- Missing conditions = automatic rejection
- Conflicts = automatic NO_TRADE
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Literal


class VetoReason(Enum):
    """Why a decision was vetoed."""
    
    # Rule 1.x: Market Framework
    NO_HTF_ALIGNMENT = "HTF structure unclear or neutral (Rule 1.1)"
    BIAS_CONFLICT = "HTF and LTF bias conflict (Rule 1.2)"
    COUNTER_TREND_NO_MSS = "Counter-trend without 1H MSS (Rule 1.2.2)"
    
    # Rule 2.x: Structure
    NO_DISPLACEMENT = "Entry without displacement detected (Rule 2.3)"
    NO_STRUCTURE_BREAK = "No confirmed structure break (Rule 2.2)"
    
    # Rule 3.x: Liquidity
    LIQUIDITY_NOT_SWEPT = "No liquidity sweep before entry (Rule 3.4)"
    
    # Rule 5.x: PD Arrays
    PD_ZONE_WRONG = "Price not in correct premium/discount zone (Rule 5.1)"
    MITIGATED_PD_ARRAY = "Entry PD array already mitigated (Rule 5.5)"
    NO_VALID_FVG = "No valid FVG for entry (Rule 5.2)"
    
    # Rule 8.x: Session
    SESSION_INVALID = "Outside valid trading session (Rule 8.1)"
    NEWS_COOLDOWN = "Within high-impact news window (Rule 8.4)"
    
    # Rule 9.x: Invalidation
    MAX_TRADES_REACHED = "Maximum trades per session reached (Rule 9.3)"
    
    # Phase control
    PHASE_MISMATCH = "Market phase does not support entry"
    
    # Confluence
    MISSING_CONFLUENCE = "Insufficient confluence elements (Rule 10)"


@dataclass
class TradeSetup:
    """Trade setup details when decision is TRADE."""
    
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float = 0.0
    position_size_pct: float = 1.0  # % of account to risk
    
    # Entry model used (Rule 6.x)
    entry_model: str = ""  # e.g., "OTE", "FVG", "Sweep→Disp→FVG"
    entry_rule: str = ""   # e.g., "6.3"
    
    # PD array used for entry
    pd_array_type: str = ""  # "FVG", "OB", "OTE"
    pd_array_level: Optional[float] = None
    
    def __post_init__(self):
        if self.stop_loss and self.entry_price and self.take_profit:
            risk = abs(self.entry_price - self.stop_loss)
            reward = abs(self.take_profit - self.entry_price)
            self.risk_reward = round(reward / risk, 2) if risk > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward": self.risk_reward,
            "position_size_pct": self.position_size_pct,
            "entry_model": self.entry_model,
            "entry_rule": self.entry_rule,
            "pd_array_type": self.pd_array_type
        }


@dataclass
class ProposedDecision:
    """
    Decision proposed by the LLM Agent.
    
    This is NOT the final decision - it must pass through the Validator.
    """
    
    decision: Literal["TRADE", "WAIT", "NO_TRADE"]
    confidence: float  # 0.0 to 1.0
    
    # Reasoning from LLM
    reasoning: str = ""
    brief_reason: str = ""
    
    # Rule citations from LLM
    rule_citations: List[str] = field(default_factory=list)
    
    # Trade setup (if decision is TRADE)
    setup: Optional[TradeSetup] = None
    
    # Context summary at time of decision
    context_summary: str = ""
    
    # Meta
    timestamp: datetime = field(default_factory=datetime.utcnow)
    llm_latency_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "brief_reason": self.brief_reason,
            "rule_citations": self.rule_citations,
            "setup": self.setup.to_dict() if self.setup else None,
            "timestamp": self.timestamp.isoformat(),
            "llm_latency_ms": self.llm_latency_ms
        }


@dataclass
class ValidationResult:
    """
    Result of decision validation.
    
    Contains approval status, any vetoes, and adjustments.
    """
    
    approved: bool
    original_decision: str
    final_decision: str
    
    # Veto reasons (if rejected)
    veto_reasons: List[VetoReason] = field(default_factory=list)
    
    # Warnings (don't veto but reduce confidence)
    warnings: List[str] = field(default_factory=list)
    
    # Confidence adjustment
    original_confidence: float = 0.0
    adjusted_confidence: float = 0.0
    
    # Audit
    validation_timestamp: datetime = field(default_factory=datetime.utcnow)
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    
    @property
    def was_vetoed(self) -> bool:
        return not self.approved and len(self.veto_reasons) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "was_vetoed": self.was_vetoed,
            "original_decision": self.original_decision,
            "final_decision": self.final_decision,
            "veto_reasons": [v.value for v in self.veto_reasons],
            "warnings": self.warnings,
            "original_confidence": self.original_confidence,
            "adjusted_confidence": self.adjusted_confidence,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "validation_timestamp": self.validation_timestamp.isoformat()
        }
    
    def to_audit_log(self) -> str:
        """Generate audit log for the decision."""
        lines = [
            f"## Decision Validation",
            f"**Result**: {'✅ APPROVED' if self.approved else '❌ VETOED'}",
            f"**Original**: {self.original_decision} ({self.original_confidence:.0%})",
            f"**Final**: {self.final_decision} ({self.adjusted_confidence:.0%})",
            ""
        ]
        
        if self.veto_reasons:
            lines.append("### Veto Reasons")
            for reason in self.veto_reasons:
                lines.append(f"- ❌ {reason.value}")
            lines.append("")
        
        if self.warnings:
            lines.append("### Warnings")
            for warning in self.warnings:
                lines.append(f"- ⚠️ {warning}")
            lines.append("")
        
        if self.checks_passed:
            lines.append("### Checks Passed")
            for check in self.checks_passed:
                lines.append(f"- ✅ {check}")
        
        return "\n".join(lines)


@dataclass
class AgentDecision:
    """
    Final agent decision after validation.
    
    This is what gets returned to the caller and recorded in context.
    """
    
    # Core decision
    decision: Literal["TRADE", "WAIT", "NO_TRADE"]
    confidence: float  # Adjusted confidence
    
    # Reasoning
    reasoning: Optional[str] = None
    brief_reason: str = ""
    rule_citations: List[str] = field(default_factory=list)
    
    # Trade setup (if decision is TRADE)
    setup: Optional[TradeSetup] = None
    
    # Validation result (for audit)
    validation: Optional[ValidationResult] = None
    
    # Context at time of decision
    observation_hash: str = ""
    phase_at_decision: str = ""
    context_summary: str = ""
    
    # Meta
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_latency_ms: int = 0
    
    @property
    def was_vetoed(self) -> bool:
        return self.validation is not None and self.validation.was_vetoed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "brief_reason": self.brief_reason,
            "rule_citations": self.rule_citations,
            "setup": self.setup.to_dict() if self.setup else None,
            "was_vetoed": self.was_vetoed,
            "validation": self.validation.to_dict() if self.validation else None,
            "observation_hash": self.observation_hash,
            "phase_at_decision": self.phase_at_decision,
            "timestamp": self.timestamp.isoformat(),
            "total_latency_ms": self.total_latency_ms
        }
