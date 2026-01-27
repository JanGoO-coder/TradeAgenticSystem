"""
Agent Engine - Wrapper for the Hierarchical ICT Trading Agent.

This module provides a clean interface to the new hierarchical agent architecture:
- MainAgent: Orchestrator with state machine
- StrategyAgent: Market context analysis
- WorkerAgent: Pattern detection and execution

Now integrates with unified DataProvider and PositionExecutor for consistent
live/backtest behavior. Supports hot-reload of rules configuration.
"""
import sys
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Add the source path to import the agent modules
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
AGENT_DIR = PROJECT_ROOT / "agent"
AGENT_SRC_DIR = AGENT_DIR / "src"

# Insert paths if not already present
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
if str(AGENT_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_SRC_DIR))


logger = logging.getLogger(__name__)

# Lazy imports for trading context
TradingContext = None
DataProvider = None
PositionExecutor = None


def _lazy_import_context():
    """Lazy import trading context to avoid circular imports."""
    global TradingContext, DataProvider, PositionExecutor
    if TradingContext is None:
        from app.core.trading_context import TradingContext as TC
        from app.core.data_provider import DataProvider as DP
        from app.core.position_executor import PositionExecutor as PE
        TradingContext = TC
        DataProvider = DP
        PositionExecutor = PE


