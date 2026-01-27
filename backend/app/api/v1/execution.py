"""Execution mode, trading, and position management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

from app.core.config import get_settings, Settings
from app.services.trade_service import get_trade_service, TradeExecutionService
from app.domain.trading import (
    OrderRequest, OrderResponse, OrderType,
    Position, PendingOrder, AccountInfo,
    ModifyPositionRequest, ClosePositionRequest, ClosePositionResponse,
    TradeValidation, RiskLimits, TradeAuditEntry,
    PendingApproval, ApprovalDecision,
    EmergencyStopRequest, EmergencyStopResponse,
    LotSizeRequest, LotSizeResponse
)

router = APIRouter(tags=["Execution"])


class ExecutionMode(str, Enum):
    ANALYSIS_ONLY = "ANALYSIS_ONLY"
    SIMULATION = "SIMULATION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EXECUTION = "EXECUTION"


class ModeResponse(BaseModel):
    """Current execution mode."""
    mode: ExecutionMode
    description: str
    can_execute: bool


class ModeUpdateRequest(BaseModel):
    """Request to update execution mode."""
    mode: ExecutionMode


class SimulatedTrade(BaseModel):
    """A simulated (paper) trade."""
    id: str
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    status: str  # OPEN, CLOSED_WIN, CLOSED_LOSS, CANCELLED
    entry_time: str
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    setup_name: str
    confluence_score: int


class SimulateTradeRequest(BaseModel):
    """Request to simulate a trade."""
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    setup_name: str = "Manual"
    confluence_score: int = 5


class DecisionRecord(BaseModel):
    """Record of a trading decision."""
    id: str
    timestamp: str
    symbol: str
    status: str  # TRADE_NOW, WAIT, NO_TRADE
    reason: str
    setup_name: Optional[str] = None
    action_taken: str  # APPROVED, REJECTED, IGNORED, AUTO
    outcome: Optional[str] = None  # WIN, LOSS, PENDING, N/A


class PerformanceMetrics(BaseModel):
    """Trading performance metrics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    largest_win: float
    largest_loss: float
    average_rr: float
    profit_factor: float


# In-memory storage for MVP (would be database in production)
_current_mode: ExecutionMode = ExecutionMode.ANALYSIS_ONLY
_simulated_trades: List[SimulatedTrade] = []
_decisions: List[DecisionRecord] = []


@router.get("/mode", response_model=ModeResponse)
async def get_mode() -> ModeResponse:
    """Get current execution mode."""
    descriptions = {
        ExecutionMode.ANALYSIS_ONLY: "Analysis only - no trading actions",
        ExecutionMode.SIMULATION: "Paper trading - simulated executions",
        ExecutionMode.APPROVAL_REQUIRED: "Requires manual approval for each trade",
        ExecutionMode.EXECUTION: "Live trading - real executions (CAUTION)",
    }
    can_execute = _current_mode in [ExecutionMode.SIMULATION, ExecutionMode.EXECUTION]

    return ModeResponse(
        mode=_current_mode,
        description=descriptions[_current_mode],
        can_execute=can_execute
    )


@router.put("/mode", response_model=ModeResponse)
async def set_mode(request: ModeUpdateRequest) -> ModeResponse:
    """
    Update execution mode.

    Mode transitions:
    - ANALYSIS_ONLY → SIMULATION: Always allowed
    - SIMULATION → APPROVAL_REQUIRED: Always allowed
    - APPROVAL_REQUIRED → EXECUTION: Requires confirmation
    - Any → ANALYSIS_ONLY: Always allowed (safe fallback)
    """
    global _current_mode

    # Block direct jump to EXECUTION from ANALYSIS_ONLY
    if request.mode == ExecutionMode.EXECUTION and _current_mode == ExecutionMode.ANALYSIS_ONLY:
        raise HTTPException(
            status_code=400,
            detail="Cannot jump directly to EXECUTION mode. Progress through SIMULATION first."
        )

    _current_mode = request.mode

    return await get_mode()


