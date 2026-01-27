"""
Main Trading Agent - The Brain.

This agent receives market observations from tools, retrieves relevant
strategies via RAG, and reasons over them to make trading decisions.

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
from app.tools.observer import MarketObservation, run_all_observations


@dataclass
class AgentDecision:
    """
    The agent's trading decision with full reasoning trace.
    """
    # Decision
    decision: Literal["TRADE", "WAIT", "NO_TRADE"]
    confidence: float  # 0.0 to 1.0

    # Reasoning (verbose mode only)
    reasoning: Optional[str] = None
    brief_reason: str = ""

    # Rule citations
    rule_citations: List[str] = field(default_factory=list)

    # Trade setup (if decision is TRADE)
    setup: Optional[dict] = None  # {direction, entry, stop_loss, take_profit}

    # Meta
    observation_hash: str = ""
    strategy_context: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    latency_ms: int = 0
    mode: str = "concise"

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "brief_reason": self.brief_reason,
            "rule_citations": self.rule_citations,
            "setup": self.setup,
            "observation_hash": self.observation_hash,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "mode": self.mode
        }


class MainAgent:
    """
    The hybrid trading agent.

    Architecture:
    - Tools provide observations (what the market looks like)
    - RAG provides strategy context (what the rules say)
    - LLM reasons over both to decide (what to do)

    The agent does NOT execute trades. It only provides decisions
    with reasoning that can be reviewed by a human.
    """

    SYSTEM_INSTRUCTION = """You are an expert ICT (Inner Circle Trader) analyst.

Your role is to analyze market observations and determine if trading conditions align
with the provided ICT strategies and rules.

You must:
1. Carefully review the market observations provided
2. Consider the relevant strategy rules retrieved for this context
3. Reason about whether conditions meet the criteria for a trade
4. Be conservative - only recommend trades when multiple confluences align
5. Always cite specific rule numbers when making decisions

Key ICT Concepts to consider:
- Higher Timeframe (HTF) bias must be clear
- Lower Timeframe (LTF) must align with HTF
- Liquidity must be swept before entries
- Entries should be at premium/discount levels or PD arrays (FVG, OB)
- Kill zones are preferred trading windows
- Risk management is paramount

