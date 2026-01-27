"""Backtest simulation service.

Simulates historical data playback for strategy testing.
Allows stepping through historical data bar by bar with synchronized timeframes.
Includes position management with spread simulation and TP/SL hit detection.
Supports tick-by-tick replay for accurate intra-bar TP/SL detection.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import logging
import uuid
import json
from pathlib import Path

from app.services.mt5_service import get_mt5_service, TickCacheManager
from app.domain.trading import (
    BacktestPosition, BacktestTrade, BacktestStatistics,
    BacktestExport, BacktestExportMetadata, BacktestExitReason,
    TradeDirection
)
from app.core.config import get_settings
from app.core.symbol_utils import get_pip_multiplier

logger = logging.getLogger(__name__)


class BacktestPositionManager:
    """Manages simulated positions during backtest with spread and TP/SL handling."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.positions: Dict[str, BacktestPosition] = {}
        self.trades: List[BacktestTrade] = []
        self._equity_curve: List[Dict] = []
        self._peak_equity = 0.0
        self._current_equity = 0.0

    def open_position(
        self,
        direction: TradeDirection,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float],
        volume: float,
        spread: float,
        bar_index: int,
        timestamp: str,
        setup_name: Optional[str] = None,
        agent_analysis: Optional[dict] = None
    ) -> BacktestPosition:
        """
        Open a new simulated position with spread applied.

        For BUY: entry at ask (price + spread/2)
        For SELL: entry at bid (price - spread/2)
        """
        position_id = str(uuid.uuid4())[:8]

        # Apply spread to entry price
        if direction == TradeDirection.LONG:
            adjusted_entry = entry_price + (spread / 2)  # Buy at ask
        else:
            adjusted_entry = entry_price - (spread / 2)  # Sell at bid

        position = BacktestPosition(
            id=position_id,
            symbol=self.symbol,
            direction=direction,
            entry_price=round(adjusted_entry, 5),
            entry_timestamp=timestamp,
            entry_bar_index=bar_index,
            volume=volume,
            stop_loss=stop_loss,
            take_profit=take_profit,
            spread_at_entry=spread,
            current_price=entry_price,
            unrealized_pnl_pips=0.0,
            setup_name=setup_name
        )

        self.positions[position_id] = position
        logger.info(f"Opened backtest position {position_id}: {direction.value} @ {adjusted_entry}")

        return position

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: BacktestExitReason,
        bar_index: int,
        timestamp: str,
        pip_value_per_lot: float = 10.0,
        agent_analysis: Optional[dict] = None
    ) -> Optional[BacktestTrade]:
        """Close a position and record the trade with P&L in pips and USD."""
        if position_id not in self.positions:
            logger.warning(f"Position {position_id} not found")
            return None

        position = self.positions.pop(position_id)

        # Calculate P&L in pips using shared pip multiplier utility
        pip_multiplier = get_pip_multiplier(self.symbol)

        if position.direction == TradeDirection.LONG:
            pnl_pips = (exit_price - position.entry_price) * pip_multiplier
        else:
            pnl_pips = (position.entry_price - exit_price) * pip_multiplier

        # Calculate P&L in USD: pips * pip_value_per_lot * volume
        pnl_usd = pnl_pips * pip_value_per_lot * position.volume

        # Calculate R:R (risk was entry to SL)
        # For LONG: SL should be below entry, risk = entry - SL (positive)
        # For SHORT: SL should be above entry, risk = SL - entry (positive)
        if position.direction == TradeDirection.LONG:
            risk_pips = (position.entry_price - position.stop_loss) * pip_multiplier
        else:
            risk_pips = (position.stop_loss - position.entry_price) * pip_multiplier

        # Use absolute value for risk to handle inverted SL cases, but log warning
        if risk_pips < 0:
            logger.warning(f"Position {position_id}: SL appears to be on wrong side of entry (risk_pips={risk_pips})")
            risk_pips = abs(risk_pips)

        pnl_rr = pnl_pips / risk_pips if risk_pips != 0 else 0.0

        trade = BacktestTrade(
            id=position.id,
            symbol=self.symbol,
            direction=position.direction,
            entry_timestamp=position.entry_timestamp,
            entry_bar_index=position.entry_bar_index,
            entry_price=position.entry_price,
            exit_timestamp=timestamp,
            exit_bar_index=bar_index,
            exit_price=exit_price,
            exit_reason=exit_reason,
            volume=position.volume,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            spread_at_entry=position.spread_at_entry,
            pnl_pips=round(pnl_pips, 1),
            pnl_usd=round(pnl_usd, 2),
            pnl_rr=round(pnl_rr, 2),
            setup_name=position.setup_name,
            agent_analysis=agent_analysis
        )

        self.trades.append(trade)
        self._update_equity(pnl_pips, pnl_usd, timestamp)

        logger.info(f"Closed backtest position {position_id}: {exit_reason.value} @ {exit_price}, P&L: {pnl_pips:.1f} pips (${pnl_usd:.2f})")

        return trade

    def check_tp_sl_hit(
        self,
        high: float,
        low: float,
        bar_index: int,
        timestamp: str,
        pip_value_per_lot: float = 10.0
    ) -> List[BacktestTrade]:
        """
        Check if any open positions hit TP or SL on the current bar.
        Returns list of auto-closed trades.
        """
        closed_trades = []
        positions_to_close = []

        for pos_id, pos in self.positions.items():
            exit_reason = None
            exit_price = None

            if pos.direction == TradeDirection.LONG:
                # Check SL first (worst case)
                if low <= pos.stop_loss:
                    exit_reason = BacktestExitReason.SL_HIT
                    exit_price = pos.stop_loss
                # Then check TP
                elif pos.take_profit and high >= pos.take_profit:
                    exit_reason = BacktestExitReason.TP_HIT
                    exit_price = pos.take_profit
            else:  # SHORT
                # Check SL first
                if high >= pos.stop_loss:
                    exit_reason = BacktestExitReason.SL_HIT
                    exit_price = pos.stop_loss
                # Then check TP
                elif pos.take_profit and low <= pos.take_profit:
                    exit_reason = BacktestExitReason.TP_HIT
                    exit_price = pos.take_profit

            if exit_reason:
                positions_to_close.append((pos_id, exit_price, exit_reason))

        # Close positions outside the loop to avoid modifying dict during iteration
        for pos_id, exit_price, exit_reason in positions_to_close:
            trade = self.close_position(pos_id, exit_price, exit_reason, bar_index, timestamp, pip_value_per_lot)
            if trade:
                closed_trades.append(trade)

        return closed_trades

    def update_unrealized_pnl(self, current_price: float):
        """Update unrealized P&L for all open positions."""
        # Use shared pip multiplier utility
        pip_multiplier = get_pip_multiplier(self.symbol)

        for pos in self.positions.values():
            pos.current_price = current_price
            if pos.direction == TradeDirection.LONG:
                pos.unrealized_pnl_pips = round((current_price - pos.entry_price) * pip_multiplier, 1)
            else:
                pos.unrealized_pnl_pips = round((pos.entry_price - current_price) * pip_multiplier, 1)

    def _update_equity(self, pnl_pips: float, pnl_usd: float, timestamp: str):
        """Update equity curve tracking in both pips and USD."""
        self._current_equity += pnl_pips
        self._peak_equity = max(self._peak_equity, self._current_equity)
        self._equity_curve.append({
            "timestamp": timestamp,
            "equity_pips": self._current_equity,
            "equity_usd": pnl_usd,  # This trade's USD P&L
            "peak": self._peak_equity,
            "drawdown": self._peak_equity - self._current_equity
        })

    def get_statistics(self) -> BacktestStatistics:
        """Calculate comprehensive backtest statistics."""
        if not self.trades:
            return BacktestStatistics()

        winners = [t for t in self.trades if t.pnl_pips > 0]
        losers = [t for t in self.trades if t.pnl_pips <= 0]

        gross_profit = sum(t.pnl_pips for t in winners)
        gross_loss = abs(sum(t.pnl_pips for t in losers))
        total_pnl_usd = sum(t.pnl_usd for t in self.trades)

        # Calculate max drawdown from equity curve
        max_dd = max((e["drawdown"] for e in self._equity_curve), default=0.0)

        # Calculate consecutive wins/losses
        max_consec_wins = max_consec_losses = current_streak = 0
        last_was_win = None

        for trade in self.trades:
            is_win = trade.pnl_pips > 0
            if last_was_win is None or is_win == last_was_win:
                current_streak += 1
            else:
                current_streak = 1

            if is_win:
                max_consec_wins = max(max_consec_wins, current_streak)
            else:
                max_consec_losses = max(max_consec_losses, current_streak)

            last_was_win = is_win

        return BacktestStatistics(
            total_trades=len(self.trades),
            winners=len(winners),
            losers=len(losers),
            win_rate=len(winners) / len(self.trades) if self.trades else 0.0,
            profit_factor=gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0,
            total_pnl_pips=round(sum(t.pnl_pips for t in self.trades), 1),
            total_pnl_usd=round(total_pnl_usd, 2),
            gross_profit_pips=round(gross_profit, 1),
            gross_loss_pips=round(gross_loss, 1),
            max_drawdown_pips=round(max_dd, 1),
            average_rr=round(sum(t.pnl_rr for t in self.trades) / len(self.trades), 2) if self.trades else 0.0,
            largest_win_pips=round(max((t.pnl_pips for t in winners), default=0.0), 1),
            largest_loss_pips=round(min((t.pnl_pips for t in losers), default=0.0), 1),
            average_win_pips=round(gross_profit / len(winners), 1) if winners else 0.0,
            average_loss_pips=round(gross_loss / len(losers), 1) if losers else 0.0,
            consecutive_wins=max_consec_wins,
            consecutive_losses=max_consec_losses
        )

    def reset(self):
        """Reset all positions and trades."""
        self.positions.clear()
        self.trades.clear()
        self._equity_curve.clear()
        self._peak_equity = 0.0
        self._current_equity = 0.0


