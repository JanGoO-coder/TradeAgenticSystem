"""Analysis API endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.domain.requests import AnalysisRequest, BatchAnalysisRequest
from app.domain.responses import TradeSetupResponse
from app.agent.engine import get_agent_engine, TradingAgentEngine
from app.core.exceptions import AgentError

router = APIRouter(prefix="/analyze", tags=["Analysis"])


@router.post("", response_model=dict)
async def analyze_snapshot(
    request: AnalysisRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine)
) -> dict:
    """
    Run trade analysis on a single market snapshot.
    
    This is the primary endpoint for getting trade setup recommendations
    from the ICT trading agent.
    
    Returns a TradeSetupResponse with:
    - status: TRADE_NOW, WAIT, or NO_TRADE
    - setup: Entry details if TRADE_NOW
    - checklist: Pass/fail for all required checks
    - explanation: Human-readable reasoning
    """
    if not engine.is_available:
        raise AgentError(f"Trading agent not available: {engine.last_error}")
    
    # Convert request to snapshot dict
    snapshot = {
        "symbol": request.symbol,
        "timestamp": request.timestamp,
        "timeframe_bars": request.timeframe_bars,
        "account_balance": request.account_balance,
        "risk_pct": request.risk_pct,
        "session": request.session,
        "economic_calendar": [e.model_dump() for e in request.economic_calendar],
        "user_max_trades_per_session": request.user_max_trades_per_session
    }
    
    try:
        result = engine.analyze(snapshot)
        return result
    except RuntimeError as e:
        raise AgentError(str(e))


@router.post("/batch", response_model=List[dict])
async def analyze_batch(
    request: BatchAnalysisRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine)
) -> List[dict]:
    """
    Run trade analysis on multiple market snapshots.
    
    Useful for scanning multiple pairs or timeframes.
    """
    if not engine.is_available:
        raise AgentError(f"Trading agent not available: {engine.last_error}")
    
    results = []
    for snapshot_request in request.snapshots:
        snapshot = {
            "symbol": snapshot_request.symbol,
            "timestamp": snapshot_request.timestamp,
            "timeframe_bars": snapshot_request.timeframe_bars,
            "account_balance": snapshot_request.account_balance,
            "risk_pct": snapshot_request.risk_pct,
            "session": snapshot_request.session,
            "economic_calendar": [e.model_dump() for e in snapshot_request.economic_calendar],
            "user_max_trades_per_session": snapshot_request.user_max_trades_per_session
        }
        
        try:
            result = engine.analyze(snapshot)
            results.append(result)
        except RuntimeError as e:
            results.append({"error": str(e), "symbol": snapshot_request.symbol})
    
    return results
