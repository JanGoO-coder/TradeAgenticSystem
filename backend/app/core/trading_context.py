"""
TradingContext Factory - Unified Live/Backtest Context Creation.

This module provides a factory for creating complete trading contexts
that wire together DataProvider and PositionExecutor implementations
based on the execution mode (LIVE or BACKTEST).
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

from app.core.data_provider import (
    DataProvider, DataMode,
    LiveDataProvider, BacktestDataProvider,
    create_data_provider,
)
from app.core.position_executor import (
    PositionExecutor,
    MT5PositionExecutor, BacktestPositionExecutor,
    create_position_executor,
)

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode for trading context."""
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"


@dataclass
class TradingContext:
    """
    Complete trading context with data and execution providers.

    This is the primary abstraction passed to agents - they don't
    need to know whether they're running live or in backtest mode.
    """
    data_provider: DataProvider
    position_executor: PositionExecutor
    mode: ExecutionMode
    symbol: str

    # Optional session info
    session_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    starting_balance: float = 10000.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for debugging/logging."""
        return {
            "mode": self.mode.value,
            "symbol": self.symbol,
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "starting_balance": self.starting_balance,
            "data_provider_status": self.data_provider.get_status().to_dict(),
            "account_state": self.position_executor.get_account_info().to_dict(),
        }


class TradingContextFactory:
    """
    Factory for creating and managing trading contexts.

    Wires together the appropriate DataProvider and PositionExecutor
    implementations based on execution mode.
    """

    def __init__(self, mt5_service=None, backtest_service=None):
        """
        Initialize factory with service dependencies.

        Args:
            mt5_service: MT5Service instance (for LIVE mode)
            backtest_service: BacktestService instance (for BACKTEST mode)
        """
        self._mt5_service = mt5_service
        self._backtest_service = backtest_service
        self._active_context: Optional[TradingContext] = None

    def create_live_context(
        self,
        symbol: str,
        session_id: Optional[str] = None,
    ) -> TradingContext:
        """
        Create a live trading context using MT5.

        Args:
            symbol: Trading symbol
            session_id: Optional session identifier

        Returns:
            Configured TradingContext for live trading

        Raises:
            ValueError: If MT5 service not available
        """
        if self._mt5_service is None:
            raise ValueError("MT5 service not configured for live trading")

        if not self._mt5_service.is_connected:
            raise ValueError("MT5 not connected")

        # Create providers
        data_provider = LiveDataProvider(self._mt5_service)
        data_provider.set_symbol(symbol)

        position_executor = MT5PositionExecutor(self._mt5_service)

        # Get account info for starting balance
        account = position_executor.get_account_info()

        context = TradingContext(
            data_provider=data_provider,
            position_executor=position_executor,
            mode=ExecutionMode.LIVE,
            symbol=symbol,
            session_id=session_id,
            start_time=datetime.utcnow(),
            starting_balance=account.balance,
        )

        self._active_context = context
        logger.info(f"Created LIVE trading context for {symbol}")

        return context

    def create_backtest_context(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        timeframes: List[str] = None,
        starting_balance: float = 10000.0,
        session_id: Optional[str] = None,
    ) -> TradingContext:
        """
        Create a backtest trading context.

        Args:
            symbol: Trading symbol
            start_time: Backtest start date
            end_time: Backtest end date
            timeframes: Timeframes to load (default: ["1H", "15M", "5M"])
            starting_balance: Initial account balance
            session_id: Optional session identifier

        Returns:
            Configured TradingContext for backtesting

        Raises:
            ValueError: If backtest service not available
        """
        if self._backtest_service is None:
            raise ValueError("Backtest service not configured")

        timeframes = timeframes or ["1H", "15M", "5M"]

        # Load historical data
        load_result = self._backtest_service.load_backtest_data(
            symbol=symbol,
            from_date=start_time,
            to_date=end_time,
            timeframes=timeframes,
        )

        logger.info(f"Loaded backtest data: {load_result}")

        # Create providers
        data_provider = BacktestDataProvider(self._backtest_service, self._mt5_service)

        position_executor = BacktestPositionExecutor(
            symbol=symbol,
            starting_balance=starting_balance,
        )

        context = TradingContext(
            data_provider=data_provider,
            position_executor=position_executor,
            mode=ExecutionMode.BACKTEST,
            symbol=symbol,
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            starting_balance=starting_balance,
        )

        self._active_context = context
        logger.info(f"Created BACKTEST trading context for {symbol} from {start_time} to {end_time}")

        return context

    def create_context(
        self,
        mode: ExecutionMode,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        timeframes: List[str] = None,
        starting_balance: float = 10000.0,
        session_id: Optional[str] = None,
    ) -> TradingContext:
        """
        Create a trading context based on mode.

        This is the primary factory method - use this for most cases.

        Args:
            mode: ExecutionMode.LIVE or ExecutionMode.BACKTEST
            symbol: Trading symbol
            start_time: Start date (required for BACKTEST)
            end_time: End date (required for BACKTEST)
            timeframes: Timeframes to load (BACKTEST only)
            starting_balance: Initial balance (BACKTEST only)
            session_id: Optional session identifier

        Returns:
            Configured TradingContext
        """
        if mode == ExecutionMode.LIVE:
            return self.create_live_context(symbol, session_id)
        else:
            if start_time is None or end_time is None:
                raise ValueError("start_time and end_time required for BACKTEST mode")

            return self.create_backtest_context(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                timeframes=timeframes,
                starting_balance=starting_balance,
                session_id=session_id,
            )

    @property
    def active_context(self) -> Optional[TradingContext]:
        """Get currently active trading context."""
        return self._active_context

    def reset_context(self):
        """Reset and clear the active context."""
        if self._active_context:
            # Reset position executor if backtest
            if self._active_context.mode == ExecutionMode.BACKTEST:
                self._active_context.position_executor.reset()

            self._active_context = None
            logger.info("Trading context reset")


# =============================================================================
# Global Factory Instance
# =============================================================================

_factory_instance: Optional[TradingContextFactory] = None


def get_trading_context_factory() -> TradingContextFactory:
    """Get or create the global TradingContextFactory instance."""
    global _factory_instance

    if _factory_instance is None:
        # Import services lazily to avoid circular imports
        from app.services.mt5_service import get_mt5_service
        from app.services.backtest_service import get_backtest_service

        _factory_instance = TradingContextFactory(
            mt5_service=get_mt5_service(),
            backtest_service=get_backtest_service(),
        )

    return _factory_instance


def create_trading_context(
    mode: str,
    symbol: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    timeframes: List[str] = None,
    starting_balance: float = 10000.0,
    session_id: Optional[str] = None,
) -> TradingContext:
    """
    Convenience function to create a trading context.

    This is the simplest API for context creation.

    Args:
        mode: "LIVE" or "BACKTEST"
        symbol: Trading symbol
        start_time: Start date (required for BACKTEST)
        end_time: End date (required for BACKTEST)
        timeframes: Timeframes to load (BACKTEST only)
        starting_balance: Initial balance (BACKTEST only)
        session_id: Optional session identifier

    Returns:
        Configured TradingContext
    """
    factory = get_trading_context_factory()
    exec_mode = ExecutionMode(mode.upper())

    return factory.create_context(
        mode=exec_mode,
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        timeframes=timeframes,
        starting_balance=starting_balance,
        session_id=session_id,
    )
