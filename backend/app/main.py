"""
ICT Trading Platform - FastAPI Backend Application

Main entry point for the API server.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.v1 import analysis, session, health, chat, execution, data, market_data
from app.api.v1 import agent, backtest, ai_chat, strategies
from app.api.v1.websocket import router as websocket_router

# Get settings
settings = get_settings()

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

# New LLM Agent endpoints
app.include_router(
    agent.router,
    prefix=settings.api_v1_prefix
)

# Smart Backtest endpoints
app.include_router(
    backtest.router,
    prefix=settings.api_v1_prefix
)

# AI Chat (RAG-powered)
app.include_router(
    ai_chat.router,
    prefix=settings.api_v1_prefix
)

# Strategy Management (add/remove rules)
app.include_router(
    strategies.router,
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
