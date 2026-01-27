"""
Unified Session API - Complete trading session management.

This router provides a unified API for both LIVE and BACKTEST modes,
replacing the old separate backtest endpoints. All session operations
go through the TradingAgentEngine with unified DataProvider/PositionExecutor.

Endpoints:
- POST /session/init - Initialize a new session
- GET /session/state - Get current session state
- POST /session/advance - Advance simulation time (BACKTEST)
- POST /session/open-trade - Open a position
- POST /session/close-trade - Close a position
- GET /session/positions - Get open positions
- GET /session/trades - Get closed trades
- GET /session/statistics - Get trading statistics
- GET /session/audit-trail - Get message log for Glass Box
- GET /session/tick-history - Get tick events for visualization
- POST /session/analyze - Run agent analysis
- GET /session/current - Get current session/killzone info
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from app.domain.responses import SessionInfoResponse, KillZoneStatusResponse
from app.agent.engine import get_agent_engine, TradingAgentEngine

router = APIRouter(tags=["Session"])


# =============================================================================
# Request/Response Models
# =============================================================================

class InitSessionRequest(BaseModel):
    """Request to initialize a trading session."""
    symbol: str = Field(..., description="Trading symbol", example="EURUSD")
    mode: str = Field(..., description="LIVE or BACKTEST", example="BACKTEST")
    start_time: Optional[datetime] = Field(None, description="Session start (required for BACKTEST)")
    end_time: Optional[datetime] = Field(None, description="Session end (required for BACKTEST)")
    starting_balance: float = Field(10000.0, ge=100, description="Initial account balance")
    timeframes: Optional[List[str]] = Field(None, description="Timeframes to load", example=["1H", "15M", "5M"])
    auto_execute: bool = Field(True, description="Enable autonomous trade execution when setups pass")


class InitSessionResponse(BaseModel):
    """Response from session initialization."""
    success: bool
    session_id: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AdvanceTimeRequest(BaseModel):
    """Request to advance simulation time."""
    bars: int = Field(1, ge=1, le=1000, description="Number of bars to advance")


class AdvanceTimeResponse(BaseModel):
    """Response from time advancement."""
    success: bool
    status: str = "OK"
    bars_advanced: int = 0
    current_index: int = 0
    total_bars: int = 0
    progress: float = 0.0
    current_time: Optional[str] = None
    closed_trades: List[Dict[str, Any]] = Field(default_factory=list)
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class OpenTradeRequest(BaseModel):
    """Request to open a trade."""
    direction: str = Field(..., description="LONG or SHORT", example="LONG")
    entry_price: float = Field(..., gt=0, description="Entry price")
    stop_loss: float = Field(..., gt=0, description="Stop loss price")
    take_profit: Optional[float] = Field(None, description="Take profit (auto-calculated if None)")
    volume: Optional[float] = Field(None, ge=0.01, description="Lot size (auto-calculated if None)")
    risk_pct: float = Field(1.0, ge=0.1, le=10.0, description="Risk percentage for auto sizing")
    setup_name: str = Field("", description="Name of the trading setup")
    risk_reward: Optional[float] = Field(None, ge=0.5, le=10.0, description="R:R for TP calculation")


class OpenTradeResponse(BaseModel):
    """Response from opening a trade."""
    success: bool
    position_id: Optional[str] = None
    entry_price: float = 0.0
    volume: float = 0.0
    error: Optional[str] = None


class CloseTradeRequest(BaseModel):
    """Request to close a trade."""
    position_id: str = Field(..., description="Position ID to close")
    exit_price: Optional[float] = Field(None, description="Exit price (current if None)")
    reason: str = Field("MANUAL", description="Close reason")


class CloseTradeResponse(BaseModel):
    """Response from closing a trade."""
    success: bool
    position_id: str
    exit_price: float = 0.0
    realized_pnl: float = 0.0
    realized_pips: float = 0.0
    realized_rr: float = 0.0
    result: Optional[str] = None
    error: Optional[str] = None


class SessionStateResponse(BaseModel):
    """Full session state response."""
    model_config = {"extra": "ignore"}  # Ignore extra fields from engine state

    session_id: Optional[str] = None
    symbol: Optional[str] = None
    mode: Optional[str] = None
    current_time: Optional[Union[str, datetime]] = None
    simulation_speed: float = 1.0
    phase: str = "IDLE"
    market_context: Optional[Dict[str, Any]] = None
    current_setup: Optional[Dict[str, Any]] = None
    pending_setups: List[Dict[str, Any]] = Field(default_factory=list)
    open_positions: List[Dict[str, Any]] = Field(default_factory=list)
    closed_trades: List[Dict[str, Any]] = Field(default_factory=list)
    starting_balance: float = 10000.0
    balance: float = 10000.0
    equity: float = 10000.0
    total_pnl: float = 0.0
    win_count: int = 0
    loss_count: int = 0
    trades_this_session: int = 0
    max_trades_per_session: int = 2
    can_trade: bool = True
    win_rate: float = 0.0
    # Backtest progress fields
    current_bar_index: Optional[int] = None
    total_bars: Optional[int] = None
    progress: Optional[float] = None


class StatisticsResponse(BaseModel):
    """Trading statistics response."""
    total_trades: int = 0
    winners: int = 0
    losers: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_pnl_pips: float = 0.0
    total_pnl_usd: float = 0.0
    gross_profit_pips: float = 0.0
    gross_loss_pips: float = 0.0
    max_drawdown: float = 0.0
    average_rr: float = 0.0
    balance: float = 0.0
    starting_balance: float = 0.0


class AnalyzeRequest(BaseModel):
    """Request for agent analysis."""
    snapshot: Optional[Dict[str, Any]] = Field(None, description="Market snapshot (auto-generated if None)")


class AnalyzeResponse(BaseModel):
    """Response from agent analysis."""
    success: bool
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SnapshotResponse(BaseModel):
    """Snapshot response for charting."""
    symbol: str
    timestamp: Optional[str] = None
    current_index: int = 0
    total_bars: int = 0
    progress: float = 0.0
    timeframe_bars: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    error: Optional[str] = None


class StepBackRequest(BaseModel):
    """Request to step back."""
    bars: int = Field(1, ge=1)


class JumpRequest(BaseModel):
    """Request to jump to index."""
    index: int = Field(..., ge=0)


class AutoAdvanceRequest(BaseModel):
    """Request for auto-advancing until trade or limit."""
    max_bars: int = Field(100, ge=1, le=10000, description="Maximum bars to advance")
    stop_on_trade: bool = Field(True, description="Stop when trade is executed")
    stop_on_setup: bool = Field(False, description="Stop when setup is found (even if not executed)")


class AutoAdvanceResponse(BaseModel):
    """Response from auto-advance."""
    success: bool
    bars_advanced: int = 0
    stopped_reason: str = ""  # "MAX_BARS", "TRADE_EXECUTED", "SETUP_FOUND", "SESSION_END", "ERROR"
    trades_executed: List[Dict[str, Any]] = Field(default_factory=list)
    setups_found: List[Dict[str, Any]] = Field(default_factory=list)
    final_state: Optional[Dict[str, Any]] = None
    current_time: Optional[str] = None
    progress: float = 0.0
    error: Optional[str] = None


# =============================================================================
# Session Management Endpoints
# =============================================================================

@router.post("/session/init", response_model=InitSessionResponse)
async def initialize_session(
    request: InitSessionRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> InitSessionResponse:
    """
    Initialize a new trading session.

    Creates a unified trading context with DataProvider and PositionExecutor
    based on the specified mode (LIVE or BACKTEST).

    For BACKTEST mode, loads historical data for the specified date range.
    For LIVE mode, connects to MT5 terminal for real-time data.
    """
    try:
        # Validate mode
        mode = request.mode.upper()
        if mode not in ("LIVE", "BACKTEST"):
            raise HTTPException(400, f"Invalid mode: {mode}. Must be LIVE or BACKTEST")

        # Validate backtest requirements
        if mode == "BACKTEST":
            if not request.start_time or not request.end_time:
                raise HTTPException(400, "start_time and end_time required for BACKTEST mode")
            if request.end_time <= request.start_time:
                raise HTTPException(400, "end_time must be after start_time")

        result = engine.initialize_session(
            symbol=request.symbol,
            mode=mode,
            start_time=request.start_time or datetime.utcnow(),
            end_time=request.end_time,
            starting_balance=request.starting_balance,
            timeframes=request.timeframes,
            auto_execute_enabled=request.auto_execute,
        )

        if "error" in result:
            return InitSessionResponse(success=False, error=result["error"])

        return InitSessionResponse(
            success=True,
            session_id=result.get("session_id"),
            state=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        return InitSessionResponse(success=False, error=str(e))


@router.get("/session/state", response_model=SessionStateResponse)
async def get_session_state(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> SessionStateResponse:
    """
    Get current session state.

    Returns complete session information including:
    - Current positions and closed trades
    - Balance and equity
    - Market context (if available)
    - Win/loss statistics
    """
    state = engine.get_session_state()

    if not state:
        raise HTTPException(404, "No active session. Call /session/init first.")

    return SessionStateResponse(**state)


@router.post("/session/advance", response_model=AdvanceTimeResponse)
async def advance_time(
    request: AdvanceTimeRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> AdvanceTimeResponse:
    """
    Advance simulation time (BACKTEST mode only).

    Steps forward by the specified number of bars, checking TP/SL
    on each bar. Uses tick data when available for accurate
    intra-bar detection, falls back to bar OHLC otherwise.
    """
    result = engine.advance_time(request.bars)

    if "error" in result:
        return AdvanceTimeResponse(success=False, error=result["error"])

    # Map Agent Status
    phase = result.get("agent_phase", "IDLE")
    status = "OK"
    if phase in ["ANALYZING", "DECIDING", "EXECUTING"]:
        status = "WAITING"

    return AdvanceTimeResponse(
        success=True,
        status=status,
        bars_advanced=result.get("bars_advanced", 0),
        current_index=result.get("current_index", 0),
        total_bars=result.get("total_bars", 0),
        progress=result.get("progress", 0.0),
        current_time=result.get("current_time"),
        closed_trades=result.get("closed_trades", []),
        positions=result.get("positions", []),
    )


@router.get("/session/snapshot", response_model=SnapshotResponse)
async def get_session_snapshot(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> SnapshotResponse:
    """
    Get current market snapshot for charting.
    """
    result = engine.get_market_snapshot()
    if "error" in result:
        return SnapshotResponse(symbol="", error=result["error"])
        
    return SnapshotResponse(**result)


@router.post("/session/step-back", response_model=AdvanceTimeResponse)
async def step_back(
    request: StepBackRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> AdvanceTimeResponse:
    """
    Step simulation backward.
    """
    result = engine.step_back(request.bars)
    
    if "error" in result:
        return AdvanceTimeResponse(success=False, error=result["error"])
        
    return AdvanceTimeResponse(
        success=True,
        bars_advanced=-request.bars,
        current_index=result.get("current_index", 0),
        total_bars=result.get("total_bars", 0),
        progress=result.get("progress", 0.0),
        current_time=result.get("current_time"),
    )


@router.post("/session/jump", response_model=AdvanceTimeResponse)
async def jump_to(
    request: JumpRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> AdvanceTimeResponse:
    """
    Jump to specific bar index.
    """
    result = engine.jump_to(request.index)
    
    if "error" in result:
        return AdvanceTimeResponse(success=False, error=result["error"])
        
    return AdvanceTimeResponse(
        success=True,
        current_index=result.get("current_index", 0),
        total_bars=result.get("total_bars", 0),
        progress=result.get("progress", 0.0),
        current_time=result.get("current_time"),
    )


@router.post("/session/reset", response_model=AdvanceTimeResponse)
async def reset_session(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> AdvanceTimeResponse:
    """
    Reset simulation to start.
    """
    result = engine.reset_simulation()
    
    if "error" in result:
        return AdvanceTimeResponse(success=False, error=result["error"])
        
    return AdvanceTimeResponse(
        success=True,
        current_index=result.get("current_index", 0),
        total_bars=result.get("total_bars", 0),
        progress=result.get("progress", 0.0),
        current_time=result.get("current_time"),
    )


@router.post("/session/auto-advance", response_model=AutoAdvanceResponse)
async def auto_advance(
    request: AutoAdvanceRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> AutoAdvanceResponse:
    """
    Auto-advance simulation until a trade is executed or limit reached.

    This enables autonomous trading by continuously advancing the simulation
    and letting the agent execute trades when valid setups are found.

    Use this to:
    - Run backtests hands-free until a trade is made
    - Find the next setup automatically
    - Test agent behavior over many bars quickly

    Args:
        max_bars: Maximum bars to advance (1-10000)
        stop_on_trade: Stop when a trade is executed (default: True)
        stop_on_setup: Stop when a setup is found even if not executed

    Returns:
        Stopped reason, trades executed, setups found, final state
    """
    result = engine.auto_advance(
        max_bars=request.max_bars,
        stop_on_trade=request.stop_on_trade,
        stop_on_setup=request.stop_on_setup,
    )

    if "error" in result:
        return AutoAdvanceResponse(
            success=False,
            bars_advanced=result.get("bars_advanced", 0),
            stopped_reason=result.get("stopped_reason", "ERROR"),
            error=result["error"],
        )

    return AutoAdvanceResponse(
        success=True,
        bars_advanced=result.get("bars_advanced", 0),
        stopped_reason=result.get("stopped_reason", ""),
        trades_executed=result.get("trades_executed", []),
        setups_found=result.get("setups_found", []),
        final_state=result.get("final_state"),
        current_time=result.get("current_time"),
        progress=result.get("progress", 0.0),
    )


class RunContinuousRequest(BaseModel):
    """Request for continuous autonomous scanning."""
    continue_after_trade: bool = Field(True, description="Keep scanning after trades are executed")
    max_consecutive_errors: int = Field(10, ge=1, le=100, description="Stop after this many consecutive errors")


class RunContinuousResponse(BaseModel):
    """Response from continuous scanning."""
    success: bool
    bars_advanced: int = 0
    stopped_reason: str = ""  # "SESSION_END", "ERROR", "MAX_ERRORS"
    trades_executed: List[Dict[str, Any]] = Field(default_factory=list)
    setups_found: List[Dict[str, Any]] = Field(default_factory=list)
    closed_trades: List[Dict[str, Any]] = Field(default_factory=list)
    statistics: Optional[Dict[str, Any]] = None
    current_time: Optional[str] = None
    progress: float = 0.0
    error: Optional[str] = None


@router.post("/session/run-continuous", response_model=RunContinuousResponse)
async def run_continuous(
    request: RunContinuousRequest = RunContinuousRequest(),
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> RunContinuousResponse:
    """
    Run fully autonomous continuous scanning until session end.

    This is the fully autonomous mode that:
    - Scans every bar for trade setups matching predefined strategies
    - Validates setups against all ICT rules and confluence checks
    - Automatically executes trades when valid setups are found
    - Continues scanning after trades (does NOT stop)
    - Tracks all trades, TP/SL hits, and provides final statistics

    Use this for:
    - Running complete backtests autonomously
    - Testing strategy performance over entire date ranges
    - Hands-free backtest execution

    Returns:
        Complete session results with all trades and statistics
    """
    result = engine.run_continuous(
        continue_after_trade=request.continue_after_trade,
        max_consecutive_errors=request.max_consecutive_errors,
    )

    if "error" in result:
        return RunContinuousResponse(
            success=False,
            bars_advanced=result.get("bars_advanced", 0),
            stopped_reason=result.get("stopped_reason", "ERROR"),
            trades_executed=result.get("trades_executed", []),
            closed_trades=result.get("closed_trades", []),
            error=result["error"],
        )

    return RunContinuousResponse(
        success=True,
        bars_advanced=result.get("bars_advanced", 0),
        stopped_reason=result.get("stopped_reason", "SESSION_END"),
        trades_executed=result.get("trades_executed", []),
        setups_found=result.get("setups_found", []),
        closed_trades=result.get("closed_trades", []),
        statistics=result.get("statistics"),
        current_time=result.get("current_time"),
        progress=result.get("progress", 1.0),
    )


# =============================================================================
# Trade Execution Endpoints
# =============================================================================

@router.post("/session/open-trade", response_model=OpenTradeResponse)
async def open_trade(
    request: OpenTradeRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> OpenTradeResponse:
    """
    Open a new trade through the unified executor.

    Supports both LIVE (MT5) and BACKTEST execution modes.
    Auto-calculates lot size and take profit if not provided.
    """
    # Calculate TP from R:R if not provided
    take_profit = request.take_profit
    if take_profit is None and request.risk_reward:
        sl_distance = abs(request.entry_price - request.stop_loss)
        tp_distance = sl_distance * request.risk_reward

        if request.direction.upper() == "LONG":
            take_profit = request.entry_price + tp_distance
        else:
            take_profit = request.entry_price - tp_distance

    result = engine.open_trade(
        direction=request.direction.upper(),
        entry_price=request.entry_price,
        stop_loss=request.stop_loss,
        take_profit=take_profit,
        volume=request.volume,
        risk_pct=request.risk_pct,
        setup_name=request.setup_name,
    )

    if "error" in result:
        return OpenTradeResponse(success=False, error=result["error"])

    return OpenTradeResponse(
        success=result.get("success", False),
        position_id=result.get("position_id"),
        entry_price=result.get("entry_price", 0.0),
        volume=result.get("volume", 0.0),
        error=result.get("error_message"),
    )


@router.post("/session/close-trade", response_model=CloseTradeResponse)
async def close_trade(
    request: CloseTradeRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> CloseTradeResponse:
    """
    Close an existing trade.

    Works for both LIVE and BACKTEST modes.
    If exit_price not specified, uses current market price.
    """
    result = engine.close_trade(
        position_id=request.position_id,
        exit_price=request.exit_price,
        reason=request.reason,
    )

    if "error" in result:
        return CloseTradeResponse(
            success=False,
            position_id=request.position_id,
            error=result["error"],
        )

    return CloseTradeResponse(
        success=result.get("success", False),
        position_id=result.get("position_id", request.position_id),
        exit_price=result.get("exit_price", 0.0),
        realized_pnl=result.get("realized_pnl", 0.0),
        realized_pips=result.get("realized_pips", 0.0),
        realized_rr=result.get("realized_rr", 0.0),
        result=result.get("result"),
        error=result.get("error_message"),
    )


@router.post("/session/close-all")
async def close_all_positions(
    symbol: Optional[str] = None,
    reason: str = "EMERGENCY_STOP",
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> Dict[str, Any]:
    """
    Close all open positions (emergency stop).
    """
    if not engine.trading_context:
        raise HTTPException(404, "No active session")

    results = engine.trading_context.position_executor.close_all_positions(
        symbol=symbol,
        reason=reason,
    )

    return {
        "success": True,
        "positions_closed": len(results),
        "results": [r.to_dict() for r in results],
    }


# =============================================================================
# Query Endpoints
# =============================================================================

@router.get("/session/positions")
async def get_positions(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> List[Dict[str, Any]]:
    """Get all open positions."""
    return engine.get_positions()


@router.get("/session/trades")
async def get_trades(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> List[Dict[str, Any]]:
    """Get all closed trades."""
    return engine.get_closed_trades()


@router.get("/session/statistics", response_model=StatisticsResponse)
async def get_statistics(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> StatisticsResponse:
    """Get trading statistics for current session."""
    stats = engine.get_statistics()
    return StatisticsResponse(**stats)


@router.get("/session/audit-trail")
async def get_audit_trail(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> List[Dict[str, Any]]:
    """
    Get message audit trail for Glass Box replay.

    Returns all logged MessageEnvelope entries from the session.
    """
    return engine.get_audit_trail()


@router.get("/session/tick-history")
async def get_tick_history(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> List[Dict[str, Any]]:
    """
    Get tick history for visualization.

    Returns TickEvent entries for timeline visualization.
    """
    return engine.get_tick_history()


# =============================================================================
# Analysis Endpoints
# =============================================================================

@router.post("/session/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> AnalyzeResponse:
    """
    Run agent analysis on current market state.

    If no snapshot provided, generates one from current session data.
    """
    try:
        if not engine.is_available:
            return AnalyzeResponse(success=False, error="Agent not available")

        snapshot = request.snapshot

        # Auto-generate snapshot if not provided
        if not snapshot and engine.trading_context:
            data_provider = engine.trading_context.data_provider
            symbol = engine.trading_context.symbol

            # Get multi-timeframe bars
            bars_1h = data_provider.get_bars(symbol, "1H", 50)
            bars_15m = data_provider.get_bars(symbol, "15M", 100)
            bars_5m = data_provider.get_bars(symbol, "5M", 50)

            status = data_provider.get_status()

            snapshot = {
                "symbol": symbol,
                "timestamp": status.current_time.isoformat() + "Z" if status.current_time else datetime.utcnow().isoformat() + "Z",
                "timeframe_bars": {  # Note: must use 'timeframe_bars', not 'candles'
                    "1H": [b.to_dict() for b in bars_1h],
                    "15M": [b.to_dict() for b in bars_15m],
                    "5M": [b.to_dict() for b in bars_5m],
                },
                "spread": data_provider.get_spread(symbol),
                "backtest_mode": engine.trading_context.mode.value == "BACKTEST",
                "auto_execute_enabled": False,  # Can be made configurable later
            }

        if not snapshot:
            return AnalyzeResponse(success=False, error="No snapshot provided and no active session")

        analysis = engine.analyze(snapshot)

        return AnalyzeResponse(success=True, analysis=analysis)

    except Exception as e:
        return AnalyzeResponse(success=False, error=str(e))


# =============================================================================
# Session Info Endpoints (backward compatible)
# =============================================================================

@router.get("/session/current", response_model=SessionInfoResponse)
async def get_current_session(
    engine: TradingAgentEngine = Depends(get_agent_engine)
) -> SessionInfoResponse:
    """
    Get current trading session information.

    Returns:
    - Current session name (London, NY, Asia)
    - Kill zone status
    - Current time in UTC and EST
    """
    now = datetime.utcnow()
    session_info = engine.get_current_session(now)

    return SessionInfoResponse(
        session=session_info["session"],
        kill_zone_active=session_info["kill_zone_active"],
        kill_zone_name=session_info.get("kill_zone_name"),
        time_until_next_zone=None,
        current_time_utc=session_info["current_time_utc"],
        current_time_est=session_info["current_time_est"]
    )


@router.get("/killzone/status", response_model=KillZoneStatusResponse)
async def get_killzone_status(
    engine: TradingAgentEngine = Depends(get_agent_engine)
) -> KillZoneStatusResponse:
    """
    Check if currently inside a Kill Zone.

    Kill Zones per Rule 8.1:
    - London: 2:00 AM - 5:00 AM EST (07:00-10:00 UTC)
    - NY: 7:00 AM - 10:00 AM EST (12:00-15:00 UTC)
    """
    now = datetime.utcnow()
    session_info = engine.get_current_session(now)

    return KillZoneStatusResponse(
        in_kill_zone=session_info["kill_zone_active"],
        session=session_info.get("kill_zone_name"),
        rule_refs=session_info.get("rule_refs", ["8.1"])
    )


# =============================================================================
# Data Provider Status
# =============================================================================

@router.get("/session/data-status")
async def get_data_status(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> Dict[str, Any]:
    """Get data provider status (current bar, progress, etc.)."""
    if not engine.trading_context:
        raise HTTPException(404, "No active session")

    status = engine.trading_context.data_provider.get_status()
    return status.to_dict()


@router.get("/session/account")
async def get_account_info(
    engine: TradingAgentEngine = Depends(get_agent_engine),
) -> Dict[str, Any]:
    """Get account information (balance, equity, margin)."""
    if not engine.trading_context:
        raise HTTPException(404, "No active session")

    account = engine.trading_context.position_executor.get_account_info()
    return account.to_dict()
