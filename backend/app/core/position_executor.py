"""
Unified PositionExecutor Interface for Trade Execution.

This module provides a consistent interface for managing positions
across both live (MT5) and backtest modes. The agent code uses this
abstraction without knowing the underlying execution venue.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging
import uuid
import time
import random

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class TradeDirection(str, Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeResult(str, Enum):
    """Closed trade result classification."""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


class CloseReason(str, Enum):
    """Reason for position close."""
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    MANUAL = "MANUAL"
    TRAILING_STOP = "TRAILING_STOP"
    END_OF_SESSION = "END_OF_SESSION"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"


# =============================================================================
# Request/Response Models
# =============================================================================

@dataclass
class OpenPositionRequest:
    """Request to open a new position."""
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: Optional[float] = None
    volume: Optional[float] = None  # Auto-calculate if None
    risk_pct: float = 1.0  # Risk percentage for auto lot sizing
    setup_name: str = ""
    comment: str = ""
    magic: int = 12345
    # Backtest-specific
    bar_index: Optional[int] = None
    timestamp: Optional[str] = None
    agent_analysis: Optional[Dict[str, Any]] = None


@dataclass
class PositionState:
    """Current state of an open position."""
    id: str  # ticket (MT5) or uuid (backtest)
    symbol: str
    direction: TradeDirection
    volume: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: Optional[float]
    unrealized_pnl: float  # in account currency
    unrealized_pips: float
    open_time: str
    setup_name: str = ""
    # Extended fields for hierarchical model compatibility
    entry_bar_index: Optional[int] = None
    spread_at_entry: Optional[float] = None
    entry_slippage: float = 0.0
    entry_delay_ms: int = 0
    agent_analysis: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction.value if isinstance(self.direction, TradeDirection) else self.direction,
            "volume": self.volume,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pips": self.unrealized_pips,
            "open_time": self.open_time,
            "setup_name": self.setup_name,
            "entry_bar_index": self.entry_bar_index,
            "spread_at_entry": self.spread_at_entry,
            "entry_slippage": self.entry_slippage,
            "entry_delay_ms": self.entry_delay_ms,
            "agent_analysis": self.agent_analysis,
        }

    def to_hierarchical(self) -> Dict:
        """Convert to hierarchical Position format for SessionState."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction.value if isinstance(self.direction, TradeDirection) else self.direction,
            "entry_price": self.entry_price,
            "volume": self.volume,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit or 0.0,
            "opened_at": self.open_time,
            "setup_name": self.setup_name,
            "unrealized_pnl": self.unrealized_pnl,
            "current_price": self.current_price,
            "entry_bar_index": self.entry_bar_index,
            "spread_at_entry": self.spread_at_entry,
        }


@dataclass
class OpenResult:
    """Result of opening a position."""
    success: bool
    position_id: Optional[str] = None
    entry_price: float = 0.0
    volume: float = 0.0
    slippage: float = 0.0
    delay_ms: int = 0
    risk_check_passed: bool = True
    error_message: Optional[str] = None
    position: Optional[PositionState] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "position_id": self.position_id,
            "entry_price": self.entry_price,
            "volume": self.volume,
            "error_message": self.error_message,
            "position": self.position.to_dict() if self.position else None,
        }


@dataclass
class CloseResult:
    """Result of closing a position."""
    success: bool
    position_id: str
    exit_price: float = 0.0
    volume_closed: float = 0.0
    realized_pnl: float = 0.0
    realized_pips: float = 0.0
    realized_rr: float = 0.0
    exit_reason: CloseReason = CloseReason.MANUAL
    exit_time: str = ""
    result: TradeResult = TradeResult.BREAKEVEN
    error_message: Optional[str] = None
    # Extended fields
    exit_bar_index: Optional[int] = None
    exit_slippage: float = 0.0
    exit_delay_ms: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "position_id": self.position_id,
            "exit_price": self.exit_price,
            "volume_closed": self.volume_closed,
            "realized_pnl": self.realized_pnl,
            "realized_pips": self.realized_pips,
            "realized_rr": self.realized_rr,
            "exit_reason": self.exit_reason.value if isinstance(self.exit_reason, CloseReason) else self.exit_reason,
            "exit_time": self.exit_time,
            "result": self.result.value if isinstance(self.result, TradeResult) else self.result,
            "error_message": self.error_message,
            "exit_bar_index": self.exit_bar_index,
            "exit_slippage": self.exit_slippage,
            "exit_delay_ms": self.exit_delay_ms,
        }

    def to_hierarchical_trade(self, position: PositionState, pip_multiplier: float = 1.0) -> Dict:
        """Convert to hierarchical ClosedTrade format for SessionState."""
        return {
            "id": self.position_id,
            "symbol": position.symbol,
            "direction": position.direction.value if isinstance(position.direction, TradeDirection) else position.direction,
            "entry_price": position.entry_price,
            "exit_price": self.exit_price,
            "volume": self.volume_closed,
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit or 0.0,
            "opened_at": position.open_time,
            "closed_at": self.exit_time,
            "setup_name": position.setup_name,
            "pnl_pips": self.realized_pips,
            "pnl_usd": self.realized_pnl,
            "pnl_rr": self.realized_rr,
            "result": self.result.value if isinstance(self.result, TradeResult) else self.result,
            "close_reason": self.exit_reason.value if isinstance(self.exit_reason, CloseReason) else self.exit_reason,
            "entry_bar_index": position.entry_bar_index,
            "exit_bar_index": self.exit_bar_index,
            "slippage_pips": round((position.entry_slippage + self.exit_slippage) * pip_multiplier, 2),
            "execution_delay_ms": position.entry_delay_ms + self.exit_delay_ms,
            "risk_check_passed": True, # Implied if we are closing a position that was opened
            "agent_analysis": position.agent_analysis,
        }


