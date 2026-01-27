"""
Worker Agent Models.

Input/Output schemas for the Worker Agent (Executor).
"""
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field

from ..state import (
    MarketContext, TradeSetup, Position, ClosedTrade,
    OrderDirection, OrderType, OHLCV
)


# =============================================================================
# Request Models
# =============================================================================

class SnapshotRequest(BaseModel):
    """
    Request for market data snapshot.

    Sent from Main Agent to Worker Agent via GET_SNAPSHOT action.
    """
    symbol: str
    timeframes: List[str] = Field(default_factory=lambda: ["1H", "15M", "5M"])
    bars_per_timeframe: int = 100
    include_news: bool = True
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class SetupScanRequest(BaseModel):
    """
    Request to scan for trade setups.

    Sent from Main Agent to Worker Agent via SCAN_SETUPS action.
    """
    symbol: str
    timestamp: datetime
    timeframe_bars: Dict[str, List[Dict[str, Any]]]
    market_context: MarketContext
    enabled_models: List[str] = Field(
        default_factory=lambda: ["ICT_2022", "OTE", "FVG", "SILVERBULLET"]
    )


class ExecutionRequest(BaseModel):
    """
    Request to execute a trade.

    Sent from Main Agent to Worker Agent via EXECUTE_ORDER action.
    """
    symbol: str
    direction: OrderDirection
    order_type: OrderType = OrderType.LIMIT
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: Optional[float] = None  # Auto-calculated if None
    setup_name: str
    risk_pct: float = 1.0
    agent_analysis: Optional[Dict[str, Any]] = None


class ClosePositionRequest(BaseModel):
    """
    Request to close a position.

    Sent from Main Agent to Worker Agent via CLOSE_POSITION action.
    """
    position_id: str
    reason: str = "MANUAL"


class AdvanceTimeRequest(BaseModel):
    """
    Request to advance simulation time.

    Sent from Main Agent to Worker Agent via ADVANCE_TIME action.
    """
    bars: int = 1
    check_tp_sl: bool = True


# =============================================================================
# Response Models
# =============================================================================

class SnapshotResponse(BaseModel):
    """
    Response with market data snapshot.
    """
    success: bool
    symbol: str
    timestamp: datetime
    timeframe_bars: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    economic_events: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class SetupScanResponse(BaseModel):
    """
    Response with detected trade setups.
    """
    success: bool
    setups: List[TradeSetup] = Field(default_factory=list)
    scan_time_ms: float = 0.0
    error: Optional[str] = None


class ExecutionResponse(BaseModel):
    """
    Response confirming trade execution.
    """
    success: bool
    position: Optional[Position] = None
    calculated_volume: Optional[float] = None
    message: str = ""
    error: Optional[str] = None


class ClosePositionResponse(BaseModel):
    """
    Response confirming position closure.
    """
    success: bool
    trade: Optional[ClosedTrade] = None
    message: str = ""
    error: Optional[str] = None


class AdvanceTimeResponse(BaseModel):
    """
    Response after advancing simulation time.
    """
    success: bool
    new_time: datetime
    bars_advanced: int
    progress_pct: float
    has_more: bool
    auto_closed_trades: List[ClosedTrade] = Field(default_factory=list)
    error: Optional[str] = None


# =============================================================================
# Internal Analysis Models
# =============================================================================

class FVGResult(BaseModel):
    """Fair Value Gap detection result."""
    type: Literal["BULLISH_FVG", "BEARISH_FVG"]
    index: int
    top: float
    bottom: float
    midpoint: float
    rule_refs: List[str] = Field(default_factory=lambda: ["5.2", "6.2"])


class SweepResult(BaseModel):
    """Liquidity sweep detection result."""
    type: Literal["SELL_SIDE_SWEEP", "BUY_SIDE_SWEEP"]
    swing_price: float
    sweep_price: float
    candle_index: int
    rule_refs: List[str] = Field(default_factory=lambda: ["3.1", "3.4"])


class MSSResult(BaseModel):
    """Market Structure Shift detection result."""
    type: Literal["BULLISH_MSS", "BEARISH_MSS"]
    break_level: float
    close_price: float
    rule_refs: List[str] = Field(default_factory=lambda: ["2.3", "2.2"])


class OTEZone(BaseModel):
    """Optimal Trade Entry zone."""
    direction: OrderDirection
    zone_top: float
    zone_mid: float  # 70.5% level
    zone_bottom: float
    rule_refs: List[str] = Field(default_factory=lambda: ["6.1"])


class PDZone(BaseModel):
    """Premium/Discount zone."""
    zone: Literal["PREMIUM", "DISCOUNT", "EQUILIBRIUM"]
    level: float  # 0-1 position
    favorable: bool
    rule_refs: List[str] = Field(default_factory=lambda: ["5.1"])


class TurtleSoupResult(BaseModel):
    """
    Turtle Soup pattern detection result.

    Linda Bradford Raschke's "Turtle Soup" pattern:
    - Price takes out a recent swing high/low (stop run)
    - Quick reversal back inside the previous range
    - Entry on the failure of the breakout

    This is a counter-trend reversal setup.
    """
    type: Literal["TURTLE_SOUP_LONG", "TURTLE_SOUP_SHORT"]
    swing_taken: float  # The swing level that was taken out
    sweep_extreme: float  # The extreme price of the false breakout
    close_back: float  # The close price back inside range
    candle_index: int
    lookback_period: int  # How many bars back the swing was
    reversal_strength: float  # 0-1 measure of reversal quality
    rule_refs: List[str] = Field(default_factory=lambda: ["3.4", "2.3", "6.7"])
