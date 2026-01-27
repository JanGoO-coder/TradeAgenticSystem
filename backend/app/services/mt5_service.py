"""MetaTrader 5 data fetching service.

This service provides methods to connect to MT5 terminal and fetch historical market data.
MT5 terminal must be installed and running for this service to function.
"""
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Timeframe mapping for MT5
TIMEFRAME_MAP = {
    "1M": 1,      # TIMEFRAME_M1
    "5M": 5,      # TIMEFRAME_M5
    "15M": 15,    # TIMEFRAME_M15
    "30M": 30,    # TIMEFRAME_M30
    "1H": 60,     # TIMEFRAME_H1 (in minutes)
    "4H": 240,    # TIMEFRAME_H4
    "1D": 1440,   # TIMEFRAME_D1
}

# Try to import MetaTrader5, but allow graceful fallback
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not installed. MT5 features will be disabled.")


class MT5Service:
    """MetaTrader 5 data fetching service."""

    def __init__(self):
        self._connected = False
        self._initialized = False
        self._cache_dir = Path("data/tick_cache")
        self._cache_ttl_hours = 24  # Cache expires after 24 hours

    @property
    def is_available(self) -> bool:
        """Check if MT5 package is available."""
        return MT5_AVAILABLE

    @property
    def is_connected(self) -> bool:
        """Check if connected to MT5 terminal."""
        return self._connected and self._initialized

    def connect(self, login: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None) -> bool:
        """
        Initialize MT5 connection.

        Args:
            login: MT5 account login (optional - uses default terminal if not set)
            password: MT5 account password
            server: Broker server name

        Returns:
            True if connection successful, False otherwise
        """
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 package not installed")
            return False

        # Initialize MT5 connection
        if not mt5.initialize():
            error = mt5.last_error()
            logger.error(f"MT5 initialization failed: {error}")
            return False

        self._initialized = True

        # Login if credentials provided
        if login and password and server:
            if not mt5.login(login, password, server=server):
                error = mt5.last_error()
                logger.error(f"MT5 login failed: {error}")
                return False

        self._connected = True
        logger.info("MT5 connection established")
        return True

    def disconnect(self):
        """Shutdown MT5 connection."""
        if MT5_AVAILABLE and self._initialized:
            mt5.shutdown()
        self._connected = False
        self._initialized = False
        logger.info("MT5 connection closed")

    def get_terminal_info(self) -> Optional[Dict]:
        """Get MT5 terminal information."""
        if not self.is_connected:
            return None

        info = mt5.terminal_info()
        if info is None:
            return None

        return {
            "connected": info.connected,
            "trade_allowed": info.trade_allowed,
            "company": info.company,
            "name": info.name,
            "path": info.path,
        }

    def get_symbols(self) -> List[str]:
        """Get available trading symbols."""
        if not self.is_connected:
            return []

        symbols = mt5.symbols_get()
        if symbols is None:
            return []

        return [s.name for s in symbols if s.visible]

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get information about a specific symbol."""
        if not self.is_connected:
            return None

        info = mt5.symbol_info(symbol)
        if info is None:
            return None

        return {
            "name": info.name,
            "description": info.description,
            "point": info.point,
            "digits": info.digits,
            "spread": info.spread,
            "trade_mode": info.trade_mode,
        }

    def _get_mt5_timeframe(self, timeframe: str) -> int:
        """Convert string timeframe to MT5 constant."""
        if not MT5_AVAILABLE:
            return 60  # Default to 1H

        tf_map = {
            "1M": mt5.TIMEFRAME_M1,
            "5M": mt5.TIMEFRAME_M5,
            "15M": mt5.TIMEFRAME_M15,
            "30M": mt5.TIMEFRAME_M30,
            "1H": mt5.TIMEFRAME_H1,
            "4H": mt5.TIMEFRAME_H4,
            "1D": mt5.TIMEFRAME_D1,
        }
        return tf_map.get(timeframe, mt5.TIMEFRAME_H1)

    def _format_rate(self, rate) -> Dict:
        """Format a rate record to a dictionary."""
        return {
            "timestamp": datetime.utcfromtimestamp(rate['time']).isoformat() + "Z",
            "open": float(rate['open']),
            "high": float(rate['high']),
            "low": float(rate['low']),
            "close": float(rate['close']),
            "volume": int(rate['tick_volume'])
        }

    def get_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        bar_count: int,
        from_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch historical OHLCV bars.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            timeframe: "1H", "15M", "5M", "1M", etc.
            bar_count: Number of bars to fetch
            from_date: Start date (default: now)

        Returns:
            List of OHLCV bar dictionaries
        """
        if not self.is_connected:
            logger.warning("MT5 not connected, cannot fetch historical bars")
            return []

        mt5_tf = self._get_mt5_timeframe(timeframe)
        from_date = from_date or datetime.utcnow()

        rates = mt5.copy_rates_from(symbol, mt5_tf, from_date, bar_count)

        if rates is None:
            error = mt5.last_error()
            logger.error(f"Failed to fetch rates for {symbol}: {error}")
            return []

        return [self._format_rate(r) for r in rates]

    def check_data_availability(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> Tuple[bool, Optional[datetime], Optional[datetime]]:
        """
        Check if MT5 has data available for the requested date range.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            from_date: Start of requested range
            to_date: End of requested range

        Returns:
            Tuple of (data_available, first_bar_date, last_bar_date)
            If data_available is False, the dates indicate the actual range available
        """
        if not self.is_connected:
            logger.warning("MT5 not connected, cannot check data availability")
            return (False, None, None)

        mt5_tf = self._get_mt5_timeframe(timeframe)

        # Fetch a small sample to check boundaries
        rates = mt5.copy_rates_range(symbol, mt5_tf, from_date, to_date)

        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            logger.warning(f"No data available for {symbol} {timeframe} from {from_date} to {to_date}: {error}")
            return (False, None, None)

        # Get actual date range from returned data
        first_bar = datetime.utcfromtimestamp(rates[0]['time'])
        last_bar = datetime.utcfromtimestamp(rates[-1]['time'])

        # Check if we got data covering at least 80% of requested range
        requested_span = (to_date - from_date).total_seconds()
        actual_span = (last_bar - first_bar).total_seconds()
        coverage = actual_span / requested_span if requested_span > 0 else 0

        logger.info(f"MT5 data check for {symbol} {timeframe}: {len(rates)} bars, "
                    f"range {first_bar} to {last_bar}, coverage {coverage:.1%}")

        # Consider data available if coverage is at least 50%
        data_available = coverage >= 0.5 and len(rates) >= 10

        return (data_available, first_bar, last_bar)

    def _get_cache_path(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> Path:
        """Get the cache file path for a specific data request."""
        from_str = from_date.strftime("%Y%m%d")
        to_str = to_date.strftime("%Y%m%d")
        cache_subdir = self._cache_dir / symbol
        cache_subdir.mkdir(parents=True, exist_ok=True)
        return cache_subdir / f"{timeframe}_{from_str}_{to_str}.parquet"

    def _get_cache_meta_path(self, cache_path: Path) -> Path:
        """Get the metadata file path for a cache file."""
        return cache_path.with_suffix(".meta")

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists, is not expired (24h TTL), and is from MT5."""
        if not cache_path.exists():
            return False

        # Check metadata file exists (proves data came from MT5)
        meta_path = self._get_cache_meta_path(cache_path)
        if not meta_path.exists():
            logger.info(f"Cache missing metadata (not from MT5): {cache_path}")
            # Delete orphaned cache file
            try:
                cache_path.unlink()
            except Exception:
                pass
            return False

        # Check file age
        file_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - file_mtime).total_seconds() / 3600

        if age_hours > self._cache_ttl_hours:
            logger.info(f"Cache expired ({age_hours:.1f}h old): {cache_path}")
            return False

        return True

    def _load_from_cache(self, cache_path: Path) -> Optional[List[Dict]]:
        """Load data from Parquet cache file."""
        try:
            df = pd.read_parquet(cache_path)
            logger.info(f"Loaded {len(df)} bars from cache: {cache_path}")
            return df.to_dict('records')
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_path}: {e}")
            return None

    def _save_to_cache(self, cache_path: Path, bars: List[Dict]) -> bool:
        """Save data to Parquet cache file with metadata marker."""
        try:
            df = pd.DataFrame(bars)
            df.to_parquet(cache_path, index=False)

            # Write metadata file to mark this as valid MT5 data
            meta_path = self._get_cache_meta_path(cache_path)
            meta_path.write_text(f"source=mt5\ncreated={datetime.now().isoformat()}\nbars={len(bars)}")

            logger.info(f"Saved {len(bars)} bars to cache: {cache_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_path}: {e}")
            return False

    def get_historical_range(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Fetch bars within a date range with Parquet caching.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            from_date: Start of range
            to_date: End of range
            use_cache: Whether to use disk cache (default True)

        Returns:
            List of OHLCV bar dictionaries
        """
        # Check cache first
        cache_path = self._get_cache_path(symbol, timeframe, from_date, to_date)

        if use_cache and self._is_cache_valid(cache_path):
            cached_data = self._load_from_cache(cache_path)
            if cached_data:
                return cached_data

        # Fetch from MT5
        if not self.is_connected:
            logger.warning("MT5 not connected, cannot fetch historical range")
            return []

        mt5_tf = self._get_mt5_timeframe(timeframe)

        rates = mt5.copy_rates_range(symbol, mt5_tf, from_date, to_date)

        if rates is None:
            error = mt5.last_error()
            logger.error(f"Failed to fetch rate range for {symbol}: {error}")
            return []

        bars = [self._format_rate(r) for r in rates]

        # Save to cache for future use
        if use_cache and bars:
            self._save_to_cache(cache_path, bars)

        return bars

    def get_latest_bars(
        self,
        symbol: str,
        timeframe: str,
        bar_count: int
    ) -> List[Dict]:
        """
        Fetch most recent bars (for live updates).

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            bar_count: Number of bars

        Returns:
            List of OHLCV bar dictionaries
        """
        return self.get_historical_bars(symbol, timeframe, bar_count, datetime.utcnow())

    def get_current_tick(self, symbol: str) -> Optional[Dict]:
        """
        Get latest tick data.

        Args:
            symbol: Trading symbol

        Returns:
            Tick data dictionary or None
        """
        if not self.is_connected:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "volume": tick.volume,
            "time": datetime.utcfromtimestamp(tick.time).isoformat() + "Z"
        }


# Singleton instance
_mt5_service: Optional[MT5Service] = None


def get_mt5_service() -> MT5Service:
    """Get the singleton MT5 service instance."""
    global _mt5_service
    if _mt5_service is None:
        _mt5_service = MT5Service()
    return _mt5_service