@dataclass
class AccountState:
    """Account balance and equity state."""
    balance: float
    equity: float
    margin: float = 0.0
    free_margin: float = 0.0
    margin_level: float = 0.0
    profit: float = 0.0
    currency: str = "USD"
    leverage: int = 100

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "balance": self.balance,
            "equity": self.equity,
            "margin": self.margin,
            "free_margin": self.free_margin,
            "margin_level": self.margin_level,
            "profit": self.profit,
            "currency": self.currency,
            "leverage": self.leverage,
        }


# =============================================================================
# Abstract PositionExecutor Interface
# =============================================================================

class PositionExecutor(ABC):
    """
    Unified interface for position management.

    Works identically for both live MT5 and backtest modes.
    The agent code uses this abstraction without knowing the execution venue.
    """

    @property
    @abstractmethod
    def mode(self) -> str:
        """Current execution mode ("LIVE" or "BACKTEST")."""
        pass

    @abstractmethod
    def open_position(self, request: OpenPositionRequest) -> OpenResult:
        """
        Open a new position (market order).

        Args:
            request: OpenPositionRequest with trade details

        Returns:
            OpenResult with success status and position details
        """
        pass

    @abstractmethod
    def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        volume: Optional[float] = None,
        reason: CloseReason = CloseReason.MANUAL,
        bar_index: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> CloseResult:
        """
        Close a position (full or partial).

        Args:
            position_id: Position ID to close
            exit_price: Exit price (uses current if not set)
            volume: Volume to close (full position if not set)
            reason: Reason for closing
            bar_index: Bar index (backtest only)
            timestamp: Exit timestamp

        Returns:
            CloseResult with realized P&L
        """
        pass

    @abstractmethod
    def modify_position(
        self,
        position_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Modify position SL/TP.

        Args:
            position_id: Position ID to modify
            stop_loss: New stop loss price
            take_profit: New take profit price

        Returns:
            Tuple of (success, message)
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[PositionState]:
        """
        Get all open positions.

        Returns:
            List of current position states
        """
        pass

    @abstractmethod
    def get_position(self, position_id: str) -> Optional[PositionState]:
        """
        Get specific position by ID.

        Args:
            position_id: Position ID

        Returns:
            PositionState or None if not found
        """
        pass

    @abstractmethod
    def close_all_positions(
        self,
        symbol: Optional[str] = None,
        reason: CloseReason = CloseReason.EMERGENCY_STOP,
    ) -> List[CloseResult]:
        """
        Emergency close all positions.

        Args:
            symbol: Only close positions for this symbol (all if None)
            reason: Reason for closing

        Returns:
            List of close results
        """
        pass

    @abstractmethod
    def get_account_info(self) -> AccountState:
        """
        Get account balance/equity info.

        Returns:
            Current account state
        """
        pass

    @abstractmethod
    def calculate_lot_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        risk_pct: float,
        account_balance: Optional[float] = None,
    ) -> float:
        """
        Calculate lot size based on risk parameters.

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_pct: Risk percentage (1.0 = 1%)
            account_balance: Account balance (uses current if None)

        Returns:
            Calculated lot size
        """
        pass

    def update_unrealized_pnl(self, current_prices: Dict[str, Tuple[float, float]]):
        """
        Update unrealized P&L for all positions.

        Args:
            current_prices: Dict of {symbol: (bid, ask)}
        """
        pass

    # =========================================================================
    # Backtest-specific methods (no-op for live mode)
    # =========================================================================

    def check_tp_sl_on_bar(
        self,
        symbol: str,
        high: float,
        low: float,
        bar_index: int,
        timestamp: str,
    ) -> List[CloseResult]:
        """
        Check and auto-close positions hitting TP/SL on a bar.

        Args:
            symbol: Trading symbol
            high: Bar high price
            low: Bar low price
            bar_index: Current bar index
            timestamp: Bar timestamp

        Returns:
            List of closed trade results

        Raises:
            NotImplementedError: If called in LIVE mode
        """
        raise NotImplementedError("check_tp_sl_on_bar() only available in BACKTEST mode")

    def check_tp_sl_on_tick(
        self,
        symbol: str,
        bid: float,
        ask: float,
        tick_time: float,
        bar_index: int,
    ) -> List[CloseResult]:
        """
        Check and auto-close positions hitting TP/SL on a tick.

        Args:
            symbol: Trading symbol
            bid: Tick bid price
            ask: Tick ask price
            tick_time: Tick unix timestamp
            bar_index: Current bar index

        Returns:
            List of closed trade results

        Raises:
            NotImplementedError: If called in LIVE mode
        """
        raise NotImplementedError("check_tp_sl_on_tick() only available in BACKTEST mode")

    def get_closed_trades(self) -> List[Dict]:
        """
        Get all closed trades (backtest history).

        Returns:
            List of closed trade dicts
        """
        return []

    def get_statistics(self) -> Dict:
        """
        Get trading statistics.

        Returns:
            Statistics dict
        """
        return {}

    def reset(self):
        """Reset all positions and trade history (backtest only)."""
        pass


