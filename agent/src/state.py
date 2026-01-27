"""
Core State Models for Hierarchical Agent Architecture.

This module defines the canonical state models used across all agents:
- SessionState: Main Agent's session tracking
- MarketContext: Strategy Agent's output
- TradeSetup: Worker Agent's detected pattern
- VirtualClock: Simulation time control
"""
from enum import Enum
from typing import Dict, List, Literal, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class BiasDirection(str, Enum):
    """Directional bias from HTF analysis."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SessionPhase(str, Enum):
    """Main Agent state machine phases."""
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    DECIDING = "DECIDING"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"


class EnvironmentStatus(str, Enum):
    """Trading environment status from Strategy Agent."""
    GO = "GO"          # All conditions met
    WAIT = "WAIT"      # Temporary block (news, off-hours)
    NO_TRADE = "NO_TRADE"  # Structure invalidated


class TradingSession(str, Enum):
    """Active trading session."""
    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OFF_HOURS = "OFF_HOURS"


class OrderDirection(str, Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    """Order execution type."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TradeResult(str, Enum):
    """Closed trade result."""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


# =============================================================================
# Market Data Models
# =============================================================================

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


# =============================================================================
# Strategy Agent Output: Market Context
# =============================================================================

class BiasAssessment(BaseModel):
    """HTF bias assessment from Strategy Agent (Rule 1.1)."""
    direction: BiasDirection
    confidence: float = Field(ge=0, le=1)
    rationale: str
    rule_refs: List[str] = Field(default_factory=list)


class SessionLevels(BaseModel):
    """Key price levels tracked by Strategy Agent."""
    # Previous Day (Rule 3.1)
    pdh: Optional[float] = None  # Previous Day High
    pdl: Optional[float] = None  # Previous Day Low

    # Session Opens
    midnight_open: Optional[float] = None  # 00:00 EST

    # Asian Session
    asian_high: Optional[float] = None
    asian_low: Optional[float] = None

    # London Session
    london_high: Optional[float] = None
    london_low: Optional[float] = None

    # NY Session
    ny_high: Optional[float] = None
    ny_low: Optional[float] = None

    # Current Kill Zone
    killzone_high: Optional[float] = None
    killzone_low: Optional[float] = None


class EnvironmentCheck(BaseModel):
    """Environment assessment from Strategy Agent."""
    status: EnvironmentStatus
    session: TradingSession
    killzone_active: bool
    killzone_name: Optional[str] = None
    news_clear: bool
    silverbullet_active: bool
    blocked_reasons: List[str] = Field(default_factory=list)


class MarketContext(BaseModel):
    """
    Complete market context from Strategy Agent.

    This is the output of ANALYZE_CONTEXT action.
    """
    # Bias Assessment (Rule 1.1)
    bias: BiasAssessment

    # Environment Check (Rules 8.1, 8.4, 6.6)
    environment: EnvironmentCheck

    # Key Levels (Rules 3.1, etc.)
    levels: SessionLevels

    # Validity
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None  # Context expires after N candles

    def is_valid(self, current_time: datetime) -> bool:
        """Check if context is still valid."""
        if self.valid_until is None:
            return True
        return current_time <= self.valid_until


# =============================================================================
# Worker Agent Output: Trade Setup
# =============================================================================

class TradeSetup(BaseModel):
    """
    Detected trade setup from Worker Agent.

    This is the output of SCAN_SETUPS action.
    """
    # Model Identification
    model_name: str  # "ICT_2022", "OTE", "SILVERBULLET", "FVG_ENTRY"
    model_type: str  # Category: "ENTRY", "CONTINUATION", "REVERSAL"

    # Entry Details
    entry_price: float
    entry_type: OrderType = OrderType.LIMIT
    direction: OrderDirection

    # Risk Management (Rules 7.1, 7.2)
    stop_loss: float
    take_profit: float
    risk_reward: float

    # Validation
    confidence: float = Field(ge=0, le=1)
    confluence_score: int = Field(ge=0, le=10)
    confluence_factors: List[str] = Field(default_factory=list)
    rationale: str = ""
    rule_refs: List[str] = Field(default_factory=list)

    # Timing
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None

    def is_valid(self, current_time: datetime) -> bool:
        """Check if setup is still valid."""
        if self.valid_until is None:
            return True
        return current_time <= self.valid_until


# =============================================================================
# Position & Trade Models
# =============================================================================

class Position(BaseModel):
    """
    Open position being monitored.

    Unified model for both live MT5 and backtest positions.
    Extended fields support backtest-specific tracking while
    remaining compatible with live trading.
    """
    id: str
    symbol: str
    direction: OrderDirection
    entry_price: float
    volume: float
    stop_loss: float
    take_profit: float
    opened_at: datetime
    setup_name: str
    unrealized_pnl: float = 0.0

    # Extended fields for backtest compatibility
    current_price: Optional[float] = None  # Current market price
    unrealized_pips: Optional[float] = None  # P&L in pips
    entry_bar_index: Optional[int] = None  # Bar index at entry (backtest)
    spread_at_entry: Optional[float] = None  # Spread when position opened
    entry_timestamp: Optional[datetime] = None  # Precise entry time (tick-level)
    agent_analysis: Optional[Dict[str, Any]] = None  # AI rationale reference

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "volume": self.volume,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "opened_at": self.opened_at.isoformat() if isinstance(self.opened_at, datetime) else self.opened_at,
            "setup_name": self.setup_name,
            "unrealized_pnl": self.unrealized_pnl,
            "current_price": self.current_price,
            "unrealized_pips": self.unrealized_pips,
            "entry_bar_index": self.entry_bar_index,
            "spread_at_entry": self.spread_at_entry,
            "agent_analysis": self.agent_analysis,
        }


