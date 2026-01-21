"""Execution mode and simulation endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid

from app.core.config import get_settings, Settings

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