class TradingAgentEngine:
    """
    Wrapper for the Hierarchical ICT Trading Agent.

    Provides backward-compatible interface while using the new
    Main/Strategy/Worker agent architecture internally.

    Now supports unified DataProvider/PositionExecutor injection
    for consistent live and backtest execution.
    """

    def __init__(self):
        """Initialize the agent engine."""
        self._agent_available = False
        self._main_agent = None
        self._last_error: Optional[str] = None
        self._use_new_architecture = False

        # Trading context (unified data/execution providers)
        self._trading_context = None
        self._session_id: Optional[str] = None

        # Session state tracking
        self._session_state: Optional[Dict[str, Any]] = None
        self._message_log: List[Dict[str, Any]] = []
        self._tick_log: List[Dict[str, Any]] = []
        
        # Autonomous execution flag
        self._auto_execute_enabled: bool = True
        
        # Persistence Manager
        from app.services.persistence import PersistenceManager
        self._persistence = PersistenceManager()

        self._initialize_agent()

    def _initialize_agent(self):
        """Attempt to load the hierarchical agent system."""
        try:
            # First try the new hierarchical architecture
            from src import MainAgent, load_rules, get_rules
            from src.rules_config import get_rules_manager

            # Load rules configuration
            rules_path = PROJECT_ROOT / "rules" / "config.yaml"
            if rules_path.exists():
                load_rules(str(rules_path))
                logger.info(f"Rules loaded from {rules_path}")
            else:
                logger.warning(f"Rules config not found at {rules_path}, using defaults")

            # Create execution handlers
            def execution_handler(direction, entry_price, stop_loss, take_profit, setup_name, risk_reward=None, agent_analysis=None):
                if not self._trading_context:
                    return {"success": False, "error": "No trading context"}
                
                # Use open_trade from engine which routes to position_executor with correct context
                return self.open_trade(
                    direction=direction,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    setup_name=setup_name,
                    risk_reward=risk_reward,
                    agent_analysis=agent_analysis
                )

            # Create main agent
            self._main_agent = MainAgent(execution_handler=execution_handler)
            self._agent_available = True
            self._use_new_architecture = True

            logger.info("Hierarchical agent architecture initialized")

        except Exception as e:
            logger.error(f"Agent initialization error: {e}")
            self._last_error = f"Agent initialization error: {e}"
            self._agent_available = False

    @property
    def is_available(self) -> bool:
        """Check if agent is available."""
        return self._agent_available

    @property
    def last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error

    @property
    def main_agent(self):
        """Get the MainAgent instance."""
        return self._main_agent

    @property
    def trading_context(self):
        """Get the current trading context."""
        return self._trading_context

    def set_trading_context(self, context):
        """
        Set the trading context (DataProvider + PositionExecutor).

        Args:
            context: TradingContext instance
        """
        _lazy_import_context()
        self._trading_context = context
        logger.info(f"Trading context set: mode={context.mode}, symbol={context.symbol}")

    def analyze(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run trade analysis on a market snapshot.

        Args:
            snapshot: Market snapshot matching the input contract

        Returns:
            Trade Setup Response

        Raises:
            RuntimeError: If agent is not available
        """
        if not self._agent_available:
            raise RuntimeError(f"Agent not available: {self._last_error}")

        try:
            # Optimize: Use active main agent if context matches
            if self._main_agent and self._trading_context:
                symbol = snapshot.get("symbol")
                if symbol == self._trading_context.symbol:
                    # Use current state directly
                    state = self._main_agent._state
                    return build_backward_compatible_response(
                        state=state,
                        tick_result={},  # No new tick execution
                        snapshot_data=snapshot
                    )

            return self._analyze_with_main_agent(snapshot)
        except Exception as e:
            logger.exception(f"Agent analysis failed: {e}")
            raise RuntimeError(f"Agent analysis failed: {e}")

    def _analyze_with_main_agent(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Run analysis using the new hierarchical architecture."""
        try:
            from src import MainAgent
            from datetime import datetime
            
            # Create a temporary agent for stateless analysis
            temp_agent = MainAgent()
            
            # Initialize a temporary session
            symbol = snapshot.get("symbol", "Unknown")
            # Parse timestamp if string
            ts = snapshot.get("timestamp")
            if isinstance(ts, str):
                try:
                    start_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    start_time = datetime.utcnow()
            else:
                start_time = ts or datetime.utcnow()

            temp_agent.initialize_session(
                symbol=symbol,
                mode="BACKTEST", # logical mode for analysis
                start_time=start_time
            )
            
            # Run tick
            return temp_agent.run_tick(
                timeframe_bars=snapshot.get("timeframe_bars", {}),
                economic_calendar=snapshot.get("economic_calendar", [])
            )
        except Exception as e:
            logger.exception(f"Analysis failed: {e}")
            raise RuntimeError(f"Analysis failed: {e}")

    def reload_rules(self) -> Dict[str, Any]:
        """
        Hot-reload rules configuration.

        Returns:
            Dict with success status and message
        """
        # Always use new architecture logic
        # if not self._use_new_architecture:
        #    return {
        #        "success": False,
        #        "message": "Hot-reload not available in legacy mode"
        #    }

        try:
            from src import reload_rules, get_rules

            success, message = reload_rules()

            if success:
                # Update main agent's config reference
                self._main_agent.config = get_rules()
                self._main_agent.strategy_agent.config = get_rules()
                self._main_agent.worker_agent.config = get_rules()

            return {
                "success": success,
                "message": message,
                "config_version": get_rules().version if success else None
            }
        except Exception as e:
            logger.exception(f"Rules reload failed: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    def get_rules_config(self) -> Dict[str, Any]:
        """
        Get current rules configuration.

        Returns:
            Current rules as dict
        """
        try:
            from src import get_rules
            config = get_rules()
            return config.model_dump()
        except Exception as e:
            logger.error(f"Failed to get rules: {e}")
            return {"error": str(e)}

    def initialize_session(
        self,
        symbol: str,
        mode: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        starting_balance: float = 10000.0,
        timeframes: List[str] = None,
        auto_execute_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Initialize a new trading session with unified context.

        Args:
            symbol: Trading symbol
            mode: "LIVE" or "BACKTEST"
            start_time: Session start time
            end_time: Session end time (required for BACKTEST)
            starting_balance: Initial balance
            timeframes: Timeframes to load (BACKTEST only)
            auto_execute_enabled: Enable automatic trade execution when setups pass validation

        Returns:
            Session state dict
        """
        _lazy_import_context()

        try:
            # Zombie Session Prevention: Clean up existing session before creating new one
            if self._session_id or self._trading_context:
                logger.info(f"Cleaning up previous session {self._session_id} before new initialization")
                self._trading_context = None
                self._main_agent = None # Reset main agent wrapper if we want full hard reset, but usually we just reset state
                # Re-initializing main agent happens later based on config
            
            # Generate session ID
            self._session_id = str(uuid.uuid4())[:8]

            # Create trading context via factory
            from app.core.trading_context import create_trading_context

            self._trading_context = create_trading_context(
                mode=mode,
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                timeframes=timeframes or ["1H", "15M", "5M"],
                starting_balance=starting_balance,
                session_id=self._session_id,
            )

            # Reset logs
            self._message_log = []
            self._tick_log = []
            
            # Store auto-execute flag
            self._auto_execute_enabled = auto_execute_enabled

            # Initialize session state
            self._session_state = {
                "session_id": self._session_id,
                "symbol": symbol,
                "mode": mode,
                "current_time": start_time.isoformat() + "Z" if start_time else datetime.utcnow().isoformat() + "Z",
                "simulation_speed": 1.0,
                "phase": "IDLE",
                "market_context": None,
                "current_setup": None,
                "pending_setups": [],
                "open_positions": [],
                "closed_trades": [],
                "starting_balance": starting_balance,
                "balance": starting_balance,
                "equity": starting_balance,
                "total_pnl": 0.0,
                "win_count": 0,
                "loss_count": 0,
                "trades_this_session": 0,
                "max_trades_per_session": 2,
                "can_trade": True,
                "win_rate": 0.0,
            }

            # If using main agent, also initialize there
            if self._main_agent:
                try:
                    agent_state = self._main_agent.initialize_session(
                        symbol=symbol,
                        mode=mode,
                        start_time=start_time,
                        end_time=end_time
                    )
                    # Merge agent state with our state
                    if hasattr(agent_state, 'model_dump'):
                        agent_dict = agent_state.model_dump(mode='json')
                        self._session_state.update(agent_dict)
                except Exception as e:
                    logger.warning(f"MainAgent session init failed: {e}")

            # Check for existing persisted state (Resume Session)
            persisted_state = self._persistence.load_session(self._session_id)
            if persisted_state:
                logger.info(f"Resuming session {self._session_id} from persistence")
                if self._main_agent:
                    self._main_agent.import_state(persisted_state)
            
            # Log session initialization
            self._log_message("ENGINE", "SESSION", "INITIALIZE", {
                "symbol": symbol,
                "mode": mode,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
            })

            logger.info(f"Session {self._session_id} initialized: {mode} {symbol}")

            return self._session_state

        except Exception as e:
            logger.exception(f"Session initialization failed: {e}")
            return {"error": str(e)}

    def get_session_state(self) -> Dict[str, Any]:
        """Get current session state with live position data."""
        if not self._session_state:
            return {}

        # Update positions from executor
        if self._trading_context:
            positions = self._trading_context.position_executor.get_positions()
            self._session_state["open_positions"] = [p.to_hierarchical() for p in positions]

            closed = self._trading_context.position_executor.get_closed_trades()
            self._session_state["closed_trades"] = closed

            account = self._trading_context.position_executor.get_account_info()
            self._session_state["balance"] = account.balance
            self._session_state["equity"] = account.equity

            stats = self._trading_context.position_executor.get_statistics()
            self._session_state["win_count"] = stats.get("winners", 0)
            self._session_state["loss_count"] = stats.get("losers", 0)
            self._session_state["total_pnl"] = stats.get("total_pnl_usd", 0.0)

            total = self._session_state["win_count"] + self._session_state["loss_count"]
            self._session_state["win_rate"] = (
                self._session_state["win_count"] / total * 100 if total > 0 else 0.0
            )
            self._session_state["trades_this_session"] = total

            # Get backtest progress from data provider (BACKTEST mode only)
            if self._trading_context.mode.value == "BACKTEST":
                try:
                    status = self._trading_context.data_provider.get_status()
                    self._session_state["current_bar_index"] = status.current_index
                    self._session_state["total_bars"] = status.total_bars
                    self._session_state["progress"] = status.progress
                    if status.current_time:
                        self._session_state["current_time"] = status.current_time.isoformat() + "Z"
                except Exception as e:
                    logger.debug(f"Could not get data provider status: {e}")

        # Try to get from main agent too
        if self._main_agent and self._main_agent.state:
            try:
                agent_state = self._main_agent.state.model_dump(mode='json')
                # Merge market context if available
                if agent_state.get("market_context"):
                    self._session_state["market_context"] = agent_state["market_context"]
                if agent_state.get("current_setup"):
                    self._session_state["current_setup"] = agent_state["current_setup"]
                if agent_state.get("phase"):
                    self._session_state["phase"] = agent_state["phase"]
            except Exception as e:
                logger.debug(f"Could not get agent state: {e}")

        return self._session_state

    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary statistics."""
        if self._trading_context:
            return self._trading_context.position_executor.get_statistics()
        if self._main_agent:
            return self._main_agent.get_session_summary()
        return {}

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get message audit trail for Glass Box replay."""
        return self._message_log.copy()

    def get_tick_history(self) -> List[Dict[str, Any]]:
        """Get tick history for visualization."""
        return self._tick_log.copy()

    def _log_message(
        self,
        from_agent: str,
        to_agent: str,
        action: str,
        payload: Dict[str, Any],
    ):
        """Log a message to the audit trail."""
        msg_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat() + "Z"

        self._message_log.append({
            "id": msg_id,
            "timestamp": timestamp,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "action": action,
            "payload": payload,
            "correlation_id": self._session_id or "",
        })

        # Also track tick events
        tick_count = len(self._tick_log)
        self._tick_log.append({
            "tick": tick_count + 1,
            "time": timestamp,
            "events": [{"agent": from_agent, "action": action}],
        })

    def advance_time(self, bars: int = 1) -> Dict[str, Any]:
        """
        Advance simulation time with tick-level TP/SL checking.

        Uses tick data when available for accurate intra-bar detection,
        falls back to bar OHLC when tick data unavailable.

        Args:
            bars: Number of bars to advance

        Returns:
            Advance result with closed trades and new state
        """
        if not self._trading_context:
            return {"error": "No trading context - initialize session first"}

        if self._trading_context.mode.value != "BACKTEST":
            return {"error": "advance_time() only available in BACKTEST mode"}

        data_provider = self._trading_context.data_provider
        position_executor = self._trading_context.position_executor
        symbol = self._trading_context.symbol

        all_closed_trades = []

        try:
            for _ in range(bars):
                # Step data provider forward
                step_result = data_provider.step_forward(1)

                if step_result.get("error"):
                    return step_result

                # Get current bar info
                status = data_provider.get_status()
                current_time = status.current_time
                bar_index = status.current_index

                # Get latest bar for TP/SL checking
                latest_bars = data_provider.get_bars(symbol, "5M", 1)
                if not latest_bars:
                    continue

                bar = latest_bars[-1]
                timestamp = bar.timestamp

                # Try to load tick data for this bar
                try:
                    bar_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    from app.core.data_provider import TIMEFRAME_MINUTES
                    bar_end = bar_time + __import__('datetime').timedelta(minutes=5)

                    ticks = data_provider.load_ticks_for_bar(bar_time, bar_end)

                    if ticks:
                        # Tick-level TP/SL checking (more accurate)
                        for tick in ticks:
                            closed = position_executor.check_tp_sl_on_tick(
                                symbol=symbol,
                                bid=tick.bid,
                                ask=tick.ask,
                                tick_time=tick.time,
                                bar_index=bar_index,
                            )
                            all_closed_trades.extend([c.to_dict() for c in closed])
                    else:
                        # Bar-level fallback
                        closed = position_executor.check_tp_sl_on_bar(
                            symbol=symbol,
                            high=bar.high,
                            low=bar.low,
                            bar_index=bar_index,
                            timestamp=timestamp,
                        )
                        all_closed_trades.extend([c.to_dict() for c in closed])

                except Exception as e:
                    logger.debug(f"Tick loading failed, using bar: {e}")
                    closed = position_executor.check_tp_sl_on_bar(
                        symbol=symbol,
                        high=bar.high,
                        low=bar.low,
                        bar_index=bar_index,
                        timestamp=timestamp,
                    )
                    all_closed_trades.extend([c.to_dict() for c in closed])

                # Update unrealized P&L
                bid, ask = data_provider.get_current_price(symbol)
                position_executor.update_unrealized_pnl({symbol: (bid, ask)})

                # Update session state time
                if self._session_state:
                    self._session_state["current_time"] = timestamp

                # Log advance
                self._log_message("ENGINE", "DATA", "ADVANCE_TIME", {
                    "bars": 1,
                    "bar_index": bar_index,
                    "timestamp": timestamp,
                })

                # =========================================================
                # TRIGGER AGENT LOGIC
                # =========================================================
                if self._use_new_architecture and self._main_agent:
                    try:
                        # Get multi-timeframe data for agent analysis
                        tf_bars = data_provider.get_multi_timeframe_bars(
                            symbol,
                            {"1H": 100, "15M": 100, "5M": 100}
                        )
                        
                        # Convert to dict format expected by agent
                        tf_data = {
                            tf: [b.to_dict() for b in bars] 
                            for tf, bars in tf_bars.items()
                        }
                        
                        # Run agent tick
                        agent_result = self._main_agent.run_tick(
                            timeframe_bars=tf_data,
                            economic_calendar=[]
                        )
                        
                        # Check for trade execution
                        if agent_result and agent_result.get("trade_executed"):
                            trade_info = agent_result["trade_executed"]
                            if trade_info.get("success"):
                                # Trade was executed by agent, refresh positions from executor
                                pass
                            
                    except Exception as e:
                        # Soft Handling: Log error but allow advancement to continue
                        # unless it's a critical system failure
                        logger.error(f"Agent execution failed at index {bar_index}: {e}")
                        self._log_message("ENGINE", "AGENT", "ERROR", {"error": str(e)})
                        # We do NOT raise here to prevent 500 in auto-advance, 
                        # but we capture it for the response if needed.

            # Get final agent phase for status mapping
            agent_phase = "IDLE"
            if self._main_agent and hasattr(self._main_agent, 'state') and self._main_agent.state:
                agent_phase = self._main_agent.state.phase
            
            # Persist state after tick
            if self._main_agent and self._session_id:
                state_data = self._main_agent.export_state()
                self._persistence.save_session(self._session_id, state_data)

            # Return result
            return {
                "success": True,
                "agent_phase": str(agent_phase),
                "bars_advanced": bars,
                "current_index": status.current_index,
                "total_bars": status.total_bars,
                "progress": status.progress,
                "current_time": status.current_time.isoformat() if status.current_time else None,
                "closed_trades": all_closed_trades,
                "positions": [p.to_dict() for p in position_executor.get_positions()],
            }

        except Exception as e:
            logger.exception(f"advance_time failed: {e}")
            return {"error": str(e)}

    def step_back(self, bars: int = 1) -> Dict[str, Any]:
        """
        Move simulation backward (BACKTEST mode only).
        """
        if not self._trading_context:
            return {"error": "No trading context"}
        if self._trading_context.mode.value != "BACKTEST":
            return {"error": "Only available in BACKTEST mode"}

        try:
            return self._trading_context.data_provider.step_backward(bars)
        except Exception as e:
            return {"error": str(e)}

    def jump_to(self, index: int) -> Dict[str, Any]:
        """
        Jump to specific bar index (BACKTEST mode only).
        """
        if not self._trading_context:
            return {"error": "No trading context"}
        if self._trading_context.mode.value != "BACKTEST":
            return {"error": "Only available in BACKTEST mode"}

        try:
            return self._trading_context.data_provider.jump_to(index)
        except Exception as e:
            return {"error": str(e)}

    def reset_simulation(self) -> Dict[str, Any]:
        """
        Reset simulation to start (BACKTEST mode only).
        """
        if not self._trading_context:
            return {"error": "No trading context"}
        if self._trading_context.mode.value != "BACKTEST":
            return {"error": "Only available in BACKTEST mode"}

        try:
            result = self._trading_context.data_provider.reset()
            # Also reset positions
            self._trading_context.position_executor.close_all_positions(reason="RESET")
            return result
        except Exception as e:
            return {"error": str(e)}

    def auto_advance(
        self,
        max_bars: int = 100,
        stop_on_trade: bool = True,
        stop_on_setup: bool = False,
    ) -> Dict[str, Any]:
        """
        Auto-advance simulation until a trade is executed, setup found, or max bars reached.

        This enables autonomous trading by continuously advancing and letting
        the agent execute trades when valid setups are found.

        Args:
            max_bars: Maximum number of bars to advance
            stop_on_trade: Stop when a trade is executed
            stop_on_setup: Stop when a setup is found (even if not executed)

        Returns:
            Dict with bars_advanced, stopped_reason, trades_executed, etc.
        """
        if not self._trading_context:
            return {"error": "No trading context - initialize session first"}
        if self._trading_context.mode.value != "BACKTEST":
            return {"error": "auto_advance() only available in BACKTEST mode"}
        if not self._auto_execute_enabled:
            return {"error": "auto_execute is not enabled for this session"}

        data_provider = self._trading_context.data_provider
        position_executor = self._trading_context.position_executor
        symbol = self._trading_context.symbol

        bars_advanced = 0
        stopped_reason = "MAX_BARS"
        trades_executed = []
        setups_found = []
        all_closed_trades = []

        try:
            for i in range(max_bars):
                # Check if we've reached the end
                status = data_provider.get_status()
                if status.progress >= 1.0:
                    stopped_reason = "SESSION_END"
                    break

                # Step forward one bar
                step_result = data_provider.step_forward(1)
                if step_result.get("error"):
                    stopped_reason = "ERROR"
                    return {
                        "error": step_result["error"],
                        "bars_advanced": bars_advanced,
                        "stopped_reason": stopped_reason,
                    }

                bars_advanced += 1
                status = data_provider.get_status()
                bar_index = status.current_index

                # Get latest bar for TP/SL checking
                latest_bars = data_provider.get_bars(symbol, "5M", 1)
                if not latest_bars:
                    continue

                bar = latest_bars[-1]
                timestamp = bar.timestamp

                # Check TP/SL on current bar
                closed = position_executor.check_tp_sl_on_bar(
                    symbol=symbol,
                    high=bar.high,
                    low=bar.low,
                    bar_index=bar_index,
                    timestamp=timestamp,
                )
                for c in closed:
                    all_closed_trades.append(c.to_dict())

                # Update session time
                if self._session_state:
                    self._session_state["current_time"] = timestamp

                # =========================================================
                # RUN AGENT LOGIC
                # =========================================================
                if self._use_new_architecture and self._main_agent:
                    try:
                        # Get multi-timeframe data
                        tf_bars = data_provider.get_multi_timeframe_bars(
                            symbol,
                            {"1H": 100, "15M": 100, "5M": 100}
                        )
                        tf_data = {
                            tf: [b.to_dict() for b in bars_list]
                            for tf, bars_list in tf_bars.items()
                        }

                        # Run agent tick
                        agent_result = self._main_agent.run_tick(
                            timeframe_bars=tf_data,
                            economic_calendar=[]
                        )

                        # Track setups found
                        if agent_result.get("setup"):
                            setups_found.append(agent_result["setup"])
                            if stop_on_setup:
                                stopped_reason = "SETUP_FOUND"
                                break

                        # Track trades executed
                        if agent_result.get("trade_executed"):
                            trade_info = agent_result["trade_executed"]
                            if trade_info.get("success"):
                                trades_executed.append(trade_info)
                                self._log_message("ENGINE", "AGENT", "TRADE_EXECUTED", trade_info)

                                if stop_on_trade:
                                    stopped_reason = "TRADE_EXECUTED"
                                    break

                    except Exception as e:
                        logger.error(f"Agent execution failed at bar {bar_index}: {e}")
                        self._log_message("ENGINE", "AGENT", "ERROR", {"error": str(e)})

                # Update unrealized P&L
                try:
                    bid, ask = data_provider.get_current_price(symbol)
                    position_executor.update_unrealized_pnl({symbol: (bid, ask)})
                except Exception:
                    pass

            # Final status
            final_status = data_provider.get_status()

            return {
                "success": True,
                "bars_advanced": bars_advanced,
                "stopped_reason": stopped_reason,
                "trades_executed": trades_executed,
                "setups_found": setups_found,
                "closed_trades": all_closed_trades,
                "current_time": final_status.current_time.isoformat() if final_status.current_time else None,
                "progress": final_status.progress,
                "current_index": final_status.current_index,
                "total_bars": final_status.total_bars,
                "final_state": self.get_session_state(),
            }

        except Exception as e:
            logger.exception(f"auto_advance failed: {e}")
            return {
                "error": str(e),
                "bars_advanced": bars_advanced,
                "stopped_reason": "ERROR",
            }

    def run_continuous(
        self,
        continue_after_trade: bool = True,
        max_consecutive_errors: int = 10,
    ) -> Dict[str, Any]:
        """
        Run continuous autonomous scanning until session end.

        This is the fully autonomous mode that:
        - Scans every bar for setups
        - Executes trades when valid setups are found
        - Continues scanning after trades (does not stop)
        - Tracks all trades executed and TP/SL hits
        - Runs until the end of the backtest session

        Args:
            continue_after_trade: If True, keeps scanning after trades (default: True)
            max_consecutive_errors: Stop after N consecutive errors

        Returns:
            Dict with complete session results including all trades executed
        """
        if not self._trading_context:
            return {"error": "No trading context - initialize session first"}
        if self._trading_context.mode.value != "BACKTEST":
            return {"error": "run_continuous() only available in BACKTEST mode"}
        if not self._auto_execute_enabled:
            return {"error": "auto_execute is not enabled for this session"}

        data_provider = self._trading_context.data_provider
        position_executor = self._trading_context.position_executor
        symbol = self._trading_context.symbol

        # Track cumulative stats
        total_bars_advanced = 0
        all_trades_executed = []
        all_setups_found = []
        all_closed_trades = []
        consecutive_errors = 0

        logger.info(f"🚀 Starting continuous autonomous scanning for {symbol}")

        try:
            while True:
                # Check if we've reached the end
                status = data_provider.get_status()
                if status.progress >= 1.0:
                    logger.info(f"✅ Session complete - {total_bars_advanced} bars scanned")
                    break

                # Step forward one bar
                step_result = data_provider.step_forward(1)
                if step_result.get("error"):
                    consecutive_errors += 1
                    logger.warning(f"Step error: {step_result['error']}")
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Max consecutive errors reached ({max_consecutive_errors})")
                        break
                    continue

                consecutive_errors = 0  # Reset on success
                total_bars_advanced += 1
                status = data_provider.get_status()
                bar_index = status.current_index

                # Get latest bar for TP/SL checking
                latest_bars = data_provider.get_bars(symbol, "5M", 1)
                if not latest_bars:
                    continue

                bar = latest_bars[-1]
                timestamp = bar.timestamp

                # Check TP/SL on current bar
                closed = position_executor.check_tp_sl_on_bar(
                    symbol=symbol,
                    high=bar.high,
                    low=bar.low,
                    bar_index=bar_index,
                    timestamp=timestamp,
                )
                for c in closed:
                    closed_dict = c.to_dict()
                    all_closed_trades.append(closed_dict)
                    result = "WIN" if closed_dict.get("pnl_pips", 0) > 0 else "LOSS"
                    logger.info(f"📊 Position closed: {result} | {closed_dict.get('pnl_pips', 0):.1f} pips")

                # Update session time
                if self._session_state:
                    self._session_state["current_time"] = timestamp

                # =========================================================
                # RUN AGENT LOGIC
                # =========================================================
                if self._use_new_architecture and self._main_agent:
                    try:
                        # Get multi-timeframe data
                        tf_bars = data_provider.get_multi_timeframe_bars(
                            symbol,
                            {"1H": 100, "15M": 100, "5M": 100}
                        )
                        tf_data = {
                            tf: [b.to_dict() for b in bars_list]
                            for tf, bars_list in tf_bars.items()
                        }

                        # Run agent tick
                        agent_result = self._main_agent.run_tick(
                            timeframe_bars=tf_data,
                            economic_calendar=[]
                        )

                        # Track setups found
                        if agent_result.get("setup"):
                            setup = agent_result["setup"]
                            all_setups_found.append(setup)
                            logger.info(f"🔍 Setup found: {setup.get('model_name', 'Unknown')}")

                        # Track trades executed
                        if agent_result.get("trade_executed"):
                            trade_info = agent_result["trade_executed"]
                            if trade_info.get("success"):
                                all_trades_executed.append(trade_info)
                                self._log_message("ENGINE", "AGENT", "TRADE_EXECUTED", trade_info)
                                logger.info(
                                    f"🎯 TRADE EXECUTED: "
                                    f"{agent_result.get('setup', {}).get('model_name', 'Unknown')} | "
                                    f"Entry: {trade_info.get('entry_price')}"
                                )
                                # Continue scanning if continue_after_trade is True

                    except Exception as e:
                        logger.error(f"Agent execution failed at bar {bar_index}: {e}")
                        self._log_message("ENGINE", "AGENT", "ERROR", {"error": str(e)})

                # Update unrealized P&L
                try:
                    bid, ask = data_provider.get_current_price(symbol)
                    position_executor.update_unrealized_pnl({symbol: (bid, ask)})
                except Exception:
                    pass

                # Log progress periodically
                if total_bars_advanced % 100 == 0:
                    logger.info(
                        f"📈 Progress: {status.progress * 100:.1f}% | "
                        f"Bars: {total_bars_advanced} | "
                        f"Trades: {len(all_trades_executed)} | "
                        f"Closed: {len(all_closed_trades)}"
                    )

            # Final status
            final_status = data_provider.get_status()
            final_stats = position_executor.get_statistics()

            logger.info(
                f"\n{'='*60}\n"
                f"🏁 CONTINUOUS SCAN COMPLETE\n"
                f"{'='*60}\n"
                f"Total Bars: {total_bars_advanced}\n"
                f"Trades Executed: {len(all_trades_executed)}\n"
                f"Setups Found: {len(all_setups_found)}\n"
                f"Positions Closed: {len(all_closed_trades)}\n"
                f"Win Rate: {final_stats.get('win_rate', 0):.1f}%\n"
                f"Total P&L: {final_stats.get('total_pnl_pips', 0):.1f} pips\n"
                f"{'='*60}"
            )

            return {
                "success": True,
                "bars_advanced": total_bars_advanced,
                "stopped_reason": "SESSION_END",
                "trades_executed": all_trades_executed,
                "setups_found": all_setups_found,
                "closed_trades": all_closed_trades,
                "current_time": final_status.current_time.isoformat() if final_status.current_time else None,
                "progress": final_status.progress,
                "current_index": final_status.current_index,
                "total_bars": final_status.total_bars,
                "statistics": final_stats,
                "final_state": self.get_session_state(),
            }

        except Exception as e:
            logger.exception(f"run_continuous failed: {e}")
            return {
                "error": str(e),
                "bars_advanced": total_bars_advanced,
                "trades_executed": all_trades_executed,
                "closed_trades": all_closed_trades,
                "stopped_reason": "ERROR",
            }

    def get_market_snapshot(self) -> Dict[str, Any]:
        """
        Get current market snapshot for charting.
        """
        if not self._trading_context:
            return {"error": "No trading context"}
            
        try:
            provider = self._trading_context.data_provider
            symbol = self._trading_context.symbol
            
            # Use raw bars from provider
            bars_1h = provider.get_bars(symbol, "1H", 100)
            bars_15m = provider.get_bars(symbol, "15M", 100)
            bars_5m = provider.get_bars(symbol, "5M", 100)
            
            status = provider.get_status()
            
            return {
                "symbol": symbol,
                "timestamp": status.current_time.isoformat() + "Z" if status.current_time else None,
                "current_index": getattr(status, 'current_index', 0),
                "total_bars": getattr(status, 'total_bars', 0),
                "progress": getattr(status, 'progress', 0.0),
                "timeframe_bars": {
                    "1H": [b.to_dict() for b in bars_1h],
                    "15M": [b.to_dict() for b in bars_15m],
                    "5M": [b.to_dict() for b in bars_5m],
                }
            }
        except Exception as e:
            logger.exception(f"Snapshot failed: {e}")
            return {"error": str(e)}

    def open_trade(
        self,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        volume: Optional[float] = None,
        risk_pct: float = 1.0,
        setup_name: str = "",
        risk_reward: Optional[float] = None,
        agent_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Open a new trade through the unified executor.
        """
        if not self._trading_context:
            return {"error": "No active session"}

        # Determine direction
        try:
            from app.core.position_executor import TradeDirection, OpenPositionRequest
            dir_enum = TradeDirection.LONG if direction.upper() == "LONG" else TradeDirection.SHORT
        except ValueError:
            return {"error": f"Invalid direction: {direction}"}

        # Create request
        request = OpenPositionRequest(
            symbol=self._trading_context.symbol,
            direction=dir_enum,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            risk_pct=risk_pct,
            setup_name=setup_name,
            agent_analysis=agent_analysis
        )

        # Add backtest-specific info
        if self._trading_context.mode.value == "BACKTEST":
            status = self._trading_context.data_provider.get_status()
            request.bar_index = status.current_index
            request.timestamp = status.current_time.isoformat() + "Z" if status.current_time else None

        result = self._trading_context.position_executor.open_position(request)

        # Log the trade
        self._log_message("ENGINE", "EXECUTOR", "OPEN_TRADE", {
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "result": result.to_dict(),
        })

        return result.to_dict()

    def close_trade(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        reason: str = "MANUAL",
    ) -> Dict[str, Any]:
        """
        Close a trade through the unified executor.

        Args:
            position_id: Position ID to close
            exit_price: Exit price (optional - uses current if None)
            reason: Close reason

        Returns:
            Close result dict
        """
        if not self._trading_context:
            return {"error": "No trading context - initialize session first"}

        from app.core.position_executor import CloseReason

        try:
            close_reason = CloseReason(reason)
        except ValueError:
            close_reason = CloseReason.MANUAL

        result = self._trading_context.position_executor.close_position(
            position_id=position_id,
            exit_price=exit_price,
            reason=close_reason,
        )

        # Log the close
        self._log_message("ENGINE", "EXECUTOR", "CLOSE_TRADE", {
            "position_id": position_id,
            "exit_price": exit_price,
            "reason": reason,
            "result": result.to_dict(),
        })

        return result.to_dict()

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        if not self._trading_context:
            return []

        positions = self._trading_context.position_executor.get_positions()
        return [p.to_dict() for p in positions]

    def get_closed_trades(self) -> List[Dict[str, Any]]:
        """Get all closed trades."""
        if not self._trading_context:
            return []

        return self._trading_context.position_executor.get_closed_trades()

    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics."""
        if not self._trading_context:
            return {}

        return self._trading_context.position_executor.get_statistics()

    def get_current_session(self, timestamp: datetime = None) -> Dict[str, Any]:
        """
        Get current session information.

        Args:
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Session information dict
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        try:
            from src.strategy_agent.tools import check_killzone, detect_session

            kz_result = check_killzone(timestamp)
            session = detect_session(timestamp)

            # Calculate EST time (UTC - 5)
            est_hour = (timestamp.hour - 5) % 24
            est_minute = timestamp.minute

            return {
                "session": session.value,
                "kill_zone_active": kz_result["active"],
                "kill_zone_name": kz_result.get("name"),
                "current_time_utc": timestamp.isoformat() + "Z",
                "current_time_est": f"{est_hour:02d}:{est_minute:02d}",
                "rule_refs": kz_result.get("rule_refs", ["8.1"])
            }
        except ImportError:
            return self._fallback_session_detection(timestamp)

    def _fallback_session_detection(self, timestamp: datetime) -> Dict[str, Any]:
        """Fallback session detection without importing tools."""
        hour_utc = timestamp.hour
        est_hour = (hour_utc - 5) % 24

        if 7 <= hour_utc < 10:
            session = "London"
            in_kz = True
            kz_name = "London"
        elif 12 <= hour_utc < 15:
            session = "NY"
            in_kz = True
            kz_name = "NY"
        elif 3 <= hour_utc < 8:
            session = "London"
            in_kz = False
            kz_name = None
        elif 8 <= hour_utc < 17:
            session = "NY"
            in_kz = False
            kz_name = None
        else:
            session = "Asia"
            in_kz = False
            kz_name = None

        return {
            "session": session,
            "kill_zone_active": in_kz,
            "kill_zone_name": kz_name,
            "current_time_utc": timestamp.isoformat() + "Z",
            "current_time_est": f"{est_hour:02d}:{timestamp.minute:02d}",
            "rule_refs": ["8.1"]
        }


# Singleton instance
_agent_engine: Optional[TradingAgentEngine] = None


def get_agent_engine() -> TradingAgentEngine:
    """Get or create the agent engine singleton."""
    global _agent_engine
    if _agent_engine is None:
        _agent_engine = TradingAgentEngine()
    return _agent_engine


def reset_agent_engine() -> TradingAgentEngine:
    """Reset and return a fresh agent engine."""
    global _agent_engine
    _agent_engine = TradingAgentEngine()
    return _agent_engine


def build_backward_compatible_response(
    state: Any,
    tick_result: Dict[str, Any],
    snapshot_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build response in the old TradeSetupResponse format for backward compatibility.
    """
    try:
        from src.state import SessionPhase
    except ImportError:
        # Fallback if src not directly available
        from ..agent.main_agent.state import SessionPhase

    context = state.market_context
    setup = state.current_setup

    # Map phase to old status
    phase = state.phase
    if phase in [SessionPhase.EXECUTING, SessionPhase.MONITORING]:
        status = "TRADE_NOW"
    elif phase == SessionPhase.ANALYZING and context and context.environment.blocked_reasons:
        status = "WAIT"
    else:
        status = "NO_TRADE"

    if setup:
        status = "TRADE_NOW"

    # Build HTF bias (old format)
    if context:
        htf_bias = {
            "value": context.bias.direction.value,
            "rule_refs": context.bias.rule_refs
        }
    else:
        htf_bias = {"value": "NEUTRAL", "rule_refs": ["1.1"]}

    # Build LTF alignment (old format)
    ltf_alignment = {
        "timeframe": "15M",
        "alignment": "ALIGNED" if setup else "NOT_ALIGNED",
        "rule_refs": ["1.2", "1.2.1"]
    }

    # Build setup (old format)
    if setup:
        setup_dict = {
            "name": setup.model_name,
            "type": setup.model_type,
            "entry_price": setup.entry_price,
            "entry_type": setup.entry_type.value,
            "stop_loss": setup.stop_loss,
            "take_profit": [setup.take_profit],
            "invalidation_point": setup.stop_loss,
            "is_counter_trend": False,
            "confluence_score": setup.confluence_score,
            "rule_refs": setup.rule_refs
        }
    else:
        setup_dict = {
            "name": "None",
            "type": "None",
            "entry_price": None,
            "entry_type": None,
            "stop_loss": None,
            "take_profit": None,
            "invalidation_point": None,
            "is_counter_trend": False,
            "confluence_score": 0,
            "rule_refs": []
        }

    # Build risk params (old format)
    risk = {
        "account_balance": snapshot_data.get("account_balance", 10000),
        "risk_pct": snapshot_data.get("risk_pct", 1.0),
        "position_size": 0.1 if setup else 0,
        "rr": setup.risk_reward if setup else None
    }

    # Build checklist (old format)
    checklist = {
        "htf_bias_exists": context and context.bias.direction.value != "NEUTRAL",
        "ltf_mss": setup is not None,
        "pd_alignment": setup is not None,
        "liquidity_sweep_detected": setup and "liquidity_sweep" in setup.confluence_factors if setup else False,
        "session_ok": context and context.environment.killzone_active if context else False,
        "news_ok": context and context.environment.news_clear if context else True,
        "rr_minimum_met": setup and setup.risk_reward >= 2.0 if setup else False
    }

    # Build explanation
    explanation_parts = []
    if context:
        explanation_parts.append(
            f"HTF Bias: {context.bias.direction.value} per Rules {', '.join(context.bias.rule_refs)}"
        )
        explanation_parts.append(
            f"Environment: {context.environment.status.value} | Session: {context.environment.session.value}"
        )
    if setup:
        explanation_parts.append(
            f"Setup: {setup.model_name} with confluence {setup.confluence_score}/10"
        )
    if tick_result.get("reason"):
        explanation_parts.append(tick_result["reason"])

    explanation = " | ".join(explanation_parts)

    # Build nodes triggered (for backward compat)
    nodes_triggered = ["Main_Agent"]
    if tick_result.get("context"):
        nodes_triggered.append("Strategy_Agent")
    if tick_result.get("setup"):
        nodes_triggered.append("Worker_Agent")
    if tick_result.get("trade_executed"):
        nodes_triggered.append("Executor")

    # Calculate confidence
    confidence = 0.0
    if setup:
        confidence = setup.confidence
    elif context:
        confidence = context.bias.confidence * 0.5

    return {
        "symbol": state.symbol,
        "timestamp": state.current_time.isoformat(),
        "status": status,
        "reason_short": tick_result.get("reason", "") or (setup.rationale if setup else "No setup"),
        "htf_bias": htf_bias,
        "ltf_alignment": ltf_alignment,
        "setup": setup_dict,
        "risk": risk,
        "checklist": checklist,
        "explanation": explanation,
        "graph_nodes_triggered": nodes_triggered,
        "confidence": confidence,

        # New fields from hierarchical architecture
        "phase": state.phase.value,
        "session_id": state.session_id,
        "tick": tick_result.get("tick", 0),
        "actions": tick_result.get("actions", []),
        "trade_executed": tick_result.get("trade_executed")
    }
