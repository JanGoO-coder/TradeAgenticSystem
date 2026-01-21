"""Session and Kill Zone API endpoints."""
from fastapi import APIRouter, Depends
from datetime import datetime

from app.domain.responses import SessionInfoResponse, KillZoneStatusResponse
from app.agent.engine import get_agent_engine, TradingAgentEngine

router = APIRouter(tags=["Session"])


@router.get("/session/current", response_model=SessionInfoResponse)
async def get_current_session(
    engine: TradingAgentEngine = Depends(get_agent_engine)
) -> SessionInfoResponse:
    """
    Get current trading session information.
    
    Returns:
    - Current session name (London, NY, Asia)
    - Kill zone status
    - Current time in UTC and EST
    """
    now = datetime.utcnow()
    session_info = engine.get_current_session(now)
    
    return SessionInfoResponse(
        session=session_info["session"],
        kill_zone_active=session_info["kill_zone_active"],
        kill_zone_name=session_info.get("kill_zone_name"),
        time_until_next_zone=None,  # TODO: Calculate next zone
        current_time_utc=session_info["current_time_utc"],
        current_time_est=session_info["current_time_est"]
    )


@router.get("/killzone/status", response_model=KillZoneStatusResponse)
async def get_killzone_status(
    engine: TradingAgentEngine = Depends(get_agent_engine)
) -> KillZoneStatusResponse:
    """
    Check if currently inside a Kill Zone.
    
    Kill Zones per Rule 8.1:
    - London: 2:00 AM - 5:00 AM EST (07:00-10:00 UTC)
    - NY: 7:00 AM - 10:00 AM EST (12:00-15:00 UTC)
    """
    now = datetime.utcnow()
    session_info = engine.get_current_session(now)
    
    return KillZoneStatusResponse(
        in_kill_zone=session_info["kill_zone_active"],
        session=session_info.get("kill_zone_name"),
        rule_refs=session_info.get("rule_refs", ["8.1"])
    )
