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


@router.get("/health/services")
async def services_health() -> dict:
    """
    Detailed health check for all services.

    Returns status of:
    - ChromaDB (vector store)
    - LLM service (LM Studio)
    - Strategy Store (RAG)
    """
    from app.services.vector_store import get_vector_store
    from app.services.llm_service import get_llm_service
    from app.services.strategy_store import get_strategy_store

    services = {}
    overall_status = "healthy"

    # Check ChromaDB
    try:
        vector_store = await get_vector_store()
        chromadb_healthy = await vector_store.health_check()
        services["chromadb"] = {
            "status": "healthy" if chromadb_healthy else "degraded",
            "connected": chromadb_healthy
        }
        if not chromadb_healthy:
            overall_status = "degraded"
    except Exception as e:
        services["chromadb"] = {
            "status": "error",
            "error": str(e)
        }
        overall_status = "degraded"

    # Check LLM
    try:
        llm = get_llm_service()
        rate_status = llm.get_rate_limit_status()
        services["llm"] = {
            "status": "healthy",
            "rpm_limit": rate_status.get("rpm_limit", rate_status.get("limiter_max_rate")),
            "calls_last_minute": rate_status.get("calls_last_minute", rate_status.get("requests_made", 0))
        }
    except Exception as e:
        services["llm"] = {
            "status": "error",
            "error": str(e)
        }
        overall_status = "degraded"

    # Check Strategy Store
    try:
        store = await get_strategy_store()
        rules = await store.list_all_rules()
        services["strategy_store"] = {
            "status": "healthy",
            "rules_loaded": len(rules)
        }
    except Exception as e:
        services["strategy_store"] = {
            "status": "error",
            "error": str(e)
        }
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services
    }


