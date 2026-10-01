"""
Smart Backtest API Endpoints.

Endpoints for the time-machine backtesting system.
Uses the ICT Architecture for market analysis.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
import json
import asyncio
import traceback

from app.services.smart_backtest_service import get_smart_backtest_service

router = APIRouter(prefix="/backtest", tags=["Backtesting"])


def _trade_status_from_result(result: Optional[str]) -> str:
    """Map backend trade result enum to frontend-friendly status."""
    mapping = {
        "OPEN": "open",
        "WIN": "won",
        "LOSS": "lost",
        "BREAKEVEN": "breakeven",
        "SKIPPED": "skipped",
    }
    return mapping.get((result or "").upper(), "open")


def _create_batch_streaming_response(step_size: int, max_concurrent: int) -> StreamingResponse:
    """Create SSE response for batch backtest progress."""

    async def event_stream():
        service = await get_smart_backtest_service()

        async for event in service.run_ict_batch(
            step_size=step_size,
            max_concurrent=max_concurrent,
        ):
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.01)  # Small delay for buffering

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new backtest session."""
    symbol: str = Field(..., description="Trading symbol")
    from_date: datetime = Field(..., description="Start date")
    to_date: datetime = Field(..., description="End date")
    htf_timeframe: str = Field("1H", description="Higher timeframe")
    ltf_timeframe: str = Field("15M", description="Lower timeframe")


class StepRequest(BaseModel):
    """Request to step forward/backward."""
    bars: int = Field(1, description="Number of bars to move")


class JumpRequest(BaseModel):
    """Request to jump to specific index."""
    index: int = Field(..., description="Target index")


class RunBatchRequest(BaseModel):
    """Request to run batch backtest."""
    step_size: int = Field(1, description="Candles per step")
    max_concurrent: int = Field(10, description="Max parallel calls")


class MT5StatusResponse(BaseModel):
    """MT5 connection status for backtest."""
    connected: bool
    available: bool


# ============================================================================
# Session Management
# ============================================================================

@router.get("/mt5-status")
async def get_backtest_mt5_status() -> MT5StatusResponse:
    """
    Get MT5 connection status for backtesting.

    Use this before creating a session to check if MT5 is available.
    """
    from app.services.mt5_service import get_mt5_service
    mt5 = get_mt5_service()

    return MT5StatusResponse(
        connected=mt5.is_connected,
        available=mt5.is_available
    )


@router.post("/session")
async def create_session(request: CreateSessionRequest) -> dict:
    """
    Create a new backtest session.

    Loads historical data from MT5 and prepares for time-machine analysis.

    Requires MT5 terminal to be running with valid data for the requested symbol and date range.
    Returns a 503 error if MT5 is not connected, or a 400 error if data is not available.
    """
    try:
        service = await get_smart_backtest_service()

        session = service.create_session(
            symbol=request.symbol,
            from_date=request.from_date,
            to_date=request.to_date,
            htf_timeframe=request.htf_timeframe,
            ltf_timeframe=request.ltf_timeframe
        )

        return session.to_dict()

    except ValueError as e:
        # MT5 connection or data availability errors
        error_msg = str(e)
        if "not connected" in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail=error_msg
            )
        else:
            # Data availability or other validation errors
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session")
async def get_current_session() -> Optional[dict]:
    """
    Get the current active session.

    Returns null when no active session exists.
    """
    service = await get_smart_backtest_service()
    session = service.get_session()

    if not session:
        return None

    return session.to_dict()


@router.get("/session/{session_id}")
async def get_session_by_id(session_id: str) -> dict:
    """
    Load and return a specific session.
    """
    try:
        service = await get_smart_backtest_service()
        session = service.load_session(session_id)
        return session.to_full_dict()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions() -> dict:
    """
    List all saved backtest sessions.
    """
    service = await get_smart_backtest_service()
    sessions = service.list_sessions()

    return {
        "count": len(sessions),
        "sessions": sessions
    }


@router.post("/session/save")
async def save_current_session() -> dict:
    """
    Save the current session to disk.
    """
    try:
        service = await get_smart_backtest_service()
        path = service.save_session()

        return {
            "message": "Session saved",
            "path": path
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Time Machine Controls
# ============================================================================

@router.post("/step/forward")
async def step_forward(request: Optional[StepRequest] = None) -> dict:
    """
    Step forward in time and run analysis.
    """
    try:
        service = await get_smart_backtest_service()
        bars = request.bars if request else 1
        result = await service.step_forward(bars)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        error_msg = str(e)
        # Check for rate limit errors
        if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="LLM API rate limit exceeded. Please wait a moment before stepping forward again."
            )
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/step/backward")
async def step_backward(request: Optional[StepRequest] = None) -> dict:
    """
    Step backward in time.
    """
    try:
        service = await get_smart_backtest_service()
        bars = request.bars if request else 1
        result = service.step_backward(bars)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jump")
async def jump_to_index(request: JumpRequest) -> dict:
    """
    Jump to a specific candle index.
    """
    try:
        service = await get_smart_backtest_service()
        result = service.jump_to(request.index)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot")
