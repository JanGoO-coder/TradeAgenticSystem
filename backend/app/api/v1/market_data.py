"""Market data API endpoints.

Provides endpoints for fetching historical market data from MT5
and managing backtest simulations.
"""
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.mt5_service import get_mt5_service
from app.core.config import get_settings

router = APIRouter(prefix="/market-data", tags=["market-data"])


# Request/Response Models
class HistoricalDataRequest(BaseModel):
    """Request for historical market data."""
    symbol: str
    timeframes: List[str] = ["1H", "15M", "5M"]
    bar_counts: Dict[str, int] = {"1H": 50, "15M": 100, "5M": 50}


class HistoricalRangeRequest(BaseModel):
    """Request for historical data within a date range."""
    symbol: str
    timeframe: str
    from_date: datetime
    to_date: datetime


class MT5ConnectionRequest(BaseModel):
    """Request to connect to MT5."""
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None


class OHLCV(BaseModel):
    """OHLCV bar data."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int


# Endpoints
@router.get("/status")
async def get_mt5_status() -> Dict:
    """Get MT5 connection status."""
    mt5_service = get_mt5_service()

    result = {
        "available": mt5_service.is_available,
        "connected": mt5_service.is_connected,
        "terminal_info": None
    }

    if mt5_service.is_connected:
        result["terminal_info"] = mt5_service.get_terminal_info()

    return result


@router.post("/connect")
async def connect_mt5(request: MT5ConnectionRequest) -> Dict:
    """
    Connect to MT5 terminal.

    If no credentials are provided, uses the default logged-in terminal.
    """
    mt5_service = get_mt5_service()
    settings = get_settings()

    # Use credentials from request or settings
    login = request.login or settings.mt5_login
    password = request.password or settings.mt5_password
    server = request.server or settings.mt5_server

    success = mt5_service.connect(login, password, server)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to connect to MT5. Ensure MT5 terminal is running."
        )

    return {
        "connected": True,
        "message": "Successfully connected to MT5",
        "terminal_info": mt5_service.get_terminal_info()
    }


@router.post("/disconnect")
async def disconnect_mt5() -> Dict:
    """Disconnect from MT5 terminal."""
    mt5_service = get_mt5_service()
    mt5_service.disconnect()
    return {"connected": False, "message": "Disconnected from MT5"}


@router.get("/symbols")
async def get_available_symbols() -> Dict:
    """Get symbols available in MT5."""
    mt5_service = get_mt5_service()

    if not mt5_service.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Not connected to MT5. Call /connect first."
        )

    symbols = mt5_service.get_symbols()
    return {"symbols": symbols, "count": len(symbols)}


@router.get("/symbols/{symbol}")
async def get_symbol_info(symbol: str) -> Dict:
    """Get information about a specific symbol."""
    mt5_service = get_mt5_service()

    if not mt5_service.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Not connected to MT5. Call /connect first."
        )

    info = mt5_service.get_symbol_info(symbol)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    return info


@router.post("/historical")
async def fetch_historical_data(request: HistoricalDataRequest) -> Dict:
    """
    Fetch historical data from MT5.

    Returns OHLCV data for multiple timeframes.
    """
    mt5_service = get_mt5_service()

    if not mt5_service.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Not connected to MT5. Call /connect first."
        )

    result = {}
    for tf in request.timeframes:
        bar_count = request.bar_counts.get(tf, 50)
        bars = mt5_service.get_historical_bars(request.symbol, tf, bar_count)
        result[tf] = bars

    return {
        "symbol": request.symbol,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "timeframe_bars": result
    }


@router.post("/historical/range")
async def fetch_historical_range(request: HistoricalRangeRequest) -> Dict:
    """Fetch data for a specific date range."""
    mt5_service = get_mt5_service()

    if not mt5_service.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Not connected to MT5. Call /connect first."
        )

    bars = mt5_service.get_historical_range(
        request.symbol,
        request.timeframe,
        request.from_date,
        request.to_date
    )

    return {
        "symbol": request.symbol,
        "timeframe": request.timeframe,
        "from_date": request.from_date.isoformat(),
        "to_date": request.to_date.isoformat(),
        "bars": bars,
        "count": len(bars)
    }


@router.get("/tick/{symbol}")
async def get_current_tick(symbol: str) -> Dict:
    """Get latest tick data for a symbol."""
    mt5_service = get_mt5_service()

    if not mt5_service.is_connected:
        raise HTTPException(
            status_code=400,
            detail="Not connected to MT5. Call /connect first."
        )

    tick = mt5_service.get_current_tick(symbol)
    if tick is None:
        raise HTTPException(status_code=404, detail=f"No tick data for {symbol}")

    return {"symbol": symbol, "tick": tick}


# ============================================================================
# Backtest Endpoints
# ============================================================================

from app.services.backtest_service import get_backtest_service


class BacktestLoadRequest(BaseModel):
    """Request to load backtest data."""
    symbol: str
    from_date: datetime
    to_date: datetime
    timeframes: List[str] = ["1H", "15M", "5M"]


class BacktestStepRequest(BaseModel):
    """Request to step the backtest."""
    bars: int = 1


class BacktestJumpRequest(BaseModel):
    """Request to jump to a specific index."""
    index: int


@router.get("/backtest/status")
async def get_backtest_status() -> Dict:
    """Get current backtest status."""
    backtest_service = get_backtest_service()
    return backtest_service.get_status()


@router.post("/backtest/load")
async def load_backtest(request: BacktestLoadRequest) -> Dict:
    """
    Load historical data for backtesting from MT5.

    Requires MT5 terminal to be running. Returns 503 if MT5 is not connected.
    """
    try:
        backtest_service = get_backtest_service()

        result = backtest_service.load_backtest_data(
            request.symbol,
            request.from_date,
            request.to_date,
            request.timeframes
        )

        return result
    except ValueError as e:
        error_msg = str(e)
        if "not connected" in error_msg.lower():
            raise HTTPException(status_code=503, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)


@router.post("/backtest/step")
async def step_backtest(request: BacktestStepRequest) -> Dict:
    """Advance backtest by N bars and return snapshot."""
    backtest_service = get_backtest_service()

    if not backtest_service.is_loaded:
        raise HTTPException(status_code=400, detail="No backtest data loaded")

    step_result = backtest_service.step_forward(request.bars)
    snapshot = backtest_service.get_current_snapshot()

    return {**step_result, "snapshot": snapshot}


@router.post("/backtest/step-back")
async def step_backtest_back(request: BacktestStepRequest) -> Dict:
    """Move backtest backward by N bars."""
    backtest_service = get_backtest_service()

    if not backtest_service.is_loaded:
        raise HTTPException(status_code=400, detail="No backtest data loaded")

    step_result = backtest_service.step_backward(request.bars)
    snapshot = backtest_service.get_current_snapshot()

    return {**step_result, "snapshot": snapshot}


@router.get("/backtest/snapshot")
async def get_backtest_snapshot() -> Dict:
    """Get current backtest data window."""
    backtest_service = get_backtest_service()

    if not backtest_service.is_loaded:
        raise HTTPException(status_code=400, detail="No backtest data loaded")

    return backtest_service.get_current_snapshot()


@router.post("/backtest/reset")
async def reset_backtest() -> Dict:
    """Reset backtest to beginning."""
    backtest_service = get_backtest_service()

    if not backtest_service.is_loaded:
        raise HTTPException(status_code=400, detail="No backtest data loaded")

    return backtest_service.reset()


@router.post("/backtest/jump")
async def jump_backtest(request: BacktestJumpRequest) -> Dict:
    """Jump to a specific index in the backtest."""
    backtest_service = get_backtest_service()

    if not backtest_service.is_loaded:
        raise HTTPException(status_code=400, detail="No backtest data loaded")

    result = backtest_service.jump_to(request.index)
    snapshot = backtest_service.get_current_snapshot()

    return {**result, "snapshot": snapshot}
