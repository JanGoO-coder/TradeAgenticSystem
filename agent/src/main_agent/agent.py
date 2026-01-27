"""
Main Agent - The Orchestrator.

Central brain that receives goals, maintains state, delegates tasks,
and synthesizes results. Does NOT do heavy analysis or execution itself.

Responsibilities:
- State Management (IDLE → ANALYZING → DECIDING → EXECUTING → MONITORING)
- Clock Control (Simulation time advancement)
- Delegation Router (Strategy Agent for context, Worker Agent for execution)
- Risk Policy Enforcement (Max drawdown, position limits, R:R thresholds)
- Signal Synthesis (Combine analysis to form trade decisions)
- Final Approval (Last checkpoint before trade execution)
- Logging (All inter-agent messages for replay)
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal, Union
import uuid

from ..state import (
    SessionState, SessionPhase, MarketContext, TradeSetup,
    Position, ClosedTrade, VirtualClock,
    BiasDirection, EnvironmentStatus, OrderDirection, TradeResult
)
from ..rules_config import RulesConfig, get_rules, reload_rules
from ..protocol import (
    MessageEnvelope, MessageLog, TickLog, TickEvent,
    ActionType, AgentRole, create_request,
    ReceiptPayload, ErrorPayload
)
from ..strategy_agent import StrategyAgent
from ..strategy_agent.models import MarketContextRequest
from ..worker_agent import WorkerAgent
from ..worker_agent.models import (
    SetupScanRequest, ExecutionRequest, AdvanceTimeRequest
)

logger = logging.getLogger(__name__)


# =============================================================================
# Sub-States for Reliability
# =============================================================================
class ReliabilityState:
    """Tracks state of in-flight requests."""
    def __init__(self):
        self.pending_request: Optional[MessageEnvelope] = None
        self.last_sent_time: Optional[datetime] = None
        self.retry_count: int = 0
        self.max_retries: int = 3
        self.timeout_ms: int = 5000

    def reset(self):
        self.pending_request = None
        self.last_sent_time = None
        self.retry_count = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state."""
        return {
            "pending_request": self.pending_request.model_dump() if self.pending_request else None,
            "last_sent_time": self.last_sent_time.isoformat() if self.last_sent_time else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_ms": self.timeout_ms
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReliabilityState":
        """Deserialize state."""
        obj = cls()
        if data.get("pending_request"):
            obj.pending_request = MessageEnvelope(**data["pending_request"])
        
        if data.get("last_sent_time"):
            try:
                obj.last_sent_time = datetime.fromisoformat(data["last_sent_time"])
            except:
                pass
                
        obj.retry_count = data.get("retry_count", 0)
        obj.max_retries = data.get("max_retries", 3)
        obj.timeout_ms = data.get("timeout_ms", 5000)
        return obj


class MainAgent:
    """
    The Main Agent (Orchestrator).

    Manages the lifecycle of a trading session through a state machine.
    Delegates analysis to Strategy Agent and execution to Worker Agent.

    Usage:
        agent = MainAgent()
        agent.initialize_session(symbol="EURUSD", mode="BACKTEST", ...)
        result = agent.run_tick(ohlcv_data)
    """

    def __init__(
        self,
        config: Optional[RulesConfig] = None,
        **kwargs
    ):
        """
        Initialize Main Agent.

        Args:
            config: Rules configuration (uses global if not provided)
            **kwargs: Additional handlers for sub-agents
        """
        self.config = config or get_rules()

        # Shared message log for audit trail
        self.message_log = MessageLog()
        self.tick_log = TickLog()

        # Sub-agents
        self.strategy_agent = StrategyAgent(self.config, self.message_log)
        self.worker_agent = WorkerAgent(
            self.config,
            self.message_log,
            execution_handler=kwargs.get("execution_handler"),
            close_handler=kwargs.get("close_handler")
        )

        # Session state (initialized via initialize_session)
        self._state: Optional[SessionState] = None
        self._clock: Optional[VirtualClock] = None

        # Correlation ID for current session
        self._correlation_id: str = ""
        
        # Reliability tracking
        self._rel_state = ReliabilityState()

    def export_state(self) -> Dict[str, Any]:
        """Export internal state for persistence."""
        return {
            "correlation_id": self._correlation_id,
            "session_state": self._state.model_dump() if self._state else None,
            "reliability_state": self._rel_state.to_dict(),
            "message_log_count": len(self.message_log) if self.message_log else 0
        }

    def import_state(self, data: Dict[str, Any]) -> None:
        """Import state from persistence."""
        if not data:
            return
            
        self._correlation_id = data.get("correlation_id", "")
        
        # Restore Session State
        if data.get("session_state") and "session_id" in data["session_state"]:
            self._state = SessionState(**data["session_state"])
            
        # Restore Reliability State
        if data.get("reliability_state"):
            self._rel_state = ReliabilityState.from_dict(data["reliability_state"])

    # =========================================================================
    # Session Management
    # =========================================================================

    def initialize_session(
        self,
        symbol: str,
        mode: Literal["LIVE", "BACKTEST"],
        start_time: datetime,
        end_time: Optional[datetime] = None,
        starting_balance: float = 10000.0,
        timeframe: str = "5M"
    ) -> SessionState:
        """
        Initialize a new trading session.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            mode: "LIVE" or "BACKTEST"
            start_time: Session start time
            end_time: Session end time (required for BACKTEST)
            starting_balance: Initial account balance
            timeframe: Base timeframe for simulation

        Returns:
            Initialized SessionState
        """
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        self._correlation_id = session_id

        # Initialize virtual clock for backtest
        if mode == "BACKTEST":
            if end_time is None:
                end_time = start_time + timedelta(days=30)
            self._clock = VirtualClock(start_time, end_time, timeframe)
        else:
            self._clock = None

        # Create session state
        self._state = SessionState(
            session_id=session_id,
            symbol=symbol,
            mode=mode,
            current_time=start_time,
            phase=SessionPhase.IDLE,
            starting_balance=starting_balance,
            balance=starting_balance,
            equity=starting_balance,
            max_trades_per_session=self.config.invalidation.max_trades_per_session
        )

        # Reset sub-agents and reliability state
        self.strategy_agent.reset()
        self.message_log.clear()
        self.tick_log = TickLog()
        self._rel_state.reset()

        logger.info(
            f"Session initialized: {session_id} | {symbol} | {mode} | "
            f"Balance: ${starting_balance}"
        )

        return self._state

    @property
    def state(self) -> Optional[SessionState]:
        """Get current session state."""
        return self._state

    @property
    def clock(self) -> Optional[VirtualClock]:
        """Get virtual clock (backtest only)."""
        return self._clock

    # =========================================================================
    # Main Execution Loop
    # =========================================================================

    def run_tick(
        self,
        timeframe_bars: Dict[str, List[Dict[str, Any]]],
        economic_calendar: List[Any] = None
    ) -> Dict[str, Any]:
        """
        Run a single tick of the trading session.

        This is the main entry point called by the backend.

        Args:
            timeframe_bars: OHLCV data by timeframe {"1H": [...], "15M": [...], "5M": [...]}
            economic_calendar: List of economic events

        Returns:
            Dict with tick results including state, context, setups, actions
        """
        if self._state is None:
            raise RuntimeError("Session not initialized. Call initialize_session() first.")

        economic_calendar = economic_calendar or []

        # Create tick event for visualization
        tick = self.tick_log.new_tick(self._state.current_time)

        result = {
            "tick": tick.tick,
            "time": self._state.current_time.isoformat(),
            "phase": self._state.phase.value,
            "actions": [],
            "context": None,
            "setup": None,
            "setups_scanned": 0,
            "setups_rejected": [],
            "trade_executed": None,
            "reason": "",
            "analysis_summary": None
        }

        try:
            # Execute state machine
            result = self._execute_state_machine(
                timeframe_bars, economic_calendar, tick, result
            )
            
            # Log summary for visibility
            if result.get("trade_executed") and result["trade_executed"].get("success"):
                logger.info(f"🎯 TRADE EXECUTED: {result['setup'].get('model_name', 'Unknown')} at tick {tick.tick}")
            elif result.get("setup"):
                logger.info(f"📊 Setup found: {result['setup'].get('model_name', 'Unknown')} (tick {tick.tick})")
            elif result.get("reason"):
                logger.debug(f"⏳ No action: {result['reason']} (tick {tick.tick})")

        except Exception as e:
            logger.exception(f"Tick execution failed: {e}")
            result["error"] = str(e)
            tick.add_event(AgentRole.MAIN, "ERROR", error=str(e))

        return result

    def _execute_state_machine(
        self,
        timeframe_bars: Dict[str, List[Dict[str, Any]]],
        economic_calendar: List[Any],
        tick: TickEvent,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the state machine based on current phase.
        """
        state = self._state

        # IDLE → ANALYZING
        if state.phase == SessionPhase.IDLE:
            state.phase = SessionPhase.ANALYZING
            tick.add_event(AgentRole.MAIN, "PHASE_CHANGE", new_phase="ANALYZING")
            result["actions"].append("Started analysis")

        # ANALYZING: Request context from Strategy Agent
        if state.phase == SessionPhase.ANALYZING:
            context = self._request_analysis_reliable(timeframe_bars, economic_calendar, tick)
            
            if context is None:
                # Waiting for response or retrying
                result["actions"].append("Waiting for analysis")
                return result

            result["context"] = context.model_dump()

            if context.environment.status == EnvironmentStatus.GO:
                state.phase = SessionPhase.DECIDING
                tick.add_event(AgentRole.MAIN, "PHASE_CHANGE", new_phase="DECIDING")
                result["actions"].append("Environment GO - moving to deciding")
                result["analysis_summary"] = {
                    "bias": context.bias.direction.value,
                    "confidence": context.bias.confidence,
                    "session": context.environment.session.value if context.environment.session else None,
                    "killzone_active": context.environment.killzone_active,
                    "silverbullet_active": context.environment.silverbullet_active
                }
                logger.info(f"✅ Environment GO: bias={context.bias.direction.value}, session={context.environment.session.value if context.environment.session else 'None'}")
            else:
                reason = "Environment not favorable"
                if context:
                    reason = ", ".join(context.environment.blocked_reasons) or reason
                result["reason"] = reason
                tick.add_event(AgentRole.MAIN, "WAIT", reason=reason)
                # Stay in ANALYZING, wait for next tick
                # NOTE: Reliability state is reset inside request method when success

        # DECIDING: Request setups from Worker Agent
        if state.phase == SessionPhase.DECIDING:
            if state.market_context is None:
                state.phase = SessionPhase.ANALYZING
                return result

            setups_result = self._request_setups_reliable(timeframe_bars, tick)
            
            # None implies waiting/retrying
            if setups_result is None:
                result["actions"].append("Waiting for setup scan")
                return result
                
            setups = setups_result
            result["setups_scanned"] = len(setups)

            if setups:
                # Select best setup
                best_setup = self._select_best_setup(setups)
                result["setup"] = best_setup.model_dump() if best_setup else None
                
                logger.info(f"🔍 {len(setups)} setup(s) found, best: {best_setup.model_name if best_setup else 'None'}")

                if best_setup and self._validate_setup(best_setup, tick):
                    state.current_setup = best_setup
                    state.phase = SessionPhase.EXECUTING
                    tick.add_event(AgentRole.MAIN, "PHASE_CHANGE", new_phase="EXECUTING")
                    result["actions"].append(f"Setup approved: {best_setup.model_name}")
                    logger.info(f"✅ Setup APPROVED: {best_setup.model_name} | R:R={best_setup.risk_reward:.1f} | Confluence={best_setup.confluence_score}")
                else:
                    result["reason"] = "Setup validation failed"
                    result["setups_rejected"].append({
                        "model": best_setup.model_name if best_setup else "Unknown",
                        "reason": "Failed risk/confluence checks"
                    })
                    state.phase = SessionPhase.ANALYZING
                    logger.info(f"❌ Setup REJECTED: validation failed")
            else:
                result["reason"] = "No valid setups found"
                state.phase = SessionPhase.ANALYZING

        # EXECUTING: Execute trade via Worker Agent
        if state.phase == SessionPhase.EXECUTING:
            if state.current_setup:
                # Reliable execution request
                trade_result = self._execute_trade_reliable(tick)
                
                if trade_result is None:
                    result["actions"].append("Waiting for execution")
                    return result
                
                result["trade_executed"] = trade_result

                if trade_result and trade_result.get("success"):
                    state.phase = SessionPhase.MONITORING
                    state.trades_this_session += 1
                    tick.add_event(AgentRole.MAIN, "PHASE_CHANGE", new_phase="MONITORING")
                    result["actions"].append("Trade executed - monitoring")
                else:
                    state.phase = SessionPhase.ANALYZING
                    result["reason"] = trade_result.get("error", "Execution failed")
            else:
                state.phase = SessionPhase.ANALYZING

        # MONITORING: Watch open positions
        if state.phase == SessionPhase.MONITORING:
            if not state.open_positions:
                # No open positions, back to analyzing
                state.phase = SessionPhase.ANALYZING
                state.current_setup = None
                tick.add_event(AgentRole.MAIN, "PHASE_CHANGE", new_phase="ANALYZING")
                result["actions"].append("No open positions - back to analyzing")

        result["phase"] = state.phase.value
        return result

    # =========================================================================
    # Reliable Delegation Methods
    # =========================================================================

    def _send_reliable_message(
        self, 
        target_agent: Any, 
        action: ActionType, 
        payload: Dict[str, Any],
        tick: TickEvent
    ) -> Optional[MessageEnvelope]:
        """
        Generic reliable message sender with Retry and Timeout logic.
        
        Returns:
            Response MessageEnvelope if success/completed.
            None if still waiting (ACKd or Timeout not reached).
        """
        now = datetime.utcnow()
        
        # 1. New Request
        if not self._rel_state.pending_request or self._rel_state.pending_request.action != action:
            # Create new request
            msg = create_request(
                from_agent=AgentRole.MAIN,
                to_agent=AgentRole.STRATEGY if target_agent == self.strategy_agent else AgentRole.WORKER,
                action=action,
                payload=payload,
                correlation_id=self._correlation_id
            )
            msg.timeout_ms = self._rel_state.timeout_ms
            msg.retry_count = 0
            
            self._rel_state.pending_request = msg
            self._rel_state.last_sent_time = now
            self._rel_state.retry_count = 0
            
            tick.add_event(AgentRole.MAIN, f"SEND_{action.value}", retry=0)
            
            # Send (Blocking for now, but logical flow supports async)
            response = target_agent.handle_message(msg)
            return self._handle_response_logic(response, tick)

        # 2. Existing Request (Retry/Timeout Check)
        else:
            elapsed = (now - self._rel_state.last_sent_time).total_seconds() * 1000
            
            if elapsed > self._rel_state.timeout_ms:
                if self._rel_state.retry_count < self._rel_state.max_retries:
                    # RETRY
                    self._rel_state.retry_count += 1
                    self._rel_state.last_sent_time = now
                    msg = self._rel_state.pending_request
                    msg.retry_count = self._rel_state.retry_count
                    msg.timestamp = now # Update timestamp for log
                    
                    tick.add_event(AgentRole.MAIN, f"RETRY_{action.value}", count=self._rel_state.retry_count)
                    logger.warning(f"Timeout waiting for {action.value}. Retrying ({self._rel_state.retry_count}/{self._rel_state.max_retries})...")
                    
                    response = target_agent.handle_message(msg)
                    return self._handle_response_logic(response, tick)
                else:
                    # FAIL
                    tick.add_event(AgentRole.MAIN, f"FAIL_{action.value}", reason="MAX_RETRIES")
                    logger.error(f"Max retries reached for {action.value}. Aborting.")
                    self._rel_state.reset()
                    return None # Or raise exception? For now return None to stall/reset
            
            # Not timed out yet, just waiting (if we were async)
            # Since we are sync, we shouldn't really reach here unless we returned ACK previously.
            return None

    def _handle_response_logic(self, response: MessageEnvelope, tick: TickEvent) -> Optional[MessageEnvelope]:
        """Handle validation of response types."""
        if not response:
            return None
            
        if response.action == ActionType.ACK:
            tick.add_event(response.from_agent, "ACK_RECEIVED")
            return None # Keep waiting for full result
            
        if response.action == ActionType.NACK:
            tick.add_event(response.from_agent, "NACK_RECEIVED", details=response.payload.get("details"))
            # Treat NACK as immediate failure to retry if retryable, else abort
            # For simplicity, we trigger retry logic on next tick or abort now
            # Here we just abort to keep it safe
            self._rel_state.reset()
            return None
            
        if response.action == ActionType.ERROR:
            tick.add_event(response.from_agent, "ERROR_RECEIVED", error=response.error)
            self._rel_state.reset()
            return response # Let caller handle error envelope
            
        # Success Result
        self._rel_state.reset()
        return response

    def _request_analysis_reliable(
        self,
        timeframe_bars: Dict[str, List[Dict[str, Any]]],
        economic_calendar: List[Any],
        tick: TickEvent
    ) -> Optional[MarketContext]:
        """Request market context analysis (Reliable)."""
        payload = {
            "symbol": self._state.symbol,
            "timestamp": self._state.current_time.isoformat(),
            "timeframe_bars": timeframe_bars,
            "economic_calendar": [e.model_dump() if hasattr(e, 'model_dump') else e for e in economic_calendar],
            "correlation_id": self._correlation_id # Explicit in payload too
        }
        
        response = self._send_reliable_message(
            self.strategy_agent, 
            ActionType.ANALYZE_CONTEXT, 
            payload,
            tick
        )
        
        if response and response.action == ActionType.CONTEXT_RESULT:
            context_data = response.payload.get("context")
            if context_data:
                context = MarketContext(**context_data)
                self._state.market_context = context
                tick.add_event(
                    AgentRole.STRATEGY,
                    "CONTEXT_ANALYZED",
                    bias=context.bias.direction.value,
                    env=context.environment.status.value
                )
                return context
        
        if response and response.action == ActionType.ERROR:
             tick.add_event(AgentRole.STRATEGY, "ANALYSIS_FAILED", error=response.error)
             
        return None

    def _request_setups_reliable(
        self,
        timeframe_bars: Dict[str, List[Dict[str, Any]]],
        tick: TickEvent
    ) -> Optional[List[TradeSetup]]:
        """Request setup scan (Reliable)."""
        payload = {
            "symbol": self._state.symbol,
            "timestamp": self._state.current_time.isoformat(),
            "timeframe_bars": timeframe_bars,
            "market_context": self._state.market_context.model_dump(),
            "enabled_models": ["ICT_2022", "FVG", "OTE", "SILVERBULLET"]
        }
        
        response = self._send_reliable_message(
            self.worker_agent,
            ActionType.SCAN_SETUPS,
            payload,
            tick
        )
        
        if response and response.action == ActionType.SETUP_RESULT:
            setups_data = response.payload.get("setups", [])
            setups = [TradeSetup(**s) for s in setups_data]
            if setups:
                tick.add_event(AgentRole.WORKER, "SETUPS_FOUND", count=len(setups))
            else:
                tick.add_event(AgentRole.WORKER, "NO_SETUPS")
            return setups
            
        if response and response.action == ActionType.ERROR:
            tick.add_event(AgentRole.WORKER, "SCAN_FAILED", error=response.error)
            return [] # Empty list on error to proceed with 0 setups
            
        return None

    def _execute_trade_reliable(self, tick: TickEvent) -> Optional[Dict[str, Any]]:
        """
        Execute approved trade via Worker Agent (Reliable).
        """
        setup = self._state.current_setup
        if not setup:
            return {"success": False, "error": "No setup to execute"}

        payload = {
            "symbol": self._state.symbol,
            "direction": setup.direction.value,
            "order_type": setup.entry_type.value,
            "entry_price": setup.entry_price,
            "stop_loss": setup.stop_loss,
            "take_profit": setup.take_profit,
            "setup_name": setup.model_name,
            "risk_pct": self.config.risk.default_risk_pct,
            "agent_analysis": {
                "rationale": setup.rationale,
                "confidence": setup.confidence,
                "confluence_score": setup.confluence_score,
                "confluence_factors": setup.confluence_factors,
                "rule_refs": setup.rule_refs,
                "model_type": setup.model_type
            }
        }
        
        response = self._send_reliable_message(
            self.worker_agent,
            ActionType.EXECUTE_ORDER,
            payload,
            tick
        )
        
        if response and response.action == ActionType.EXECUTION_RECEIPT:
            position_data = response.payload.get("position")
            if position_data:
                position = Position(**position_data)
                self._state.open_positions.append(position)
                tick.add_event(AgentRole.WORKER, "TRADE_EXECUTED", position_id=position.id)
                return {
                    "success": True,
                    "position_id": position.id,
                    "entry_price": position.entry_price,
                    "volume": position.volume
                }
        
        if response and response.action == ActionType.ERROR:
             error = response.error or "Execution failed"
             tick.add_event(AgentRole.WORKER, "EXECUTION_FAILED", error=error)
             return {"success": False, "error": error}

        return None

    def _select_best_setup(self, setups: List[TradeSetup]) -> Optional[TradeSetup]:
        """
        Select the best setup from multiple candidates.

        Priority: ICT_2022 > SILVERBULLET > FVG > OTE
        """
        if not setups:
            return None

        # Sort by model priority and confidence
        model_priority = {"ICT_2022": 4, "SILVERBULLET": 3, "FVG_ENTRY": 2, "OTE": 1}

        sorted_setups = sorted(
            setups,
            key=lambda s: (model_priority.get(s.model_name, 0), s.confidence, s.confluence_score),
            reverse=True
        )

        return sorted_setups[0]

    def _validate_setup(self, setup: TradeSetup, tick: TickEvent) -> bool:
        """
        Validate setup against risk policy.

        Checks:
        - R:R meets minimum
        - Session trade limit not exceeded
        - Confluence score meets minimum
        """
        # Check R:R
        if setup.risk_reward < self.config.risk.min_rr:
            tick.add_event(
                AgentRole.MAIN,
                "SETUP_REJECTED",
                reason=f"R:R {setup.risk_reward} < minimum {self.config.risk.min_rr}"
            )
            return False

        # Check session trade limit
        if not self._state.can_trade:
            tick.add_event(
                AgentRole.MAIN,
                "SETUP_REJECTED",
                reason=f"Session trade limit reached ({self._state.max_trades_per_session})"
            )
            return False

        # Check confluence score
        min_confluence = self.config.confluence_weights.min_score_for_trade
        if setup.confluence_score < min_confluence:
            tick.add_event(
                AgentRole.MAIN,
                "SETUP_REJECTED",
                reason=f"Confluence {setup.confluence_score} < minimum {min_confluence}"
            )
            return False

        tick.add_event(AgentRole.MAIN, "SETUP_APPROVED", model=setup.model_name)
        return True

    # =========================================================================
    # Clock Control
    # =========================================================================

    def advance_time(self, bars: int = 1) -> Dict[str, Any]:
        """
        Advance simulation time by N bars (backtest only).

        Called by Main Agent's clock control.
        """
        if self._clock is None:
            return {"success": False, "error": "Clock not available (live mode?)"}

        new_time = self._clock.advance(bars)
        self._state.current_time = new_time

        # Also advance via Worker Agent to sync with backend
        request_msg = create_request(
            from_agent=AgentRole.MAIN,
            to_agent=AgentRole.WORKER,
            action=ActionType.ADVANCE_TIME,
            payload={"bars": bars},
            correlation_id=self._correlation_id
        )

        response_msg = self.worker_agent.handle_message(request_msg)

        return {
            "success": True,
            "new_time": new_time.isoformat(),
            "progress": self._clock.progress,
            "is_complete": self._clock.is_complete(),
            "tick_count": self._clock.tick_count
        }

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def reload_rules(self) -> tuple[bool, str]:
        """
        Hot-reload rules configuration.
        """
        success, message = reload_rules()

        if success:
            self.config = get_rules()
            self.strategy_agent.config = self.config
            self.worker_agent.config = self.config

            # Update session state with new limits
            if self._state:
                self._state.max_trades_per_session = self.config.invalidation.max_trades_per_session

        return success, message

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """
        Get full message audit trail for replay.
        """
        return self.message_log.to_dict_list()

    def get_tick_history(self) -> List[Dict[str, Any]]:
        """
        Get tick history for visualization.
        """
        return self.tick_log.to_dict_list()

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get session summary statistics.
        """
        if self._state is None:
            return {}

        return {
            "session_id": self._state.session_id,
            "symbol": self._state.symbol,
            "mode": self._state.mode,
            "phase": self._state.phase.value,
            "balance": self._state.balance,
            "equity": self._state.equity,
            "total_pnl": self._state.total_pnl,
            "win_count": self._state.win_count,
            "loss_count": self._state.loss_count,
            "win_rate": self._state.win_rate,
            "trades_this_session": self._state.trades_this_session,
            "open_positions": len(self._state.open_positions),
            "closed_trades": len(self._state.closed_trades)
        }
