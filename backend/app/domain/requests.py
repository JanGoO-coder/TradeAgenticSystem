"""Domain models - API Request schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class OHLCVBar(BaseModel):
    """Single candlestick bar."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class EconomicEvent(BaseModel):
    """Economic calendar event."""
    event_name: str
    currency: str
    impact: str  # HIGH, MEDIUM, LOW
    time: str


class AnalysisRequest(BaseModel):
    """Request body for trade analysis endpoint."""
    symbol: str = Field(..., example="EURUSD")
    timestamp: str = Field(..., example="2026-01-21T14:00:00Z")
    timeframe_bars: Dict[str, List[Dict[str, Any]]] = Field(
        ..., 
        description="OHLCV bars keyed by timeframe: 1H, 15M, 5M"
    )
    account_balance: float = Field(..., ge=0, example=10000.0)
    risk_pct: float = Field(default=1.0, ge=0.1, le=10.0)
    session: Optional[str] = Field(default=None, description="London, NY, or Asia")
    economic_calendar: List[EconomicEvent] = Field(default=[])
    user_max_trades_per_session: Optional[int] = Field(default=None)


class BatchAnalysisRequest(BaseModel):
    """Request body for batch analysis endpoint."""
    snapshots: List[AnalysisRequest]


class ExplainRequest(BaseModel):
    """Request body for explanation endpoint."""
    analysis_id: Optional[str] = None
    setup_response: Optional[Dict[str, Any]] = None