@router.post("/execute/simulate", response_model=SimulatedTrade)
async def simulate_trade(request: SimulateTradeRequest) -> SimulatedTrade:
    """
    Create a simulated (paper) trade.

    This records the trade for performance tracking without real execution.
    """
    if _current_mode == ExecutionMode.ANALYSIS_ONLY:
        raise HTTPException(
            status_code=400,
            detail="Cannot simulate trades in ANALYSIS_ONLY mode. Switch to SIMULATION first."
        )

    trade = SimulatedTrade(
        id=str(uuid.uuid4()),
        symbol=request.symbol,
        direction=request.direction,
        entry_price=request.entry_price,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        position_size=request.position_size,
        status="OPEN",
        entry_time=datetime.utcnow().isoformat() + "Z",
        setup_name=request.setup_name,
        confluence_score=request.confluence_score
    )

    _simulated_trades.append(trade)

    # Also record as a decision
    decision = DecisionRecord(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat() + "Z",
        symbol=request.symbol,
        status="TRADE_NOW",
        reason=f"Simulated {request.direction} trade",
        setup_name=request.setup_name,
        action_taken="APPROVED",
        outcome="PENDING"
    )
    _decisions.append(decision)

    return trade


@router.get("/trades/simulated", response_model=List[SimulatedTrade])
async def get_simulated_trades() -> List[SimulatedTrade]:
    """Get all simulated trades."""
    return _simulated_trades


@router.post("/trades/{trade_id}/close")
async def close_simulated_trade(trade_id: str, exit_price: float) -> SimulatedTrade:
    """Close an open simulated trade with an exit price."""
    for trade in _simulated_trades:
        if trade.id == trade_id and trade.status == "OPEN":
            trade.exit_time = datetime.utcnow().isoformat() + "Z"
            trade.exit_price = exit_price

            # Calculate P&L
            if trade.direction == "LONG":
                pips = (exit_price - trade.entry_price) * 10000
            else:
                pips = (trade.entry_price - exit_price) * 10000

            trade.pnl = pips * trade.position_size * 10  # Rough estimate
            trade.status = "CLOSED_WIN" if trade.pnl > 0 else "CLOSED_LOSS"

            return trade

    raise HTTPException(status_code=404, detail="Trade not found or already closed")


@router.get("/audit/decisions", response_model=List[DecisionRecord])
async def get_decisions(limit: int = 50) -> List[DecisionRecord]:
    """Get trading decision history."""
    return _decisions[-limit:][::-1]  # Most recent first


@router.post("/audit/decisions")
async def record_decision(
    symbol: str,
    status: str,
    reason: str,
    action: str,
    setup_name: Optional[str] = None
) -> DecisionRecord:
    """Record a trading decision."""
    decision = DecisionRecord(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat() + "Z",
        symbol=symbol,
        status=status,
        reason=reason,
        setup_name=setup_name,
        action_taken=action,
        outcome="N/A" if action in ["REJECTED", "IGNORED"] else "PENDING"
    )
    _decisions.append(decision)
    return decision


@router.get("/audit/metrics", response_model=PerformanceMetrics)
async def get_performance_metrics() -> PerformanceMetrics:
    """Calculate performance metrics from simulated trades."""
    closed_trades = [t for t in _simulated_trades if t.status in ["CLOSED_WIN", "CLOSED_LOSS"]]

    if not closed_trades:
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            average_rr=0.0,
            profit_factor=0.0
        )

    winning = [t for t in closed_trades if t.status == "CLOSED_WIN"]
    losing = [t for t in closed_trades if t.status == "CLOSED_LOSS"]

    total_pnl = sum(t.pnl or 0 for t in closed_trades)
    gross_profit = sum(t.pnl or 0 for t in winning)
    gross_loss = abs(sum(t.pnl or 0 for t in losing))

    return PerformanceMetrics(
        total_trades=len(closed_trades),
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=len(winning) / len(closed_trades) * 100 if closed_trades else 0,
        total_pnl=total_pnl,
        largest_win=max((t.pnl or 0 for t in winning), default=0),
        largest_loss=min((t.pnl or 0 for t in losing), default=0),
        average_rr=0.0,  # Would need SL/TP data
        profit_factor=gross_profit / gross_loss if gross_loss > 0 else gross_profit
    )


# ==================== NEW TRADING ENDPOINTS ====================

# Dependency to get trade service
def get_trade_svc() -> TradeExecutionService:
    return get_trade_service()


# -------------------- Account --------------------

