"""
Strategy API - Endpoints for strategy management.

Endpoints:
- GET /strategies - List available strategies
- GET /strategies/active - Get current active strategy
- POST /strategies/switch - Switch to a different strategy
- GET /debug/market-facts - Get last computed market facts
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import sys
import os

# Add agent path for imports
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
root_dir = os.path.dirname(backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

try:
    from agent.src.strategy_agent.agent import StrategyAgent
    from agent.src.protocol import MessageLog
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategies", tags=["strategies"])


# =============================================================================
# Response Models
# =============================================================================

class StrategyInfo(BaseModel):
    """Information about a strategy."""
    name: str
    is_active: bool


class StrategyListResponse(BaseModel):
    """Response for listing strategies."""
    active_strategy: str
    available_strategies: List[str]
    count: int


class ActiveStrategyResponse(BaseModel):
    """Response for getting active strategy."""
    name: str
    content: str


class SwitchStrategyRequest(BaseModel):
    """Request to switch strategy."""
    strategy_name: str


class SwitchStrategyResponse(BaseModel):
    """Response for strategy switch."""
    success: bool
    message: str
    new_strategy: Optional[str] = None


class MarketFactsResponse(BaseModel):
    """Response for market facts debug endpoint."""
    success: bool
    facts: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


# =============================================================================
# Singleton Agent Instance
# =============================================================================

# Lazy-loaded singleton for the Strategy Agent
_strategy_agent: Optional[StrategyAgent] = None


def get_strategy_agent() -> StrategyAgent:
    """Get or create the singleton StrategyAgent instance."""
    global _strategy_agent
    if _strategy_agent is None:
        if not AGENT_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Agent module not available. Check import paths."
            )
        _strategy_agent = StrategyAgent(message_log=MessageLog())
    return _strategy_agent


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=StrategyListResponse)
@router.get("/", response_model=StrategyListResponse)
async def list_strategies():
    """
    List all available strategies.
    
    Returns:
        List of strategy names with active status
    """
    try:
        agent = get_strategy_agent()
        available = agent.get_available_strategies()
        
        return StrategyListResponse(
            active_strategy="active_strategy",  # The default loaded strategy
            available_strategies=available,
            count=len(available)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=ActiveStrategyResponse)
async def get_active_strategy():
    """
    Get the currently active strategy content.
    
    Returns:
        Strategy name and full content
    """
    try:
        agent = get_strategy_agent()
        
        return ActiveStrategyResponse(
            name="active_strategy",
            content=agent.active_strategy
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get active strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch", response_model=SwitchStrategyResponse)
async def switch_strategy(request: SwitchStrategyRequest):
    """
    Switch to a different strategy.
    
    Args:
        request: Contains strategy_name to switch to
        
    Returns:
        Success status and message
    """
    try:
        agent = get_strategy_agent()
        
        # Validate strategy exists
        available = agent.get_available_strategies()
        if request.strategy_name not in available:
            raise HTTPException(
                status_code=404,
                detail=f"Strategy '{request.strategy_name}' not found. "
                       f"Available: {available}"
            )
        
        # Switch strategy
        success = agent.switch_strategy(request.strategy_name)
        
        if success:
            return SwitchStrategyResponse(
                success=True,
                message=f"Successfully switched to strategy: {request.strategy_name}",
                new_strategy=request.strategy_name
            )
        else:
            return SwitchStrategyResponse(
                success=False,
                message=f"Failed to switch to strategy: {request.strategy_name}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to switch strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Debug Endpoints
# =============================================================================

debug_router = APIRouter(prefix="/debug", tags=["debug"])


@debug_router.get("/market-facts", response_model=MarketFactsResponse)
async def get_market_facts():
    """
    Get the last computed market facts from the Strategy Agent.
    
    This is a debug endpoint to inspect what observations the agent
    is seeing from the market observers.
    
    Returns:
        Last computed market facts or message if none available
    """
    try:
        agent = get_strategy_agent()
        facts = agent.get_last_market_facts()
        
        if facts:
            return MarketFactsResponse(
                success=True,
                facts=facts
            )
        else:
            return MarketFactsResponse(
                success=True,
                facts=None,
                message="No market facts computed yet. Run an analysis first."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get market facts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/reasoning-schema")
async def get_reasoning_schema():
    """
    Get the expected schema for LLM reasoning output.
    
    Returns:
        JSON schema for DecisionSchema
    """
    try:
        from agent.src.strategy_agent.reasoning_engine import DecisionSchema
        return {
            "schema": DecisionSchema.model_json_schema(),
            "description": "Expected output format from LLM reasoning"
        }
    except Exception as e:
        logger.exception(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))
