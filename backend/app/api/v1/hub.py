"""Agentic ICT hub API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.domain.hub import (
    HubDecisionRequest,
    HubDecisionResponse,
    HubJournalEntry,
    HubJournalResponse,
    HubStateResponse,
)
from app.hub.master_agent import get_master_agent

router = APIRouter(prefix="/hub", tags=["Hub"])


@router.post("/decision", response_model=HubDecisionResponse)
async def get_hub_decision(request: HubDecisionRequest) -> HubDecisionResponse:
    """Run a single master-agent decision cycle."""

    agent = await get_master_agent()
    return await agent.decision_cycle(request)


@router.get("/state/{symbol}", response_model=HubStateResponse)
async def get_hub_state(symbol: str) -> HubStateResponse:
    """Get compact per-symbol hub state."""

    agent = await get_master_agent()
    return HubStateResponse(symbol=symbol, state=agent.get_state(symbol))


@router.get("/journal/{symbol}", response_model=HubJournalResponse)
async def get_hub_journal(symbol: str, limit: int = Query(100, ge=1, le=1000)) -> HubJournalResponse:
    """Get persisted hub journal entries for a symbol."""

    agent = await get_master_agent()
    entries = [HubJournalEntry(**entry) for entry in agent.get_journal(symbol, limit=limit)]
    return HubJournalResponse(symbol=symbol, count=len(entries), entries=entries)


@router.post("/reset/{symbol}")
async def reset_hub_symbol(symbol: str, balance: float | None = None) -> dict:
    """Reset hub state + risk/journal for a symbol."""

    agent = await get_master_agent()
    return agent.reset_symbol(symbol, balance=balance)