# =============================================================================
# MT5 Position Executor (Live)
# =============================================================================

class MT5PositionExecutor(PositionExecutor):
    """
    Live position executor wrapping MT5Service.

    Executes real trades through MetaTrader 5 terminal with
    position state caching (500ms TTL) to avoid MT5 overload.
    """

    CACHE_TTL_MS = 500  # Position cache TTL in milliseconds

    def __init__(self, mt5_service):
        """
        Initialize MT5 executor.

        Args:
            mt5_service: MT5Service instance
        """
        self._mt5 = mt5_service
        self._position_cache: List[PositionState] = []
        self._cache_time: float = 0

    @property
    def mode(self) -> str:
        return "LIVE"

    def _refresh_cache_if_stale(self):
        """Refresh position cache if TTL expired."""
        now = time.time() * 1000
        if now - self._cache_time > self.CACHE_TTL_MS:
            self._position_cache = self._fetch_positions()
            self._cache_time = now

    def _fetch_positions(self) -> List[PositionState]:
        """Fetch positions from MT5."""
        if not self._mt5.is_connected:
            return []

        mt5_positions = self._mt5.get_positions()
        result = []

        for pos in mt5_positions:
            direction = TradeDirection.LONG if pos.get("type") == "BUY" else TradeDirection.SHORT

            result.append(PositionState(
                id=str(pos["ticket"]),
                symbol=pos["symbol"],
                direction=direction,
                volume=pos["volume"],
                entry_price=pos["open_price"],
                current_price=pos["current_price"],
                stop_loss=pos["stop_loss"],
                take_profit=pos.get("take_profit"),
                unrealized_pnl=pos["profit"],
                unrealized_pips=pos.get("pips", 0.0),
                open_time=pos["open_time"],
                setup_name=pos.get("comment", ""),
            ))

        return result

    def open_position(self, request: OpenPositionRequest) -> OpenResult:
        """Open position through MT5."""
        if not self._mt5.is_connected:
            return OpenResult(
                success=False,
                error_message="MT5 not connected",
            )

        # Calculate lot size if not provided
        volume = request.volume
        if volume is None:
            volume = self.calculate_lot_size(
                request.symbol,
                request.entry_price,
                request.stop_loss,
                request.risk_pct,
            )

        # Determine order type
        from app.domain.trading import (
    BacktestPosition, BacktestTrade, BacktestStatistics,
    BacktestExport, BacktestExportMetadata, BacktestExitReason,
    TradeDirection, RiskLimits, OrderType
)
        order_type = OrderType.MARKET_BUY if request.direction == TradeDirection.LONG else OrderType.MARKET_SELL

        # Execute through MT5
        from app.domain.trading import OrderRequest
        order_request = OrderRequest(
            symbol=request.symbol,
            order_type=order_type,
            volume=volume,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            comment=request.setup_name or request.comment,
            magic=request.magic,
        )

        result = self._mt5.place_market_order(
            symbol=request.symbol,
            order_type=order_type,
            volume=volume,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            comment=request.setup_name or request.comment,
        )

        if result.get("success"):
            # Invalidate cache
            self._cache_time = 0

            return OpenResult(
                success=True,
                position_id=str(result.get("ticket")),
                entry_price=result.get("price", request.entry_price),
                volume=volume,
            )
        else:
            return OpenResult(
                success=False,
                error_message=result.get("error_message", "Unknown error"),
            )

    def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        volume: Optional[float] = None,
        reason: CloseReason = CloseReason.MANUAL,
        bar_index: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> CloseResult:
        """Close position through MT5."""
        if not self._mt5.is_connected:
            return CloseResult(
                success=False,
                position_id=position_id,
                error_message="MT5 not connected",
            )

        # Get position first
        position = self.get_position(position_id)
        if not position:
            return CloseResult(
                success=False,
                position_id=position_id,
                error_message=f"Position {position_id} not found",
            )

        result = self._mt5.close_position(int(position_id), volume)

        if result.get("success"):
            # Invalidate cache
            self._cache_time = 0

            return CloseResult(
                success=True,
                position_id=position_id,
                exit_price=result.get("close_price", exit_price or position.current_price),
                volume_closed=result.get("volume_closed", volume or position.volume),
                realized_pnl=result.get("profit", 0.0),
                realized_pips=0.0,  # MT5 doesn't return pips directly
                exit_reason=reason,
                exit_time=timestamp or datetime.utcnow().isoformat() + "Z",
            )
        else:
            return CloseResult(
                success=False,
                position_id=position_id,
                error_message=result.get("error_message", "Unknown error"),
            )

    def modify_position(
        self,
        position_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """Modify position SL/TP through MT5."""
        if not self._mt5.is_connected:
            return (False, "MT5 not connected")

        success, message = self._mt5.modify_position(int(position_id), stop_loss, take_profit)

        if success:
            # Invalidate cache
            self._cache_time = 0

        return (success, message)

    def get_positions(self) -> List[PositionState]:
        """Get positions with caching."""
        self._refresh_cache_if_stale()
        return self._position_cache

    def get_position(self, position_id: str) -> Optional[PositionState]:
        """Get specific position."""
        self._refresh_cache_if_stale()
        for pos in self._position_cache:
            if pos.id == position_id:
                return pos
        return None

    def close_all_positions(
        self,
        symbol: Optional[str] = None,
        reason: CloseReason = CloseReason.EMERGENCY_STOP,
    ) -> List[CloseResult]:
        """Close all positions through MT5."""
        if not self._mt5.is_connected:
            return []

        results = []
        positions = self.get_positions()

        for pos in positions:
            if symbol is None or pos.symbol == symbol:
                result = self.close_position(pos.id, reason=reason)
                results.append(result)

        return results

    def get_account_info(self) -> AccountState:
        """Get account info from MT5."""
        if not self._mt5.is_connected:
            return AccountState(balance=0, equity=0)

        info = self._mt5.get_account_info()
        if not info:
            return AccountState(balance=0, equity=0)

        return AccountState(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.free_margin,
            margin_level=info.margin_level or 0.0,
            profit=info.profit,
            currency=info.currency,
            leverage=info.leverage,
        )

    def calculate_lot_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        risk_pct: float,
        account_balance: Optional[float] = None,
    ) -> float:
        """Calculate lot size through MT5."""
        if not self._mt5.is_connected:
            return 0.01  # Minimum

        balance = account_balance or self.get_account_info().balance

        result = self._mt5.calculate_lot_size(
            symbol=symbol,
            account_balance=balance,
            risk_pct=risk_pct,
            entry_price=entry_price,
            stop_loss=stop_loss,
        )

        return result.get("lot_size", 0.01)


