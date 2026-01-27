"""
Unified DataProvider Interface for Market Data.

This module provides a consistent interface for accessing market data
across both live (MT5) and backtest (historical) modes. The agent code
uses this abstraction without knowing the underlying data source.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class DataMode(str, Enum):
    """Data provider mode."""
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"


class Timeframe(str, Enum):
    """Standard timeframes."""
    M1 = "1M"
    M5 = "5M"
    M15 = "15M"
    M30 = "30M"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"


# Timeframe to minutes mapping
TIMEFRAME_MINUTES = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
    # Also support string keys
    "1M": 1, "5M": 5, "15M": 15, "30M": 30,
    "1H": 60, "4H": 240, "1D": 1440,
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class OHLCVBar:
    """Single OHLCV candle with optional spread."""
    timestamp: str  # ISO 8601 UTC
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    spread: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "spread": self.spread,
        }


@dataclass
class Tick:
    """Single tick with bid/ask prices."""
    time: float  # Unix timestamp
    bid: float
    ask: float
    volume: int = 0

    @property
    def spread(self) -> float:
        """Calculate spread from bid/ask."""
        return self.ask - self.bid

    @property
    def mid(self) -> float:
        """Calculate mid price."""
        return (self.bid + self.ask) / 2

    @property
    def datetime(self) -> datetime:
        """Convert to datetime."""
        return datetime.utcfromtimestamp(self.time)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "time": self.time,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
        }


@dataclass
class SymbolInfo:
    """Symbol specifications."""
    name: str
    digits: int  # Price decimal places
    point: float  # Minimum price change
    spread: float  # Current spread
    volume_min: float  # Minimum lot size
    volume_max: float  # Maximum lot size
    volume_step: float  # Lot size increment
    contract_size: float  # Contract size (usually 100000 for forex)
    tick_value: float  # Value per tick in account currency
    tick_size: float = 0.0  # Tick size
    currency_base: str = ""  # Base currency
    currency_profit: str = ""  # Profit currency

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "digits": self.digits,
            "point": self.point,
            "spread": self.spread,
            "volume_min": self.volume_min,
            "volume_max": self.volume_max,
            "volume_step": self.volume_step,
            "contract_size": self.contract_size,
            "tick_value": self.tick_value,
            "tick_size": self.tick_size,
            "currency_base": self.currency_base,
            "currency_profit": self.currency_profit,
        }


@dataclass
class DataProviderStatus:
    """Status of the data provider."""
    mode: DataMode
    connected: bool
    symbol: Optional[str] = None
    current_time: Optional[datetime] = None
    # Backtest-specific
    loaded: bool = False
    current_index: int = 0
    total_bars: int = 0
    progress: float = 0.0
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    data_source: str = "unknown"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "mode": self.mode.value,
            "connected": self.connected,
            "symbol": self.symbol,
            "current_time": self.current_time.isoformat() if self.current_time else None,
            "loaded": self.loaded,
            "current_index": self.current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "data_source": self.data_source,
        }


# =============================================================================
# Abstract DataProvider Interface
# =============================================================================

class DataProvider(ABC):
    """
    Unified interface for market data access.

    Works identically for both live MT5 and backtest modes.
    The agent code uses this abstraction without knowing the data source.
    """

    @property
    @abstractmethod
    def mode(self) -> DataMode:
        """Current data mode (LIVE or BACKTEST)."""
        pass

    @property
    @abstractmethod
    def current_time(self) -> datetime:
        """Current market time (real for live, simulated for backtest)."""
        pass

    @property
    @abstractmethod
    def symbol(self) -> str:
        """Current symbol being tracked."""
        pass

    @abstractmethod
    def get_status(self) -> DataProviderStatus:
        """Get current provider status."""
        pass

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        count: int
    ) -> List[OHLCVBar]:
        """
        Get N most recent bars up to current_time.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            timeframe: Timeframe string (e.g., "1H", "15M")
            count: Number of bars to retrieve

        Returns:
            List of OHLCV bars, oldest first
        """
        pass

    @abstractmethod
    def get_current_tick(self, symbol: str) -> Optional[Tick]:
        """
        Get latest tick (live) or current simulated tick (backtest).

        Args:
            symbol: Trading symbol

        Returns:
            Current tick or None if unavailable
        """
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> Tuple[float, float]:
        """
        Get current bid/ask prices.

        Args:
            symbol: Trading symbol

        Returns:
            Tuple of (bid, ask) prices
        """
        pass

    @abstractmethod
    def get_spread(self, symbol: str) -> float:
        """
        Get current spread in price units.

        Args:
            symbol: Trading symbol

        Returns:
            Current spread
        """
        pass

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """
        Get symbol specifications.

        Args:
            symbol: Trading symbol

        Returns:
            SymbolInfo or None if not available
        """
        pass

    def get_multi_timeframe_bars(
        self,
        symbol: str,
        timeframes: Dict[str, int]
    ) -> Dict[str, List[OHLCVBar]]:
        """
        Get bars for multiple timeframes at once.

        Args:
            symbol: Trading symbol
            timeframes: Dict of {timeframe: count}

        Returns:
            Dict of {timeframe: [bars]}
        """
        result = {}
        for tf, count in timeframes.items():
            result[tf] = self.get_bars(symbol, tf, count)
        return result

    # =========================================================================
    # Backtest-specific methods (no-op for live mode)
    # =========================================================================

    def load_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframes: List[str]
    ) -> Dict:
        """
        Load historical data for backtesting.

        Args:
            symbol: Trading symbol
            from_date: Start date
            to_date: End date
            timeframes: List of timeframes to load

        Returns:
            Load result with bar counts

        Raises:
            NotImplementedError: If called in LIVE mode
        """
        raise NotImplementedError("load_data() only available in BACKTEST mode")

    def step_forward(self, bars: int = 1) -> Dict:
        """
        Advance simulation by N bars.

        Args:
            bars: Number of bars to advance

        Returns:
            Step result with new state

        Raises:
            NotImplementedError: If called in LIVE mode
        """
        raise NotImplementedError("step_forward() only available in BACKTEST mode")

    def step_backward(self, bars: int = 1) -> Dict:
        """
        Move simulation back N bars.

        Args:
            bars: Number of bars to move back

        Returns:
            Step result with new state

        Raises:
            NotImplementedError: If called in BACKTEST mode
        """
        raise NotImplementedError("step_backward() only available in BACKTEST mode")

    def jump_to(self, index: int) -> Dict:
        """
        Jump to specific bar index.

        Args:
            index: Target bar index

        Returns:
            Jump result with new state

        Raises:
            NotImplementedError: If called in LIVE mode
        """
        raise NotImplementedError("jump_to() only available in BACKTEST mode")

    def reset(self) -> Dict:
        """
        Reset simulation to start.

        Returns:
            Reset result

        Raises:
            NotImplementedError: If called in LIVE mode
        """
        raise NotImplementedError("reset() only available in BACKTEST mode")

    def load_ticks_for_bar(
        self,
        bar_start: datetime,
        bar_end: datetime
    ) -> List[Tick]:
        """
        Load tick data for a specific bar (for tick-level TP/SL checking).

        Args:
            bar_start: Bar open time
            bar_end: Bar close time

        Returns:
            List of ticks within the bar

        Raises:
            NotImplementedError: If called in LIVE mode
        """
        raise NotImplementedError("load_ticks_for_bar() only available in BACKTEST mode")

    def get_ticks_available(self) -> bool:
        """Check if tick data is available for current bar."""
        return False


# =============================================================================
# Live Data Provider (MT5)
# =============================================================================

class LiveDataProvider(DataProvider):
    """
    Live data provider wrapping MT5Service.

    Provides real-time market data from MetaTrader 5 terminal.
    """

    def __init__(self, mt5_service):
        """
        Initialize live data provider.

        Args:
            mt5_service: MT5Service instance
        """
        self._mt5 = mt5_service
        self._symbol: str = ""

    @property
    def mode(self) -> DataMode:
        return DataMode.LIVE

    @property
    def current_time(self) -> datetime:
        """Get current server time from MT5."""
        if self._mt5.is_connected:
            # Get server time from MT5
            try:
                import MetaTrader5 as mt5
                info = mt5.terminal_info()
                if info:
                    # Terminal build time as proxy for server time
                    # In practice, use tick time
                    tick = self._mt5.get_current_tick(self._symbol or "EURUSD")
                    if tick:
                        return datetime.utcfromtimestamp(tick["time"])
            except Exception:
                pass
        return datetime.utcnow()

    @property
    def symbol(self) -> str:
        return self._symbol

    def set_symbol(self, symbol: str):
        """Set the current symbol."""
        self._symbol = symbol

    def get_status(self) -> DataProviderStatus:
        """Get live provider status."""
        return DataProviderStatus(
            mode=DataMode.LIVE,
            connected=self._mt5.is_connected,
            symbol=self._symbol,
            current_time=self.current_time,
            loaded=self._mt5.is_connected,
            data_source="mt5_live",
        )

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        count: int
    ) -> List[OHLCVBar]:
        """Get recent bars from MT5."""
        if not self._mt5.is_connected:
            logger.warning("MT5 not connected, returning empty bars")
            return []

        bars_data = self._mt5.get_recent_bars(symbol, timeframe, count)

        result = []
        for bar in bars_data:
            result.append(OHLCVBar(
                timestamp=bar["timestamp"] if isinstance(bar["timestamp"], str)
                          else bar["timestamp"].isoformat() + "Z",
                open=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar.get("volume", 0),
                spread=bar.get("spread"),
            ))

        return result

    def get_current_tick(self, symbol: str) -> Optional[Tick]:
        """Get current tick from MT5."""
        if not self._mt5.is_connected:
            return None

        tick_data = self._mt5.get_current_tick(symbol)
        if not tick_data:
            return None

        return Tick(
            time=tick_data["time"],
            bid=tick_data["bid"],
            ask=tick_data["ask"],
            volume=tick_data.get("volume", 0),
        )

    def get_current_price(self, symbol: str) -> Tuple[float, float]:
        """Get current bid/ask from MT5."""
        tick = self.get_current_tick(symbol)
        if tick:
            return (tick.bid, tick.ask)

        # Fallback: use symbol info
        info = self.get_symbol_info(symbol)
        if info:
            mid = info.spread / 2
            return (mid - info.spread/2, mid + info.spread/2)

        return (0.0, 0.0)

    def get_spread(self, symbol: str) -> float:
        """Get current spread from MT5."""
        tick = self.get_current_tick(symbol)
        if tick:
            return tick.spread

        info = self.get_symbol_info(symbol)
        if info:
            return info.spread * info.point

        return 0.0

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """Get symbol info from MT5."""
        if not self._mt5.is_connected:
            return None

        info = self._mt5.get_symbol_info(symbol)
        if not info:
            return None

        return SymbolInfo(
            name=info.get("name", symbol),
            digits=info.get("digits", 5),
            point=info.get("point", 0.00001),
            spread=info.get("spread", 0),
            volume_min=info.get("volume_min", 0.01),
            volume_max=info.get("volume_max", 100.0),
            volume_step=info.get("volume_step", 0.01),
            contract_size=info.get("contract_size", 100000),
            tick_value=info.get("tick_value", 1.0),
            tick_size=info.get("tick_size", 0.00001),
            currency_base=info.get("currency_base", ""),
            currency_profit=info.get("currency_profit", ""),
        )


# =============================================================================
# Backtest Data Provider
# =============================================================================

class BacktestDataProvider(DataProvider):
    """
    Backtest data provider wrapping BacktestService.

    Provides historical data replay with simulation time control.
    """

    def __init__(self, backtest_service, mt5_service=None):
        """
        Initialize backtest data provider.

        Args:
            backtest_service: BacktestService instance
            mt5_service: Optional MT5Service for fetching historical data
        """
        self._backtest = backtest_service
        self._mt5 = mt5_service
        self._ticks_loaded: List[Tick] = []

    @property
    def mode(self) -> DataMode:
        return DataMode.BACKTEST

    @property
    def current_time(self) -> datetime:
        """Get current simulation time."""
        if hasattr(self._backtest, 'current_time') and self._backtest.current_time:
            if isinstance(self._backtest.current_time, str):
                return datetime.fromisoformat(self._backtest.current_time.replace("Z", "+00:00"))
            return self._backtest.current_time
        return datetime.utcnow()

    @property
    def symbol(self) -> str:
        return self._backtest.symbol if hasattr(self._backtest, 'symbol') else ""

    def get_status(self) -> DataProviderStatus:
        """Get backtest provider status."""
        status = self._backtest.get_status()
        return DataProviderStatus(
            mode=DataMode.BACKTEST,
            connected=True,
            symbol=status.get("symbol"),
            current_time=self.current_time,
            loaded=status.get("loaded", False),
            current_index=status.get("current_index", 0),
            total_bars=status.get("total_bars", 0),
            progress=status.get("progress", 0.0),
            from_date=status.get("from_date"),
            to_date=status.get("to_date"),
            data_source=status.get("source", "backtest"),
        )

    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        count: int
    ) -> List[OHLCVBar]:
        """Get bars from backtest service up to current index."""
        # Use snapshot method to get bars
        snapshot = self._backtest.get_current_snapshot({timeframe: count})

        # Note: get_current_snapshot returns "timeframe_bars", not "candles"
        bars_data = snapshot.get("timeframe_bars", {}).get(timeframe, [])

        result = []
        for bar in bars_data:
            result.append(OHLCVBar(
                timestamp=bar["timestamp"] if isinstance(bar.get("timestamp"), str)
                          else bar.get("timestamp", ""),
                open=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar.get("volume", 0),
                spread=bar.get("spread"),
            ))

        return result


    def get_current_tick(self, symbol: str) -> Optional[Tick]:
        """Get simulated current tick from latest bar close."""
        bars = self.get_bars(symbol, "5M", 1)
        if not bars:
            return None

        bar = bars[-1]
        spread = bar.spread or 0.00012  # Default spread

        return Tick(
            time=datetime.fromisoformat(bar.timestamp.replace("Z", "+00:00")).timestamp()
                 if bar.timestamp else self.current_time.timestamp(),
            bid=bar.close - spread/2,
            ask=bar.close + spread/2,
            volume=bar.volume,
        )

    def get_current_price(self, symbol: str) -> Tuple[float, float]:
        """Get current simulated bid/ask."""
        tick = self.get_current_tick(symbol)
        if tick:
            return (tick.bid, tick.ask)
        return (0.0, 0.0)

    def get_spread(self, symbol: str) -> float:
        """Get current spread from latest bar data."""
        bars = self.get_bars(symbol, "5M", 1)
        if bars and bars[-1].spread:
            return bars[-1].spread

        # Default spreads by symbol type
        if "XAU" in symbol or "GOLD" in symbol:
            return 0.30
        elif "JPY" in symbol:
            return 0.015
        else:
            return 0.00012

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """Get symbol info (may use MT5 if available, else defaults)."""
        # Try MT5 first
        if self._mt5 and self._mt5.is_connected:
            info = self._mt5.get_symbol_info(symbol)
            if info:
                return SymbolInfo(
                    name=info.get("name", symbol),
                    digits=info.get("digits", 5),
                    point=info.get("point", 0.00001),
                    spread=info.get("spread", 0),
                    volume_min=info.get("volume_min", 0.01),
                    volume_max=info.get("volume_max", 100.0),
                    volume_step=info.get("volume_step", 0.01),
                    contract_size=info.get("contract_size", 100000),
                    tick_value=info.get("tick_value", 1.0),
                )

        # Default symbol info
        if "XAU" in symbol or "GOLD" in symbol:
            return SymbolInfo(
                name=symbol, digits=2, point=0.01, spread=30,
                volume_min=0.01, volume_max=100, volume_step=0.01,
                contract_size=100, tick_value=1.0,
            )
        elif "JPY" in symbol:
            return SymbolInfo(
                name=symbol, digits=3, point=0.001, spread=15,
                volume_min=0.01, volume_max=100, volume_step=0.01,
                contract_size=100000, tick_value=0.01,
            )
        else:
            return SymbolInfo(
                name=symbol, digits=5, point=0.00001, spread=12,
                volume_min=0.01, volume_max=100, volume_step=0.01,
                contract_size=100000, tick_value=1.0,
            )

    # =========================================================================
    # Backtest-specific methods
    # =========================================================================

    def load_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframes: List[str]
    ) -> Dict:
        """Load historical data for backtesting."""
        return self._backtest.load_backtest_data(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            timeframes=timeframes,
        )

    def step_forward(self, bars: int = 1) -> Dict:
        """Advance simulation by N bars."""
        return self._backtest.step_forward(bars)

    def step_backward(self, bars: int = 1) -> Dict:
        """Move simulation back N bars."""
        return self._backtest.step_backward(bars)

    def jump_to(self, index: int) -> Dict:
        """Jump to specific bar index."""
        return self._backtest.jump_to(index)

    def reset(self) -> Dict:
        """Reset simulation to start."""
        return self._backtest.reset()

    def load_ticks_for_bar(
        self,
        bar_start: datetime,
        bar_end: datetime
    ) -> List[Tick]:
        """Load tick data for a specific bar."""
        # Use tick cache manager from backtest service
        if hasattr(self._backtest, 'tick_cache') and self._backtest.tick_cache:
            raw_ticks = self._backtest.tick_cache.get_ticks_in_range(bar_start, bar_end)
            self._ticks_loaded = [
                Tick(
                    time=t["time"],
                    bid=t["bid"],
                    ask=t["ask"],
                    volume=t.get("volume", 0),
                )
                for t in raw_ticks
            ]
            return self._ticks_loaded

        return []

    def get_ticks_available(self) -> bool:
        """Check if tick data was loaded for current bar."""
        return len(self._ticks_loaded) > 0


# =============================================================================
# Factory Function
# =============================================================================

def create_data_provider(
    mode: DataMode,
    mt5_service=None,
    backtest_service=None,
) -> DataProvider:
    """
    Factory function to create the appropriate data provider.

    Args:
        mode: DataMode.LIVE or DataMode.BACKTEST
        mt5_service: MT5Service instance (required for LIVE)
        backtest_service: BacktestService instance (required for BACKTEST)

    Returns:
        Configured DataProvider instance
    """
    if mode == DataMode.LIVE:
        if mt5_service is None:
            raise ValueError("mt5_service required for LIVE mode")
        return LiveDataProvider(mt5_service)
    else:
        if backtest_service is None:
            raise ValueError("backtest_service required for BACKTEST mode")
        return BacktestDataProvider(backtest_service, mt5_service)
