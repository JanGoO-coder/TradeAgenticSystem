"""
Main Trading Agent - The Brain.

This agent uses the ICT Architecture for market analysis:
- Event-based observation
- Persistent context
- Phase detection
- Decision validation

The code does not make trading decisions.
The code only observes and reports.
The agent reasons, evaluates, and decides.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Literal
import json

from app.core.config import get_settings
from app.services.llm_service import get_gemini_service, GeminiService
from app.services.strategy_store import get_strategy_store, StrategyStore
from app.tools.observer import run_event_observation

# ICT Architecture Components
from app.domain.observation import ObservationResult
from app.domain.decision import (
    ProposedDecision,
    ValidationResult,
    AgentDecision as DomainAgentDecision,
    TradeSetup
)
from app.domain.phase import MarketPhase
from app.services.market_context import get_context_manager, MarketContextManager
from app.services.phase_detector import get_phase_detector, PhaseDetector
from app.agent.prompt_builder import get_prompt_builder, ICTPromptBuilder
from app.agent.decision_validator import get_decision_validator, DecisionValidator


class MainAgent:
    """
    The ICT Trading Agent.

    Architecture:
    - Event Observer provides factual market events
    - Context Manager tracks persistent state
    - Phase Detector identifies PO3 phases
    - Prompt Builder generates dynamic ICT prompts
    - Decision Validator enforces hard rules

    The agent does NOT execute trades. It only provides decisions
    with reasoning that can be reviewed by a human.
    """

    def __init__(self):
        self.settings = get_settings()
        self.gemini: Optional[GeminiService] = None
        self.strategy_store: Optional[StrategyStore] = None
        self._initialized = False
        
        # ICT Architecture Components
        self.context_manager: Optional[MarketContextManager] = None
        self.phase_detector: Optional[PhaseDetector] = None
        self.prompt_builder: Optional[ICTPromptBuilder] = None
        self.decision_validator: Optional[DecisionValidator] = None
        self._previous_observations: dict = {}  # symbol -> ObservationResult

    async def initialize(self):
        """Initialize the agent's dependencies."""
        if self._initialized:
            return

        self.gemini = get_gemini_service()
        self.strategy_store = await get_strategy_store()
        
        # Initialize ICT components
        self.context_manager = get_context_manager()
        self.phase_detector = get_phase_detector()
        self.prompt_builder = get_prompt_builder()
        self.decision_validator = get_decision_validator()
        
        self._initialized = True

    # =========================================================================
    # ICT ARCHITECTURE METHODS
    # =========================================================================
    
    async def analyze_ict(
        self,
        htf_candles: List[dict],
        ltf_candles: List[dict],
        symbol: str,
        timestamp: Optional[datetime] = None,
        mode: Optional[Literal["verbose", "concise"]] = None
    ) -> tuple[ObservationResult, DomainAgentDecision]:
        """
        Analyze market using the ICT architecture.
        
        This is the primary method for analysis. It uses:
        1. Event-based observer (factual events)
        2. Persistent context manager (stateful memory)
        3. Phase detector (PO3 phases)
        4. Dynamic prompt builder (ICT rulebook)
        5. Decision validator (hard veto rules)
        
        Args:
            htf_candles: Higher timeframe candles (1H)
            ltf_candles: Lower timeframe candles (15M)
            symbol: Trading symbol (e.g., "EURUSD")
            timestamp: Analysis timestamp
            mode: Reasoning mode
            
        Returns:
            Tuple of (ObservationResult, AgentDecision)
        """
        await self.initialize()
        
        start_time = datetime.utcnow()
        mode = mode or self.settings.reasoning_mode
        timestamp = timestamp or datetime.utcnow()
        
        # ==== STEP 1: OBSERVE (emit factual events) ====
        previous_obs = self._previous_observations.get(symbol)
        observation = run_event_observation(
            htf_candles=htf_candles,
            ltf_candles=ltf_candles,
            symbol=symbol,
            timestamp=timestamp,
            previous_observation=previous_obs
        )
        self._previous_observations[symbol] = observation
        
        # ==== STEP 2: UPDATE CONTEXT ====
        context = self.context_manager.update_from_observation(
            symbol=symbol,
            observation_data=observation.raw_data,
            events=observation.events
        )
        
        # ==== STEP 3: DETECT PHASE ====
        phase, phase_confidence, phase_reason = self.phase_detector.detect_phase(
            context=context,
            recent_events=observation.events
        )
        context.phase.transition_to(phase, phase_reason, phase_confidence)
        
        # ==== STEP 4: BUILD PROMPT ====
        system_prompt = self.prompt_builder.build_system_prompt(context)
        analysis_prompt = self.prompt_builder.build_analysis_prompt(
            observation_summary=observation.to_summary(),
            context=context
        )
        
        # ==== STEP 5: CALL LLM (proposes decision) ====
        llm_start = datetime.utcnow()
        response = await self.gemini.generate(
            prompt=analysis_prompt,
            mode=mode,
            system_instruction=system_prompt,
            temperature=0.3
        )
        llm_latency = int((datetime.utcnow() - llm_start).total_seconds() * 1000)
        
        # ==== STEP 6: PARSE LLM RESPONSE ====
        proposed = self._parse_llm_response_to_proposed(response, llm_latency)
        
        # ==== STEP 7: VALIDATE (hard veto rules) ====
        validation = self.decision_validator.validate(
            proposed=proposed,
            context=context,
            observation_data=observation.raw_data
        )
        
        # ==== STEP 8: CREATE FINAL DECISION ====
        final_decision = self.decision_validator.create_final_decision(
            proposed=proposed,
            validation=validation,
            context=context
        )
        
        # Record in context
        context.record_decision(final_decision.decision, final_decision.confidence)
        
        # Calculate total latency
        total_latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        final_decision.total_latency_ms = total_latency
        
        return observation, final_decision
    
    def _parse_llm_response_to_proposed(
        self,
        response: dict,
        llm_latency_ms: int
    ) -> ProposedDecision:
        """Parse LLM response into ProposedDecision."""
        content = response.get("content", "")
        parsed = response.get("parsed")
        
        if parsed:
            # Successfully parsed JSON
            setup = None
            if parsed.get("setup"):
                setup_data = parsed["setup"]
                setup = TradeSetup(
                    direction=setup_data.get("direction", "LONG"),
                    entry_price=float(setup_data.get("entry_price", 0)),
                    stop_loss=float(setup_data.get("stop_loss", 0)),
                    take_profit=float(setup_data.get("take_profit", 0)),
                    entry_model=setup_data.get("entry_model", ""),
                    pd_array_type=setup_data.get("pd_array_type", "")
                )
            
            # Filter rule citations to valid IDs
            import re
            raw_citations = parsed.get("rule_citations", [])
            valid_citations = [
                c for c in raw_citations
                if isinstance(c, str) and re.match(r'^\d{1,2}\.\d{1,2}$', c)
            ]
            
            return ProposedDecision(
                decision=parsed.get("decision", "NO_TRADE"),
                confidence=float(parsed.get("confidence", 0.5)),
                reasoning=content if self.settings.reasoning_mode == "verbose" else "",
                brief_reason=parsed.get("brief_reason", ""),
                rule_citations=valid_citations,
                setup=setup,
                context_update=parsed.get("context_update", ""),
                llm_latency_ms=llm_latency_ms
            )
        
        # Fallback: couldn't parse JSON
        return ProposedDecision(
            decision="NO_TRADE",
            confidence=0.3,
            reasoning=content,
            brief_reason="LLM response could not be parsed",
            llm_latency_ms=llm_latency_ms
        )
    
    async def analyze_ict_snapshot(
        self,
        htf_candles: List[dict],
        ltf_candles: List[dict],
        symbol: str,
        timestamp: Optional[datetime] = None
    ) -> dict:
        """
        Quick ICT analysis returning a summary dict for API responses.
        
        Convenience method for API endpoints.
        """
        observation, decision = await self.analyze_ict(
            htf_candles=htf_candles,
            ltf_candles=ltf_candles,
            symbol=symbol,
            timestamp=timestamp
        )
        
        return {
            "symbol": symbol,
            "timestamp": observation.timestamp.isoformat(),
            "decision": decision.decision,
            "confidence": decision.confidence,
            "brief_reason": decision.brief_reason,
            "phase": decision.phase_at_decision,
            "validated": decision.validation.approved if decision.validation else True,
            "veto_reasons": [v.value for v in decision.validation.veto_reasons] if decision.validation else [],
            "events_count": len(observation.events),
            "latency_ms": decision.total_latency_ms
        }
    
    def get_context(self, symbol: str):
        """Get the persistent context for a symbol."""
        if self.context_manager:
            return self.context_manager.get_context(symbol)
        return None
    
    def reset_context(self, symbol: str):
        """Reset the context for a symbol."""
        if self.context_manager:
            self.context_manager.reset_context(symbol)
        if symbol in self._previous_observations:
            del self._previous_observations[symbol]


# Singleton instance
_main_agent: Optional[MainAgent] = None


async def get_main_agent() -> MainAgent:
    """Get or create the main agent singleton."""
    global _main_agent
    if _main_agent is None:
        _main_agent = MainAgent()
        await _main_agent.initialize()
    return _main_agent