# =============================================================================
# Backtest Position Executor
# =============================================================================

class BacktestPositionExecutor(PositionExecutor):
    """
    Backtest position executor with tick-level TP/SL checking.

    Simulates position management with spread handling, P&L calculation,
    and accurate TP/SL detection using tick data when available.
    """

    def __init__(
        self,
        symbol: str,
        starting_balance: float = 10000.0,
        pip_value_per_lot: float = 10.0,
    ):
        """
        Initialize backtest executor.

        Args:
            symbol: Trading symbol
            starting_balance: Initial account balance
            pip_value_per_lot: Pip value per standard lot
        """
        self._symbol = symbol
        self._starting_balance = starting_balance
        self._balance = starting_balance
        self._pip_value_per_lot = pip_value_per_lot

        # Position tracking
        self._positions: Dict[str, PositionState] = {}
        self._closed_trades: List[Dict] = []

        # Statistics
        self._equity_curve: List[Dict] = []
        self._peak_equity = starting_balance
        self._win_count = 0
        self._loss_count = 0
        
        # Risk Management State
        self._max_daily_loss_pct = 5.0
        self._max_drawdown_pct = 10.0
        self._daily_loss = 0.0
        self._current_day = None
        
        # Simulation Config
        self._latency_min_ms = 50
        self._latency_max_ms = 300

    @property
    def mode(self) -> str:
        return "BACKTEST"

    def _get_pip_multiplier(self, symbol: str) -> float:
        """Get pip multiplier for symbol type."""
        if "XAU" in symbol or "GOLD" in symbol:
            return 10  # Gold: 1 pip = $0.10 movement
        elif "JPY" in symbol:
            return 100  # JPY pairs
        elif any(idx in symbol for idx in ["US30", "NAS", "SPX", "DAX"]):
            return 1  # Indices
        else:
            return 10000  # Standard forex

    def _calculate_pnl(
        self,
        direction: TradeDirection,
        entry_price: float,
        exit_price: float,
        volume: float,
        stop_loss: float,
    ) -> Tuple[float, float, float, TradeResult]:
        """
        Calculate P&L in pips, USD, and R:R.

        Returns:
            Tuple of (pnl_pips, pnl_usd, pnl_rr, result)
        """
        pip_multiplier = self._get_pip_multiplier(self._symbol)

        if direction == TradeDirection.LONG:
            pnl_pips = (exit_price - entry_price) * pip_multiplier
            risk_pips = (entry_price - stop_loss) * pip_multiplier
        else:
            pnl_pips = (entry_price - exit_price) * pip_multiplier
            risk_pips = (stop_loss - entry_price) * pip_multiplier

        # Handle edge cases
        if risk_pips < 0:
            risk_pips = abs(risk_pips)

        pnl_usd = pnl_pips * self._pip_value_per_lot * volume
        pnl_rr = pnl_pips / risk_pips if risk_pips != 0 else 0.0

        # Classify result
        if pnl_pips > 0.5:
            result = TradeResult.WIN
        elif pnl_pips < -0.5:
            result = TradeResult.LOSS
        else:
            result = TradeResult.BREAKEVEN

        return (round(pnl_pips, 1), round(pnl_usd, 2), round(pnl_rr, 2), result)

    def _apply_slippage(self, price: float) -> float:
        """
        Apply realistic slippage to price.
        
        Simulates execution slippage based on random distribution:
        - 70% chance of 0-0.2 pip slippage (normal)
        - 20% chance of 0.2-0.5 pip slippage (minor volatility)
        - 10% chance of 0.5-2.0 pip slippage (high volatility)
        
        Note: Slippage is usually against the trader.
        """
        import random
        
        # Determine base point size
        if "JPY" in self._symbol:
            point = 0.001
        elif "XAU" in self._symbol:
            point = 0.01
        else:
            point = 0.00001
            
        r = random.random()
        if r < 0.7:
            slip_pips = random.uniform(0, 0.2)
        elif r < 0.9:
            slip_pips = random.uniform(0.2, 0.5)
        else:
            slip_pips = random.uniform(0.5, 2.0)
            
        # Direction of slippage (80% negative/against trade, 20% positive)
        # For simplicity in this function, we just return a "worse" price delta magnitude
        # The caller should apply it in the direction that hurts the trade
        return slip_pips * point

    def _simulate_delay(self) -> int:
        """Simulate execution latency in milliseconds."""
        return random.randint(self._latency_min_ms, self._latency_max_ms)

    def _check_risk_limits(self, risk_amount: float, timestamp_str: str) -> Tuple[bool, Optional[str]]:
        """
        Check if trade violates risk limits.
        
        Args:
            risk_amount: Value at risk for this trade
            timestamp_str: Current timestamp
            
        Returns:
            Tuple (allowed, reason)
        """
        # Parse date to reset daily loss
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            current_date = ts.date()
            
            if self._current_day != current_date:
                self._current_day = current_date
                self._daily_loss = 0.0
        except ValueError:
            pass
            
        # Check Daily Loss
        daily_loss_limit = self._starting_balance * (self._max_daily_loss_pct / 100.0)
        if self._daily_loss >= daily_loss_limit:
            return False, f"Daily loss limit reached (${self._daily_loss:.2f} >= ${daily_loss_limit:.2f})"
            
        # Check Max Drawdown
        current_drawdown = self._peak_equity - self._balance
        drawdown_limit = self._starting_balance * (self._max_drawdown_pct / 100.0)
        
        if current_drawdown >= drawdown_limit:
            return False, f"Max drawdown limit reached (${current_drawdown:.2f} >= ${drawdown_limit:.2f})"
            
        return True, None

    def open_position(self, request: OpenPositionRequest) -> OpenResult:
        """Open a simulated position with spread, slippage, and risk checks."""
        position_id = str(uuid.uuid4())[:8]
        timestamp = request.timestamp or datetime.utcnow().isoformat() + "Z"

        # 1. Calculate Volume (if needed)
        volume = request.volume
        if volume is None:
            volume = self.calculate_lot_size(
                request.symbol,
                request.entry_price,
                request.stop_loss,
                request.risk_pct,
            )

        # 2. Check Risk Limits
        # Calculate risk amount for this trade
        pip_multiplier = self._get_pip_multiplier(request.symbol)
        sl_pips = abs(request.entry_price - request.stop_loss) * pip_multiplier
        risk_amount = sl_pips * self._pip_value_per_lot * volume
        
        allowed, rejection_reason = self._check_risk_limits(risk_amount, timestamp)
        if not allowed:
            logger.warning(f"Trade rejected by Risk Manager: {rejection_reason}")
            return OpenResult(
                success=False,
                error_message=f"Risk Rejection: {rejection_reason}",
                risk_check_passed=False
            )

        # 3. Simulate Execution Environment
        # Get spread
        spread = 0.00012 
        if "XAU" in request.symbol:
            spread = 0.30
        elif "JPY" in request.symbol:
            spread = 0.015

        # Calculate slippage & delay
        slippage = self._apply_slippage(request.entry_price)
        delay_ms = self._simulate_delay()

        # Apply spread and slippage to entry price
        if request.direction == TradeDirection.LONG:
            adjusted_entry = request.entry_price + (spread / 2) + slippage
        else:
            adjusted_entry = request.entry_price - (spread / 2) - slippage

        # 4. Create Position State
        position = PositionState(
            id=position_id,
            symbol=request.symbol,
            direction=request.direction,
            volume=volume,
            entry_price=round(adjusted_entry, 5),
            current_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            unrealized_pnl=0.0,
            unrealized_pips=0.0,
            open_time=timestamp,
            setup_name=request.setup_name,
            entry_bar_index=request.bar_index,
            spread_at_entry=spread,
            entry_slippage=slippage,
            entry_delay_ms=delay_ms,
            agent_analysis=request.agent_analysis
        )

        self._positions[position_id] = position

        logger.info(
            f"Opened realistic backtest position {position_id}: {request.direction.value} "
            f"@ {adjusted_entry:.5f} (spread: {spread}, slippage: {slippage:.5f}, delay: {delay_ms}ms)"
        )

        return OpenResult(
            success=True,
            position_id=position_id,
            entry_price=adjusted_entry,
            volume=volume,
            position=position,
            slippage=slippage,
            delay_ms=delay_ms,
            risk_check_passed=True
        )

    def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        volume: Optional[float] = None,
        reason: CloseReason = CloseReason.MANUAL,
        bar_index: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> CloseResult:
        """Close a simulated position with slippage and update risk metrics."""
        if position_id not in self._positions:
            return CloseResult(
                success=False,
                position_id=position_id,
                error_message=f"Position {position_id} not found",
            )

        position = self._positions.pop(position_id)

        # Use current price if not provided
        base_exit_price = exit_price or position.current_price
        
        # Apply slippage & delay
        slippage = 0.0
        delay_ms = 0
        
        if reason in [CloseReason.MANUAL, CloseReason.EMERGENCY_STOP, CloseReason.SL_HIT]:
            slippage = self._apply_slippage(base_exit_price)
            delay_ms = self._simulate_delay()
        
        # Long exit (Sell): Bid - Slippage
        # Short exit (Buy): Ask + Slippage
        if position.direction == TradeDirection.LONG:
            final_exit_price = base_exit_price - slippage
        else:
            final_exit_price = base_exit_price + slippage

        final_volume = volume or position.volume
        exit_time = timestamp or datetime.utcnow().isoformat() + "Z"

        # Calculate P&L
        pnl_pips, pnl_usd, pnl_rr, trade_result = self._calculate_pnl(
            position.direction,
            position.entry_price,
            final_exit_price,
            final_volume,
            position.stop_loss,
        )

        # Update balance
        self._balance += pnl_usd
        
        # Update Daily Loss (if negative P&L)
        if pnl_usd < 0:
            # Check if day changed happens in _check_risk_limits usually, 
            # but we should ensure we are adding to the current day's loss
            try:
                ts = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
                if self._current_day != ts.date():
                     self._current_day = ts.date()
                     self._daily_loss = 0.0
            except ValueError:
                pass
            self._daily_loss += abs(pnl_usd)

        # Update statistics
        if trade_result == TradeResult.WIN:
            self._win_count += 1
        elif trade_result == TradeResult.LOSS:
            self._loss_count += 1

        # Track equity curve
        self._peak_equity = max(self._peak_equity, self._balance)
        self._equity_curve.append({
            "timestamp": exit_time,
            "equity": self._balance,
            "peak": self._peak_equity,
            "drawdown": self._peak_equity - self._balance,
        })

        close_result = CloseResult(
            success=True,
            position_id=position_id,
            exit_price=final_exit_price,
            volume_closed=final_volume,
            realized_pnl=pnl_usd,
            realized_pips=pnl_pips,
            realized_rr=pnl_rr,
            exit_reason=reason,
            exit_time=exit_time,
            result=trade_result,
            exit_bar_index=bar_index,
            exit_slippage=slippage,
            exit_delay_ms=delay_ms
        )

        # Record closed trade
        pip_multiplier = self._get_pip_multiplier(self._symbol)
        self._closed_trades.append(close_result.to_hierarchical_trade(position, pip_multiplier))

        logger.info(
            f"Closed realistic backtest position {position_id}: {reason.value} @ {final_exit_price:.5f} "
            f"(slippage: {slippage:.5f}, delay: {delay_ms}ms), "
            f"P&L: {pnl_pips} pips (${pnl_usd})"
        )

        return close_result

    def modify_position(
        self,
        position_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """Modify position SL/TP."""
        if position_id not in self._positions:
            return (False, f"Position {position_id} not found")

        position = self._positions[position_id]

        if stop_loss is not None:
            # Create new position state with updated SL
            self._positions[position_id] = PositionState(
                id=position.id,
                symbol=position.symbol,
                direction=position.direction,
                volume=position.volume,
                entry_price=position.entry_price,
                current_price=position.current_price,
                stop_loss=stop_loss,
                take_profit=take_profit if take_profit is not None else position.take_profit,
                unrealized_pnl=position.unrealized_pnl,
                unrealized_pips=position.unrealized_pips,
                open_time=position.open_time,
                setup_name=position.setup_name,
                entry_bar_index=position.entry_bar_index,
                spread_at_entry=position.spread_at_entry,
            )
        elif take_profit is not None:
            self._positions[position_id] = PositionState(
                id=position.id,
                symbol=position.symbol,
                direction=position.direction,
                volume=position.volume,
                entry_price=position.entry_price,
                current_price=position.current_price,
                stop_loss=position.stop_loss,
                take_profit=take_profit,
                unrealized_pnl=position.unrealized_pnl,
                unrealized_pips=position.unrealized_pips,
                open_time=position.open_time,
                setup_name=position.setup_name,
                entry_bar_index=position.entry_bar_index,
                spread_at_entry=position.spread_at_entry,
            )

        return (True, "Position modified")

    def get_positions(self) -> List[PositionState]:
        """Get all open positions."""
        return list(self._positions.values())

    def get_position(self, position_id: str) -> Optional[PositionState]:
        """Get specific position."""
        return self._positions.get(position_id)

    def close_all_positions(
        self,
        symbol: Optional[str] = None,
        reason: CloseReason = CloseReason.EMERGENCY_STOP,
    ) -> List[CloseResult]:
        """Close all positions."""
        results = []
        position_ids = list(self._positions.keys())

        for pos_id in position_ids:
            pos = self._positions.get(pos_id)
            if pos and (symbol is None or pos.symbol == symbol):
                result = self.close_position(pos_id, reason=reason)
                results.append(result)

        return results

    def get_account_info(self) -> AccountState:
        """Get simulated account info."""
        # Calculate unrealized P&L
        unrealized = sum(pos.unrealized_pnl for pos in self._positions.values())

        return AccountState(
            balance=self._balance,
            equity=self._balance + unrealized,
            profit=unrealized,
            currency="USD",
            leverage=100,
        )

    def calculate_lot_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        risk_pct: float,
        account_balance: Optional[float] = None,
    ) -> float:
        """Calculate lot size based on risk."""
        balance = account_balance or self._balance
        risk_amount = balance * (risk_pct / 100)

        pip_multiplier = self._get_pip_multiplier(symbol)
        sl_pips = abs(entry_price - stop_loss) * pip_multiplier

        if sl_pips <= 0:
            return 0.01

        lot_size = risk_amount / (sl_pips * self._pip_value_per_lot)

        # Clamp to valid range
        lot_size = max(0.01, min(100.0, lot_size))

        # Round to 2 decimal places
        return round(lot_size, 2)

    def update_unrealized_pnl(self, current_prices: Dict[str, Tuple[float, float]]):
        """Update unrealized P&L for all positions."""
        pip_multiplier = self._get_pip_multiplier(self._symbol)

        for pos_id, position in self._positions.items():
            if position.symbol in current_prices:
                bid, ask = current_prices[position.symbol]

                # Use bid for longs (sell to close), ask for shorts (buy to close)
                if position.direction == TradeDirection.LONG:
                    current_price = bid
                    pnl_pips = (current_price - position.entry_price) * pip_multiplier
                else:
                    current_price = ask
                    pnl_pips = (position.entry_price - current_price) * pip_multiplier

                pnl_usd = pnl_pips * self._pip_value_per_lot * position.volume

                # Update position (create new instance to maintain immutability pattern)
                self._positions[pos_id] = PositionState(
                    id=position.id,
                    symbol=position.symbol,
                    direction=position.direction,
                    volume=position.volume,
                    entry_price=position.entry_price,
                    current_price=current_price,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    unrealized_pnl=round(pnl_usd, 2),
                    unrealized_pips=round(pnl_pips, 1),
                    open_time=position.open_time,
                    setup_name=position.setup_name,
                    entry_bar_index=position.entry_bar_index,
                    spread_at_entry=position.spread_at_entry,
                    agent_analysis=position.agent_analysis,
                )

    # =========================================================================
    # Backtest-specific methods
    # =========================================================================

    def check_tp_sl_on_bar(
        self,
        symbol: str,
        high: float,
        low: float,
        bar_index: int,
        timestamp: str,
    ) -> List[CloseResult]:
        """Check TP/SL hits on bar OHLC (fallback when no tick data)."""
        closed = []
        positions_to_close = []

        for pos_id, pos in self._positions.items():
            if pos.symbol != symbol:
                continue

            exit_reason = None
            exit_price = None

            if pos.direction == TradeDirection.LONG:
                # Check SL first (worst case)
                if low <= pos.stop_loss:
                    exit_reason = CloseReason.SL_HIT
                    exit_price = pos.stop_loss
                elif pos.take_profit and high >= pos.take_profit:
                    exit_reason = CloseReason.TP_HIT
                    exit_price = pos.take_profit
            else:  # SHORT
                if high >= pos.stop_loss:
                    exit_reason = CloseReason.SL_HIT
                    exit_price = pos.stop_loss
                elif pos.take_profit and low <= pos.take_profit:
                    exit_reason = CloseReason.TP_HIT
                    exit_price = pos.take_profit

            if exit_reason:
                positions_to_close.append((pos_id, exit_price, exit_reason))

        for pos_id, exit_price, exit_reason in positions_to_close:
            result = self.close_position(
                pos_id,
                exit_price=exit_price,
                reason=exit_reason,
                bar_index=bar_index,
                timestamp=timestamp,
            )
            if result.success:
                closed.append(result)

        return closed

    def check_tp_sl_on_tick(
        self,
        symbol: str,
        bid: float,
        ask: float,
        tick_time: float,
        bar_index: int,
    ) -> List[CloseResult]:
        """Check TP/SL hits on tick (accurate intra-bar detection)."""
        closed = []
        positions_to_close = []
        timestamp = datetime.utcfromtimestamp(tick_time).isoformat() + "Z"

        for pos_id, pos in self._positions.items():
            if pos.symbol != symbol:
                continue

            exit_reason = None
            exit_price = None

            if pos.direction == TradeDirection.LONG:
                # LONG exits at bid
                if bid <= pos.stop_loss:
                    exit_reason = CloseReason.SL_HIT
                    exit_price = pos.stop_loss
                elif pos.take_profit and bid >= pos.take_profit:
                    exit_reason = CloseReason.TP_HIT
                    exit_price = pos.take_profit
            else:  # SHORT
                # SHORT exits at ask
                if ask >= pos.stop_loss:
                    exit_reason = CloseReason.SL_HIT
                    exit_price = pos.stop_loss
                elif pos.take_profit and ask <= pos.take_profit:
                    exit_reason = CloseReason.TP_HIT
                    exit_price = pos.take_profit

            if exit_reason:
                positions_to_close.append((pos_id, exit_price, exit_reason, timestamp))

        for pos_id, exit_price, exit_reason, ts in positions_to_close:
            result = self.close_position(
                pos_id,
                exit_price=exit_price,
                reason=exit_reason,
                bar_index=bar_index,
                timestamp=ts,
            )
            if result.success:
                closed.append(result)

        return closed

    def get_closed_trades(self) -> List[Dict]:
        """Get all closed trades."""
        return self._closed_trades.copy()

    def get_statistics(self) -> Dict:
        """Get trading statistics."""
        if not self._closed_trades:
            return {
                "total_trades": 0,
                "winners": 0,
                "losers": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl_pips": 0.0,
                "total_pnl_usd": 0.0,
                "max_drawdown": 0.0,
                "average_rr": 0.0,
            }

        winners = [t for t in self._closed_trades if t["pnl_pips"] > 0]
        losers = [t for t in self._closed_trades if t["pnl_pips"] <= 0]

        gross_profit = sum(t["pnl_pips"] for t in winners)
        gross_loss = abs(sum(t["pnl_pips"] for t in losers))

        max_dd = max((e["drawdown"] for e in self._equity_curve), default=0.0)

        return {
            "total_trades": len(self._closed_trades),
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": len(winners) / len(self._closed_trades) if self._closed_trades else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0,
            "total_pnl_pips": round(sum(t["pnl_pips"] for t in self._closed_trades), 1),
            "total_pnl_usd": round(sum(t["pnl_usd"] for t in self._closed_trades), 2),
            "gross_profit_pips": round(gross_profit, 1),
            "gross_loss_pips": round(gross_loss, 1),
            "max_drawdown": round(max_dd, 2),
            "average_rr": round(sum(t["pnl_rr"] for t in self._closed_trades) / len(self._closed_trades), 2),
            "balance": self._balance,
            "starting_balance": self._starting_balance,
        }

    def reset(self):
        """Reset all state."""
        self._positions.clear()
        self._closed_trades.clear()
        self._equity_curve.clear()
        self._balance = self._starting_balance
        self._peak_equity = self._starting_balance
        self._win_count = 0
        self._loss_count = 0


# =============================================================================
# Factory Function
# =============================================================================

def create_position_executor(
    mode: str,
    mt5_service=None,
    symbol: str = "EURUSD",
    starting_balance: float = 10000.0,
) -> PositionExecutor:
    """
    Factory function to create the appropriate position executor.

    Args:
        mode: "LIVE" or "BACKTEST"
        mt5_service: MT5Service instance (required for LIVE)
        symbol: Trading symbol (for BACKTEST)
        starting_balance: Starting balance (for BACKTEST)

    Returns:
        Configured PositionExecutor instance
    """
    if mode == "LIVE":
        if mt5_service is None:
            raise ValueError("mt5_service required for LIVE mode")
        return MT5PositionExecutor(mt5_service)
    else:
        return BacktestPositionExecutor(
            symbol=symbol,
            starting_balance=starting_balance,
        )
