"""MetaTrader 5 data fetching and trading service.

This service provides methods to connect to MT5 terminal, fetch historical market data,
and execute trading operations. MT5 terminal must be installed and running for this service to function.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import os
import json
import gzip
from pathlib import Path

from app.domain.trading import (
    AccountInfo, Position, PendingOrder, HistoricalTrade,
    OrderRequest, OrderResponse, OrderType,
    ModifyPositionRequest, ClosePositionResponse,
    LotSizeRequest, LotSizeResponse
)
from app.core.config import get_settings

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


# ============================================================================
# TICK CACHE MANAGER - Hourly chunked tick data with lazy loading
# ============================================================================

class TickCacheManager:
    """
    Manages tick data caching with hourly chunks and 3-chunk sliding window.

    Features:
    - Stores tick data in hourly gzip-compressed JSON files
    - Maintains max 3 hour-chunks in memory (prev/current/next)
    - Lazy-loads chunks as simulation progresses
    - Memory limit ~50MB (configurable)
    """

    def __init__(self, symbol: str, cache_dir: str = None):
        settings = get_settings()
        self.symbol = symbol
        self.cache_dir = Path(cache_dir or settings.tick_cache_dir) / symbol
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory chunk cache: {hour_key: [ticks]}
        self._loaded_chunks: Dict[str, List[Dict]] = {}
        self._chunk_load_order: List[str] = []  # Track load order for eviction
        self._max_chunks = settings.tick_buffer_hours  # Default 3

        # Statistics
        self._total_ticks_loaded = 0
        self._cache_hits = 0
        self._cache_misses = 0

    def _get_chunk_key(self, dt: datetime) -> str:
        """Get chunk key for a datetime (YYYYMMDD_HH format)."""
        return dt.strftime("%Y%m%d_%H")

    def _get_chunk_path(self, chunk_key: str) -> Path:
        """Get file path for a chunk."""
        return self.cache_dir / f"{chunk_key}.json.gz"

    def _save_chunk(self, chunk_key: str, ticks: List[Dict]) -> bool:
        """Save tick chunk to compressed file."""
        try:
            path = self._get_chunk_path(chunk_key)
            # Compress tick data (use short keys to save space)
            compressed_ticks = [
                {"t": t["time"], "b": t["bid"], "a": t["ask"], "v": t.get("volume", 0)}
                for t in ticks
            ]
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                json.dump({
                    "symbol": self.symbol,
                    "chunk_key": chunk_key,
                    "tick_count": len(ticks),
                    "ticks": compressed_ticks
                }, f)
            logger.info(f"Saved tick chunk {chunk_key}: {len(ticks)} ticks")
            return True
        except Exception as e:
            logger.error(f"Failed to save tick chunk {chunk_key}: {e}")
            return False

    def _load_chunk(self, chunk_key: str) -> Optional[List[Dict]]:
        """Load tick chunk from file (returns None if not cached)."""
        path = self._get_chunk_path(chunk_key)
        if not path.exists():
            return None

        try:
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
            # Expand compressed tick format
            ticks = [
                {"time": t["t"], "bid": t["b"], "ask": t["a"], "volume": t.get("v", 0)}
                for t in data["ticks"]
            ]
            logger.info(f"Loaded tick chunk {chunk_key}: {len(ticks)} ticks from cache")
            return ticks
        except Exception as e:
            logger.error(f"Failed to load tick chunk {chunk_key}: {e}")
            return None

    def _evict_old_chunks(self):
        """Evict oldest chunks to stay within memory limit."""
        while len(self._loaded_chunks) > self._max_chunks and self._chunk_load_order:
            oldest_key = self._chunk_load_order.pop(0)
            if oldest_key in self._loaded_chunks:
                evicted_count = len(self._loaded_chunks[oldest_key])
                del self._loaded_chunks[oldest_key]
                self._total_ticks_loaded -= evicted_count
                logger.debug(f"Evicted tick chunk {oldest_key} ({evicted_count} ticks)")

    def get_ticks_for_hour(self, hour_start: datetime, mt5_service: 'MT5Service' = None) -> List[Dict]:
        """
        Get all ticks for a specific hour. Lazy-loads from cache or MT5.

        Args:
            hour_start: Start of the hour (minute/second should be 0)
            mt5_service: MT5Service instance for fetching if not cached

        Returns:
            List of tick dicts with time, bid, ask, volume
        """
        chunk_key = self._get_chunk_key(hour_start)

        # Check if already loaded
        if chunk_key in self._loaded_chunks:
            self._cache_hits += 1
            logger.debug(f"Tick cache HIT for {chunk_key}: {len(self._loaded_chunks[chunk_key])} ticks")
            return self._loaded_chunks[chunk_key]

        self._cache_misses += 1

        # Try to load from file cache
        ticks = self._load_chunk(chunk_key)

        # If not cached, fetch from MT5
        if ticks is None and mt5_service:
            if mt5_service.is_connected:
                hour_end = hour_start + timedelta(hours=1)
                logger.info(f"Fetching ticks from MT5 for {chunk_key}: {hour_start} to {hour_end}")
                ticks = mt5_service.get_raw_ticks(self.symbol, hour_start, hour_end)
                if ticks:
                    # Save to cache
                    saved = self._save_chunk(chunk_key, ticks)
                    logger.info(f"Fetched and cached {len(ticks)} ticks for {chunk_key}, saved={saved}")
                else:
                    logger.warning(f"No ticks returned from MT5 for {chunk_key}")
            else:
                logger.warning(f"MT5 not connected, cannot fetch ticks for {chunk_key}")
        elif ticks is None:
            logger.warning(f"No mt5_service provided and no cache for {chunk_key}")

        if ticks is None:
            ticks = []

        # Evict old chunks before loading new one
        self._evict_old_chunks()

        # Add to loaded chunks
        self._loaded_chunks[chunk_key] = ticks
        self._chunk_load_order.append(chunk_key)
        self._total_ticks_loaded += len(ticks)

        return ticks

    def preload_window(self, center_time: datetime, mt5_service: 'MT5Service' = None) -> Dict[str, int]:
        """
        Preload tick chunks for a time window (prev/current/next hour).

        Args:
            center_time: Current simulation time
            mt5_service: MT5Service for fetching

        Returns:
            Dict with loaded chunk info
        """
        # Normalize to hour start
        center_hour = center_time.replace(minute=0, second=0, microsecond=0)
        prev_hour = center_hour - timedelta(hours=1)
        next_hour = center_hour + timedelta(hours=1)

        loaded = {}
        for hour in [prev_hour, center_hour, next_hour]:
            ticks = self.get_ticks_for_hour(hour, mt5_service)
            loaded[self._get_chunk_key(hour)] = len(ticks)

        return loaded

    def get_ticks_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Get all ticks within a time range from loaded chunks.

        Args:
            start_time: Range start (unix timestamp or datetime)
            end_time: Range end

        Returns:
            List of ticks in range, sorted by time
        """
        if isinstance(start_time, datetime):
            start_ts = start_time.timestamp()
        else:
            start_ts = start_time

        if isinstance(end_time, datetime):
            end_ts = end_time.timestamp()
        else:
            end_ts = end_time

        result = []
        for chunk_ticks in self._loaded_chunks.values():
            for tick in chunk_ticks:
                if start_ts <= tick["time"] < end_ts:
                    result.append(tick)

        # Sort by time
        result.sort(key=lambda t: t["time"])
        return result

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "symbol": self.symbol,
            "loaded_chunks": len(self._loaded_chunks),
            "chunk_keys": list(self._loaded_chunks.keys()),
            "total_ticks_loaded": self._total_ticks_loaded,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits / max(1, self._cache_hits + self._cache_misses)
        }

    def clear(self):
        """Clear all loaded chunks from memory."""
        self._loaded_chunks.clear()
        self._chunk_load_order.clear()
        self._total_ticks_loaded = 0