Decision Guidelines:
- TRADE: Clear bias, multiple confluences, liquidity taken, valid entry level
- WAIT: Bias exists but setup not complete, or waiting for liquidity sweep
- NO_TRADE: No clear bias, conflicting signals, outside kill zone with no setup"""

    def __init__(self):
        self.settings = get_settings()
        self.gemini: Optional[GeminiService] = None
        self.strategy_store: Optional[StrategyStore] = None
        self._initialized = False

    async def initialize(self):
        """Initialize the agent's dependencies."""
        if self._initialized:
            return

        self.gemini = get_gemini_service()
        self.strategy_store = await get_strategy_store()
        self._initialized = True

    async def analyze(
        self,
        observation: MarketObservation,
        mode: Optional[Literal["verbose", "concise"]] = None
    ) -> AgentDecision:
        """
        Analyze a market observation and produce a trading decision.

        Args:
            observation: Complete market observation from tools
            mode: Reasoning mode ("verbose" for UI, "concise" for batch)

        Returns:
            AgentDecision with decision, reasoning, and rule citations
        """
        await self.initialize()

        start_time = datetime.utcnow()
        mode = mode or self.settings.reasoning_mode

        # Step 1: Generate market summary for RAG query
        market_summary = observation.to_summary()

        # Step 2: Retrieve relevant strategies
        strategy_context = await self.strategy_store.get_strategies_for_context(
            market_summary,
            k=5
        )

        # Step 3: Build prompt
        prompt = self._build_prompt(observation, strategy_context)

        # Step 4: Call LLM
        response = await self.gemini.generate(
            prompt=prompt,
            mode=mode,
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=0.3  # Lower temperature for more consistent decisions
        )

        end_time = datetime.utcnow()
        latency_ms = int((end_time - start_time).total_seconds() * 1000)

        # Step 5: Parse response
        decision = self._parse_response(response, observation, mode, latency_ms)
        decision.strategy_context = strategy_context[:500]  # Truncate for storage

        return decision

    async def analyze_snapshot(
        self,
        htf_candles: List[dict],
        ltf_candles: List[dict],
        symbol: str,
        timestamp: Optional[datetime] = None,
        mode: Optional[Literal["verbose", "concise"]] = None,
        micro_candles: Optional[List[dict]] = None
    ) -> tuple[MarketObservation, AgentDecision]:
        """
        Full analysis pipeline: observe → retrieve → reason → decide.

        Convenience method that runs observation and analysis in one call.

        Args:
            htf_candles: Higher timeframe candles
            ltf_candles: Lower timeframe candles
            symbol: Trading symbol
            timestamp: Analysis timestamp
            mode: Reasoning mode
            micro_candles: Optional micro timeframe candles

        Returns:
            Tuple of (MarketObservation, AgentDecision)
        """
        # Run observation tools
        observation = run_all_observations(
            htf_candles=htf_candles,
            ltf_candles=ltf_candles,
            symbol=symbol,
            timestamp=timestamp,
            micro_candles=micro_candles
        )

        # Run agent analysis
        decision = await self.analyze(observation, mode)

        return observation, decision

    def _build_prompt(
        self,
        observation: MarketObservation,
        strategy_context: str
    ) -> str:
        """Build the analysis prompt for the LLM."""

        prompt_parts = [
            "# Market Analysis Request",
            "",
            f"**Symbol**: {observation.symbol}",
            f"**Time**: {observation.timestamp.strftime('%Y-%m-%d %H:%M')} UTC",
            f"**Current Price**: {observation.current_price:.5f}",
            "",
            "---",
            "",
            "## Current Market Observations",
            "",
            observation.to_summary(),
            "",
            "---",
            "",
            "## Relevant Strategy Rules",
            "",
            strategy_context,
            "",
            "---",
            "",
            "## Your Task",
            "",
            "Based on the observations above and the strategy rules provided:",
            "",
            "1. Analyze whether the current market conditions align with any trading setup",
            "2. Consider all confluences: bias, structure, liquidity, PD arrays, session",
            "3. Make a decision: TRADE, WAIT, or NO_TRADE",
            "4. If TRADE, provide specific entry, stop loss, and take profit levels",
            "5. Cite the specific rule numbers that support your decision",
            "",
            "Remember: Be conservative. Only recommend TRADE when you have strong confluence.",
        ]

        return "\n".join(prompt_parts)

    def _parse_response(
        self,
        response: dict,
        observation: MarketObservation,
        mode: str,
        latency_ms: int
    ) -> AgentDecision:
        """Parse LLM response into AgentDecision."""

        content = response.get("content", "")
        parsed = response.get("parsed")

        # Default decision
        decision = AgentDecision(
            decision="NO_TRADE",
            confidence=0.0,
            observation_hash=observation.state_hash,
            latency_ms=latency_ms,
            mode=mode
        )

        if parsed:
            # Successfully parsed JSON
            decision.decision = parsed.get("decision", "NO_TRADE")
            decision.confidence = float(parsed.get("confidence", 0.0))

            # Filter rule citations to only valid rule IDs (like 1.1, 6.5, etc)
            raw_citations = parsed.get("rule_citations", [])
            valid_citations = []
            for citation in raw_citations:
                if isinstance(citation, str):
                    # Must be a valid rule ID pattern (1-2 digits, dot, 1-2 digits)
                    import re
                    if re.match(r'^\d{1,2}\.\d{1,2}$', citation):
                        valid_citations.append(citation)
            decision.rule_citations = valid_citations

            decision.brief_reason = parsed.get("brief_reason", "")
            decision.setup = parsed.get("setup")

            if mode == "verbose":
                decision.reasoning = content
        else:
            # Fallback: try to extract decision from text
            content_upper = content.upper()

            if "TRADE" in content_upper and "NO_TRADE" not in content_upper and "WAIT" not in content_upper:
                decision.decision = "TRADE"
                decision.confidence = 0.5
            elif "WAIT" in content_upper:
                decision.decision = "WAIT"
                decision.confidence = 0.5
            else:
                decision.decision = "NO_TRADE"
                decision.confidence = 0.3

            decision.reasoning = content
            # Show the full LLM output when JSON parsing fails
            decision.brief_reason = content

            # Try to extract rule citations - only valid rule ID patterns
            import re
            # Only match patterns like 1.1, 6.5, 8.1 (not prices like 1.08628)
            rule_pattern = r'\b([1-9]\.\d{1,2})\b'
            rules = re.findall(rule_pattern, content)
            decision.rule_citations = list(set(rules))[:5]

        return decision

    async def explain_decision(
        self,
        decision: AgentDecision,
        observation: MarketObservation
    ) -> str:
        """
        Generate a detailed explanation of a decision for the UI.

        Useful when the original decision was made in concise mode
        but the user wants more details.
        """
        await self.initialize()

        prompt = f"""
Please explain in detail why this trading decision was made:

**Decision**: {decision.decision}
**Confidence**: {decision.confidence:.0%}
**Rules Cited**: {', '.join(decision.rule_citations) if decision.rule_citations else 'None'}
**Brief Reason**: {decision.brief_reason}

The market conditions were:
{observation.to_summary()}

Explain step by step:
1. What the market structure shows
2. What liquidity conditions were present
3. What PD arrays (FVGs, OBs) were relevant
4. Why this decision aligns (or doesn't align) with ICT methodology
"""

        response = await self.gemini.generate(
            prompt=prompt,
            mode="verbose",
            system_instruction=self.SYSTEM_INSTRUCTION,
            temperature=0.5
        )

        return response.get("content", "Unable to generate explanation")


# Singleton instance
_main_agent: Optional[MainAgent] = None


async def get_main_agent() -> MainAgent:
    """Get or create the main agent singleton."""
    global _main_agent
    if _main_agent is None:
        _main_agent = MainAgent()
        await _main_agent.initialize()
    return _main_agent
