"""
Agent Analysis API Endpoints.

New endpoints that use the hybrid LLM agent for market analysis.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

from app.agent.main_agent import get_main_agent
from app.tools.observer import run_all_observations
from app.services.strategy_store import get_strategy_store, reindex_strategies

router = APIRouter(prefix="/agent", tags=["Agent Analysis"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeRequest(BaseModel):
    """Request for agent analysis."""
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    htf_candles: List[dict] = Field(..., description="Higher timeframe candles (1H)")
    ltf_candles: List[dict] = Field(..., description="Lower timeframe candles (15M)")
    micro_candles: Optional[List[dict]] = Field(None, description="Micro timeframe candles (5M)")
    timestamp: Optional[datetime] = Field(None, description="Analysis timestamp (defaults to now)")
    mode: Literal["verbose", "concise"] = Field("verbose", description="Reasoning mode")


class ObservationResponse(BaseModel):
    """Market observation response."""
    symbol: str
    timestamp: str
    current_price: float
    summary: str
    state_hash: str

    # Key observations
    htf_bias: dict
    ltf_alignment: dict
    session: dict
    killzone: dict

    # Details
    sweeps: List[dict]
    fvgs: List[dict]
    premium_discount: dict


class DecisionResponse(BaseModel):
    """Agent decision response."""
    decision: str
    confidence: float
    reasoning: Optional[str]
    brief_reason: str
    rule_citations: List[str]
    setup: Optional[dict]
    latency_ms: int
    mode: str


class FullAnalysisResponse(BaseModel):
    """Complete analysis response with observation and decision."""
    observation: ObservationResponse
    decision: DecisionResponse


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/analyze", response_model=FullAnalysisResponse)
async def analyze_market(request: AnalyzeRequest) -> FullAnalysisResponse:
    """
    Run full agent analysis on market data.

    This is the primary endpoint for the hybrid agent. It:
    1. Runs all observation tools on the provided candles
    2. Retrieves relevant strategies via RAG
    3. Calls Gemini to reason and decide
    4. Returns observation + decision with reasoning
    """
    try:
        agent = await get_main_agent()

        observation, decision = await agent.analyze_snapshot(
            htf_candles=request.htf_candles,
            ltf_candles=request.ltf_candles,
            symbol=request.symbol,
            timestamp=request.timestamp,
            mode=request.mode,
            micro_candles=request.micro_candles
        )

        # Build response
        obs_response = ObservationResponse(
            symbol=observation.symbol,
            timestamp=observation.timestamp.isoformat(),
            current_price=observation.current_price,
            summary=observation.to_summary(),
            state_hash=observation.state_hash,
            htf_bias=observation.htf_bias,
            ltf_alignment=observation.ltf_alignment,
            session=observation.session,
            killzone=observation.killzone,
            sweeps=observation.sweeps,
            fvgs=observation.fvgs,
            premium_discount=observation.premium_discount
        )

        dec_response = DecisionResponse(
            decision=decision.decision,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
            brief_reason=decision.brief_reason,
            rule_citations=decision.rule_citations,
            setup=decision.setup,
            latency_ms=decision.latency_ms,
            mode=decision.mode
        )

        return FullAnalysisResponse(
            observation=obs_response,
            decision=dec_response
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/observe", response_model=ObservationResponse)
async def observe_market(request: AnalyzeRequest) -> ObservationResponse:
    """
    Run observation tools only (no agent reasoning).

    Useful for:
    - Debugging tool output
    - Fast market state checks
    - When you don't need a decision
    """
    try:
        observation = run_all_observations(
            htf_candles=request.htf_candles,
            ltf_candles=request.ltf_candles,
            symbol=request.symbol,
            timestamp=request.timestamp,
            micro_candles=request.micro_candles
        )

        return ObservationResponse(
            symbol=observation.symbol,
            timestamp=observation.timestamp.isoformat(),
            current_price=observation.current_price,
            summary=observation.to_summary(),
            state_hash=observation.state_hash,
            htf_bias=observation.htf_bias,
            ltf_alignment=observation.ltf_alignment,
            session=observation.session,
            killzone=observation.killzone,
            sweeps=observation.sweeps,
            fvgs=observation.fvgs,
            premium_discount=observation.premium_discount
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain")
async def explain_decision(
    decision: DecisionResponse,
    observation_summary: str
) -> dict:
    """
    Get detailed explanation for a decision.

    Use this when you have a concise decision and want more details.
    """
    # This would call agent.explain_decision() with proper observation
    # For now, return the reasoning if available
    if decision.reasoning:
        return {"explanation": decision.reasoning}

    return {
        "explanation": (
            f"Decision: {decision.decision} ({decision.confidence:.0%} confidence)\n\n"
            f"Reason: {decision.brief_reason}\n\n"
            f"Rules Applied: {', '.join(decision.rule_citations) if decision.rule_citations else 'None'}"
        )
    }


# ============================================================================
# Strategy Endpoints
# ============================================================================

@router.get("/strategies")
async def list_strategies() -> dict:
    """
    List all loaded strategy files.
    """
    try:
        store = await get_strategy_store()
        rules = await store.list_all_rules()

        return {
            "rule_count": len(rules),
            "rules": sorted(rules),
            "collection": store.settings.strategy_collection
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/search")
async def search_strategies(
    query: str = Query(..., description="Search query"),
    k: int = Query(5, description="Number of results")
) -> dict:
    """
    Semantic search over strategies.
    """
    try:
        store = await get_strategy_store()
        results = await store.search_strategies(query, k=k)

        return {
            "query": query,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/rule/{rule_id}")
async def get_rule(rule_id: str) -> dict:
    """
    Get a specific rule by ID.
    """
    try:
        store = await get_strategy_store()
        rule = await store.get_rule(rule_id)

        if not rule:
            raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

        return rule
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategies/reindex")
async def reindex_all_strategies() -> dict:
    """
    Force reindex all strategy files.

    Use this after modifying markdown files.
    """
    try:
        await reindex_strategies()

        store = await get_strategy_store()
        rules = await store.list_all_rules()

        return {
            "message": "Reindexing complete",
            "rule_count": len(rules)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Rate Limit Status
# ============================================================================

@router.get("/rate-limit/status")
async def get_rate_limit_status() -> dict:
    """
    Get current rate limiting status.
    """
    from app.services.llm_service import get_gemini_service

    service = get_gemini_service()
    return service.get_rate_limit_status()