# ============================================================================
# TICK REPLAY ENGINE - Accurate intra-bar TP/SL detection using tick data
# ============================================================================

class TickReplayEngine:
    """
    Replays tick data within bars for accurate TP/SL hit detection.

    Key features:
    - Uses tick sequence (bid/ask) to determine true TP/SL hit order
    - For LONG positions: SL checked against bid, TP against bid
    - For SHORT positions: SL checked against ask, TP against ask
    - Reports tick-by-tick progress for UI feedback
    """

    def __init__(self, symbol: str, position_manager: BacktestPositionManager):
        self.symbol = symbol
        self.position_manager = position_manager
        self._tick_cache: Optional[TickCacheManager] = None
        self._mt5_service = None

        # Replay state
        self._current_bar_ticks: List[Dict] = []
        self._tick_index = 0
        self._total_ticks_in_bar = 0

    def initialize(self, mt5_service, tick_cache: TickCacheManager = None):
        """Initialize with MT5 service and optional tick cache."""
        self._mt5_service = mt5_service
        self._tick_cache = tick_cache or TickCacheManager(self.symbol)

    def load_bar_ticks(self, bar_start: datetime, bar_end: datetime) -> int:
        """
        Load ticks for a specific bar time range.

        Args:
            bar_start: Bar open time
            bar_end: Bar close time (start of next bar)

        Returns:
            Number of ticks loaded
        """
        if not self._tick_cache:
            return 0

        # Preload tick chunks covering this bar
        self._tick_cache.preload_window(bar_start, self._mt5_service)

        # Get ticks in range
        self._current_bar_ticks = self._tick_cache.get_ticks_in_range(bar_start, bar_end)
        self._tick_index = 0
        self._total_ticks_in_bar = len(self._current_bar_ticks)

        logger.debug(f"Loaded {self._total_ticks_in_bar} ticks for bar {bar_start}")
        return self._total_ticks_in_bar

    def replay_bar_ticks(
        self,
        bar_index: int,
        timestamp: str,
        pip_value_per_lot: float = 10.0
    ) -> Dict:
        """
        Replay all ticks in the current bar to check TP/SL hits in order.

        This is the key difference from bar-based checking:
        - Processes each tick in sequence
        - For LONG: checks bid price against SL/TP
        - For SHORT: checks ask price against SL/TP
        - Determines which hit first based on tick sequence

        Returns:
            Dict with closed trades and tick progress info
        """
        closed_trades = []

        for tick in self._current_bar_ticks:
            self._tick_index += 1

            bid = tick["bid"]
            ask = tick["ask"]
            tick_time = datetime.utcfromtimestamp(tick["time"])

            # Check each open position
            positions_to_close = []

            for pos_id, pos in self.position_manager.positions.items():
                exit_reason = None
                exit_price = None

                if pos.direction == TradeDirection.LONG:
                    # LONG position: exits at bid price
                    # Check SL first (worst case for simulation fairness)
                    if bid <= pos.stop_loss:
                        exit_reason = BacktestExitReason.SL_HIT
                        exit_price = pos.stop_loss  # Fill at SL price (slippage not modeled)
                    elif pos.take_profit and bid >= pos.take_profit:
                        exit_reason = BacktestExitReason.TP_HIT
                        exit_price = pos.take_profit
                else:
                    # SHORT position: exits at ask price
                    if ask >= pos.stop_loss:
                        exit_reason = BacktestExitReason.SL_HIT
                        exit_price = pos.stop_loss
                    elif pos.take_profit and ask <= pos.take_profit:
                        exit_reason = BacktestExitReason.TP_HIT
                        exit_price = pos.take_profit

                if exit_reason:
                    positions_to_close.append((pos_id, exit_price, exit_reason))

            # Close positions hit on this tick
            for pos_id, exit_price, exit_reason in positions_to_close:
                trade = self.position_manager.close_position(
                    position_id=pos_id,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    bar_index=bar_index,
                    timestamp=tick_time.isoformat() + "Z",  # Use tick time, not bar time
                    pip_value_per_lot=pip_value_per_lot
                )
                if trade:
                    closed_trades.append(trade)
                    logger.info(f"Tick replay: closed {pos_id} at tick {self._tick_index}/{self._total_ticks_in_bar}")

        return {
            "closed_trades": closed_trades,
            "ticks_processed": self._tick_index,
            "total_ticks": self._total_ticks_in_bar,
            "tick_replay_complete": self._tick_index >= self._total_ticks_in_bar
        }

    def get_progress(self) -> Dict:
        """Get current tick replay progress."""
        return {
            "ticks_processed": self._tick_index,
            "total_ticks": self._total_ticks_in_bar,
            "progress_pct": (self._tick_index / max(1, self._total_ticks_in_bar)) * 100
        }

    def clear(self):
        """Clear current bar ticks."""
        self._current_bar_ticks = []
        self._tick_index = 0
        self._total_ticks_in_bar = 0


