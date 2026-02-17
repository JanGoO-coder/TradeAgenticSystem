"""
Agent Analysis API Endpoints.

New endpoints that use the hybrid LLM agent for market analysis.
Uses the ICT Architecture for market reasoning.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

from app.agent.main_agent import get_main_agent
from app.tools.observer import run_all_observations, run_event_observation
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
# ICT Architecture Request/Response Models
# ============================================================================

class ICTAnalyzeRequest(BaseModel):
    """Request for ICT architecture analysis."""
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    htf_candles: List[dict] = Field(..., description="Higher timeframe candles (1H)")
    ltf_candles: List[dict] = Field(..., description="Lower timeframe candles (15M)")
    timestamp: Optional[datetime] = Field(None, description="Analysis timestamp (defaults to now)")
    mode: Literal["verbose", "concise"] = Field("verbose", description="Reasoning mode")


class ICTDecisionResponse(BaseModel):
    """ICT Architecture decision response with validation."""
    decision: str
    confidence: float
    brief_reason: str
    rule_citations: List[str]
    setup: Optional[dict]
    latency_ms: int
    
    # ICT-specific fields
    phase: Optional[str]
    validated: bool
    veto_reasons: List[str]


class ICTAnalysisResponse(BaseModel):
    """Complete ICT analysis response."""
    symbol: str
    timestamp: str
    current_price: float
    events_count: int
    observation_summary: str
    decision: ICTDecisionResponse


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/analyze", response_model=ICTAnalysisResponse)
async def analyze_market(request: ICTAnalyzeRequest) -> ICTAnalysisResponse:
    """
    Run full ICT Architecture analysis on market data.

    This is the primary endpoint for analysis. It uses the full ICT pipeline:
    1. Event-based observer (factual events)
    2. Context manager with memory
    3. Phase detection (PO3)
    4. Decision validator (10 hard veto rules)
    5. Returns observation + validated decision
    """
    try:
        agent = await get_main_agent()

        observation, decision = await agent.analyze_ict(
            htf_candles=request.htf_candles,
            ltf_candles=request.ltf_candles,
            symbol=request.symbol,
            timestamp=request.timestamp,
            mode=request.mode
        )

        # Convert TradeSetup to dict if present
        setup_dict = None
        if decision.setup:
            setup = decision.setup
            setup_dict = {
                "direction": setup.direction,
                "entry": setup.entry_price,
                "stop_loss": setup.stop_loss,
                "take_profit": setup.take_profit,
                "entry_model": setup.entry_model,
                "pd_array_type": setup.pd_array_type
            }

        # Build decision response
        dec_response = ICTDecisionResponse(
            decision=decision.decision,
            confidence=decision.confidence,
            brief_reason=decision.brief_reason,
            rule_citations=decision.rule_citations,
            setup=setup_dict,
            latency_ms=decision.total_latency_ms,
            phase=decision.phase_at_decision,
            validated=decision.validation.approved if decision.validation else True,
            veto_reasons=[v.value for v in decision.validation.veto_reasons] if decision.validation else []
        )

        return ICTAnalysisResponse(
            symbol=observation.symbol,
            timestamp=observation.timestamp.isoformat(),
            current_price=observation.current_price,
            events_count=len(observation.events),
            observation_summary=observation.to_summary(),
            decision=dec_response
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/observe")
async def observe_market(request: ICTAnalyzeRequest) -> dict:
    """
    Run ICT event-based observation only (no agent reasoning).

    Returns factual market events without LLM decision.
    Useful for debugging the observer or fast market state checks.
    """
    try:
        observation = run_event_observation(
            htf_candles=request.htf_candles,
            ltf_candles=request.ltf_candles,
            symbol=request.symbol,
            timestamp=request.timestamp
        )

        return {
            "symbol": observation.symbol,
            "timestamp": observation.timestamp.isoformat(),
            "current_price": observation.current_price,
            "state_hash": observation.state_hash,
            "events_count": len(observation.events),
            "events": [str(e) for e in observation.events],
            "summary": observation.to_summary()
        }

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
