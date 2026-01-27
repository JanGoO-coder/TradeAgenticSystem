"""
Worker Agent - The Executor.

Purely mechanical execution with zero strategic opinion.

Responsibilities (post Neuro-Symbolic refactor):
- Order Execution via Backend/Broker API
- Position Management (open, close)
- Time Advancement (backtest mode)
- Safety Validation

NOTE: Pattern scanning has been moved to the Strategy Agent (LLM-driven).
The Worker no longer performs setup detection.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
import time as time_module

from ..state import (
    BiasDirection, OrderDirection, OrderType, EnvironmentStatus,
    TradeSetup, Position
)
from ..rules_config import RulesConfig, get_rules
from ..protocol import (
    MessageEnvelope, ActionType, AgentRole, MessageLog,
    create_request, create_error_response, ReceiptPayload
)
from .models import (
    SetupScanRequest, ExecutionRequest,
    ClosePositionRequest, AdvanceTimeRequest
)
from .tools import (
    calculate_position_size, calculate_risk_reward,
    execute_backtest_trade, close_backtest_position,
    step_backtest_forward
)

logger = logging.getLogger(__name__)


class WorkerAgent:
    """
    The Worker Agent (Executor).

    Pure executor: Validates orders, sends to broker, manages positions.
    Has no strategic opinion - follows instructions from Main Agent.
    
    Post Neuro-Symbolic Refactor:
    - SCAN_SETUPS is now handled by Strategy Agent (LLM-driven)
    - Worker only executes validated trade commands
    
    Reliability Features:
    - Idempotency: Prevents duplicate orders via correlation_id tracking.
    - Safety Catch: Validates orders before sending to broker.
    - Strict Protocol: Returns standard receipts and error payloads.
    """

    def __init__(
        self,
        config: Optional[RulesConfig] = None,
        message_log: Optional[MessageLog] = None,
        execution_handler: Optional[Any] = None,
        close_handler: Optional[Any] = None
    ):
        self.config = config or get_rules()
        self.message_log = message_log or MessageLog()
        self.execution_handler = execution_handler
        self.close_handler = close_handler
        
        # Reliability State
        self._processed_ids: Set[str] = set()
        self._execution_receipts: Dict[str, MessageEnvelope] = {}

    def handle_message(self, message: MessageEnvelope) -> MessageEnvelope:
        """
        Handle an incoming message from Main Agent with reliability checks.
        """
        self.message_log.append(message)
        start_time = time_module.perf_counter()

        # 1. Idempotency Check (for state-changing actions)
        if message.action in [ActionType.EXECUTE_ORDER, ActionType.CLOSE_POSITION]:
            if message.correlation_id in self._processed_ids:
                logger.warning(f"Idempotency hit: {message.correlation_id}. Returning previous receipt.")
                if message.correlation_id in self._execution_receipts:
                    return self._execution_receipts[message.correlation_id]
                else:
                    return create_error_response(message, "Duplicate request processing already in progress.")

        try:
            response_env = None

            # Route by Action
            if message.action == ActionType.SCAN_SETUPS:
                response_env = self._handle_scan(message)

            elif message.action == ActionType.EXECUTE_ORDER:
                response_env = self._handle_execution(message)

            elif message.action == ActionType.ADVANCE_TIME:
                response_env = self._handle_advance_time(message)

            elif message.action == ActionType.CLOSE_POSITION:
                response_env = self._handle_close_position(message)

            else:
                response_env = create_error_response(
                    message, f"Unknown action: {message.action}"
                )

            # Metadata
            elapsed_ms = (time_module.perf_counter() - start_time) * 1000
            response_env.meta["processing_time_ms"] = elapsed_ms
            
            self.message_log.append(response_env)
            return response_env

        except Exception as e:
            logger.exception(f"Worker failure: {e}")
            return create_error_response(message, str(e))

    # =========================================================================
    # Handlers
    # =========================================================================

    def _handle_scan(self, message: MessageEnvelope) -> MessageEnvelope:
        """
        Handle SCAN_SETUPS request.
        
        NOTE: Pattern scanning has moved to the Strategy Agent (LLM-driven).
        The Worker no longer performs setup detection. This handler returns
        an empty result for backwards compatibility.
        """
        logger.info("SCAN_SETUPS received - Worker no longer handles pattern scanning")
        return message.create_reply(
            action=ActionType.SETUP_RESULT,
            payload={
                "setups": [],
                "note": "Pattern scanning moved to Strategy Agent (LLM-driven). "
                        "Use ANALYZE_CONTEXT to get setup suggestions."
            }
        )

    def _handle_execution(self, message: MessageEnvelope) -> MessageEnvelope:
        """Handle EXECUTE_ORDER request with Safety Catch."""
        try:
            request = ExecutionRequest(**message.payload)
            
            # A. Safety Validation
            validation_error = self._validate_order(request)
            if validation_error:
                return message.create_nack(reason=f"Safety Validation Failed: {validation_error}")

            # Mark as processed (start of processing)
            self._processed_ids.add(message.correlation_id)

            # B. Execute
            result = self._execute_trade(request)
            
            if result.get("success"):
                position_data = result.get("position").model_dump()
                response = message.create_reply(
                    action=ActionType.EXECUTION_RECEIPT,
                    payload={
                        "position": position_data,
                        "status": "FILLED",
                        "order_id": position_data["id"]
                    }
                )
                # Cache receipt
                self._execution_receipts[message.correlation_id] = response
                return response
            else:
                # Execution failed at broker level
                return create_error_response(message, result.get("error", "Broker rejection"))

        except Exception as e:
            return create_error_response(message, f"Execution logic failed: {e}")

    def _handle_advance_time(self, message: MessageEnvelope) -> MessageEnvelope:
        """Handle ADVANCE_TIME request (backtest mode)."""
        try:
            request = AdvanceTimeRequest(**message.payload)
            result = step_backtest_forward(request.bars)

            if result.get("success"):
                return message.create_reply(
                    action=ActionType.TIME_ADVANCED,
                    payload={
                        "new_time": datetime.utcnow().isoformat(),
                        "progress": result.get("progress", 0)
                    }
                )
            else:
                return create_error_response(message, result.get("error", "Time advance failed"))
        except Exception as e:
            return create_error_response(message, f"Time advance crash: {e}")

    def _handle_close_position(self, message: MessageEnvelope) -> MessageEnvelope:
        """Handle CLOSE_POSITION request."""
        try:
            request = ClosePositionRequest(**message.payload)
            
            # Idempotency
            self._processed_ids.add(message.correlation_id)

            if self.close_handler:
                result = self.close_handler(request.position_id, request.reason)
            else:
                result = close_backtest_position(request.position_id, request.reason)

            if result.get("success"):
                response = message.create_reply(
                    action=ActionType.EXECUTION_RECEIPT,
                    payload={"status": "CLOSED", "message": result.get("message")}
                )
                self._execution_receipts[message.correlation_id] = response
                return response
            else:
                return create_error_response(message, result.get("error", "Close failed"))

        except Exception as e:
             return create_error_response(message, f"Close crash: {e}")

    # =========================================================================
    # Internal Logic
    # =========================================================================

    def _validate_order(self, request: ExecutionRequest) -> Optional[str]:
        """
        The Safety Catch.
        Returns check failure message string if invalid, None if valid.
        """
        # 1. Price Checks
        if request.entry_price <= 0:
            return f"Invalid entry price: {request.entry_price}"
        if request.stop_loss <= 0:
            return f"Invalid SL: {request.stop_loss}"
        if request.take_profit <= 0:
            return f"Invalid TP: {request.take_profit}"

        # 2. Logic Checks
        if request.direction == OrderDirection.LONG:
            if request.stop_loss >= request.entry_price:
                return "Long SL must be below Entry"
            if request.take_profit <= request.entry_price:
                return "Long TP must be above Entry"
        else: # SHORT
            if request.stop_loss <= request.entry_price:
                return "Short SL must be above Entry"
            if request.take_profit >= request.entry_price:
                return "Short TP must be below Entry"

        # 3. Risk Sanity (Hard limit 5% risk per trade)
        if request.risk_pct > 0.05:
            return f"Risk {request.risk_pct*100}% exceeds safety limit (5%)"

        return None

    def _execute_trade(self, request: ExecutionRequest) -> Dict[str, Any]:
        """Internal execution logic."""
        # Calculate size
        volume = request.volume
        if volume is None:
            size_result = calculate_position_size(
                account_balance=10000, 
                risk_pct=request.risk_pct,
                entry_price=request.entry_price,
                stop_loss=request.stop_loss,
                pip_value=self.config.risk.pip_value_per_lot
            )
            volume = size_result["position_size"]

        # Broker/Sim Call
        if self.execution_handler:
            result = self.execution_handler(
                direction=request.direction.value,
                entry_price=request.entry_price,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                setup_name=request.setup_name,
                risk_reward=None,
                agent_analysis=request.agent_analysis
            )
        else:
            result = execute_backtest_trade(
                direction=request.direction.value,
                entry_price=request.entry_price,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                setup_name=request.setup_name
            )

        if result.get("success"):
            position = Position(
                id=result.get("position_id", ""),
                symbol=request.symbol,
                direction=request.direction,
                entry_price=result.get("entry_price", request.entry_price),
                volume=result.get("volume", volume),
                stop_loss=request.stop_loss,
                take_profit=result.get("take_profit", request.take_profit),
                opened_at=datetime.utcnow(),
                setup_name=request.setup_name,
                agent_analysis=request.agent_analysis
            )
            return {"success": True, "position": position}
        
        return {"success": False, "error": result.get("error")}

    def reset(self):
        """Reset worker state."""
        self._processed_ids.clear()
        self._execution_receipts.clear()