class BacktestService:
    """Simulates historical data as live stream for backtesting."""

    # Primary timeframe for stepping (5M for candle-by-candle execution)
    PRIMARY_TIMEFRAME = "5M"

    def __init__(self):
        self.mt5 = get_mt5_service()
        self._running = False
        self._current_index = 0
        self._data: Dict[str, List[Dict]] = {}
        self._spread_map: Dict[str, float] = {}
        self._symbol: Optional[str] = None
        self._from_date: Optional[datetime] = None
        self._to_date: Optional[datetime] = None
        self._loaded = False
        self._position_manager: Optional[BacktestPositionManager] = None
        self._spread_source: str = "none"

        # Tick replay mode
        self._tick_mode = False
        self._tick_replay_engine: Optional[TickReplayEngine] = None
        self._tick_cache: Optional[TickCacheManager] = None
        self._agent_auto_execute = False  # Whether agent auto-executes trades

        # Risk management settings
        self._initial_balance = 10000.0  # Starting balance in USD
        self._current_balance = 10000.0  # Track realized P&L
        self._risk_per_trade = 1.0  # Risk % per trade (1% default)
        self._default_rr = 2.0  # Default risk:reward ratio
        self._pip_value_per_lot = 10.0  # USD per pip for 1 standard lot (forex majors)

    def _get_pip_multiplier(self) -> int:
        """Get the pip multiplier based on the symbol type."""
        if not self._symbol:
            return 10000  # Default forex

        if "XAU" in self._symbol or "GOLD" in self._symbol:
            return 10  # Gold: 1 pip = $0.10 movement
        elif "JPY" in self._symbol:
            return 100  # JPY pairs: 1 pip = 0.01
        elif any(idx in self._symbol for idx in ["US30", "NAS", "SPX", "DAX"]):
            return 1  # Indices: 1 pip = 1 point
        else:
            return 10000  # Standard forex pairs

    def configure_risk(
        self,
        initial_balance: Optional[float] = None,
        risk_per_trade: Optional[float] = None,
        default_rr: Optional[float] = None
    ):
        """Configure risk management settings."""
        if initial_balance is not None:
            self._initial_balance = initial_balance
            self._current_balance = initial_balance
        if risk_per_trade is not None:
            self._risk_per_trade = max(0.1, min(10.0, risk_per_trade))  # Limit 0.1% to 10%
        if default_rr is not None:
            self._default_rr = max(0.5, min(10.0, default_rr))  # Limit 0.5 to 10 RR

        logger.info(f"Risk configured: balance=${self._initial_balance}, risk={self._risk_per_trade}%, RR={self._default_rr}")

    def calculate_lot_size(self, entry_price: float, stop_loss: float) -> float:
        """
        Calculate lot size based on risk per trade.

        Formula: Lot Size = (Balance * Risk%) / (SL Pips * Pip Value per Lot)
        """
        # Use consistent pip multiplier for all calculations
        if self._symbol and ("XAU" in self._symbol or "GOLD" in self._symbol):
            pip_multiplier = 10  # Gold: 1 pip = $0.10 movement
        elif self._symbol and "JPY" in self._symbol:
            pip_multiplier = 100
        elif self._symbol and any(idx in self._symbol for idx in ["US30", "NAS", "SPX", "DAX"]):
            pip_multiplier = 1
        else:
            pip_multiplier = 10000

        sl_pips = abs(entry_price - stop_loss) * pip_multiplier

        if sl_pips == 0:
            return 0.01  # Minimum lot

        risk_amount = self._current_balance * (self._risk_per_trade / 100)
        lot_size = risk_amount / (sl_pips * self._pip_value_per_lot)

        # Round to 2 decimal places, min 0.01, max 10.0 lots
        lot_size = round(max(0.01, min(10.0, lot_size)), 2)

        logger.info(f"Calculated lot size: {lot_size} (risk ${risk_amount:.2f}, SL {sl_pips:.1f} pips)")
        return lot_size

    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        direction: TradeDirection,
        risk_reward: Optional[float] = None
    ) -> float:
        """
        Calculate take profit based on risk:reward ratio.

        TP = Entry + (Risk Distance * RR Ratio) for LONG
        TP = Entry - (Risk Distance * RR Ratio) for SHORT
        """
        rr = risk_reward if risk_reward is not None else self._default_rr
        risk_distance = abs(entry_price - stop_loss)
        reward_distance = risk_distance * rr

        if direction == TradeDirection.LONG:
            tp = entry_price + reward_distance
        else:
            tp = entry_price - reward_distance

        # Round appropriately for different instruments
        if self._symbol and ("XAU" in self._symbol or "GOLD" in self._symbol):
            decimals = 2  # Gold typically uses 2 decimal places
        elif self._symbol and "JPY" in self._symbol:
            decimals = 3
        else:
            decimals = 5
        tp = round(tp, decimals)

        logger.info(f"Calculated TP: {tp} (RR={rr}, risk={risk_distance:.5f})")
        return tp

    def get_risk_settings(self) -> Dict:
        """Get current risk management settings."""
        return {
            "initial_balance": self._initial_balance,
            "current_balance": round(self._current_balance, 2),
            "risk_per_trade": self._risk_per_trade,
            "default_rr": self._default_rr,
            "pip_value_per_lot": self._pip_value_per_lot
        }

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
        """Get total number of bars in the primary timeframe (5M)."""
        return len(self._data.get(self.PRIMARY_TIMEFRAME, []))

    @property
    def progress(self) -> float:
        """Get progress as percentage (0-100)."""
        if self.total_bars == 0:
            return 0.0
        return (self._current_index / self.total_bars) * 100

    @property
    def current_time(self) -> Optional[datetime]:
        """
        Get current simulation time from the current bar's timestamp.
        
        This is the simulated backtest time, NOT the real clock time.
        Used by agents for kill zone detection and session checks.
        """
        primary_bars = self._data.get(self.PRIMARY_TIMEFRAME, [])
        if not primary_bars or self._current_index >= len(primary_bars):
            return None
        
        current_bar = primary_bars[self._current_index]
        timestamp_str = current_bar.get("timestamp", "")
        
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        return None

    @property
    def symbol(self) -> Optional[str]:
        """Get current symbol."""
        return self._symbol


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
        """
        if timeframes is None:
            timeframes = ["1H", "15M", "5M"]

        self._symbol = symbol
        self._from_date = from_date
        self._to_date = to_date
        self._data = {}
        self._spread_map = {}
        self._current_index = 0
        self._running = False
        self._position_manager = BacktestPositionManager(symbol)

        # Check if MT5 is connected
        if not self.mt5.is_connected:
            # Try to connect
            if not self.mt5.connect():
                logger.warning("MT5 not available, using sample data for backtest")
                # Generate sample data for backtest
                self._data = self._generate_sample_data(symbol, from_date, to_date, timeframes)
                self._spread_map = self._generate_sample_spread(symbol, from_date, to_date)
                self._spread_source = "sample"
                self._attach_spread_to_bars()
                self._loaded = True
                return {
                    "symbol": symbol,
                    "from_date": from_date.isoformat(),
                    "to_date": to_date.isoformat(),
                    "bar_counts": {tf: len(bars) for tf, bars in self._data.items()},
                    "source": "sample",
                    "spread_source": "sample"
                }

        # Load data from MT5
        for tf in timeframes:
            bars = self.mt5.get_historical_range(symbol, tf, from_date, to_date)
            self._data[tf] = bars
            logger.info(f"Loaded {len(bars)} bars for {symbol} {tf}")

        # Load spread data (downsampled to 1 tick per minute)
        self._spread_map = self.mt5.get_spread_data(symbol, from_date, to_date)
        self._spread_source = "historical_ticks_1min" if self._spread_map else "symbol_info"

        # Attach spread to each bar
        self._attach_spread_to_bars()

        self._loaded = True

        # Initialize tick cache and replay engine if tick_mode was already enabled
        if self._tick_mode:
            if not self._tick_cache:
                self._tick_cache = TickCacheManager(self._symbol)
                logger.info(f"Initialized tick cache for {self._symbol} (deferred from tick_mode)")
            if not self._tick_replay_engine:
                self._tick_replay_engine = TickReplayEngine(self._symbol, self._position_manager)
                self._tick_replay_engine.initialize(self.mt5, self._tick_cache)
                logger.info(f"Initialized tick replay engine for {self._symbol} (deferred from tick_mode)")



        # Find the starting index that matches the requested from_date
        # The data loading might return bars starting earlier than from_date (e.g. if aligned to day start)
        # or we might want to start mid-way through the loaded data
        if self.PRIMARY_TIMEFRAME in self._data:
            primary_bars = self._data[self.PRIMARY_TIMEFRAME]
            start_index = 0
            
            # Ensure from_date is treated as UTC for comparison
            compare_date = from_date
            if compare_date.tzinfo is None:
                compare_date = compare_date.replace(tzinfo=timezone.utc)
            
            # Use a buffer of 1 minute to avoid slight timestamp mismatches
            target_ts = compare_date.timestamp() - 60
            logger.info(f"Target TS: {target_ts} for {from_date}")
            
            for i, bar in enumerate(primary_bars):
                try:
                    bar_ts = datetime.fromisoformat(bar["timestamp"].replace("Z", "+00:00")).timestamp()
                    if i == 0:
                        logger.info(f"First bar TS: {bar_ts} ({bar['timestamp']})")
                    
                    if bar_ts >= target_ts:
                        start_index = i
                        logger.info(f"Found start index {i} at {bar['timestamp']}")
                        break
                except (ValueError, KeyError):
                    continue
            
            # If prompt start time is after all loaded data, start at end
            if start_index == 0 and len(primary_bars) > 0:
                try:
                    last_bar = primary_bars[-1]
                    last_ts = datetime.fromisoformat(last_bar["timestamp"].replace("Z", "+00:00")).timestamp()
                    first_bar = primary_bars[0]
                    first_ts = datetime.fromisoformat(first_bar["timestamp"].replace("Z", "+00:00")).timestamp()
                    
                    # Only override if target is actually after the last bar (and not just matching first bar)
                    # Use a small buffer (e.g. 1 min) for safety
                    if target_ts > last_ts:
                        logger.warning(f"Requested start time {from_date} is after last loaded bar ({last_bar['timestamp']}). Starting at end.")
                        start_index = len(primary_bars) - 1
                except Exception as e:
                    logger.error(f"Error checking start index bounds: {e}")
            
            self._current_index = start_index
            logger.info(f"Set initial backtest index to {self._current_index} for start time {from_date}")

        return {
            "symbol": symbol,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "bar_counts": {tf: len(bars) for tf, bars in self._data.items()},
            "source": "mt5",
            "spread_source": self._spread_source
        }

    def _attach_spread_to_bars(self):
        """Attach spread values to each bar based on timestamp."""
        if not self._spread_map:
            return

        for tf, bars in self._data.items():
            for bar in bars:
                bar_time = bar.get("timestamp", "")
                # Find the closest minute spread
                minute_key = bar_time[:16] + ":00Z"  # Truncate to minute
                bar["spread"] = self._spread_map.get(minute_key, self._get_default_spread())

    def _get_default_spread(self) -> float:
        """Get default spread for the symbol."""
        if "JPY" in self._symbol:
            return 0.02
        elif "XAU" in self._symbol or "GOLD" in self._symbol:
            return 0.30
        else:
            return 0.00012

    def _generate_sample_spread(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, float]:
        """Generate sample spread data."""
        import random
        random.seed(sum(ord(c) for c in symbol))

        default_spread = self._get_default_spread() if self._symbol else 0.00012
        spread_map = {}
        current = from_date

        while current <= to_date:
            minute_str = current.replace(second=0, microsecond=0).isoformat() + "Z"
            variation = 1.0 + (random.random() - 0.5) * 0.2
            spread_map[minute_str] = round(default_spread * variation, 6)
            current += timedelta(minutes=1)

        return spread_map

    def _generate_sample_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframes: List[str]
    ) -> Dict[str, List[Dict]]:
        """Generate sample data when MT5 is not available."""
        import math

        result = {}
        seed = sum(ord(c) for c in symbol)
        base_price = 1.08 if "EUR" in symbol else 150.0 if "JPY" in symbol else 2000.0 if "XAU" in symbol else 1.0
        volatility = 0.002

        for tf in timeframes:
            # Calculate bar count based on timeframe
            tf_minutes = {"1M": 1, "5M": 5, "15M": 15, "30M": 30, "1H": 60, "4H": 240, "1D": 1440}.get(tf, 60)
            total_minutes = (to_date - from_date).total_seconds() / 60
            bar_count = int(total_minutes / tf_minutes)
            # Increased cap: 5000 for 5M, 2000 for 15M, 500 for 1H to allow proper backtesting
            max_bars = {"5M": 5000, "15M": 2000, "1H": 500, "1M": 10000}.get(tf, 3000)
            bar_count = min(bar_count, max_bars)

            bars = []
            price = base_price
            trend = (seed % 3) - 1

            for i in range(bar_count):
                timestamp = from_date.timestamp() + (i * tf_minutes * 60)
                change = (math.sin(seed + i * 0.1) * volatility) + (trend * volatility * 0.2)
                high = price * (1 + abs(change) + volatility * 0.5)
                low = price * (1 - abs(change) - volatility * 0.5)
                close = price * (1 + change)

                bars.append({
                    "timestamp": datetime.utcfromtimestamp(timestamp).isoformat() + "Z",
                    "open": round(price, 5),
                    "high": round(high, 5),
                    "low": round(low, 5),
                    "close": round(close, 5),
                    "volume": 1000 + (seed % 500) + i * 10
                })
                price = close

            result[tf] = bars

        return result

    def get_current_snapshot(self, bars_per_tf: Dict[str, int] = None) -> Dict:
        """
        Get current visible data window with synchronized timeframes.

        Uses 5M as the primary stepping timeframe. 1H and 15M bars are aligned
        to fall within the visible 5M range.

        Args:
            bars_per_tf: Number of bars to show per timeframe

        Returns:
            Dict with current data snapshot
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        if bars_per_tf is None:
            # Increased defaults for proper agent analysis
            # Agent needs at least 10+ 1H bars for structure, 20+ 15M for patterns
            bars_per_tf = {"1H": 100, "15M": 300, "5M": 200}

        # Get 5M bars as primary timeline
        primary_bars = self._data.get(self.PRIMARY_TIMEFRAME, [])
        if not primary_bars or self._current_index >= len(primary_bars):
            return {"error": "Invalid index"}

        max_primary = bars_per_tf.get(self.PRIMARY_TIMEFRAME, 100)
        end_primary = min(self._current_index + 1, len(primary_bars))
        start_primary = max(0, end_primary - max_primary)
        visible_primary = primary_bars[start_primary:end_primary]

        # Get current bar
        current_bar = primary_bars[self._current_index] if self._current_index < len(primary_bars) else visible_primary[-1] if visible_primary else None
        current_timestamp = current_bar.get("timestamp", "") if current_bar else ""

        snapshot = {
            "symbol": self._symbol,
            "timestamp": current_bar.get("timestamp", datetime.utcnow().isoformat() + "Z") if current_bar else datetime.utcnow().isoformat() + "Z",
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "timeframe_bars": {self.PRIMARY_TIMEFRAME: visible_primary},
            "current_bar": current_bar,
            "spread": current_bar.get("spread", self._get_default_spread()) if current_bar else self._get_default_spread()
        }

        # Get timestamp range for aligning higher timeframes
        if visible_primary:
            first_time = visible_primary[0].get("timestamp", "")
            last_time = visible_primary[-1].get("timestamp", "")
        else:
            first_time = last_time = ""

        # Synchronize 1H and 15M to the 5M visible range
        for tf in ["1H", "15M"]:
            if tf != self.PRIMARY_TIMEFRAME and tf in self._data and first_time and last_time:
                aligned_bars = self._get_aligned_bars_for_display(tf, first_time, last_time, bars_per_tf.get(tf, 50))
                snapshot["timeframe_bars"][tf] = aligned_bars

        # Add position data
        if self._position_manager:
            snapshot["open_positions"] = [p.model_dump() for p in self._position_manager.positions.values()]
            snapshot["total_trades"] = len(self._position_manager.trades)

        return snapshot

    def _get_aligned_bars_for_display(
        self,
        timeframe: str,
        start_time: str,
        end_time: str,
        max_bars: int
    ) -> List[Dict]:
        """
        Get bars aligned to a time range for display purposes, STRICTLY enforcing
        that no future bars relative to 'end_time' are returned.
        """
        bars = self._data.get(timeframe, [])
        if not bars:
            return []

        # Parse timestamps for comparison
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            
            # STRICT: Verify we are not leaking future data
            # If end_time matches the current simulation time, we must absolutely ensure
            # we don't return bars that opened AFTER this time (unless they are the current forming bar).
            # For HTF (1H/4H), we only want completed bars or the currently forming one up to current time.
            
            # Since get_current_snapshot sets end_time to current_bar.timestamp, 
            # we can treat end_dt as the hard cutoff.
            
            # Note: We do NOT expand the range forward (future) anymore.
            # We only expand backward to ensure we fill the view.
            if timeframe == "1H":
                start_dt = start_dt - timedelta(hours=5) # Look back further for sufficient history
            elif timeframe == "15M":
                start_dt = start_dt - timedelta(hours=2)
                
        except (ValueError, AttributeError):
            return bars[-max_bars:]

        # Filter bars within range
        aligned = []
        for bar in bars:
            try:
                bar_time = datetime.fromisoformat(bar.get("timestamp", "").replace("Z", "+00:00"))
                
                # STRICT CUTOFF: Bar open time must be <= end_dt
                if start_dt <= bar_time <= end_dt:
                    aligned.append(bar)
                elif bar_time > end_dt:
                    # Optimized: Since bars are likely sorted, we can break early
                    break
                    
            except (ValueError, AttributeError):
                continue

        # Limit to max_bars (keep most recent)
        return aligned[-max_bars:] if len(aligned) > max_bars else aligned

    def run_simulation_step(self) -> Dict:
        """
        Advance one step (5M) and run the agent logic (Continuous Scanning).
        
        This is the core loop method for the realistic backtest simulation.
        It advances time, runs the agent on the new snapshot, and executes trades if signaled.
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}
            
        # 1. Advance time by 1 bar (5M)
        step_result = self.step_forward(1)
        if step_result.get("error"):
            return step_result
            
        # 2. Get the new snapshot for the agent
        # We request sufficient history for HTF analysis
        snapshot = self.get_current_snapshot({
            "1H": 200,   # Deep history for structure
            "15M": 200,  # Deep history for patterns
            "5M": 200
        })
        
        # 3. Add account/session context to snapshot
        if self._position_manager:
            account_info = self.get_risk_settings()
            snapshot["account_balance"] = account_info["current_balance"]
            snapshot["risk_pct"] = account_info["risk_per_trade"]
            snapshot["auto_execute_enabled"] = self._agent_auto_execute
            snapshot["backtest_mode"] = True
            
            # Add MT5 session context if available (or mockup)
            snapshot["session"] = "NY" # TODO: Dynamic session detection
            snapshot["economic_calendar"] = [] # TODO: specific news injection
        
        # 4. Return the data for the agent to process
        # The actual agent call happens in the API/Engine layer, but we return 
        # the comprehensive state here.
        return {
            "step": step_result,
            "snapshot": snapshot,
            "agent_input": snapshot # Duplicate for clarity
        }

    def set_tick_mode(self, enabled: bool) -> Dict:
        """
        Enable or disable tick-by-tick replay mode.

        When enabled, step_forward will replay all ticks within each bar
        for accurate TP/SL hit detection order.

        Note: If symbol is not yet loaded, tick mode will be set but
        tick_cache and tick_replay_engine will be initialized on load_data.
        """
        self._tick_mode = enabled

        if enabled:
            if self._symbol:
                # Symbol loaded - initialize tick cache and replay engine now
                if not self._tick_cache:
                    self._tick_cache = TickCacheManager(self._symbol)
                    logger.info(f"Initialized tick cache for {self._symbol}")
                if not self._tick_replay_engine and self._position_manager:
                    self._tick_replay_engine = TickReplayEngine(self._symbol, self._position_manager)
                    self._tick_replay_engine.initialize(self.mt5, self._tick_cache)
                    logger.info(f"Initialized tick replay engine for {self._symbol}")
                logger.info(f"Tick mode enabled for {self._symbol}")
            else:
                # Symbol not loaded yet - will initialize on load_data
                logger.info("Tick mode enabled (will initialize cache on data load)")
        else:
            logger.info("Tick mode disabled")

        return {
            "tick_mode": self._tick_mode,
            "symbol": self._symbol,
            "tick_cache_ready": self._tick_cache is not None,
            "message": f"Tick mode {'enabled' if enabled else 'disabled'}"
        }

    def set_agent_auto_execute(self, enabled: bool) -> Dict:
        """
        Enable or disable agent auto-execution of trades.

        When enabled, the agent will automatically place trades
        when it detects a valid setup at bar close.
        """
        self._agent_auto_execute = enabled
        logger.info(f"Agent auto-execute {'enabled' if enabled else 'disabled'}")
        return {
            "agent_auto_execute": self._agent_auto_execute,
            "message": f"Agent auto-execute {'enabled' if enabled else 'disabled'}"
        }

    def get_mode_settings(self) -> Dict:
        """Get current mode settings with diagnostic info."""
        return {
            "tick_mode": self._tick_mode,
            "agent_auto_execute": self._agent_auto_execute,
            "tick_cache_stats": self._tick_cache.get_stats() if self._tick_cache else None,
            "symbol": self._symbol,
            "data_loaded": self._loaded,
            "tick_cache_ready": self._tick_cache is not None,
            "tick_replay_engine_ready": self._tick_replay_engine is not None,
            "mt5_connected": self.mt5.is_connected if self.mt5 else False
        }

    def step_forward(self, bars: int = 1) -> Dict:
        """
        Advance simulation by N bars.

        If tick_mode is enabled, replays all ticks within each bar for
        accurate TP/SL hit detection order.

        Args:
            bars: Number of bars to advance

        Returns:
            Dict with new position info, auto-closed trades, and tick progress
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        auto_closed_trades = []
        primary_bars = self._data.get(self.PRIMARY_TIMEFRAME, [])
        tick_replay_info = None

        # Step through each bar individually
        for _ in range(bars):
            if self._current_index >= self.total_bars - 1:
                break

            self._current_index += 1

            if self._position_manager and self._current_index < len(primary_bars):
                current_bar = primary_bars[self._current_index]
                timestamp = current_bar.get("timestamp", "")
                close = current_bar.get("close", 0)

                if self._tick_mode and self._tick_replay_engine and self._position_manager.positions:
                    # Tick-by-tick replay for accurate TP/SL detection
                    bar_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    bar_end = bar_time + timedelta(minutes=5)  # 5M bars

                    # Load ticks for this bar
                    tick_count = self._tick_replay_engine.load_bar_ticks(bar_time, bar_end)

                    if tick_count > 0:
                        # Replay ticks and check TP/SL
                        replay_result = self._tick_replay_engine.replay_bar_ticks(
                            self._current_index, timestamp, self._pip_value_per_lot
                        )

                        # Update balance for closed trades
                        for trade in replay_result["closed_trades"]:
                            self._current_balance += trade.pnl_usd
                            logger.info(f"Tick replay closed: ${trade.pnl_usd:.2f}, Balance: ${self._current_balance:.2f}")

                        auto_closed_trades.extend([t.model_dump() for t in replay_result["closed_trades"]])
                        tick_replay_info = {
                            "enabled": True,
                            "ticks_processed": replay_result["ticks_processed"],
                            "total_ticks": replay_result["total_ticks"]
                        }
                    else:
                        # Fallback to bar-based if no tick data
                        tick_replay_info = {"enabled": True, "ticks_processed": 0, "total_ticks": 0, "fallback": True}
                        closed = self._check_tp_sl_bar_based(current_bar, timestamp)
                        auto_closed_trades.extend(closed)
                else:
                    # Standard bar-based TP/SL check
                    closed = self._check_tp_sl_bar_based(current_bar, timestamp)
                    auto_closed_trades.extend(closed)

                # Update unrealized P&L
                self._position_manager.update_unrealized_pnl(close)

        result = {
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "has_more": self._current_index < self.total_bars - 1,
            "auto_closed_trades": auto_closed_trades,
            "current_balance": round(self._current_balance, 2)
        }

        if tick_replay_info:
            result["tick_replay"] = tick_replay_info

        return result

    def _check_tp_sl_bar_based(self, bar: Dict, timestamp: str) -> List[Dict]:
        """Bar-based TP/SL check (fallback when tick mode disabled or no ticks)."""
        high = bar.get("high", 0)
        low = bar.get("low", 0)

        closed = self._position_manager.check_tp_sl_hit(
            high, low, self._current_index, timestamp, self._pip_value_per_lot
        )

        result = []
        for trade in closed:
            self._current_balance += trade.pnl_usd
            logger.info(f"Auto-closed trade: ${trade.pnl_usd:.2f}, Balance: ${self._current_balance:.2f}")
            result.append(trade.model_dump())

        return result

    def step_backward(self, bars: int = 1) -> Dict:
        """
        Move simulation backward by N bars.
        Note: This does not undo closed trades.

        Args:
            bars: Number of bars to go back

        Returns:
            Dict with new position info
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        self._current_index = max(0, self._current_index - bars)

        # Update unrealized P&L at new position
        if self._position_manager:
            primary_bars = self._data.get(self.PRIMARY_TIMEFRAME, [])
            if self._current_index < len(primary_bars):
                close = primary_bars[self._current_index].get("close", 0)
                self._position_manager.update_unrealized_pnl(close)

        return {
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "has_more": self._current_index < self.total_bars - 1
        }

    def reset(self) -> Dict:
        """Reset to beginning of data and clear all positions/trades."""
        self._current_index = 0
        self._running = False

        if self._position_manager:
            self._position_manager.reset()

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
        status = {
            "loaded": self.is_loaded,
            "running": self.is_running,
            "symbol": self._symbol,
            "from_date": self._from_date.isoformat() if self._from_date else None,
            "to_date": self._to_date.isoformat() if self._to_date else None,
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "progress": self.progress,
            "spread_source": self._spread_source
        }

        if self._position_manager:
            status["open_positions_count"] = len(self._position_manager.positions)
            status["total_trades"] = len(self._position_manager.trades)

        return status

    # ==================== POSITION MANAGEMENT ====================

    def open_trade(
        self,
        direction: TradeDirection,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float] = None,
        volume: Optional[float] = None,
        risk_reward: Optional[float] = None,
        setup_name: Optional[str] = None,
        agent_analysis: Optional[dict] = None,
        auto_calculate: bool = True
    ) -> Optional[BacktestPosition]:
        """
        Open a simulated trade at the current bar with auto-calculation.

        Args:
            direction: LONG or SHORT
            entry_price: Entry price (spread will be applied)
            stop_loss: Stop loss price
            take_profit: Take profit price (auto-calculated if None and auto_calculate=True)
            volume: Position size in lots (auto-calculated if None and auto_calculate=True)
            risk_reward: Custom RR ratio for TP calculation (uses default if None)
            setup_name: Name of the ICT setup
            agent_analysis: Agent analysis snapshot
            auto_calculate: If True, auto-calculate lot size and TP

        Returns:
            The opened BacktestPosition or None if failed
        """
        if not self._position_manager or not self.is_loaded:
            logger.error("Cannot open trade: backtest not loaded")
            return None

        primary_bars = self._data.get(self.PRIMARY_TIMEFRAME, [])
        if self._current_index >= len(primary_bars):
            logger.error("Cannot open trade: invalid index")
            return None

        current_bar = primary_bars[self._current_index]
        timestamp = current_bar.get("timestamp", datetime.utcnow().isoformat() + "Z")
        spread = current_bar.get("spread", self._get_default_spread())

        # Auto-calculate lot size based on risk management
        if volume is None and auto_calculate:
            volume = self.calculate_lot_size(entry_price, stop_loss)
        elif volume is None:
            volume = 0.01  # Default minimum

        # Auto-calculate take profit based on RR
        if take_profit is None and auto_calculate:
            take_profit = self.calculate_take_profit(entry_price, stop_loss, direction, risk_reward)

        # Validate TP/SL are on correct sides for the direction
        sl_valid = True
        tp_valid = True

        if direction == TradeDirection.LONG:
            # LONG: SL should be BELOW entry, TP should be ABOVE entry
            if stop_loss >= entry_price:
                logger.warning(f"LONG trade: SL ({stop_loss}) should be below entry ({entry_price})")
                sl_valid = False
            if take_profit and take_profit <= entry_price:
                logger.warning(f"LONG trade: TP ({take_profit}) should be above entry ({entry_price})")
                tp_valid = False
        else:  # SHORT
            # SHORT: SL should be ABOVE entry, TP should be BELOW entry
            if stop_loss <= entry_price:
                logger.warning(f"SHORT trade: SL ({stop_loss}) should be above entry ({entry_price})")
                sl_valid = False
            if take_profit and take_profit >= entry_price:
                logger.warning(f"SHORT trade: TP ({take_profit}) should be below entry ({entry_price})")
                tp_valid = False

        if not sl_valid or not tp_valid:
            logger.error(f"Trade rejected due to invalid TP/SL placement for {direction.value} direction")
            return None

        logger.info(f"Opening trade: {direction.value} @ {entry_price}, SL={stop_loss}, TP={take_profit}, Vol={volume}")

        return self._position_manager.open_position(
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            spread=spread,
            bar_index=self._current_index,
            timestamp=timestamp,
            setup_name=setup_name,
            agent_analysis=agent_analysis
        )

    def close_trade(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        reason: BacktestExitReason = BacktestExitReason.MANUAL
    ) -> Optional[BacktestTrade]:
        """
        Close a simulated trade and update balance.

        Args:
            position_id: ID of the position to close
            exit_price: Exit price (uses current close if not provided)
            reason: Reason for closing

        Returns:
            The completed BacktestTrade or None if failed
        """
        if not self._position_manager or not self.is_loaded:
            return None

        primary_bars = self._data.get(self.PRIMARY_TIMEFRAME, [])
        if self._current_index >= len(primary_bars):
            return None

        current_bar = primary_bars[self._current_index]
        timestamp = current_bar.get("timestamp", datetime.utcnow().isoformat() + "Z")

        if exit_price is None:
            exit_price = current_bar.get("close", 0)

        trade = self._position_manager.close_position(
            position_id=position_id,
            exit_price=exit_price,
            exit_reason=reason,
            bar_index=self._current_index,
            timestamp=timestamp,
            pip_value_per_lot=self._pip_value_per_lot
        )

        # Update balance with realized P&L
        if trade:
            self._current_balance += trade.pnl_usd
            logger.info(f"Balance updated: ${self._current_balance:.2f} (trade P&L: ${trade.pnl_usd:.2f})")

        return trade

    def get_open_positions(self) -> List[BacktestPosition]:
        """Get all open backtest positions."""
        if not self._position_manager:
            return []
        return list(self._position_manager.positions.values())

    def get_trades(self) -> List[BacktestTrade]:
        """Get all completed backtest trades."""
        if not self._position_manager:
            return []
        return self._position_manager.trades

    def get_statistics(self) -> BacktestStatistics:
        """Get backtest performance statistics."""
        if not self._position_manager:
            return BacktestStatistics()
        return self._position_manager.get_statistics()

    def export_results(self) -> BacktestExport:
        """Export complete backtest results as JSON-serializable object."""
        metadata = BacktestExportMetadata(
            symbol=self._symbol or "UNKNOWN",
            from_date=self._from_date.isoformat() if self._from_date else "",
            to_date=self._to_date.isoformat() if self._to_date else "",
            total_1h_bars=len(self._data.get("1H", [])),  # Keep 1H count for reference
            spread_source=self._spread_source,
            exported_at=datetime.utcnow().isoformat() + "Z"
        )

        return BacktestExport(
            metadata=metadata,
            trades=self.get_trades(),
            statistics=self.get_statistics()
        )

    # ==================== SESSION PERSISTENCE ====================

    def save_session(self, name: str = None) -> Dict:
        """
        Save current backtest session to a JSON file.

        Args:
            name: Session name (default: auto-generated from symbol and timestamp)

        Returns:
            Dict with save status and filepath
        """
        if not self.is_loaded:
            return {"success": False, "error": "No session to save"}

        settings = get_settings()
        sessions_dir = Path(settings.sessions_dir)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if name:
            filename = f"{name}_{timestamp}.json"
        else:
            filename = f"backtest_{self._symbol}_{timestamp}.json"

        filepath = sessions_dir / filename

        # Build session data
        session_data = {
            "version": "1.0",
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "config": {
                "symbol": self._symbol,
                "from_date": self._from_date.isoformat() if self._from_date else None,
                "to_date": self._to_date.isoformat() if self._to_date else None,
                "initial_balance": self._initial_balance,
                "risk_per_trade": self._risk_per_trade,
                "default_rr": self._default_rr,
                "tick_mode": self._tick_mode,
                "agent_auto_execute": self._agent_auto_execute
            },
            "state": {
                "current_index": self._current_index,
                "current_balance": self._current_balance,
                "total_bars": self.total_bars
            },
            "positions": [p.model_dump() for p in self.get_open_positions()],
            "trades": [t.model_dump() for t in self.get_trades()],
            "statistics": self.get_statistics().model_dump()
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, default=str)

            logger.info(f"Session saved to {filepath}")
            return {
                "success": True,
                "filepath": str(filepath),
                "filename": filename,
                "trades_count": len(session_data["trades"]),
                "positions_count": len(session_data["positions"])
            }
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return {"success": False, "error": str(e)}

    def load_session(self, filepath: str) -> Dict:
        """
        Load a saved backtest session.

        Note: This restores the state but requires the original data to be loaded.

        Args:
            filepath: Path to the session JSON file

        Returns:
            Dict with load status
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            config = session_data.get("config", {})
            state = session_data.get("state", {})

            # Restore configuration
            if config.get("symbol") and config.get("from_date") and config.get("to_date"):
                # Load data if not already loaded for this symbol/range
                if (self._symbol != config["symbol"] or
                    not self._from_date or
                    self._from_date.isoformat() != config["from_date"]):

                    self.load_backtest_data(
                        symbol=config["symbol"],
                        from_date=datetime.fromisoformat(config["from_date"]),
                        to_date=datetime.fromisoformat(config["to_date"])
                    )

            # Restore risk settings
            self.configure_risk(
                initial_balance=config.get("initial_balance"),
                risk_per_trade=config.get("risk_per_trade"),
                default_rr=config.get("default_rr")
            )

            # Restore mode settings
            self._tick_mode = config.get("tick_mode", False)
            self._agent_auto_execute = config.get("agent_auto_execute", False)

            # Restore state
            self._current_index = state.get("current_index", 0)
            self._current_balance = state.get("current_balance", self._initial_balance)

            # Restore positions (recreate them)
            if self._position_manager:
                self._position_manager.reset()
                for pos_data in session_data.get("positions", []):
                    pos = BacktestPosition(**pos_data)
                    self._position_manager.positions[pos.id] = pos

                # Restore trades history
                for trade_data in session_data.get("trades", []):
                    trade = BacktestTrade(**trade_data)
                    self._position_manager.trades.append(trade)

            logger.info(f"Session loaded from {filepath}")
            return {
                "success": True,
                "symbol": config.get("symbol"),
                "current_index": self._current_index,
                "current_balance": self._current_balance,
                "positions_restored": len(session_data.get("positions", [])),
                "trades_restored": len(session_data.get("trades", []))
            }

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return {"success": False, "error": str(e)}

    def list_sessions(self) -> List[Dict]:
        """
        List all saved backtest sessions.

        Returns:
            List of session info dictionaries
        """
        settings = get_settings()
        sessions_dir = Path(settings.sessions_dir)

        if not sessions_dir.exists():
            return []

        sessions = []
        for filepath in sessions_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                config = data.get("config", {})
                state = data.get("state", {})

                sessions.append({
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "saved_at": data.get("saved_at"),
                    "symbol": config.get("symbol"),
                    "from_date": config.get("from_date"),
                    "to_date": config.get("to_date"),
                    "trades_count": len(data.get("trades", [])),
                    "final_balance": state.get("current_balance"),
                    "progress_pct": (state.get("current_index", 0) / max(1, state.get("total_bars", 1))) * 100
                })
            except Exception as e:
                logger.warning(f"Failed to read session file {filepath}: {e}")
                continue

        # Sort by saved_at descending
        sessions.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return sessions

    def delete_session(self, filepath: str) -> Dict:
        """Delete a saved session file."""
        try:
            path = Path(filepath)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted session: {filepath}")
                return {"success": True, "deleted": filepath}
            else:
                return {"success": False, "error": "File not found"}
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return {"success": False, "error": str(e)}

    def get_current_bar_data(self) -> Dict:
        """
        Get current bar data for agent analysis.

        Returns:
            Dict with current bar info and context for agent
        """
        if not self.is_loaded:
            return {"error": "No data loaded"}

        primary_bars = self._data.get(self.PRIMARY_TIMEFRAME, [])
        if self._current_index >= len(primary_bars):
            return {"error": "Invalid index"}

        current_bar = primary_bars[self._current_index]

        return {
            "symbol": self._symbol,
            "timestamp": current_bar.get("timestamp"),
            "current_index": self._current_index,
            "total_bars": self.total_bars,
            "bar": current_bar,
            "open_positions_count": len(self.get_open_positions()),
            "current_balance": round(self._current_balance, 2),
            "tick_mode": self._tick_mode,
            "agent_auto_execute": self._agent_auto_execute
        }


# Singleton instance
_backtest_service: Optional[BacktestService] = None


def get_backtest_service() -> BacktestService:
    """Get the singleton backtest service instance."""
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService()
    return _backtest_service
