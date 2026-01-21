"""Data models for the ICT Trading System."""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class BiasValue(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class AlignmentStatus(str, Enum):
    ALIGNED = "ALIGNED"
    NOT_ALIGNED = "NOT_ALIGNED"


class TradeStatus(str, Enum):
    TRADE_NOW = "TRADE_NOW"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


class EntryType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    CONDITIONAL = "CONDITIONAL"


class HTFBias(BaseModel):
    value: BiasValue
    rule_refs: List[str]


class LTFAlignment(BaseModel):
    timeframe: Literal["15M", "5M"]
    alignment: AlignmentStatus
    rule_refs: List[str]


class TradeSetup(BaseModel):
    name: str
    type: str
    entry_price: Optional[float] = None
    entry_type: Optional[EntryType] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[List[float]] = None
    invalidation_point: Optional[float] = None
    is_counter_trend: bool = False
    confluence_score: int = Field(ge=0, le=10)
    rule_refs: List[str]


class RiskParameters(BaseModel):
    account_balance: float
    risk_pct: float
    position_size: float
    rr: Optional[float] = None


class ExecutionChecklist(BaseModel):
    htf_bias_exists: bool
    ltf_mss: bool
    pd_alignment: bool
    liquidity_sweep_detected: bool
    session_ok: bool
    news_ok: bool
    rr_minimum_met: bool


class TradeSetupResponse(BaseModel):
    """The complete Trade Setup Response per the output schema."""
    symbol: str
    timestamp: str
    status: TradeStatus
    reason_short: str
    htf_bias: HTFBias
    ltf_alignment: LTFAlignment
    setup: TradeSetup
    risk: RiskParameters
    checklist: ExecutionChecklist
    explanation: str
    graph_nodes_triggered: List[str]
    confidence: float = Field(ge=0, le=1)


class OHLCV(BaseModel):
    """Single candle data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class EconomicEvent(BaseModel):
    """Economic calendar event."""
    event_name: str
    currency: str
    impact: Literal["HIGH", "MEDIUM", "LOW"]
    time: datetime


class MarketSnapshot(BaseModel):
    """Input contract for the trading system."""
    symbol: str
    timestamp: str
    timeframe_bars: dict  # {"1H": [OHLCV], "15M": [OHLCV], "5M": [OHLCV]}
    account_balance: float
    risk_pct: float = 1.0
    session: Optional[Literal["London", "NY", "Asia"]] = None
    economic_calendar: List[EconomicEvent] = []
    user_max_trades_per_session: Optional[int] = None


class GraphState(BaseModel):
    """State object passed between LangGraph nodes."""
    # Input data
    snapshot: MarketSnapshot
    
    # Node outputs
    htf_bias: Optional[HTFBias] = None
    gatekeeper_status: Optional[Literal["GO", "WAIT"]] = None
    gatekeeper_failures: List[str] = []
    ltf_alignment: Optional[LTFAlignment] = None
    detected_setup: Optional[TradeSetup] = None
    risk_params: Optional[RiskParameters] = None
    checklist: Optional[ExecutionChecklist] = None
    
    # Tracking
    nodes_triggered: List[str] = []
    final_status: Optional[TradeStatus] = None
    reason_short: str = ""
    explanation: str = ""
    confidence: float = 0.0