class MT5Service:
    """MetaTrader 5 data fetching service."""

    def __init__(self):
        self._connected = False
        self._initialized = False

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

    def get_historical_range(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict]:
        """
        Fetch bars within a date range.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            from_date: Start of range
            to_date: End of range

        Returns:
            List of OHLCV bar dictionaries
        """
        if not self.is_connected:
            logger.warning("MT5 not connected, cannot fetch historical range")
            return []

        mt5_tf = self._get_mt5_timeframe(timeframe)

        rates = mt5.copy_rates_range(symbol, mt5_tf, from_date, to_date)

        if rates is None:
            error = mt5.last_error()
            logger.error(f"Failed to fetch rate range for {symbol}: {error}")
            return []

        return [self._format_rate(r) for r in rates]

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

    def get_spread_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, float]:
        """
        Fetch historical tick data and downsample to 1 tick per minute for spread calculation.

        Args:
            symbol: Trading symbol
            from_date: Start of range
            to_date: End of range

        Returns:
            Dictionary mapping minute timestamps (ISO format) to spread values
        """
        if not self.is_connected:
            logger.warning("MT5 not connected, cannot fetch spread data")
            return {}

        try:
            # Fetch all ticks in range
            ticks = mt5.copy_ticks_range(symbol, from_date, to_date, mt5.COPY_TICKS_ALL)

            if ticks is None or len(ticks) == 0:
                logger.warning(f"No tick data available for {symbol}")
                # Fall back to symbol info spread
                return self._generate_fallback_spread(symbol, from_date, to_date)

            # Downsample to 1 tick per minute
            spread_map = {}
            seen_minutes = set()

            for tick in ticks:
                tick_time = datetime.utcfromtimestamp(tick['time'])
                # Round down to minute
                minute_key = tick_time.replace(second=0, microsecond=0)
                minute_str = minute_key.isoformat() + "Z"

                if minute_str not in seen_minutes:
                    spread = tick['ask'] - tick['bid']
                    spread_map[minute_str] = round(spread, 6)
                    seen_minutes.add(minute_str)

            logger.info(f"Loaded spread data for {symbol}: {len(spread_map)} minutes")
            return spread_map

        except Exception as e:
            logger.error(f"Error fetching spread data: {e}")
            return self._generate_fallback_spread(symbol, from_date, to_date)

    def _generate_fallback_spread(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, float]:
        """Generate fallback spread data using symbol info static spread."""
        symbol_info = self.get_symbol_info(symbol)
        if symbol_info is None:
            # Default spreads by symbol type
            if "JPY" in symbol:
                default_spread = 0.02  # 2 pips for JPY pairs
            elif "XAU" in symbol or "GOLD" in symbol:
                default_spread = 0.30  # 30 pips for gold
            else:
                default_spread = 0.00012  # 1.2 pips for major pairs
        else:
            # Convert spread from points to price
            point = symbol_info.get("point", 0.00001)
            default_spread = symbol_info.get("spread", 12) * point

        # Generate minute-by-minute spread with slight variation
        spread_map = {}
        current = from_date
        import random
        random.seed(sum(ord(c) for c in symbol))

        while current <= to_date:
            minute_str = current.replace(second=0, microsecond=0).isoformat() + "Z"
            # Add ±10% variation
            variation = 1.0 + (random.random() - 0.5) * 0.2
            spread_map[minute_str] = round(default_spread * variation, 6)
            current += timedelta(minutes=1)

        logger.info(f"Generated fallback spread data for {symbol}: {len(spread_map)} minutes")
        return spread_map

    def get_raw_ticks(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict]:
        """
        Fetch raw tick data without downsampling (for tick-by-tick replay).

        Args:
            symbol: Trading symbol
            from_date: Start of range
            to_date: End of range

        Returns:
            List of tick dictionaries with time, bid, ask, volume
        """
        if not self.is_connected:
            logger.warning("MT5 not connected, cannot fetch raw ticks")
            return []

        try:
            ticks = mt5.copy_ticks_range(symbol, from_date, to_date, mt5.COPY_TICKS_ALL)

            if ticks is None or len(ticks) == 0:
                logger.warning(f"No tick data available for {symbol} from {from_date} to {to_date}")
                return []

            # Convert to list of dicts
            result = []
            for tick in ticks:
                result.append({
                    "time": int(tick["time"]),
                    "bid": float(tick["bid"]),
                    "ask": float(tick["ask"]),
                    "volume": int(tick.get("volume", 0))
                })

            logger.info(f"Fetched {len(result)} raw ticks for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Error fetching raw ticks: {e}")
            return []

    # ==================== TRADING METHODS ====================

    def get_account_info(self) -> Optional[AccountInfo]:
        """
        Get MT5 account information.

        Returns:
            AccountInfo object with balance, equity, margin details, or None if not connected
        """
        if not self.is_connected:
            logger.warning("MT5 not connected, cannot get account info")
            return None

        info = mt5.account_info()
        if info is None:
            error = mt5.last_error()
            logger.error(f"Failed to get account info: {error}")
            return None

        terminal = mt5.terminal_info()

        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level if info.margin_level > 0 else None,
            profit=info.profit,
            currency=info.currency,
            leverage=info.leverage,
            name=info.name,
            server=info.server,
            trade_allowed=terminal.trade_allowed if terminal else True
        )

    def place_market_order(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        comment: str = "",
        magic: int = 12345,
        deviation: int = 20
    ) -> OrderResponse:
        """
        Execute a market buy or sell order.

        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            order_type: MARKET_BUY or MARKET_SELL
            volume: Lot size
            stop_loss: Stop loss price
            take_profit: Take profit price (optional)
            comment: Order comment
            magic: Magic number for identification
            deviation: Maximum price deviation in points

        Returns:
            OrderResponse with execution details
        """
        if not self.is_connected:
            return OrderResponse(
                success=False,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=0.0,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=-1,
                error_message="MT5 not connected"
            )

        # Get symbol info for price
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return OrderResponse(
                success=False,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=0.0,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=-1,
                error_message=f"Symbol {symbol} not found"
            )

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                return OrderResponse(
                    success=False,
                    order_type=order_type.value,
                    symbol=symbol,
                    volume=volume,
                    price=0.0,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    error_code=-1,
                    error_message=f"Failed to select symbol {symbol}"
                )

        # Determine price and order action
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResponse(
                success=False,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=0.0,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=-1,
                error_message="Failed to get tick data"
            )

        if order_type == OrderType.MARKET_BUY:
            price = tick.ask
            mt5_type = mt5.ORDER_TYPE_BUY
        else:
            price = tick.bid
            mt5_type = mt5.ORDER_TYPE_SELL

        # Build request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit if take_profit else 0.0,
            "deviation": deviation,
            "magic": magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Execute order
        result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            return OrderResponse(
                success=False,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=error[0] if error else -1,
                error_message=str(error[1]) if error else "Unknown error"
            )

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResponse(
                success=False,
                ticket=result.order if result.order else None,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=result.price if result.price else price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=result.retcode,
                error_message=result.comment
            )

        return OrderResponse(
            success=True,
            ticket=result.order,
            order_type=order_type.value,
            symbol=symbol,
            volume=result.volume,
            price=result.price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            execution_time=datetime.utcnow().isoformat() + "Z"
        )

    def place_pending_order(
        self,
        symbol: str,
        order_type: OrderType,
        volume: float,
        price: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        comment: str = "",
        magic: int = 12345
    ) -> OrderResponse:
        """
        Place a pending order (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP).

        Args:
            symbol: Trading symbol
            order_type: BUY_LIMIT, SELL_LIMIT, BUY_STOP, or SELL_STOP
            volume: Lot size
            price: Order price
            stop_loss: Stop loss price
            take_profit: Take profit price (optional)
            comment: Order comment
            magic: Magic number

        Returns:
            OrderResponse with order details
        """
        if not self.is_connected:
            return OrderResponse(
                success=False,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=-1,
                error_message="MT5 not connected"
            )

        # Map order type
        type_map = {
            OrderType.BUY_LIMIT: mt5.ORDER_TYPE_BUY_LIMIT,
            OrderType.SELL_LIMIT: mt5.ORDER_TYPE_SELL_LIMIT,
            OrderType.BUY_STOP: mt5.ORDER_TYPE_BUY_STOP,
            OrderType.SELL_STOP: mt5.ORDER_TYPE_SELL_STOP,
        }

        if order_type not in type_map:
            return OrderResponse(
                success=False,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=-1,
                error_message=f"Invalid pending order type: {order_type}"
            )

        # Ensure symbol is visible
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return OrderResponse(
                success=False,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=-1,
                error_message=f"Symbol {symbol} not found"
            )

        if not symbol_info.visible:
            mt5.symbol_select(symbol, True)

        # Build request
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": type_map[order_type],
            "price": price,
            "sl": stop_loss,
            "tp": take_profit if take_profit else 0.0,
            "magic": magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = mt5.last_error() if result is None else (result.retcode, result.comment)
            return OrderResponse(
                success=False,
                ticket=result.order if result and result.order else None,
                order_type=order_type.value,
                symbol=symbol,
                volume=volume,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                error_code=error[0] if error else -1,
                error_message=str(error[1]) if error else "Unknown error"
            )

        return OrderResponse(
            success=True,
            ticket=result.order,
            order_type=order_type.value,
            symbol=symbol,
            volume=result.volume,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            execution_time=datetime.utcnow().isoformat() + "Z"
        )

    def modify_order(
        self,
        ticket: int,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Modify a pending order's price, SL, or TP.

        Args:
            ticket: Order ticket number
            price: New order price (optional)
            stop_loss: New stop loss (optional)
            take_profit: New take profit (optional)

        Returns:
            Tuple of (success, message)
        """
        if not self.is_connected:
            return False, "MT5 not connected"

        # Get current order
        orders = mt5.orders_get(ticket=ticket)
        if not orders or len(orders) == 0:
            return False, f"Order {ticket} not found"

        order = orders[0]

        # Build request with current values as defaults
        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": ticket,
            "price": price if price is not None else order.price_open,
            "sl": stop_loss if stop_loss is not None else order.sl,
            "tp": take_profit if take_profit is not None else order.tp,
            "type_time": mt5.ORDER_TIME_GTC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else str(mt5.last_error())
            return False, f"Failed to modify order: {error}"

        return True, "Order modified successfully"

    def cancel_order(self, ticket: int) -> Tuple[bool, str]:
        """
        Cancel a pending order.

        Args:
            ticket: Order ticket to cancel

        Returns:
            Tuple of (success, message)
        """
        if not self.is_connected:
            return False, "MT5 not connected"

        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else str(mt5.last_error())
            return False, f"Failed to cancel order: {error}"

        return True, "Order cancelled successfully"

    def get_positions(self) -> List[Position]:
        """
        Get all open positions.

        Returns:
            List of Position objects
        """
        if not self.is_connected:
            return []

        positions = mt5.positions_get()
        if positions is None:
            return []

        result = []
        for pos in positions:
            # Calculate pips
            symbol_info = mt5.symbol_info(pos.symbol)
            point = symbol_info.point if symbol_info else 0.0001
            digits = symbol_info.digits if symbol_info else 5

            if pos.type == mt5.POSITION_TYPE_BUY:
                pips = (pos.price_current - pos.price_open) / point
                if digits == 3 or digits == 5:
                    pips /= 10
            else:
                pips = (pos.price_open - pos.price_current) / point
                if digits == 3 or digits == 5:
                    pips /= 10

            result.append(Position(
                ticket=pos.ticket,
                symbol=pos.symbol,
                type="BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
                volume=pos.volume,
                open_price=pos.price_open,
                current_price=pos.price_current,
                stop_loss=pos.sl,
                take_profit=pos.tp if pos.tp > 0 else None,
                profit=pos.profit,
                swap=pos.swap,
                commission=pos.commission,
                open_time=datetime.utcfromtimestamp(pos.time).isoformat() + "Z",
                magic=pos.magic,
                comment=pos.comment,
                pips=round(pips, 1)
            ))

        return result

    def get_position(self, ticket: int) -> Optional[Position]:
        """
        Get a specific position by ticket.

        Args:
            ticket: Position ticket number

        Returns:
            Position object or None if not found
        """
        if not self.is_connected:
            return None

        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return None

        pos = positions[0]
        symbol_info = mt5.symbol_info(pos.symbol)
        point = symbol_info.point if symbol_info else 0.0001
        digits = symbol_info.digits if symbol_info else 5

        if pos.type == mt5.POSITION_TYPE_BUY:
            pips = (pos.price_current - pos.price_open) / point
            if digits == 3 or digits == 5:
                pips /= 10
        else:
            pips = (pos.price_open - pos.price_current) / point
            if digits == 3 or digits == 5:
                pips /= 10

        return Position(
            ticket=pos.ticket,
            symbol=pos.symbol,
            type="BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
            volume=pos.volume,
            open_price=pos.price_open,
            current_price=pos.price_current,
            stop_loss=pos.sl,
            take_profit=pos.tp if pos.tp > 0 else None,
            profit=pos.profit,
            swap=pos.swap,
            commission=pos.commission,
            open_time=datetime.utcfromtimestamp(pos.time).isoformat() + "Z",
            magic=pos.magic,
            comment=pos.comment,
            pips=round(pips, 1)
        )

    def modify_position(
        self,
        ticket: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Modify an open position's SL/TP.

        Args:
            ticket: Position ticket number
            stop_loss: New stop loss price (optional)
            take_profit: New take profit price (optional)

        Returns:
            Tuple of (success, message)
        """
        if not self.is_connected:
            return False, "MT5 not connected"

        # Get current position
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return False, f"Position {ticket} not found"

        pos = positions[0]

        # Build request
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": pos.symbol,
            "sl": stop_loss if stop_loss is not None else pos.sl,
            "tp": take_profit if take_profit is not None else pos.tp,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else str(mt5.last_error())
            return False, f"Failed to modify position: {error}"

        return True, "Position modified successfully"

    def close_position(
        self,
        ticket: int,
        volume: Optional[float] = None
    ) -> ClosePositionResponse:
        """
        Close an open position (fully or partially).

        Args:
            ticket: Position ticket number
            volume: Volume to close (None = close all)

        Returns:
            ClosePositionResponse with close details
        """
        if not self.is_connected:
            return ClosePositionResponse(
                success=False,
                ticket=ticket,
                symbol="",
                volume_closed=0.0,
                close_price=0.0,
                profit=0.0,
                error_code=-1,
                error_message="MT5 not connected"
            )

        # Get position info
        positions = mt5.positions_get(ticket=ticket)
        if not positions or len(positions) == 0:
            return ClosePositionResponse(
                success=False,
                ticket=ticket,
                symbol="",
                volume_closed=0.0,
                close_price=0.0,
                profit=0.0,
                error_code=-1,
                error_message=f"Position {ticket} not found"
            )

        pos = positions[0]
        close_volume = volume if volume is not None else pos.volume

        # Determine close price and order type
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return ClosePositionResponse(
                success=False,
                ticket=ticket,
                symbol=pos.symbol,
                volume_closed=0.0,
                close_price=0.0,
                profit=0.0,
                error_code=-1,
                error_message="Failed to get tick data"
            )

        if pos.type == mt5.POSITION_TYPE_BUY:
            price = tick.bid
            close_type = mt5.ORDER_TYPE_SELL
        else:
            price = tick.ask
            close_type = mt5.ORDER_TYPE_BUY

        # Build close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": pos.symbol,
            "volume": close_volume,
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else str(mt5.last_error())
            return ClosePositionResponse(
                success=False,
                ticket=ticket,
                symbol=pos.symbol,
                volume_closed=0.0,
                close_price=price,
                profit=pos.profit,
                error_code=result.retcode if result else -1,
                error_message=error
            )

        return ClosePositionResponse(
            success=True,
            ticket=ticket,
            symbol=pos.symbol,
            volume_closed=close_volume,
            close_price=result.price,
            profit=pos.profit
        )

    def close_all_positions(self, symbol: Optional[str] = None) -> List[ClosePositionResponse]:
        """
        Close all open positions (emergency function).

        Args:
            symbol: Optional symbol filter (None = close all symbols)

        Returns:
            List of ClosePositionResponse for each position
        """
        if not self.is_connected:
            return []

        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if not positions:
            return []

        results = []
        for pos in positions:
            result = self.close_position(pos.ticket)
            results.append(result)

        return results

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[PendingOrder]:
        """
        Get all pending orders.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of PendingOrder objects
        """
        if not self.is_connected:
            return []

        if symbol:
            orders = mt5.orders_get(symbol=symbol)
        else:
            orders = mt5.orders_get()

        if not orders:
            return []

        type_map = {
            mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
            mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
            mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
            mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
        }

        return [
            PendingOrder(
                ticket=order.ticket,
                symbol=order.symbol,
                order_type=type_map.get(order.type, "UNKNOWN"),
                volume=order.volume_current,
                price=order.price_open,
                stop_loss=order.sl,
                take_profit=order.tp if order.tp > 0 else None,
                time_setup=datetime.utcfromtimestamp(order.time_setup).isoformat() + "Z",
                magic=order.magic,
                comment=order.comment
            )
            for order in orders
            if order.type in type_map
        ]

    def get_trade_history(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> List[HistoricalTrade]:
        """
        Get historical closed trades.

        Args:
            from_date: Start date (default: 30 days ago)
            to_date: End date (default: now)
            symbol: Optional symbol filter

        Returns:
            List of HistoricalTrade objects
        """
        if not self.is_connected:
            return []

        if from_date is None:
            from_date = datetime.utcnow() - timedelta(days=30)
        if to_date is None:
            to_date = datetime.utcnow()

        # Get deals
        deals = mt5.history_deals_get(from_date, to_date)
        if not deals:
            return []

        # Filter by symbol if specified
        if symbol:
            deals = [d for d in deals if d.symbol == symbol]

        # Filter to entry/exit deals only
        results = []
        for deal in deals:
            if deal.entry in [mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT]:
                deal_type = "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL"
                results.append(HistoricalTrade(
                    ticket=deal.ticket,
                    order_ticket=deal.order,
                    symbol=deal.symbol,
                    type=deal_type,
                    volume=deal.volume,
                    price=deal.price,
                    profit=deal.profit,
                    swap=deal.swap,
                    commission=deal.commission,
                    time=datetime.utcfromtimestamp(deal.time).isoformat() + "Z",
                    magic=deal.magic,
                    comment=deal.comment
                ))

        return results

    def calculate_lot_size(
        self,
        symbol: str,
        account_balance: float,
        risk_pct: float,
        stop_loss_pips: float
    ) -> Optional[LotSizeResponse]:
        """
        Calculate optimal lot size based on risk parameters.

        Args:
            symbol: Trading symbol
            account_balance: Account balance
            risk_pct: Risk percentage (e.g., 1.0 for 1%)
            stop_loss_pips: Stop loss distance in pips

        Returns:
            LotSizeResponse with calculated lot size, or None if calculation fails
        """
        if not self.is_connected:
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return None

        # Get tick value (value of 1 point movement for 1 lot)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        # Calculate pip value
        # For forex pairs: 1 pip = 10 points for 5-digit brokers
        point = symbol_info.point
        digits = symbol_info.digits
        pip_size = point * 10 if digits == 5 or digits == 3 else point

        # Get contract size and tick value
        contract_size = symbol_info.trade_contract_size
        tick_value = symbol_info.trade_tick_value

        # Pip value per lot
        if tick_value > 0 and point > 0:
            pip_value = (pip_size / point) * tick_value
        else:
            # Fallback calculation
            pip_value = pip_size * contract_size

        # Calculate risk amount
        risk_amount = account_balance * (risk_pct / 100)

        # Calculate lot size
        if stop_loss_pips > 0 and pip_value > 0:
            lot_size = risk_amount / (stop_loss_pips * pip_value)
        else:
            lot_size = 0.01

        # Round to broker's lot step
        lot_step = symbol_info.volume_step
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max

        lot_size = max(min_lot, min(max_lot, round(lot_size / lot_step) * lot_step))

        return LotSizeResponse(
            symbol=symbol,
            lot_size=round(lot_size, 2),
            risk_amount=round(risk_amount, 2),
            pip_value=round(pip_value, 4),
            stop_loss_pips=stop_loss_pips
        )

    def get_symbol_info_detailed(self, symbol: str) -> Optional[Dict]:
        """Get detailed symbol information including trading specifications."""
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
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "contract_size": info.trade_contract_size,
            "tick_value": info.trade_tick_value,
            "tick_size": info.trade_tick_size,
            "trade_stops_level": info.trade_stops_level,
            "trade_freeze_level": info.trade_freeze_level,
        }


# Singleton instance
_mt5_service: Optional[MT5Service] = None


def get_mt5_service() -> MT5Service:
    """Get the singleton MT5 service instance."""
    global _mt5_service
    if _mt5_service is None:
        _mt5_service = MT5Service()
    return _mt5_service
