"""Backtest simulation service.

Simulates historical data playback for strategy testing.
Allows stepping through historical data bar by bar.
"""
from datetime import datetime
from typing import List, Dict, Optional
import logging

from app.services.mt5_service import get_mt5_service

logger = logging.getLogger(__name__)


class BacktestService:
    """Simulates historical data as live stream for backtesting."""

    def __init__(self):
        self.mt5 = get_mt5_service()
        self._running = False
        self._current_index = 0
        self._data: Dict[str, List[Dict]] = {}
        self._symbol: Optional[str] = None
        self._from_date: Optional[datetime] = None
        self._to_date: Optional[datetime] = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if backtest data is loaded."""
        return self._loaded and len(self._data) > 0

    @property
    def is_running(self) -> bool:
        """Check if backtest is running."""
        return self._running

    @property
    def current_index(self) -> int:
        """Get current position in the data."""
        return self._current_index

    @property
    def total_bars(self) -> int:
        """Get total number of bars in the primary timeframe (1H)."""
        return len(self._data.get("1H", []))

    @property
    def progress(self) -> float:
        """Get progress as percentage (0-100)."""
        if self.total_bars == 0:
            return 0.0
        return (self._current_index / self.total_bars) * 100

    def load_backtest_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframes: List[str] = None
    ) -> Dict:
        """
        Load historical data for backtesting.

        Args:
            symbol: Trading symbol
            from_date: Start date for backtest
            to_date: End date for backtest
            timeframes: List of timeframes to load

        Returns:
            Dict with loading status and bar counts

        Raises:
            ValueError: If MT5 is not connected or no data available
        """
        if timeframes is None:
            timeframes = ["1H", "15M", "5M"]

        self._symbol = symbol
        self._from_date = from_date
        self._to_date = to_date
        self._data = {}
        self._current_index = 0
        self._running = False

        # Check if MT5 is connected - require MT5, no sample data fallback
        if not self.mt5.is_connected:
            # Try to connect
            if not self.mt5.connect():
                raise ValueError(
                    "MT5 not connected. Please ensure MetaTrader 5 terminal is running "
                    "and credentials are configured in environment variables."
                )

        # Load data from MT5
        for tf in timeframes:
            bars = self.mt5.get_historical_range(symbol, tf, from_date, to_date)
            if not bars:
                raise ValueError(
                    f"MT5 returned no data for {symbol} {tf} from {from_date} to {to_date}. "
                    "Check if the symbol is available in your MT5 terminal."
                )
            self._data[tf] = bars
            logger.info(f"Loaded {len(bars)} bars for {symbol} {tf}")

        self._loaded = True

        return {
            "symbol": symbol,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "bar_counts": {tf: len(bars) for tf, bars in self._data.items()},
            "source": "mt5"
        }

    def get_current_snapshot(self, bars_per_tf: Dict[str, int] = None) -> Dict:
        """
        Get current visible data window.

        Args:
            bars_per_tf: Number of bars to show per timeframe

        Returns:
            Dict with current data snapshot
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        if bars_per_tf is None:
            bars_per_tf = {"1H": 50, "15M": 100, "5M": 50}

        snapshot = {
            "symbol": self._symbol,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "timeframe_bars": {}
        }

        for tf, bars in self._data.items():
            max_bars = bars_per_tf.get(tf, 50)
            end = min(self._current_index + max_bars, len(bars))
            start = max(0, end - max_bars)
            snapshot["timeframe_bars"][tf] = bars[start:end]

        return snapshot

    def step_forward(self, bars: int = 1) -> Dict:
        """
        Advance simulation by N bars.

        Args:
            bars: Number of bars to advance

        Returns:
            Dict with new position info
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        self._current_index = min(self._current_index + bars, self.total_bars - 1)

        return {
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "has_more": self._current_index < self.total_bars - 1
        }

    def step_backward(self, bars: int = 1) -> Dict:
        """
        Move simulation backward by N bars.

        Args:
            bars: Number of bars to go back

        Returns:
            Dict with new position info
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        self._current_index = max(0, self._current_index - bars)

        return {
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "has_more": self._current_index < self.total_bars - 1
        }

    def reset(self) -> Dict:
        """Reset to beginning of data."""
        self._current_index = 0
        self._running = False

        return {
            "current_index": 0,
            "total_bars": self.total_bars,
            "progress": 0.0,
            "message": "Reset to beginning"
        }

    def jump_to(self, index: int) -> Dict:
        """
        Jump to a specific index in the data.

        Args:
            index: Target index

        Returns:
            Dict with new position info
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        self._current_index = max(0, min(index, self.total_bars - 1))

        return {
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress
        }

    def get_status(self) -> Dict:
        """Get current backtest status."""
        return {
            "loaded": self.is_loaded,
            "running": self.is_running,
            "symbol": self._symbol,
            "from_date": self._from_date.isoformat() if self._from_date else None,
            "to_date": self._to_date.isoformat() if self._to_date else None,
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress
        }


# Singleton instance
_backtest_service: Optional[BacktestService] = None


def get_backtest_service() -> BacktestService:
    """Get the singleton backtest service instance."""
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService()
    return _backtest_service