@router.get("/account", response_model=AccountInfo)
async def get_account_info(
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Get MT5 account information.

    Returns balance, equity, margin, free margin, and trading permissions.
    """
    account = trade_service.get_account_info()
    if account is None:
        raise HTTPException(status_code=503, detail="MT5 not connected or account info unavailable")
    return account


# -------------------- Order Execution --------------------

@router.post("/execute/order", response_model=OrderResponse)
async def execute_order(
    request: OrderRequest,
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Execute a market or pending order.

    Behavior depends on current execution mode:
    - ANALYSIS_ONLY: Rejected
    - SIMULATION: Paper trade recorded
    - APPROVAL_REQUIRED: Queued for approval
    - EXECUTION: Live MT5 order

    If volume is not provided, it will be calculated from risk_pct.
    """
    return trade_service.execute_trade(request)


@router.post("/execute/validate", response_model=TradeValidation)
async def validate_order(
    request: OrderRequest,
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Validate an order without executing it.

    Checks all risk limits, symbol validity, and trade requirements.
    Use this to preview trade validation before submission.
    """
    return trade_service.validate_trade(request)


# -------------------- Positions --------------------

@router.get("/positions", response_model=List[Position])
async def get_positions(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Get all open MT5 positions.

    Optionally filter by symbol.
    """
    positions = trade_service.get_positions()
    if symbol:
        positions = [p for p in positions if p.symbol == symbol.upper()]
    return positions


@router.get("/positions/{ticket}", response_model=Position)
async def get_position(
    ticket: int,
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """Get a specific position by ticket number."""
    position = trade_service.get_position(ticket)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Position {ticket} not found")
    return position


@router.put("/positions/{ticket}", response_model=Dict[str, Any])
async def modify_position(
    ticket: int,
    stop_loss: Optional[float] = Query(None, description="New stop loss price"),
    take_profit: Optional[float] = Query(None, description="New take profit price"),
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Modify an open position's stop loss and/or take profit.

    At least one of stop_loss or take_profit must be provided.
    """
    if stop_loss is None and take_profit is None:
        raise HTTPException(status_code=400, detail="Must provide stop_loss or take_profit")

    request = ModifyPositionRequest(ticket=ticket, stop_loss=stop_loss, take_profit=take_profit)
    success, message = trade_service.modify_position(request)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message, "ticket": ticket}


@router.delete("/positions/{ticket}", response_model=ClosePositionResponse)
async def close_position(
    ticket: int,
    volume: Optional[float] = Query(None, description="Volume to close (None = close all)"),
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Close an open position.

    If volume is not specified, the entire position is closed.
    Partial closes are supported by specifying a volume less than the position size.
    """
    return trade_service.close_position(ticket, volume)


@router.post("/positions/close-all", response_model=Dict[str, Any])
async def close_all_positions(
    symbol: Optional[str] = Query(None, description="Only close positions for this symbol"),
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Close all open positions.

    WARNING: This will close all positions immediately.
    Optionally filter by symbol.
    """
    from app.services.mt5_service import get_mt5_service
    mt5 = get_mt5_service()

    if not mt5.is_connected:
        raise HTTPException(status_code=503, detail="MT5 not connected")

    results = mt5.close_all_positions(symbol)

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    total_pnl = sum(r.profit for r in successful)

    return {
        "success": len(failed) == 0,
        "positions_closed": len(successful),
        "positions_failed": len(failed),
        "total_pnl": total_pnl,
        "errors": [r.error_message for r in failed if r.error_message]
    }


# -------------------- Pending Orders --------------------

@router.get("/orders", response_model=List[PendingOrder])
async def get_pending_orders(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """Get all pending orders."""
    orders = trade_service.get_pending_orders()
    if symbol:
        orders = [o for o in orders if o.symbol == symbol.upper()]
    return orders


@router.delete("/orders/{ticket}", response_model=Dict[str, Any])
async def cancel_order(
    ticket: int,
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """Cancel a pending order."""
    success, message = trade_service.cancel_pending_order(ticket)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message, "ticket": ticket}


# -------------------- Risk Management --------------------

@router.get("/risk/limits", response_model=RiskLimits)
async def get_risk_limits(
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Get current risk limits and usage.

    Shows max limits and current usage for:
    - Daily trade count
    - Open positions
    - Daily loss percentage
    """
    return trade_service.get_risk_limits()


@router.get("/risk/daily-stats", response_model=Dict[str, Any])
async def get_daily_stats(
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Get today's trading statistics.

    Includes trade count, P&L, and drawdown information.
    """
    return trade_service.get_daily_stats()


@router.post("/risk/calculate-lot", response_model=LotSizeResponse)
async def calculate_lot_size(
    request: LotSizeRequest,
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Calculate optimal lot size based on risk parameters.

    Factors in account balance, risk percentage, and stop loss distance.
    """
    from app.services.mt5_service import get_mt5_service
    mt5 = get_mt5_service()

    result = mt5.calculate_lot_size(
        symbol=request.symbol,
        account_balance=request.account_balance,
        risk_pct=request.risk_pct,
        stop_loss_pips=request.stop_loss_pips
    )

    if result is None:
        raise HTTPException(status_code=400, detail="Failed to calculate lot size")

    return result


# -------------------- Emergency Stop --------------------

@router.post("/emergency-stop", response_model=EmergencyStopResponse)
async def trigger_emergency_stop(
    request: EmergencyStopRequest,
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    EMERGENCY: Immediately close all positions and block trading.

    This will:
    1. Set the emergency stop flag (blocks all new trades)
    2. Close all open positions (if requested)
    3. Cancel all pending orders (if requested)

    Use with extreme caution. Requires manual reset to resume trading.
    """
    return trade_service.trigger_emergency_stop(request)


@router.post("/emergency-stop/reset", response_model=Dict[str, Any])
async def reset_emergency_stop(
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Reset the emergency stop flag to allow trading again.

    This does not reopen any closed positions.
    """
    success, message = trade_service.reset_emergency_stop()
    return {"success": success, "message": message}


@router.get("/emergency-stop/status", response_model=Dict[str, Any])
async def get_emergency_status():
    """Check if emergency stop is active."""
    settings = get_settings()
    return {
        "emergency_stop_active": settings.emergency_stop,
        "execution_mode": settings.execution_mode
    }


# -------------------- Approval Workflow --------------------

@router.get("/approvals", response_model=List[PendingApproval])
async def get_pending_approvals(
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Get all pending trade approvals.

    Only relevant when in APPROVAL_REQUIRED mode.
    """
    return trade_service.get_pending_approvals()


@router.post("/approvals/{approval_id}", response_model=OrderResponse)
async def process_approval(
    approval_id: str,
    decision: str = Query(..., description="APPROVE or REJECT"),
    reason: Optional[str] = Query(None, description="Reason for decision"),
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Approve or reject a pending trade.

    If approved, the trade is executed immediately.
    If rejected, the trade is cancelled with the provided reason.
    """
    if decision not in ["APPROVE", "REJECT"]:
        raise HTTPException(status_code=400, detail="Decision must be APPROVE or REJECT")

    approval_decision = ApprovalDecision(
        approval_id=approval_id,
        decision=decision,
        reason=reason
    )

    return trade_service.process_approval(approval_decision)


# -------------------- Audit Trail --------------------

@router.get("/audit/trail", response_model=List[TradeAuditEntry])
async def get_audit_trail(
    limit: int = Query(100, ge=1, le=1000, description="Number of entries to return"),
    trade_service: TradeExecutionService = Depends(get_trade_svc)
):
    """
    Get the trade audit trail.

    Returns the most recent trade-related actions including:
    - Order executions
    - Position modifications
    - Closes
    - Rejections
    - Emergency stops
    """
    return trade_service.get_audit_log(limit)


# -------------------- Trading Configuration --------------------

@router.get("/config/trading", response_model=Dict[str, Any])
async def get_trading_config():
    """
    Get current trading configuration and limits.

    Returns all risk management settings.
    """
    settings = get_settings()
    return {
        "risk_management": {
            "max_lot_size": settings.max_lot_size,
            "min_lot_size": settings.min_lot_size,
            "max_daily_loss_pct": settings.max_daily_loss_pct,
            "max_daily_profit_pct": settings.max_daily_profit_pct,
            "max_trades_per_day": settings.max_trades_per_day,
            "max_open_positions": settings.max_open_positions,
            "max_positions_per_symbol": settings.max_positions_per_symbol,
            "max_total_exposure_pct": settings.max_total_exposure_pct,
        },
        "trade_requirements": {
            "require_stop_loss": settings.require_stop_loss,
            "require_take_profit": settings.require_take_profit,
            "min_rr_ratio": settings.min_rr_ratio,
            "max_stop_loss_pct": settings.max_stop_loss_pct,
            "min_stop_loss_pips": settings.min_stop_loss_pips,
        },
        "symbol_restrictions": {
            "allowed_symbols": settings.allowed_symbols,
            "blocked_symbols": settings.blocked_symbols,
        },
        "safety": {
            "emergency_stop": settings.emergency_stop,
            "paper_trade_first": settings.paper_trade_first,
            "min_simulation_trades": settings.min_simulation_trades,
            "require_trade_confirmation": settings.require_trade_confirmation,
            "confirmation_delay_seconds": settings.confirmation_delay_seconds,
            "double_confirm_large_trades": settings.double_confirm_large_trades,
            "large_trade_threshold_lots": settings.large_trade_threshold_lots,
        },
        "approval_mode": {
            "approval_timeout_seconds": settings.approval_timeout_seconds,
            "auto_reject_on_timeout": settings.auto_reject_on_timeout,
        },
        "execution_mode": settings.execution_mode,
    }