class ClosedTrade(BaseModel):
    """
    Completed trade record.

    Unified model for both live MT5 and backtest closed trades.
    Extended fields support backtest-specific tracking and
    accurate tick-level exit timing.
    """
    id: str
    symbol: str
    direction: OrderDirection
    entry_price: float
    exit_price: float
    volume: float
    stop_loss: float
    take_profit: float
    opened_at: datetime
    closed_at: datetime
    setup_name: str
    pnl_pips: float
    pnl_usd: float
    pnl_rr: float
    result: TradeResult
    close_reason: str

    # Extended fields for backtest compatibility
    entry_bar_index: Optional[int] = None  # Bar index at entry
    exit_bar_index: Optional[int] = None  # Bar index at exit
    exit_timestamp: Optional[datetime] = None  # Precise exit time (tick-level)
    spread_at_entry: Optional[float] = None  # Spread when opened
    agent_analysis: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "volume": self.volume,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "opened_at": self.opened_at.isoformat() if isinstance(self.opened_at, datetime) else self.opened_at,
            "closed_at": self.closed_at.isoformat() if isinstance(self.closed_at, datetime) else self.closed_at,
            "setup_name": self.setup_name,
            "pnl_pips": self.pnl_pips,
            "pnl_usd": self.pnl_usd,
            "pnl_rr": self.pnl_rr,
            "result": self.result.value,
            "close_reason": self.close_reason,
            "entry_bar_index": self.entry_bar_index,
            "exit_bar_index": self.exit_bar_index,
            "agent_analysis": self.agent_analysis,
        }


# =============================================================================
# Main Agent: Session State
# =============================================================================

class SessionState(BaseModel):
    """
    Master state object managed by Main Agent.

    Tracks the complete lifecycle of a trading session.
    """
    # Identity
    session_id: str
    symbol: str
    mode: Literal["LIVE", "BACKTEST"]

    # Clock
    current_time: datetime
    simulation_speed: float = 1.0  # Candles per second in replay

    # Phase (State Machine)
    phase: SessionPhase = SessionPhase.IDLE

    # Context (from Strategy Agent)
    market_context: Optional[MarketContext] = None

    # Detected Setup (from Worker Agent)
    current_setup: Optional[TradeSetup] = None
    pending_setups: List[TradeSetup] = Field(default_factory=list)

    # Positions
    open_positions: List[Position] = Field(default_factory=list)
    closed_trades: List[ClosedTrade] = Field(default_factory=list)

    # Metrics
    starting_balance: float
    balance: float
    equity: float
    total_pnl: float = 0.0
    win_count: int = 0
    loss_count: int = 0

    # Session Limits
    trades_this_session: int = 0
    max_trades_per_session: int = 2

    # Audit Trail (IDs reference MessageLog)
    message_ids: List[str] = Field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        total = self.win_count + self.loss_count
        return (self.win_count / total * 100) if total > 0 else 0.0

    @property
    def can_trade(self) -> bool:
        """Check if session can take more trades."""
        if self.max_trades_per_session == 0:  # Unlimited
            return True
        return self.trades_this_session < self.max_trades_per_session


# =============================================================================
# Virtual Clock (Simulation Time Control)
# =============================================================================

class VirtualClock:
    """
    Simulation clock for candle-by-candle time advancement.

    Used by Main Agent to control backtest progression.
    """

    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        timeframe: str = "5M"
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.current = start_time
        self.timeframe = timeframe
        self._tick_count = 0

        # Parse timeframe to minutes
        self._minutes_per_bar = self._parse_timeframe(timeframe)

    def _parse_timeframe(self, tf: str) -> int:
        """Convert timeframe string to minutes."""
        tf = tf.upper()
        if tf.endswith("M"):
            return int(tf[:-1])
        elif tf.endswith("H"):
            return int(tf[:-1]) * 60
        elif tf.endswith("D"):
            return int(tf[:-1]) * 1440
        return 5  # Default to 5M

    def advance(self, bars: int = 1) -> datetime:
        """
        Move forward by N candles.

        Returns:
            New current timestamp
        """
        delta = timedelta(minutes=self._minutes_per_bar * bars)
        self.current = min(self.current + delta, self.end_time)
        self._tick_count += bars
        return self.current

    def set_time(self, time: datetime) -> datetime:
        """Set current time directly."""
        self.current = max(self.start_time, min(time, self.end_time))
        return self.current

    def is_complete(self) -> bool:
        """Check if simulation has reached end."""
        return self.current >= self.end_time

    @property
    def progress(self) -> float:
        """Get progress percentage (0-100)."""
        total = (self.end_time - self.start_time).total_seconds()
        elapsed = (self.current - self.start_time).total_seconds()
        return (elapsed / total * 100) if total > 0 else 100.0

    @property
    def tick_count(self) -> int:
        """Get number of ticks elapsed."""
        return self._tick_count

    def reset(self) -> None:
        """Reset clock to start time."""
        self.current = self.start_time
        self._tick_count = 0


# =============================================================================
# Backward Compatibility Aliases (Temporary)
# =============================================================================

# These will be removed after full migration
BiasValue = BiasDirection
AlignmentStatus = Literal["ALIGNED", "NOT_ALIGNED"]
TradeStatus = Literal["TRADE_NOW", "WAIT", "NO_TRADE"]
EntryType = OrderType
