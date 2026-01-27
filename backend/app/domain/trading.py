"""Domain models for MT5 trading operations."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class OrderType(str, Enum):
    """MT5 order types."""
    MARKET_BUY = "MARKET_BUY"
    MARKET_SELL = "MARKET_SELL"
    BUY_LIMIT = "BUY_LIMIT"
    SELL_LIMIT = "SELL_LIMIT"
    BUY_STOP = "BUY_STOP"
    SELL_STOP = "SELL_STOP"


class PositionType(str, Enum):
    """Position direction type."""
    BUY = "BUY"
    SELL = "SELL"


class TradeDirection(str, Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


# ==================== Account Models ====================

class AccountInfo(BaseModel):
    """MT5 account information."""
    balance: float = Field(..., description="Account balance")
    equity: float = Field(..., description="Account equity")
    margin: float = Field(..., description="Used margin")
    free_margin: float = Field(..., description="Available margin")
    margin_level: Optional[float] = Field(None, description="Margin level percentage")
    profit: float = Field(..., description="Current floating P&L")
    currency: str = Field(..., description="Account currency")
    leverage: int = Field(..., description="Account leverage")
    name: Optional[str] = Field(None, description="Account holder name")
    server: Optional[str] = Field(None, description="Broker server")
    trade_allowed: bool = Field(True, description="Whether trading is allowed")


# ==================== Order Models ====================

class OrderRequest(BaseModel):
    """Request to place a new order."""
    symbol: str = Field(..., description="Trading symbol", example="EURUSD")
    order_type: OrderType = Field(..., description="Type of order")
    volume: Optional[float] = Field(None, ge=0.01, description="Lot size (None = calculate from risk)")
    price: Optional[float] = Field(None, description="Price for pending orders")
    stop_loss: float = Field(..., gt=0, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    comment: str = Field("", max_length=31, description="Order comment")
    magic: int = Field(12345, description="Magic number for identification")
    deviation: int = Field(20, description="Max price deviation in points")

    # Risk-based sizing
    risk_pct: Optional[float] = Field(None, ge=0.1, le=10.0, description="Risk percentage for auto lot sizing")
    account_balance: Optional[float] = Field(None, description="Account balance for risk calculation")


class OrderResponse(BaseModel):
    """Response after order execution."""
    success: bool = Field(..., description="Whether order was successful")
    ticket: Optional[int] = Field(None, description="Order ticket number")
    order_type: str = Field(..., description="Order type executed")
    symbol: str = Field(..., description="Trading symbol")
    volume: float = Field(..., description="Executed volume")
    price: float = Field(..., description="Execution price")
    stop_loss: float = Field(..., description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    error_code: Optional[int] = Field(None, description="MT5 error code if failed")
    error_message: Optional[str] = Field(None, description="Error description")
    execution_time: Optional[str] = Field(None, description="Execution timestamp")


class PendingOrder(BaseModel):
    """A pending order in MT5."""
    ticket: int = Field(..., description="Order ticket")
    symbol: str = Field(..., description="Trading symbol")
    order_type: str = Field(..., description="Order type")
    volume: float = Field(..., description="Order volume")
    price: float = Field(..., description="Order price")
    stop_loss: float = Field(..., description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    time_setup: str = Field(..., description="Order creation time")
    magic: int = Field(..., description="Magic number")
    comment: str = Field("", description="Order comment")


class ModifyOrderRequest(BaseModel):
    """Request to modify a pending order."""
    ticket: int = Field(..., description="Order ticket to modify")
    price: Optional[float] = Field(None, description="New order price")
    stop_loss: Optional[float] = Field(None, description="New stop loss")
    take_profit: Optional[float] = Field(None, description="New take profit")


# ==================== Position Models ====================

class Position(BaseModel):
    """An open position in MT5."""
    ticket: int = Field(..., description="Position ticket")
    symbol: str = Field(..., description="Trading symbol")
    type: str = Field(..., description="Position type (BUY/SELL)")
    volume: float = Field(..., description="Position volume")
    open_price: float = Field(..., description="Entry price")
    current_price: float = Field(..., description="Current market price")
    stop_loss: float = Field(..., description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    profit: float = Field(..., description="Current unrealized P&L")
    swap: float = Field(0.0, description="Swap charges")
    commission: float = Field(0.0, description="Commission")
    open_time: str = Field(..., description="Position open time")
    magic: int = Field(..., description="Magic number")
    comment: str = Field("", description="Position comment")

    # Computed fields
    pips: Optional[float] = Field(None, description="P&L in pips")
    risk_reward: Optional[float] = Field(None, description="Current R:R ratio")


class ModifyPositionRequest(BaseModel):
    """Request to modify an open position."""
    ticket: int = Field(..., description="Position ticket to modify")
    stop_loss: Optional[float] = Field(None, description="New stop loss price")
    take_profit: Optional[float] = Field(None, description="New take profit price")


class ClosePositionRequest(BaseModel):
    """Request to close a position."""
    ticket: int = Field(..., description="Position ticket to close")
    volume: Optional[float] = Field(None, description="Volume to close (None = close all)")


class ClosePositionResponse(BaseModel):
    """Response after closing a position."""
    success: bool = Field(..., description="Whether close was successful")
    ticket: int = Field(..., description="Position ticket")
    symbol: str = Field(..., description="Trading symbol")
    volume_closed: float = Field(..., description="Volume that was closed")
    close_price: float = Field(..., description="Close price")
    profit: float = Field(..., description="Realized P&L")
    error_code: Optional[int] = Field(None, description="Error code if failed")
    error_message: Optional[str] = Field(None, description="Error description")


# ==================== Trade History Models ====================

class HistoricalTrade(BaseModel):
    """A closed historical trade."""
    ticket: int = Field(..., description="Deal ticket")
    order_ticket: int = Field(..., description="Order ticket")
    symbol: str = Field(..., description="Trading symbol")
    type: str = Field(..., description="Trade type")
    volume: float = Field(..., description="Trade volume")
    price: float = Field(..., description="Execution price")
    profit: float = Field(..., description="Realized P&L")
    swap: float = Field(0.0, description="Swap charges")
    commission: float = Field(0.0, description="Commission")
    time: str = Field(..., description="Trade execution time")
    magic: int = Field(..., description="Magic number")
    comment: str = Field("", description="Trade comment")


# ==================== Risk Calculation Models ====================

class LotSizeRequest(BaseModel):
    """Request to calculate lot size."""
    symbol: str = Field(..., description="Trading symbol")
    account_balance: float = Field(..., gt=0, description="Account balance")
    risk_pct: float = Field(..., ge=0.1, le=10.0, description="Risk percentage")
    stop_loss_pips: float = Field(..., gt=0, description="Stop loss distance in pips")


class LotSizeResponse(BaseModel):
    """Calculated lot size response."""
    symbol: str = Field(..., description="Trading symbol")
    lot_size: float = Field(..., description="Calculated lot size")
    risk_amount: float = Field(..., description="Risk amount in account currency")
    pip_value: float = Field(..., description="Pip value per lot")
    stop_loss_pips: float = Field(..., description="Stop loss in pips")


# ==================== Risk & Validation Models ====================

class RiskLimits(BaseModel):
    """Current risk limits and usage."""
    max_lot_size: float = Field(..., description="Maximum allowed lot size")
    max_daily_loss_pct: float = Field(..., description="Maximum daily loss percentage")
    max_open_positions: int = Field(..., description="Maximum concurrent positions")
    max_trades_per_day: int = Field(..., description="Maximum trades per day")

    # Current usage
    current_daily_loss_pct: float = Field(0.0, description="Current daily loss percentage")
    current_open_positions: int = Field(0, description="Current open position count")
    trades_today: int = Field(0, description="Trades executed today")

    # Computed limits remaining
    can_trade: bool = Field(True, description="Whether trading is allowed")
    block_reason: Optional[str] = Field(None, description="Reason if trading is blocked")


class TradeValidation(BaseModel):
    """Result of trade validation."""
    valid: bool = Field(..., description="Whether trade is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    risk_amount: Optional[float] = Field(None, description="Calculated risk amount")
    risk_pct: Optional[float] = Field(None, description="Risk as percentage of account")
    risk_reward: Optional[float] = Field(None, description="Risk-reward ratio")


# ==================== Audit Trail Models ====================

class TradeAuditEntry(BaseModel):
    """Audit log entry for trade operations."""
    id: str = Field(..., description="Unique audit ID")
    timestamp: str = Field(..., description="Operation timestamp")
    action: str = Field(..., description="Action type (PLACE, MODIFY, CLOSE, etc.)")
    symbol: str = Field(..., description="Trading symbol")
    ticket: Optional[int] = Field(None, description="Order/Position ticket")
    request: Optional[dict] = Field(None, description="Original request data")
    result: Optional[dict] = Field(None, description="Operation result")
    success: bool = Field(..., description="Whether operation succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_mode: str = Field(..., description="Execution mode at time of action")
    user: Optional[str] = Field(None, description="User who initiated action")


# ==================== Approval Queue Models ====================

class PendingApproval(BaseModel):
    """Trade awaiting approval."""
    id: str = Field(..., description="Approval request ID")
    timestamp: str = Field(..., description="Request timestamp")
    expires_at: str = Field(..., description="Expiration timestamp")
    order_request: OrderRequest = Field(..., description="The order to be approved")
    validation: TradeValidation = Field(..., description="Pre-validation result")
    status: str = Field("PENDING", description="PENDING, APPROVED, REJECTED, EXPIRED")
    approved_by: Optional[str] = Field(None, description="Who approved")
    rejection_reason: Optional[str] = Field(None, description="Reason if rejected")


class ApprovalDecision(BaseModel):
    """Decision on a pending approval."""
    approval_id: str = Field(..., description="Approval request ID")
    decision: str = Field(..., description="APPROVE or REJECT")
    reason: Optional[str] = Field(None, description="Reason for decision")


# ==================== Emergency Stop Models ====================

class EmergencyStopRequest(BaseModel):
    """Request to trigger emergency stop."""
    close_all_positions: bool = Field(True, description="Whether to close all positions")
    cancel_pending_orders: bool = Field(True, description="Whether to cancel pending orders")
    reason: str = Field(..., description="Reason for emergency stop")


class EmergencyStopResponse(BaseModel):
    """Response after emergency stop."""
    success: bool = Field(..., description="Whether emergency stop succeeded")
    positions_closed: int = Field(0, description="Number of positions closed")
    orders_cancelled: int = Field(0, description="Number of orders cancelled")
    total_pnl: float = Field(0.0, description="Total P&L from closed positions")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    timestamp: str = Field(..., description="Emergency stop timestamp")


# ==================== Backtest Models ====================

class BacktestExitReason(str, Enum):
    """Reasons for exiting a backtest position."""
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    MANUAL = "MANUAL"
    END_OF_DATA = "END_OF_DATA"


class BacktestPosition(BaseModel):
    """An open position in backtest simulation."""
    id: str = Field(..., description="Unique position ID")
    symbol: str = Field(..., description="Trading symbol")
    direction: TradeDirection = Field(..., description="LONG or SHORT")
    entry_price: float = Field(..., description="Entry price (spread-adjusted)")
    entry_timestamp: str = Field(..., description="Entry bar timestamp")
    entry_bar_index: int = Field(..., description="Bar index at entry")
    volume: float = Field(..., description="Position size in lots")
    stop_loss: float = Field(..., description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    spread_at_entry: float = Field(..., description="Spread at time of entry")
    current_price: Optional[float] = Field(None, description="Current market price")
    unrealized_pnl_pips: Optional[float] = Field(None, description="Current unrealized P&L in pips")
    setup_name: Optional[str] = Field(None, description="ICT setup name that triggered entry")

    # Simulation details captured at entry
    entry_execution_delay_ms: int = Field(0, description="Simulated entry delay in ms")
    entry_slippage_pips: float = Field(0.0, description="Simulated entry slippage in pips")


class BacktestTrade(BaseModel):
    """A completed backtest trade."""
    id: str = Field(..., description="Unique trade ID")
    symbol: str = Field(..., description="Trading symbol")
    direction: TradeDirection = Field(..., description="LONG or SHORT")
    entry_timestamp: str = Field(..., description="Entry bar timestamp")
    entry_bar_index: int = Field(..., description="Bar index at entry")
    entry_price: float = Field(..., description="Entry price (spread-adjusted)")
    exit_timestamp: str = Field(..., description="Exit bar timestamp")
    exit_bar_index: int = Field(..., description="Bar index at exit")
    exit_price: float = Field(..., description="Exit price")
    exit_reason: BacktestExitReason = Field(..., description="Reason for exit")
    volume: float = Field(..., description="Position size in lots")
    stop_loss: float = Field(..., description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price")
    spread_at_entry: float = Field(..., description="Spread at time of entry")
    pnl_pips: float = Field(..., description="Realized P&L in pips")
    pnl_usd: float = Field(0.0, description="Realized P&L in USD")
    pnl_rr: float = Field(..., description="P&L as multiple of risk (R:R)")
    setup_name: Optional[str] = Field(None, description="ICT setup name")
    agent_analysis: Optional[dict] = Field(None, description="Agent analysis at entry")
    
    # Simulation details
    execution_delay_ms: int = Field(0, description="Simulated execution delay in ms")
    slippage_pips: float = Field(0.0, description="Simulated slippage in pips")
    risk_check_passed: bool = Field(True, description="Whether trade passed strict risk checks")
    execution_assumptions: Optional[dict] = Field(None, description="Detailed assumptions used for this trade")


class BacktestStatistics(BaseModel):
    """Statistics for backtest results."""
    total_trades: int = Field(0, description="Total number of trades")
    winners: int = Field(0, description="Number of winning trades")
    losers: int = Field(0, description="Number of losing trades")
    win_rate: float = Field(0.0, description="Win rate (0-1)")
    profit_factor: float = Field(0.0, description="Gross profit / gross loss")
    total_pnl_pips: float = Field(0.0, description="Total P&L in pips")
    total_pnl_usd: float = Field(0.0, description="Total P&L in USD")
    gross_profit_pips: float = Field(0.0, description="Sum of winning trades in pips")
    gross_loss_pips: float = Field(0.0, description="Sum of losing trades in pips")
    max_drawdown_pips: float = Field(0.0, description="Maximum drawdown in pips")
    average_rr: float = Field(0.0, description="Average risk-reward ratio")
    largest_win_pips: float = Field(0.0, description="Largest winning trade in pips")
    largest_loss_pips: float = Field(0.0, description="Largest losing trade in pips")
    average_win_pips: float = Field(0.0, description="Average winning trade in pips")
    average_loss_pips: float = Field(0.0, description="Average losing trade in pips")
    consecutive_wins: int = Field(0, description="Max consecutive winning trades")
    consecutive_losses: int = Field(0, description="Max consecutive losing trades")


class BacktestExportMetadata(BaseModel):
    """Metadata for backtest export."""
    symbol: str = Field(..., description="Trading symbol")
    from_date: str = Field(..., description="Backtest start date")
    to_date: str = Field(..., description="Backtest end date")
    total_1h_bars: int = Field(..., description="Total 1H bars processed")
    spread_source: str = Field(..., description="Source of spread data")
    exported_at: str = Field(..., description="Export timestamp")


class BacktestExport(BaseModel):
    """Complete backtest export structure."""
    metadata: BacktestExportMetadata = Field(..., description="Backtest metadata")
    trades: List[BacktestTrade] = Field(default_factory=list, description="All completed trades")
    statistics: BacktestStatistics = Field(..., description="Performance statistics")


class OpenBacktestTradeRequest(BaseModel):
    """Request to open a backtest trade with auto-calculation support."""
    direction: TradeDirection = Field(..., description="LONG or SHORT")
    entry_price: float = Field(..., description="Entry price")
    stop_loss: float = Field(..., description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit price (auto-calculated if None)")
    volume: Optional[float] = Field(None, ge=0.01, description="Position size in lots (auto-calculated if None)")
    risk_reward: Optional[float] = Field(None, ge=0.5, le=10.0, description="Custom RR ratio for TP calculation")
    setup_name: Optional[str] = Field(None, description="ICT setup name")
    agent_analysis: Optional[dict] = Field(None, description="Agent analysis snapshot")
    auto_calculate: bool = Field(True, description="Auto-calculate lot size and TP if not provided")


class CloseBacktestTradeRequest(BaseModel):
    """Request to close a backtest trade."""
    position_id: str = Field(..., description="Position ID to close")
    exit_price: Optional[float] = Field(None, description="Exit price (uses current if not set)")
    reason: BacktestExitReason = Field(BacktestExitReason.MANUAL, description="Exit reason")
