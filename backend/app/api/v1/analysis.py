"""Analysis API endpoints."""
from fastapi import APIRouter, Depends
from typing import List
from datetime import datetime

from app.domain.requests import AnalysisRequest, BatchAnalysisRequest
from app.agent.engine import get_agent_engine, TradingAgentEngine
from app.core.exceptions import AgentError
from app.core.config import get_settings
from app.domain.hub import HubDecisionRequest
from app.hub.master_agent import get_master_agent
from app.hub.adapters import hub_to_legacy_response

router = APIRouter(prefix="/analyze", tags=["Analysis"])


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


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
    settings = get_settings()
    if settings.hub_enabled:
        hub = await get_master_agent()
        hub_request = HubDecisionRequest(
            symbol=request.symbol,
            timestamp=_parse_timestamp(request.timestamp),
            timeframe_bars=request.timeframe_bars,
            account_balance=request.account_balance,
            risk_pct=request.risk_pct,
            economic_calendar=[e.model_dump() for e in request.economic_calendar],
        )
        hub_decision = await hub.decision_cycle(hub_request)
        return hub_to_legacy_response(hub_decision)

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
    settings = get_settings()
    if settings.hub_enabled:
        hub = await get_master_agent()
        results: List[dict] = []
        for snapshot_request in request.snapshots:
            hub_request = HubDecisionRequest(
                symbol=snapshot_request.symbol,
                timestamp=_parse_timestamp(snapshot_request.timestamp),
                timeframe_bars=snapshot_request.timeframe_bars,
                account_balance=snapshot_request.account_balance,
                risk_pct=snapshot_request.risk_pct,
                economic_calendar=[e.model_dump() for e in snapshot_request.economic_calendar],
            )
            hub_decision = await hub.decision_cycle(hub_request)
            results.append(hub_to_legacy_response(hub_decision))
        return results

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
