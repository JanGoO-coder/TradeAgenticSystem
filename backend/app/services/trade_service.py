"""Trade Execution Service - Orchestration layer for trading operations.

This service handles:
- Trade validation against rules and risk limits
- Mode enforcement (ANALYSIS_ONLY, SIMULATION, APPROVAL_REQUIRED, EXECUTION)
- Risk calculations and position sizing
- Trade journaling and audit trail
- Error handling with retries
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
import logging
import uuid

from app.core.config import get_settings, Settings
from app.services.mt5_service import MT5Service, get_mt5_service
from app.domain.trading import (
    OrderRequest, OrderResponse, OrderType,
    Position, PendingOrder, AccountInfo,
    ModifyPositionRequest, ClosePositionResponse,
    TradeValidation, RiskLimits, TradeAuditEntry,
    PendingApproval, ApprovalDecision,
    EmergencyStopRequest, EmergencyStopResponse,
    LotSizeResponse
)

logger = logging.getLogger(__name__)


class TradeExecutionService:
    """
    Orchestration layer for all trading operations.

    Responsibilities:
    1. Validate trades against rules and risk limits
    2. Enforce execution mode restrictions
    3. Calculate position sizes based on risk
    4. Execute or simulate trades
    5. Maintain audit trail
    """

    def __init__(self, mt5_service: Optional[MT5Service] = None, settings: Optional[Settings] = None):
        self._mt5 = mt5_service or get_mt5_service()
        self._settings = settings or get_settings()

        # In-memory storage (production would use database)
        self._audit_log: List[TradeAuditEntry] = []
        self._approval_queue: List[PendingApproval] = []
        self._daily_stats = {
            "date": datetime.utcnow().date().isoformat(),
            "trades_count": 0,
            "starting_balance": 0.0,
            "realized_pnl": 0.0,
            "max_drawdown_pct": 0.0,
        }
        self._simulated_positions: List[Dict[str, Any]] = []
        self._simulation_trade_count: int = 0

    # ==================== MODE ENFORCEMENT ====================

    def get_current_mode(self) -> str:
        """Get the current execution mode."""
        return self._settings.execution_mode

    def can_execute_live(self) -> Tuple[bool, str]:
        """Check if live execution is allowed."""
        mode = self._settings.execution_mode

        if self._settings.emergency_stop:
            return False, "Emergency stop is active - all trading blocked"

        if mode == "ANALYSIS_ONLY":
            return False, "In ANALYSIS_ONLY mode - no trading allowed"

        if mode == "SIMULATION":
            return False, "In SIMULATION mode - paper trading only"

        if mode == "APPROVAL_REQUIRED":
            return True, "APPROVAL_REQUIRED mode - trades need approval"

        if mode == "EXECUTION":
            # Check if paper trading requirement is met
            if self._settings.paper_trade_first:
                if self._simulation_trade_count < self._settings.min_simulation_trades:
                    return False, f"Need {self._settings.min_simulation_trades} simulated trades before live trading (have {self._simulation_trade_count})"
            return True, "EXECUTION mode - live trading enabled"

        return False, f"Unknown mode: {mode}"

    # ==================== VALIDATION ====================

    def validate_trade(self, request: OrderRequest) -> TradeValidation:
        """
        Validate a trade request against all rules and limits.

        Returns:
            TradeValidation with detailed results
        """
        errors = []
        warnings = []

        # 1. Emergency stop check
        if self._settings.emergency_stop:
            errors.append("Emergency stop is active - all trading blocked")
            return TradeValidation(valid=False, errors=errors, warnings=warnings)

        # 2. Symbol validation
        symbol = request.symbol.upper()

        # Check if symbol is blocked
        if symbol in self._settings.blocked_symbols:
            errors.append(f"Symbol {symbol} is blocked from trading")

        # Check if symbol is in allowed list (if list is set)
        if self._settings.allowed_symbols and symbol not in self._settings.allowed_symbols:
            errors.append(f"Symbol {symbol} is not in the allowed symbols list")

        # Verify symbol exists in MT5
        if self._mt5.is_connected:
            symbol_info = self._mt5.get_symbol_info(symbol)
            if symbol_info is None:
                errors.append(f"Symbol {symbol} not found in MT5")

        # 3. Stop loss validation
        if self._settings.require_stop_loss and not request.stop_loss:
            errors.append("Stop loss is required but not provided")

        # 4. Take profit validation
        if self._settings.require_take_profit and not request.take_profit:
            errors.append("Take profit is required but not provided")

        # 5. Risk-reward ratio check
        risk_reward = None
        if request.stop_loss and request.take_profit:
            # Get current price for calculation
            if self._mt5.is_connected:
                tick = self._mt5.get_current_tick(symbol)
                if tick:
                    if request.order_type in [OrderType.MARKET_BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]:
                        entry = tick["ask"] if request.price is None else request.price
                        risk = abs(entry - request.stop_loss)
                        reward = abs(request.take_profit - entry)
                    else:
                        entry = tick["bid"] if request.price is None else request.price
                        risk = abs(request.stop_loss - entry)
                        reward = abs(entry - request.take_profit)

                    if risk > 0:
                        risk_reward = reward / risk
                        if risk_reward < self._settings.min_rr_ratio:
                            errors.append(f"Risk-reward ratio {risk_reward:.2f} is below minimum {self._settings.min_rr_ratio}")

        # 6. Volume validation
        volume = request.volume
        if volume is not None:
            if volume > self._settings.max_lot_size:
                errors.append(f"Volume {volume} exceeds maximum lot size {self._settings.max_lot_size}")
            if volume < self._settings.min_lot_size:
                errors.append(f"Volume {volume} is below minimum lot size {self._settings.min_lot_size}")

        # 7. Daily trade limit check
        self._refresh_daily_stats()
        if self._daily_stats["trades_count"] >= self._settings.max_trades_per_day:
            errors.append(f"Daily trade limit reached ({self._settings.max_trades_per_day})")

        # 8. Open positions limit check
        if self._mt5.is_connected:
            positions = self._mt5.get_positions()
            if len(positions) >= self._settings.max_open_positions:
                errors.append(f"Maximum open positions reached ({self._settings.max_open_positions})")

            # Check per-symbol limit
            symbol_positions = [p for p in positions if p.symbol == symbol]
            if len(symbol_positions) >= self._settings.max_positions_per_symbol:
                errors.append(f"Maximum positions for {symbol} reached ({self._settings.max_positions_per_symbol})")

        # 9. Daily loss limit check
        if self._daily_stats["starting_balance"] > 0:
            current_loss_pct = (self._daily_stats["realized_pnl"] / self._daily_stats["starting_balance"]) * 100
            if current_loss_pct < 0 and abs(current_loss_pct) >= self._settings.max_daily_loss_pct:
                errors.append(f"Daily loss limit reached ({self._settings.max_daily_loss_pct}%)")

        # 10. Calculate risk amount
        risk_amount = None
        risk_pct = None
        if self._mt5.is_connected and request.stop_loss:
            account = self._mt5.get_account_info()
            if account:
                # Estimate risk based on position size
                if volume:
                    tick = self._mt5.get_current_tick(symbol)
                    if tick:
                        entry = tick["ask"] if request.order_type in [OrderType.MARKET_BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP] else tick["bid"]
                        sl_distance = abs(entry - request.stop_loss)
                        # Rough estimate: sl_distance * volume * contract_size
                        symbol_info = self._mt5.get_symbol_info_detailed(symbol)
                        if symbol_info:
                            risk_amount = sl_distance * volume * symbol_info.get("contract_size", 100000)
                            risk_pct = (risk_amount / account.balance) * 100

                            if risk_pct > self._settings.max_stop_loss_pct:
                                errors.append(f"Risk {risk_pct:.2f}% exceeds maximum {self._settings.max_stop_loss_pct}%")

        # Warnings (non-blocking)
        if volume and volume >= self._settings.large_trade_threshold_lots:
            warnings.append(f"Large trade alert: {volume} lots")

        if risk_reward and risk_reward < 3.0:
            warnings.append(f"Risk-reward ratio ({risk_reward:.2f}) is below recommended 3.0")

        return TradeValidation(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            risk_reward=risk_reward
        )

    # ==================== RISK MANAGEMENT ====================

    def get_risk_limits(self) -> RiskLimits:
        """Get current risk limits and usage."""
        self._refresh_daily_stats()

        positions = []
        can_trade = True
        block_reason = None

        if self._mt5.is_connected:
            positions = self._mt5.get_positions()

        # Check if trading is blocked
        if self._settings.emergency_stop:
            can_trade = False
            block_reason = "Emergency stop active"
        elif self._daily_stats["trades_count"] >= self._settings.max_trades_per_day:
            can_trade = False
            block_reason = "Daily trade limit reached"
        elif len(positions) >= self._settings.max_open_positions:
            can_trade = False
            block_reason = "Maximum open positions reached"

        # Calculate current daily loss
        current_daily_loss_pct = 0.0
        if self._daily_stats["starting_balance"] > 0 and self._daily_stats["realized_pnl"] < 0:
            current_daily_loss_pct = abs(self._daily_stats["realized_pnl"] / self._daily_stats["starting_balance"]) * 100
            if current_daily_loss_pct >= self._settings.max_daily_loss_pct:
                can_trade = False
                block_reason = "Daily loss limit reached"

        return RiskLimits(
            max_lot_size=self._settings.max_lot_size,
            max_daily_loss_pct=self._settings.max_daily_loss_pct,
            max_open_positions=self._settings.max_open_positions,
            max_trades_per_day=self._settings.max_trades_per_day,
            current_daily_loss_pct=current_daily_loss_pct,
            current_open_positions=len(positions),
            trades_today=self._daily_stats["trades_count"],
            can_trade=can_trade,
            block_reason=block_reason
        )

    def calculate_position_size(self, request: OrderRequest) -> Optional[float]:
        """
        Calculate position size based on risk parameters.

        Uses the provided risk_pct and account_balance, or defaults from settings.
        """
        if not self._mt5.is_connected:
            return None

        risk_pct = request.risk_pct or self._settings.default_risk_pct

        # Get account balance
        account = self._mt5.get_account_info()
        if account is None:
            return None

        balance = request.account_balance or account.balance

        # Calculate stop loss in pips
        tick = self._mt5.get_current_tick(request.symbol)
        if tick is None:
            return None

        symbol_info = self._mt5.get_symbol_info_detailed(request.symbol)
        if symbol_info is None:
            return None

        # Determine entry price
        if request.order_type in [OrderType.MARKET_BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]:
            entry = request.price if request.price else tick["ask"]
        else:
            entry = request.price if request.price else tick["bid"]

        # Calculate SL distance in pips
        point = symbol_info.get("point", 0.0001)
        digits = symbol_info.get("digits", 5)
        pip_size = point * 10 if digits in [3, 5] else point

        sl_distance = abs(entry - request.stop_loss)
        sl_pips = sl_distance / pip_size

        if sl_pips < self._settings.min_stop_loss_pips:
            logger.warning(f"SL distance {sl_pips:.1f} pips is below minimum {self._settings.min_stop_loss_pips}")

        # Use MT5 service to calculate lot size
        result = self._mt5.calculate_lot_size(
            symbol=request.symbol,
            account_balance=balance,
            risk_pct=risk_pct,
            stop_loss_pips=sl_pips
        )

        if result is None:
            return None

        # Enforce max lot size
        lot_size = min(result.lot_size, self._settings.max_lot_size)

        return lot_size

    # ==================== TRADE EXECUTION ====================

    def execute_trade(self, request: OrderRequest) -> OrderResponse:
        """
        Execute a trade based on current mode.

        In SIMULATION mode: Records paper trade
        In APPROVAL_REQUIRED mode: Queues for approval
        In EXECUTION mode: Executes live trade
        """
        # Validate first
        validation = self.validate_trade(request)
        if not validation.valid:
            return OrderResponse(
                success=False,
                order_type=request.order_type.value,
                symbol=request.symbol,
                volume=request.volume or 0.0,
                price=0.0,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                error_code=-1,
                error_message="; ".join(validation.errors)
            )

        mode = self._settings.execution_mode

        # Calculate volume if not provided
        volume = request.volume
        if volume is None:
            volume = self.calculate_position_size(request)
            if volume is None:
                return OrderResponse(
                    success=False,
                    order_type=request.order_type.value,
                    symbol=request.symbol,
                    volume=0.0,
                    price=0.0,
                    stop_loss=request.stop_loss,
                    take_profit=request.take_profit,
                    error_code=-1,
                    error_message="Failed to calculate position size"
                )

        # Execute based on mode
        if mode == "ANALYSIS_ONLY":
            return OrderResponse(
                success=False,
                order_type=request.order_type.value,
                symbol=request.symbol,
                volume=volume,
                price=0.0,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                error_code=-1,
                error_message="Cannot execute trades in ANALYSIS_ONLY mode"
            )

        if mode == "SIMULATION":
            return self._execute_simulated_trade(request, volume)

        if mode == "APPROVAL_REQUIRED":
            approval = self._queue_for_approval(request, validation, volume)
            return OrderResponse(
                success=True,
                order_type=request.order_type.value,
                symbol=request.symbol,
                volume=volume,
                price=0.0,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                error_message=f"Trade queued for approval. ID: {approval.id}"
            )

        if mode == "EXECUTION":
            return self._execute_live_trade(request, volume)

        return OrderResponse(
            success=False,
            order_type=request.order_type.value,
            symbol=request.symbol,
            volume=volume,
            price=0.0,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            error_code=-1,
            error_message=f"Unknown mode: {mode}"
        )

    def _execute_simulated_trade(self, request: OrderRequest, volume: float) -> OrderResponse:
        """Execute a simulated (paper) trade."""
        # Get simulated entry price
        if self._mt5.is_connected:
            tick = self._mt5.get_current_tick(request.symbol)
            if tick:
                if request.order_type in [OrderType.MARKET_BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP]:
                    price = tick["ask"]
                else:
                    price = tick["bid"]
            else:
                price = request.price or 1.0
        else:
            price = request.price or 1.0

        # Generate simulated ticket
        ticket = int(datetime.utcnow().timestamp() * 1000) % 1000000

        # Record simulated position
        sim_position = {
            "ticket": ticket,
            "symbol": request.symbol,
            "type": "BUY" if request.order_type in [OrderType.MARKET_BUY, OrderType.BUY_LIMIT, OrderType.BUY_STOP] else "SELL",
            "volume": volume,
            "open_price": price,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit,
            "open_time": datetime.utcnow().isoformat() + "Z",
            "magic": request.magic,
            "comment": request.comment
        }
        self._simulated_positions.append(sim_position)
        self._simulation_trade_count += 1
        self._daily_stats["trades_count"] += 1

        # Audit log
        self._log_audit(
            action="SIMULATE_TRADE",
            symbol=request.symbol,
            ticket=ticket,
            request=request.model_dump(),
            result=sim_position,
            success=True
        )

        return OrderResponse(
            success=True,
            ticket=ticket,
            order_type=request.order_type.value,
            symbol=request.symbol,
            volume=volume,
            price=price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            execution_time=datetime.utcnow().isoformat() + "Z"
        )

    def _execute_live_trade(self, request: OrderRequest, volume: float) -> OrderResponse:
        """Execute a live trade through MT5."""
        if not self._mt5.is_connected:
            return OrderResponse(
                success=False,
                order_type=request.order_type.value,
                symbol=request.symbol,
                volume=volume,
                price=0.0,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                error_code=-1,
                error_message="MT5 not connected"
            )

        # Execute based on order type
        if request.order_type in [OrderType.MARKET_BUY, OrderType.MARKET_SELL]:
            result = self._mt5.place_market_order(
                symbol=request.symbol,
                order_type=request.order_type,
                volume=volume,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                comment=request.comment,
                magic=request.magic,
                deviation=request.deviation
            )
        else:
            if request.price is None:
                return OrderResponse(
                    success=False,
                    order_type=request.order_type.value,
                    symbol=request.symbol,
                    volume=volume,
                    price=0.0,
                    stop_loss=request.stop_loss,
                    take_profit=request.take_profit,
                    error_code=-1,
                    error_message="Price required for pending orders"
                )

            result = self._mt5.place_pending_order(
                symbol=request.symbol,
                order_type=request.order_type,
                volume=volume,
                price=request.price,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                comment=request.comment,
                magic=request.magic
            )

        # Update daily stats
        if result.success:
            self._daily_stats["trades_count"] += 1

        # Audit log
        self._log_audit(
            action="LIVE_TRADE",
            symbol=request.symbol,
            ticket=result.ticket,
            request=request.model_dump(),
            result=result.model_dump(),
            success=result.success,
            error=result.error_message
        )

        return result

    # ==================== APPROVAL WORKFLOW ====================

    def _queue_for_approval(self, request: OrderRequest, validation: TradeValidation, volume: float) -> PendingApproval:
        """Queue a trade for approval."""
        # Update request with calculated volume
        request_with_volume = request.model_copy()
        request_with_volume.volume = volume

        approval = PendingApproval(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            expires_at=(datetime.utcnow() + timedelta(seconds=self._settings.approval_timeout_seconds)).isoformat() + "Z",
            order_request=request_with_volume,
            validation=validation,
            status="PENDING"
        )

        self._approval_queue.append(approval)

        self._log_audit(
            action="QUEUE_APPROVAL",
            symbol=request.symbol,
            request=request.model_dump(),
            result={"approval_id": approval.id},
            success=True
        )

        return approval

    def get_pending_approvals(self) -> List[PendingApproval]:
        """Get all pending approvals."""
        # Clean up expired approvals
        now = datetime.utcnow()
        for approval in self._approval_queue:
            if approval.status == "PENDING":
                expires_at = datetime.fromisoformat(approval.expires_at.replace("Z", "+00:00")).replace(tzinfo=None)
                if now > expires_at:
                    approval.status = "EXPIRED" if not self._settings.auto_reject_on_timeout else "REJECTED"
                    approval.rejection_reason = "Timeout - auto-expired"

        return [a for a in self._approval_queue if a.status == "PENDING"]

    def process_approval(self, decision: ApprovalDecision) -> OrderResponse:
        """Process an approval decision."""
        # Find the approval
        approval = None
        for a in self._approval_queue:
            if a.id == decision.approval_id:
                approval = a
                break

        if approval is None:
            return OrderResponse(
                success=False,
                order_type="UNKNOWN",
                symbol="",
                volume=0.0,
                price=0.0,
                stop_loss=0.0,
                error_code=-1,
                error_message=f"Approval {decision.approval_id} not found"
            )

        if approval.status != "PENDING":
            return OrderResponse(
                success=False,
                order_type=approval.order_request.order_type.value,
                symbol=approval.order_request.symbol,
                volume=approval.order_request.volume or 0.0,
                price=0.0,
                stop_loss=approval.order_request.stop_loss,
                error_code=-1,
                error_message=f"Approval already processed: {approval.status}"
            )

        if decision.decision == "REJECT":
            approval.status = "REJECTED"
            approval.rejection_reason = decision.reason

            self._log_audit(
                action="REJECT_TRADE",
                symbol=approval.order_request.symbol,
                request={"approval_id": approval.id, "reason": decision.reason},
                result={"status": "REJECTED"},
                success=True
            )

            return OrderResponse(
                success=False,
                order_type=approval.order_request.order_type.value,
                symbol=approval.order_request.symbol,
                volume=approval.order_request.volume or 0.0,
                price=0.0,
                stop_loss=approval.order_request.stop_loss,
                error_code=0,
                error_message=f"Trade rejected: {decision.reason}"
            )

        # Approve and execute
        approval.status = "APPROVED"
        approval.approved_by = "User"

        # Execute the trade
        return self._execute_live_trade(
            approval.order_request,
            approval.order_request.volume or 0.01
        )

    # ==================== POSITION MANAGEMENT ====================

    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        if not self._mt5.is_connected:
            return []
        return self._mt5.get_positions()

    def get_position(self, ticket: int) -> Optional[Position]:
        """Get a specific position."""
        if not self._mt5.is_connected:
            return None
        return self._mt5.get_position(ticket)

    def modify_position(self, request: ModifyPositionRequest) -> Tuple[bool, str]:
        """Modify a position's SL/TP."""
        if self._settings.emergency_stop:
            return False, "Emergency stop active"

        if self._settings.execution_mode == "ANALYSIS_ONLY":
            return False, "Cannot modify positions in ANALYSIS_ONLY mode"

        if not self._mt5.is_connected:
            return False, "MT5 not connected"

        success, message = self._mt5.modify_position(
            ticket=request.ticket,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit
        )

        self._log_audit(
            action="MODIFY_POSITION",
            symbol="",
            ticket=request.ticket,
            request=request.model_dump(),
            result={"success": success, "message": message},
            success=success,
            error=message if not success else None
        )

        return success, message

    def close_position(self, ticket: int, volume: Optional[float] = None) -> ClosePositionResponse:
        """Close a position."""
        if self._settings.execution_mode == "ANALYSIS_ONLY":
            return ClosePositionResponse(
                success=False,
                ticket=ticket,
                symbol="",
                volume_closed=0.0,
                close_price=0.0,
                profit=0.0,
                error_code=-1,
                error_message="Cannot close positions in ANALYSIS_ONLY mode"
            )

        if not self._mt5.is_connected:
            return ClosePositionResponse(
                success=False,
                ticket=ticket,
                symbol="",
                volume_closed=0.0,
                close_price=0.0,
                profit=0.0,
                error_code=-1,
                error_message="MT5 not connected"
            )

        result = self._mt5.close_position(ticket, volume)

        if result.success:
            self._daily_stats["realized_pnl"] += result.profit

        self._log_audit(
            action="CLOSE_POSITION",
            symbol=result.symbol,
            ticket=ticket,
            request={"ticket": ticket, "volume": volume},
            result=result.model_dump(),
            success=result.success,
            error=result.error_message
        )

        return result

    # ==================== EMERGENCY STOP ====================

    def trigger_emergency_stop(self, request: EmergencyStopRequest) -> EmergencyStopResponse:
        """Trigger emergency stop - close all positions and block trading."""
        errors = []
        positions_closed = 0
        orders_cancelled = 0
        total_pnl = 0.0

        # Set emergency flag
        self._settings.emergency_stop = True

        # Close all positions if requested
        if request.close_all_positions and self._mt5.is_connected:
            results = self._mt5.close_all_positions()
            for result in results:
                if result.success:
                    positions_closed += 1
                    total_pnl += result.profit
                else:
                    errors.append(f"Failed to close {result.ticket}: {result.error_message}")

        # Cancel all pending orders if requested
        if request.cancel_pending_orders and self._mt5.is_connected:
            pending = self._mt5.get_pending_orders()
            for order in pending:
                success, msg = self._mt5.cancel_order(order.ticket)
                if success:
                    orders_cancelled += 1
                else:
                    errors.append(f"Failed to cancel order {order.ticket}: {msg}")

        self._log_audit(
            action="EMERGENCY_STOP",
            symbol="ALL",
            request=request.model_dump(),
            result={
                "positions_closed": positions_closed,
                "orders_cancelled": orders_cancelled,
                "total_pnl": total_pnl,
                "errors": errors
            },
            success=len(errors) == 0,
            error="; ".join(errors) if errors else None
        )

        return EmergencyStopResponse(
            success=len(errors) == 0,
            positions_closed=positions_closed,
            orders_cancelled=orders_cancelled,
            total_pnl=total_pnl,
            errors=errors,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    def reset_emergency_stop(self) -> Tuple[bool, str]:
        """Reset emergency stop flag."""
        self._settings.emergency_stop = False

        self._log_audit(
            action="RESET_EMERGENCY_STOP",
            symbol="",
            request={},
            result={"emergency_stop": False},
            success=True
        )

        return True, "Emergency stop reset"

    # ==================== ACCOUNT & INFO ====================

    def get_account_info(self) -> Optional[AccountInfo]:
        """Get MT5 account information."""
        if not self._mt5.is_connected:
            return None
        return self._mt5.get_account_info()

    def get_pending_orders(self) -> List[PendingOrder]:
        """Get all pending orders."""
        if not self._mt5.is_connected:
            return []
        return self._mt5.get_pending_orders()

    def cancel_pending_order(self, ticket: int) -> Tuple[bool, str]:
        """Cancel a pending order."""
        if self._settings.execution_mode == "ANALYSIS_ONLY":
            return False, "Cannot cancel orders in ANALYSIS_ONLY mode"

        if not self._mt5.is_connected:
            return False, "MT5 not connected"

        return self._mt5.cancel_order(ticket)

    # ==================== AUDIT TRAIL ====================

    def _log_audit(
        self,
        action: str,
        symbol: str,
        ticket: Optional[int] = None,
        request: Optional[dict] = None,
        result: Optional[dict] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Log an action to the audit trail."""
        if not self._settings.log_all_trade_attempts and not success:
            return

        entry = TradeAuditEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            action=action,
            symbol=symbol,
            ticket=ticket,
            request=request,
            result=result,
            success=success,
            error=error,
            execution_mode=self._settings.execution_mode
        )

        self._audit_log.append(entry)

        # Keep only last 1000 entries
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]

        logger.info(f"AUDIT: {action} | {symbol} | {'SUCCESS' if success else 'FAILED'} | {error or ''}")

    def get_audit_log(self, limit: int = 100) -> List[TradeAuditEntry]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:][::-1]

    # ==================== DAILY STATS ====================

    def _refresh_daily_stats(self):
        """Refresh daily statistics, reset if new day."""
        today = datetime.utcnow().date().isoformat()

        if self._daily_stats["date"] != today:
            # New day - reset stats
            account = None
            if self._mt5.is_connected:
                account = self._mt5.get_account_info()

            self._daily_stats = {
                "date": today,
                "trades_count": 0,
                "starting_balance": account.balance if account else 0.0,
                "realized_pnl": 0.0,
                "max_drawdown_pct": 0.0,
            }

    def get_daily_stats(self) -> Dict[str, Any]:
        """Get today's trading statistics."""
        self._refresh_daily_stats()

        account = None
        if self._mt5.is_connected:
            account = self._mt5.get_account_info()

        return {
            **self._daily_stats,
            "current_equity": account.equity if account else 0.0,
            "floating_pnl": account.profit if account else 0.0,
            "total_pnl": self._daily_stats["realized_pnl"] + (account.profit if account else 0.0)
        }


# Singleton instance
_trade_service: Optional[TradeExecutionService] = None


def get_trade_service() -> TradeExecutionService:
    """Get the singleton trade service instance."""
    global _trade_service
    if _trade_service is None:
        _trade_service = TradeExecutionService()
    return _trade_service
