"""Domain models - API Response schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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


class HTFBiasResponse(BaseModel):
    """HTF bias information."""
    value: BiasValue
    rule_refs: List[str]


class LTFAlignmentResponse(BaseModel):
    """LTF alignment information."""
    timeframe: str
    alignment: AlignmentStatus
    rule_refs: List[str]


class SetupResponse(BaseModel):
    """Trade setup details."""
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


class RiskResponse(BaseModel):
    """Risk calculation details."""
    account_balance: float
    risk_pct: float
    position_size: float
    rr: Optional[float] = None


class ChecklistResponse(BaseModel):
    """Execution checklist."""
    htf_bias_exists: bool
    ltf_mss: bool
    pd_alignment: bool
    liquidity_sweep_detected: bool
    session_ok: bool
    news_ok: bool
    rr_minimum_met: bool


class TradeSetupResponse(BaseModel):
    """Complete trade setup response from agent."""
    symbol: str
    timestamp: str
    status: TradeStatus
    reason_short: str
    htf_bias: HTFBiasResponse
    ltf_alignment: LTFAlignmentResponse
    setup: SetupResponse
    risk: RiskResponse
    checklist: ChecklistResponse
    explanation: str
    graph_nodes_triggered: List[str]
    confidence: float = Field(ge=0, le=1)


class SessionInfoResponse(BaseModel):
    """Current session information."""
    session: str  # London, NY, Asia
    kill_zone_active: bool
    kill_zone_name: Optional[str] = None
    time_until_next_zone: Optional[int] = None  # seconds
    current_time_utc: str
    current_time_est: str


class KillZoneStatusResponse(BaseModel):
    """Kill zone status."""
    in_kill_zone: bool
    session: Optional[str] = None
    rule_refs: List[str]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    agent_available: bool
    mode: str
    timestamp: str


class RuleDefinition(BaseModel):
    """Rule definition for introspection."""
    id: str
    name: str
    category: str
    description: str
    when_valid: str
    when_invalid: str


class ExplanationNode(BaseModel):
    """Single node in explanation tree."""
    rule_id: str
    rule_name: str
    passed: bool
    reason: str
    blocking: bool = False


class ExplanationResponse(BaseModel):
    """Full explanation of a trade decision."""
    decision: TradeStatus
    nodes: List[ExplanationNode]
    summary: str
