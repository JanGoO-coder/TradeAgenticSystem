"""
Strategy Agent Models.

Input/Output schemas for the Strategy Agent (Analyst).
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from ..state import (
    BiasDirection, TradingSession, EnvironmentStatus,
    BiasAssessment, SessionLevels, EnvironmentCheck, MarketContext,
    OHLCV, EconomicEvent
)


# =============================================================================
# Request Models
# =============================================================================

class MarketContextRequest(BaseModel):
    """
    Request for market context analysis.

    Sent from Main Agent to Strategy Agent via ANALYZE_CONTEXT action.
    """
    symbol: str
    timestamp: datetime

    # OHLCV data by timeframe
    timeframe_bars: Dict[str, List[Dict[str, Any]]]  # {"1H": [...], "15M": [...]}

    # Economic calendar
    economic_calendar: List[EconomicEvent] = Field(default_factory=list)

    # Previous context (for continuity)
    previous_context: Optional[MarketContext] = None


# =============================================================================
# Response Models
# =============================================================================

class MarketContextResponse(BaseModel):
    """
    Response from Strategy Agent with full market context.

    Returned to Main Agent after ANALYZE_CONTEXT.
    """
    success: bool
    context: Optional[MarketContext] = None
    error: Optional[str] = None
    analysis_time_ms: float = 0.0


# =============================================================================
# Internal Analysis Models
# =============================================================================

class SwingPoint(BaseModel):
    """A detected swing high or low."""
    index: int
    price: float
    type: str  # "HIGH" or "LOW"
    timestamp: Optional[datetime] = None


class StructureAnalysis(BaseModel):
    """Market structure analysis result."""
    bias: BiasDirection
    structure_type: str  # "HH_HL", "LH_LL", "UNCLEAR"
    swing_highs: List[SwingPoint] = Field(default_factory=list)
    swing_lows: List[SwingPoint] = Field(default_factory=list)
    confidence: float = 0.0
    rule_refs: List[str] = Field(default_factory=list)


class SessionAnalysis(BaseModel):
    """Trading session analysis."""
    current_session: TradingSession
    killzone_active: bool
    killzone_name: Optional[str] = None
    silverbullet_active: bool
    time_until_next_kz: Optional[int] = None  # minutes
