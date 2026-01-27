"""
ICT Trading Platform - FastAPI Backend Application

Main entry point for the API server.
"""
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import AgentReliabilityException
from app.api.v1 import analysis, session, health, chat, execution, data, market_data, rules
from app.api.v1.websocket import router as websocket_router
from app.api.v1.strategies import router as strategies_router, debug_router

# Get settings
settings = get_settings()

# Create data directories on startup
def create_data_directories():
    """Ensure all data directories exist."""
    directories = [
        settings.data_dir,
        settings.tick_cache_dir,
        settings.sessions_dir,
    ]
    for dir_path in directories:
        os.makedirs(dir_path, exist_ok=True)

create_data_directories()

# Create FastAPI app
app = FastAPI(
    title=settings.project_name,
    description="API for the ICT Agentic Trading System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(AgentReliabilityException)
async def agent_reliability_exception_handler(request: Request, exc: AgentReliabilityException):
    """Handle Agent Reliability Exceptions with structured JSON."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code, 
            "message": exc.detail,
            "success": False
        },
    )

# Include routers
app.include_router(
    analysis.router,
    prefix=settings.api_v1_prefix
)
app.include_router(
    session.router,
    prefix=settings.api_v1_prefix
)
app.include_router(
    health.router,
    prefix=settings.api_v1_prefix
)
app.include_router(
    chat.router,
    prefix=settings.api_v1_prefix
)
# WebSocket router (no prefix needed)
app.include_router(websocket_router)
# Execution router
app.include_router(
    execution.router,
    prefix=settings.api_v1_prefix
)
# Data configuration router
app.include_router(
    data.router,
    prefix=settings.api_v1_prefix
)
# Market data / MT5 router
app.include_router(
    market_data.router,
    prefix=settings.api_v1_prefix
)
# Rules configuration router (hot-reload support)
app.include_router(
    rules.router,
    prefix=settings.api_v1_prefix
)
# Strategy management router (Phase 5)
app.include_router(
    strategies_router,
    prefix=settings.api_v1_prefix
)
# Debug endpoints router (Phase 5)
app.include_router(
    debug_router,
    prefix=settings.api_v1_prefix
)



@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.project_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