async def get_snapshot() -> dict:
    """
    Get current time machine snapshot with candles and session state.
    """
    try:
        service = await get_smart_backtest_service()
        return service.get_snapshot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_current_position(
    mode: Literal["verbose", "concise"] = Query("verbose", description="verbose or concise")
) -> dict:
    """
    Run ICT Architecture analysis at current position.
    
    Uses the full ICT pipeline:
    - Event-based observer
    - Context manager
    - Phase detection
    - Decision validator (veto layer)
    """
    try:
        service = await get_smart_backtest_service()
        session = service.get_session()

        if not session:
            raise HTTPException(status_code=400, detail="No active session")

        observation, decision = await service.analyze_ict_at_index(
            session.current_index,
            mode="verbose" if mode == "verbose" else "concise",
            force=True  # Always analyze when explicitly requested
        )

        return {
            "observation": observation.to_summary(),
            "observation_hash": observation.state_hash,
            "events_count": len(observation.events),
            "phase": decision.extra.get("phase") if decision.extra else None,
            "validated": decision.extra.get("validated") if decision.extra else True,
            "veto_reasons": decision.extra.get("veto_reasons") if decision.extra else [],
            "hub_status": decision.extra.get("hub_status") if decision.extra else None,
            "confluences": decision.extra.get("confluences") if decision.extra else [],
            "vetoes": decision.extra.get("vetoes") if decision.extra else [],
            "call_metrics": decision.extra.get("call_metrics") if decision.extra else {},
            "decision": decision.to_dict()
        }
    except HTTPException:
        # Re-raise HTTP exceptions as is
        raise
    except Exception as e:
        # Catch other errors
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Execution
# ============================================================================

@router.post("/run")
async def run_batch_backtest(request: Optional[RunBatchRequest] = None):
    """
    Run batch backtest using ICT Architecture with streaming progress.

    Uses the full ICT pipeline:
    - Event-based observer
    - Context manager with memory
    - Phase detection (PO3)
    - Decision validator (veto layer)

    Returns a stream of JSON events:
    - started: Session started with strategy info
    - progress: Current position, phase, validation stats
    - trades_closed: Trades that hit TP/SL
    - completed: Final results with validation stats
    - error: Error occurred
    """
    payload = request or RunBatchRequest(step_size=1, max_concurrent=10)
    return _create_batch_streaming_response(
        step_size=payload.step_size,
        max_concurrent=payload.max_concurrent,
    )


@router.get("/run")
async def run_batch_backtest_stream(
    step_size: int = Query(1, ge=1, description="Candles per step"),
    max_concurrent: int = Query(10, ge=1, description="Max parallel calls"),
):
    """Run batch backtest stream (SSE GET variant for EventSource clients)."""
    return _create_batch_streaming_response(
        step_size=step_size,
        max_concurrent=max_concurrent,
    )


# ============================================================================
# Results
# ============================================================================

@router.get("/results")
async def get_results() -> dict:
    """
    Get results from current session.
    """
    service = await get_smart_backtest_service()
    session = service.get_session()

    if not session:
        raise HTTPException(status_code=404, detail="No active session")

    decisions_by_index = {
        d.index: d for d in session.decisions
    }

    normalized_trades = []
    for trade in session.trades:
        trade_dict = trade.to_dict()
        linked_decision = decisions_by_index.get(trade.decision_index)

        take_profit = trade_dict.get("take_profit")
        trade_dict["id"] = trade_dict.get("trade_id")
        trade_dict["status"] = _trade_status_from_result(trade_dict.get("result"))
        trade_dict["take_profits"] = [take_profit] if take_profit is not None else []
        trade_dict["rule_citations"] = linked_decision.rule_citations if linked_decision else []

        normalized_trades.append(trade_dict)

    return {
        "session_id": session.session_id,
        "status": session.status,
        "progress": session.progress,
        "decisions_count": len(session.decisions),
        "trades_count": len(session.trades),
        "performance": session.performance.to_dict(),
        "trades": normalized_trades
    }


@router.get("/equity-curve")
async def get_equity_curve() -> dict:
    """
    Get equity curve data for charting.
    """
    service = await get_smart_backtest_service()
    session = service.get_session()

    if not session:
        raise HTTPException(status_code=404, detail="No active session")

    raw_curve = session.performance.equity_curve or [0.0]
    closed_trades = [
        trade for trade in session.trades
        if trade.exit_time is not None
    ]

    curve_points = []
    for i, equity in enumerate(raw_curve):
        if i == 0:
            ts = session.start_date or session.created_at
        else:
            trade_idx = min(i - 1, len(closed_trades) - 1)
            if trade_idx >= 0:
                ts = closed_trades[trade_idx].exit_time or session.created_at
            else:
                ts = session.created_at

        curve_points.append({
            "timestamp": ts.isoformat(),
            "equity": float(equity),
        })

    return {
        "curve": curve_points,
        "max_drawdown_r": session.performance.max_drawdown_r,
        "total_pnl_r": session.performance.total_pnl_r
    }
