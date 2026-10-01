"""Domain models for the agentic ICT trading hub."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


HubStatus = Literal["pending", "active", "no-trade"]


class HubOpenTrade(BaseModel):
    """Open trade snapshot used by the hub risk engine."""

    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry: float
    stop_loss: float
    take_profit: Optional[float] = None
    current_price: Optional[float] = None
    opened_at: Optional[datetime] = None
    moved_to_be: bool = False
    trailing_active: bool = False


class HubDecisionRequest(BaseModel):
    """Single-cycle decision input for the master hub agent."""

    symbol: str = Field(..., examples=["EURUSD"])
    timestamp: Optional[datetime] = None
    timeframe_bars: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Candles keyed by timeframe. Supports D1/H4/H1/M15/M5/M1 and aliases.",
    )
    account_balance: float = Field(default=10_000.0, gt=0)
    risk_pct: Optional[float] = Field(default=None, ge=0.1, le=5.0)
    economic_calendar: List[Dict[str, Any]] = Field(default_factory=list)
    open_trades: List[HubOpenTrade] = Field(default_factory=list)
    force_recompute: bool = False


class HubCallMetrics(BaseModel):
    """Per-cycle efficiency metrics."""

    llm_calls: int = 0
    subagent_calls: int = 0
    tool_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


class HubDecisionResponse(BaseModel):
    """Master hub decision output contract."""

    symbol: str
    timestamp: str
    bias: str = "neutral"
    draw: str = "none"
    poi: Optional[str] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    rr: Optional[float] = None
    size: Optional[float] = None
    session: str = "outside-killzone"
    status: HubStatus = "no-trade"
    reason: str
    confluences: List[str] = Field(default_factory=list)
    vetoes: List[str] = Field(default_factory=list)
    llm_called: bool = False
    cache_hit: bool = False
    journal_id: Optional[str] = None
    call_metrics: HubCallMetrics = Field(default_factory=HubCallMetrics)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HubStateResponse(BaseModel):
    """State snapshot payload for diagnostics/monitoring."""

    symbol: str
    state: Dict[str, Any]


class HubJournalEntry(BaseModel):
    """Journal event persisted per symbol."""

    journal_id: str
    timestamp: str
    symbol: str
    status: HubStatus
    reason: str
    bias: str
    session: str
    confluences: List[str] = Field(default_factory=list)
    vetoes: List[str] = Field(default_factory=list)
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    rr: Optional[float] = None
    size: Optional[float] = None
    llm_called: bool = False
    cache_hit: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HubJournalResponse(BaseModel):
    """Journal list response."""

    symbol: str
    count: int
    entries: List[HubJournalEntry]
