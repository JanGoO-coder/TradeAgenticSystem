"""
Rules Configuration API Endpoints.

Provides endpoints for:
- GET /rules - Get current rules configuration
- POST /rules/reload - Hot-reload rules from config file
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from ...agent.engine import get_agent_engine

router = APIRouter(prefix="/rules", tags=["Rules Configuration"])


class ReloadResponse(BaseModel):
    """Response from rules reload."""
    success: bool
    message: str
    config_version: Optional[str] = None


class RulesResponse(BaseModel):
    """Response with current rules configuration."""
    success: bool
    config: Dict[str, Any]


@router.get("", response_model=RulesResponse)
async def get_rules():
    """
    Get current rules configuration.

    Returns the full rules configuration including:
    - Timeframe settings
    - Kill zone definitions
    - Risk parameters
    - Entry model toggles
    - Confluence weights
    """
    engine = get_agent_engine()

    config = engine.get_rules_config()

    if "error" in config:
        raise HTTPException(status_code=500, detail=config["error"])

    return RulesResponse(success=True, config=config)


@router.post("/reload", response_model=ReloadResponse)
async def reload_rules():
    """
    Hot-reload rules configuration from config file.

    Reloads rules/config.yaml and applies changes immediately.
    If reload fails, previous valid configuration is retained.

    This allows changing trading parameters without restarting the server:
    - Kill zone times
    - Risk parameters (min R:R, risk %)
    - Entry model enables/disables
    - Confluence scoring weights
    """
    engine = get_agent_engine()

    result = engine.reload_rules()

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "Reload failed")
        )

    return ReloadResponse(
        success=result["success"],
        message=result["message"],
        config_version=result.get("config_version")
    )


@router.get("/session")
async def get_session_info():
    """
    Get current session information.

    Returns:
    - Current trading session (Asia/London/NY)
    - Kill zone status
    - Current time (UTC and EST)
    """
    engine = get_agent_engine()
    return engine.get_current_session()


@router.get("/summary")
async def get_session_summary():
    """
    Get current trading session summary.

    Returns statistics for the active session:
    - Balance and equity
    - Win/loss counts
    - Total P&L
    - Trade counts
    """
    engine = get_agent_engine()
    return engine.get_session_summary()


@router.get("/audit-trail")
async def get_audit_trail():
    """
    Get message audit trail for replay visualization.

    Returns all inter-agent messages logged during the session.
    Used for "Glass Box" replay in the frontend.
    """
    engine = get_agent_engine()
    return {
        "messages": engine.get_audit_trail(),
        "count": len(engine.get_audit_trail())
    }


@router.get("/tick-history")
async def get_tick_history():
    """
    Get tick history for visualization.

    Returns aggregated tick events for replay.
    """
    engine = get_agent_engine()
    return {
        "ticks": engine.get_tick_history(),
        "count": len(engine.get_tick_history())
    }
