"""Health check API endpoint."""
from fastapi import APIRouter, Depends
from datetime import datetime

from app.domain.responses import HealthResponse
from app.agent.engine import get_agent_engine, TradingAgentEngine
from app.core.config import get_settings, Settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    engine: TradingAgentEngine = Depends(get_agent_engine),
    settings: Settings = Depends(get_settings)
) -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
    - API status
    - Agent availability
    - Current execution mode
    """
    return HealthResponse(
        status="healthy",
        agent_available=engine.is_available,
        mode=settings.execution_mode,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
