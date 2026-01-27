"""
Strategy Agent - The Neuro-Symbolic Assembler.

This agent acts as a Coordinator:
1. Gathers RAW OBJECTIVE FACTS using pure market observers (The Eyes).
2. Loads the active Trading Strategy (The Playbook).
3. Feeds Facts + Strategy into the Reasoning Engine (The Brain / LLM).
4. Returns the structured decision.

It has ZERO native opinion. It does not know what "Bullish" means.
The LLM interprets facts against the strategy to determine bias.
"""
import logging
import os
from datetime import datetime
from typing import Optional, Dict, List, Any

from ..state import (
    BiasDirection, TradingSession, EnvironmentStatus,
    BiasAssessment, SessionLevels, EnvironmentCheck, MarketContext
)
from ..rules_config import RulesConfig, get_rules
from ..protocol import MessageEnvelope, ActionType, MessageLog, create_error_response
from .models import MarketContextRequest

# Pure Market Observers (The Eyes) - No opinions, only facts
from ..market_observers import build_market_facts

from .reasoning_engine import ReasoningEngine

logger = logging.getLogger(__name__)


class StrategyAgent:
    """
    The Neuro-Symbolic Strategy Agent.
    
    Architecture:
    - Tools (market_observers) = Eyes - observe market, return facts
    - Strategy files (.md) = Playbooks - natural language trading rules
    - ReasoningEngine (LLM) = Brain - interprets facts against playbook
    """

    def __init__(
        self,
        config: Optional[RulesConfig] = None,
        message_log: Optional[MessageLog] = None
    ):
        self.config = config or get_rules()
        self.message_log = message_log or MessageLog()
        self.reasoning_engine = ReasoningEngine()
        
        # Strategy system
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.strategies_dir = os.path.join(self.current_dir, "strategies")
        self.active_strategy = self._load_active_strategy()
        self.available_strategies = self._discover_strategies()
        
        # Cache for last market facts (for debugging/API exposure)
        self._last_market_facts: Optional[Dict[str, Any]] = None

    def _load_active_strategy(self) -> str:
        """Load the currently active strategy playbook."""
        strategy_path = os.path.join(self.strategies_dir, "active_strategy.md")
        try:
            with open(strategy_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info(f"Loaded active strategy from {strategy_path}")
                return content
        except FileNotFoundError:
            logger.warning(f"Strategy file not found at {strategy_path}, using default")
            return self._get_default_strategy()
    
    def _get_default_strategy(self) -> str:
        """Return a safe default strategy."""
        return """# Default Strategy
        
## Trading Rules
1. Only trade during New York session (7 AM - 4 PM EST)
2. Follow the higher timeframe (1H) structure
3. Wait for a clear setup before entering
4. If conditions are unclear, do not trade
"""
    
    def _discover_strategies(self) -> Dict[str, str]:
        """Discover all available strategy files."""
        strategies = {}
        try:
            for file in os.listdir(self.strategies_dir):
                if file.endswith(".md") and file not in ["README.md", "active_strategy.md"]:
                    name = file.replace(".md", "")
                    path = os.path.join(self.strategies_dir, file)
                    strategies[name] = path
            logger.info(f"Discovered {len(strategies)} strategies: {list(strategies.keys())}")
        except FileNotFoundError:
            logger.warning(f"Strategies directory not found: {self.strategies_dir}")
        return strategies
    
    def switch_strategy(self, strategy_name: str) -> bool:
        """Switch to a different strategy playbook."""
        if strategy_name not in self.available_strategies:
            logger.warning(f"Strategy not found: {strategy_name}")
            return False
        
        path = self.available_strategies[strategy_name]
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.active_strategy = f.read()
            logger.info(f"Switched to strategy: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load strategy {strategy_name}: {e}")
            return False
    
    def get_available_strategies(self) -> List[str]:
        """Return list of available strategy names."""
        return list(self.available_strategies.keys())
    
    def get_last_market_facts(self) -> Optional[Dict[str, Any]]:
        """Return the last computed market facts (for debugging)."""
        return self._last_market_facts

    def handle_message(self, message: MessageEnvelope) -> MessageEnvelope:
        """Handle incoming messages from Main Agent."""
        self.message_log.append(message)
        
        if message.action != ActionType.ANALYZE_CONTEXT:
            error_reply = create_error_response(message, "Expected ANALYZE_CONTEXT")
            self.message_log.append(error_reply)
            return error_reply

        try:
            request = MarketContextRequest(**message.payload)
            context = self._analyze_context(request)
            
            reply = message.create_reply(
                action=ActionType.CONTEXT_RESULT,
                payload={"context": context.model_dump()}
            )
            self.message_log.append(reply)
            return reply

        except Exception as e:
            logger.exception(f"Strategy analysis failed: {e}")
            return create_error_response(message, f"Analysis failed: {str(e)}")

    def _analyze_context(self, request: MarketContextRequest) -> MarketContext:
        """
        Neuro-Symbolic Analysis Pipeline:
        1. Gather PURE FACTS using market observers (Eyes)
        2. Feed Facts + Strategy to LLM (Brain)
        3. Map LLM decision to protocol objects
        """
        timestamp = request.timestamp
        
        # =====================================================================
        # 1. GATHER PURE FACTS (The Eyes) - No opinions, just observations
        # =====================================================================
        facts = build_market_facts(
            timestamp=timestamp,
            timeframe_bars=request.timeframe_bars
        )
        
        # Cache for debugging
        self._last_market_facts = facts
        
        logger.debug(f"Market facts gathered: {len(facts.get('structure', {}))} timeframes analyzed")
        
        # =====================================================================
        # 2. REASONING (The Brain) - LLM interprets facts against strategy
        # =====================================================================
        decision = self.reasoning_engine.analyze(self.active_strategy, facts)
        
        logger.info(f"LLM Decision: bias={decision.get('bias')}, action={decision.get('action')}, confidence={decision.get('confidence')}")
        
        # =====================================================================
        # 3. MAP DECISION TO PROTOCOL (Translation layer)
        # =====================================================================
        
        # Map bias
        bias_enum = BiasDirection.NEUTRAL
        if decision.get("bias") == "BULLISH":
            bias_enum = BiasDirection.BULLISH
        elif decision.get("bias") == "BEARISH":
            bias_enum = BiasDirection.BEARISH
            
        bias = BiasAssessment(
            direction=bias_enum,
            confidence=decision.get("confidence", 0.5),
            rationale=decision.get("reasoning", "LLM Decision")
        )
        
        # Map environment status
        env_status = EnvironmentStatus.WAIT
        if decision.get("action") == "TRADE":
            env_status = EnvironmentStatus.GO
        elif decision.get("action") == "MONITOR":
            env_status = EnvironmentStatus.WAIT
        else: 
            env_status = EnvironmentStatus.NO_TRADE
        
        # Extract session info from facts
        time_facts = facts.get("time", {})
        sessions = time_facts.get("sessions", {})
        killzones = time_facts.get("killzones", {})
        special_windows = time_facts.get("special_windows", {})
        
        # Determine current session
        current_session = TradingSession.OFF_HOURS
        if sessions.get("new_york", {}).get("active"):
            current_session = TradingSession.NEW_YORK
        elif sessions.get("london", {}).get("active"):
            current_session = TradingSession.LONDON
        elif sessions.get("asia", {}).get("active"):
            current_session = TradingSession.ASIA
        
        # Check killzone status
        ny_kz_active = killzones.get("new_york_kz", {}).get("active", False)
        london_kz_active = killzones.get("london_kz", {}).get("active", False)
        killzone_active = ny_kz_active or london_kz_active
        killzone_name = "new_york" if ny_kz_active else ("london" if london_kz_active else None)
        
        # Check silver bullet
        sb_am = special_windows.get("silver_bullet_am", {}).get("active", False)
        sb_pm = special_windows.get("silver_bullet_pm", {}).get("active", False)
        silverbullet_active = sb_am or sb_pm
        
        environment = EnvironmentCheck(
            status=env_status,
            session=current_session,
            killzone_active=killzone_active,
            killzone_name=killzone_name,
            blocked_reasons=decision.get("blocking_factors", []) if env_status == EnvironmentStatus.NO_TRADE else [],
            news_clear=True,  # TODO: Integrate news calendar
            silverbullet_active=silverbullet_active
        )
        
        # Extract key levels from facts
        liquidity = facts.get("liquidity", {})
        levels = SessionLevels(
            pdh=liquidity.get("pdh"),
            pdl=liquidity.get("pdl"),
            ny_high=liquidity.get("range_high"),
            ny_low=liquidity.get("range_low"),
            killzone_high=liquidity.get("range_high") if killzone_active else None,
            killzone_low=liquidity.get("range_low") if killzone_active else None
        )
        
        # Also capture LLM-suggested levels if provided
        key_levels = decision.get("key_levels", {})
        if key_levels:
            # LLM may suggest entry/SL/TP zones
            logger.debug(f"LLM suggested levels: {key_levels}")
        
        return MarketContext(
            bias=bias,
            environment=environment,
            levels=levels,
            analyzed_at=datetime.utcnow(),
            valid_until=datetime.utcnow()  # TODO: Add expiry logic
        )

    def reset(self):
        """Reset agent state."""
        self._last_market_facts = None
