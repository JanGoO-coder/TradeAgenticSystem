"""
Smart Backtest Service.

Enhanced backtesting with agent integration, selective analysis,
decision logging, and trade simulation.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, AsyncGenerator
import logging

from app.core.config import get_settings
from app.services.mt5_service import get_mt5_service
from app.agent.main_agent import get_main_agent, MainAgent
from app.tools.observer import run_event_observation
from app.domain.observation import ObservationResult
from app.domain.backtest import (
    BacktestSession,
    BacktestDecision,
    BacktestTrade,
    TradeResult
)

# ICT Architecture imports
from app.domain.observation import ObservationResult

logger = logging.getLogger(__name__)


class SmartBacktestService:
    """
    Smart backtesting with agent integration.

    Features:
    - Selective analysis: Only call agent when state changes
    - Decision logging: Record all agent decisions
    - Trade simulation: Track hypothetical trades to completion
    - Progress streaming: Real-time updates during batch runs
    """

    def __init__(self):
        self.settings = get_settings()
        self.mt5 = get_mt5_service()
        self._agent: Optional[MainAgent] = None

        # Data storage
        self._data: Dict[str, List[Dict]] = {}
        self._loaded = False

        # Active session
        self._session: Optional[BacktestSession] = None

        # Ensure sessions directory exists
        self._sessions_dir = Path(self.settings.backtest_sessions_dir)
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize agent dependency."""
        if self._agent is None:
            self._agent = await get_main_agent()

    # =========================================================================
    # Data Loading
    # =========================================================================

    def _ensure_mt5_connected(self) -> bool:
        """
        Ensure MT5 is connected, attempting auto-connect if needed.

        Returns:
            True if connected, False otherwise
        """
        if self.mt5.is_connected:
            return True

        # Attempt auto-connect using settings credentials
        logger.info("MT5 not connected, attempting auto-connect...")

        success = self.mt5.connect(
            login=self.settings.mt5_login,
            password=self.settings.mt5_password,
            server=self.settings.mt5_server
        )

        if success:
            logger.info("MT5 auto-connect successful")
        else:
            logger.error("MT5 auto-connect failed")

        return success

    def load_data(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        timeframes: List[str] = None
    ) -> Dict:
        """
        Load historical data for backtesting from MT5.

        Raises MT5ConnectionError if MT5 is not available.
        Never falls back to sample data.

        Args:
            symbol: Trading symbol
            from_date: Start date
            to_date: End date
            timeframes: Timeframes to load (default: 1H, 15M, 5M)

        Returns:
            Loading status with bar counts

        Raises:
            ValueError: If MT5 is not connected or no data available
        """
        if timeframes is None:
            timeframes = ["1H", "15M", "5M"]

        self._data = {}

        # Ensure MT5 is connected (auto-connect if needed)
        if not self._ensure_mt5_connected():
            raise ValueError(
                "MT5 not connected. Please ensure MetaTrader 5 terminal is running "
                "and credentials are configured in environment variables."
            )

        # Check data availability before loading
        primary_tf = timeframes[0]  # Usually 1H
        is_available, first_bar, last_bar = self.mt5.check_data_availability(
            symbol, primary_tf, from_date, to_date
        )

        if not is_available:
            available_range = ""
            if first_bar and last_bar:
                available_range = f" Available data: {first_bar.strftime('%Y-%m-%d')} to {last_bar.strftime('%Y-%m-%d')}."
            raise ValueError(
                f"No MT5 data available for {symbol} from {from_date.strftime('%Y-%m-%d')} "
                f"to {to_date.strftime('%Y-%m-%d')}.{available_range}"
            )

        # Load data from MT5
        for tf in timeframes:
            bars = self.mt5.get_historical_range(symbol, tf, from_date, to_date)
            if not bars:
                raise ValueError(
                    f"MT5 returned no data for {symbol} {tf} from {from_date} to {to_date}. "
                    "Check if the symbol is available in your MT5 terminal."
                )
            self._data[tf] = self._normalize_bars(bars)
            logger.info(f"Loaded {len(bars)} bars for {symbol} {tf} from MT5")

        self._loaded = True

        return {
            "symbol": symbol,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "bar_counts": {tf: len(bars) for tf, bars in self._data.items()},
            "source": "mt5",
            "mt5_connected": True
        }

    def _normalize_bars(self, bars: List[Dict]) -> List[Dict]:
        """Normalize bar format for consistency."""
        normalized = []
        for bar in bars:
            normalized.append({
                "time": bar.get("time") or bar.get("timestamp"),
                "open": float(bar.get("open", 0)),
                "high": float(bar.get("high", 0)),
                "low": float(bar.get("low", 0)),
                "close": float(bar.get("close", 0)),
                "volume": int(bar.get("volume", 0))
            })
        return normalized

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
        htf_timeframe: str = "1H",
        ltf_timeframe: str = "15M"
    ) -> BacktestSession:
        """
        Create a new backtest session.

        Args:
            symbol: Trading symbol
            from_date: Start date
            to_date: End date
            htf_timeframe: Higher timeframe (default 1H)
            ltf_timeframe: Lower timeframe (default 15M)

        Returns:
            New BacktestSession
        """
        # Load data if needed
        if not self._loaded or self._data.get(htf_timeframe) is None:
            self.load_data(symbol, from_date, to_date, [htf_timeframe, ltf_timeframe, "5M"])

        session = BacktestSession(
            symbol=symbol,
            start_date=from_date,
            end_date=to_date,
            htf_timeframe=htf_timeframe,
            ltf_timeframe=ltf_timeframe,
            total_candles=len(self._data.get(ltf_timeframe, [])),
            status="CREATED"
        )

        self._session = session
        return session

    def get_session(self) -> Optional[BacktestSession]:
        """Get the current active session."""
        return self._session

    def save_session(self, session: Optional[BacktestSession] = None) -> str:
        """
        Save session to disk.

        Returns:
            Path to saved file
        """
        session = session or self._session
        if not session:
            raise ValueError("No session to save")

        path = self._sessions_dir / f"{session.session_id}.json"
        session.save(str(path))
        return str(path)

    def load_session(self, session_id: str) -> BacktestSession:
        """Load a session from disk."""
        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        session = BacktestSession.load(str(path))
        self._session = session
        return session

    def list_sessions(self) -> List[Dict]:
        """List all saved sessions."""
        sessions = []
        for path in self._sessions_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                    sessions.append({
                        "session_id": data["session_id"],
                        "symbol": data["symbol"],
                        "start_date": data.get("start_date"),
                        "end_date": data.get("end_date"),
                        "status": data["status"],
                        "trades_count": data.get("trades_count", 0),
                        "total_pnl_r": data.get("performance", {}).get("total_pnl_r", 0)
                    })
            except Exception as e:
                logger.warning(f"Error loading session {path}: {e}")

        return sessions

    # =========================================================================
    # Analysis
    # =========================================================================

    def get_candles_at_index(
        self,
        index: int,
        htf_lookback: int = 50,
        ltf_lookback: int = 100
    ) -> Dict[str, List[Dict]]:
        """
        Get candles visible at a specific index (time machine view).

        Args:
            index: Current candle index in LTF
            htf_lookback: Number of HTF candles to include
            ltf_lookback: Number of LTF candles to include

        Returns:
            Dict with HTF, LTF, and micro candles
        """
        if not self._loaded:
            return {}

        session = self._session
        htf_tf = session.htf_timeframe if session else "1H"
        ltf_tf = session.ltf_timeframe if session else "15M"

        htf_data = self._data.get(htf_tf, [])
        ltf_data = self._data.get(ltf_tf, [])
        micro_data = self._data.get("5M", [])

        # Map LTF index to HTF index (approximate)
        ltf_per_htf = {"1H": 4, "4H": 16}.get(htf_tf, 4)  # 15M per HTF
        htf_index = index // ltf_per_htf

        # Get visible candles (everything up to current index)
        return {
            "htf": htf_data[max(0, htf_index - htf_lookback):htf_index + 1],
            "ltf": ltf_data[max(0, index - ltf_lookback):index + 1],
            "micro": micro_data[max(0, index * 3 - ltf_lookback * 3):index * 3 + 3] if micro_data else []
        }

    async def analyze_ict_at_index(
        self,
        index: int,
        mode: str = "concise",
        force: bool = False
    ) -> tuple[ObservationResult, BacktestDecision]:
        """
        Run ICT Architecture analysis at a specific index.
        
        Uses the new ICT architecture with:
        - Event-based observer
        - Context manager
        - Phase detection
        - Decision validator (veto layer)
        
        Args:
            index: Candle index to analyze (on LTF)
            mode: "verbose" or "concise"
            force: Force analysis even if state hasn't changed
            
        Returns:
            Tuple of (ObservationResult, BacktestDecision)
        """
        await self.initialize()
        session = self._session

        if not session:
            raise ValueError("No active session")

        # Get candles at this point in time
        candles = self.get_candles_at_index(index)

        if not candles.get("ltf"):
            raise ValueError(f"No LTF data at index {index}")

        # Get timestamp from current LTF candle
        current_candle = candles["ltf"][-1]
        time_str = current_candle["time"]

        # Clean up timezone string
        if time_str.endswith("Z"):
            time_str = time_str[:-1]
        if "+00:00" in time_str:
            time_str = time_str.split("+")[0]
        if "-" in time_str and time_str.count("-") > 2:
            parts = time_str.rsplit("-", 1)
            if ":" in parts[-1] and len(parts[-1]) <= 6:
                time_str = parts[0]

        try:
            timestamp = datetime.fromisoformat(time_str)
        except ValueError as e:
            logger.warning(f"Could not parse timestamp {time_str}: {e}")
            timestamp = datetime.now()

        # Run ICT analysis via new architecture
        observation, agent_decision = await self._agent.analyze_ict(
            htf_candles=candles["htf"],
            ltf_candles=candles["ltf"],
            symbol=session.symbol,
            timestamp=timestamp,
            mode=mode
        )

        # Convert TradeSetup to dict if present
        setup_dict = None
        if agent_decision.setup:
            setup = agent_decision.setup
            setup_dict = {
                "direction": setup.direction,
                "entry": setup.entry_price,
                "stop_loss": setup.stop_loss,
                "take_profit": setup.take_profit,
                "entry_model": setup.entry_model,
                "pd_array_type": setup.pd_array_type
            }

        # Build BacktestDecision
        decision = BacktestDecision(
            index=index,
            timestamp=timestamp,
            decision=agent_decision.decision,
            confidence=agent_decision.confidence,
            brief_reason=agent_decision.brief_reason,
            rule_citations=agent_decision.rule_citations,
            setup=setup_dict,
            observation_hash=observation.state_hash,
            price_at_decision=observation.current_price,
            latency_ms=agent_decision.total_latency_ms,
            skipped=False
        )

        # Add extra ICT context (validation result, phase)
        decision.extra = {
            "phase": agent_decision.phase_at_decision,
            "validated": agent_decision.validation.approved if agent_decision.validation else True,
            "veto_reasons": [v.value for v in agent_decision.validation.veto_reasons] if agent_decision.validation else [],
            "events_count": len(observation.events)
        }

        # Update session
        session.last_state_hash = observation.state_hash
        session.add_decision(decision)

        # Handle trade setup (only if validated/approved)
        is_approved = agent_decision.validation.approved if agent_decision.validation else True
        if decision.decision == "TRADE" and decision.setup and is_approved:
            await self._open_trade(decision, session)

        return observation, decision

    async def _open_trade(self, decision: BacktestDecision, session: BacktestSession):
        """Open a new trade based on agent decision."""
        setup = decision.setup

        trade = BacktestTrade(
            decision_index=decision.index,
            direction=setup.get("direction", "LONG"),
            entry_price=setup.get("entry", decision.price_at_decision),
            stop_loss=setup.get("stop_loss", 0),
            take_profit=setup.get("take_profit", 0),
            entry_time=decision.timestamp,
            entry_index=decision.index
        )

        # Calculate risk
        if trade.direction == "LONG":
            trade.risk_pips = (trade.entry_price - trade.stop_loss) * 10000
        else:
            trade.risk_pips = (trade.stop_loss - trade.entry_price) * 10000

        session.add_trade(trade)

    def check_trade_exits(self, index: int) -> List[BacktestTrade]:
        """
        Check if any open trades have hit TP/SL.

        Args:
            index: Current candle index

        Returns:
            List of trades that were closed
        """
        session = self._session
        if not session:
            return []

        candles = self.get_candles_at_index(index)
        if not candles.get("ltf"):
            return []

        current_candle = candles["ltf"][-1]
        high = current_candle["high"]
        low = current_candle["low"]

        # Parse timestamp safely
        time_str = current_candle["time"]
        if time_str.endswith("Z"):
            time_str = time_str[:-1]
        if "+00:00" in time_str:
            time_str = time_str.split("+")[0]
        try:
            timestamp = datetime.fromisoformat(time_str)
        except ValueError:
            timestamp = datetime.now()

        closed_trades = []

        for trade in session.trades:
            if trade.result != TradeResult.OPEN:
                continue

            if trade.direction == "LONG":
                # Check SL first (conservative)
                if low <= trade.stop_loss:
                    trade.calculate_result(
                        trade.stop_loss, index, timestamp, "SL_HIT"
                    )
                    closed_trades.append(trade)
                elif high >= trade.take_profit:
                    trade.calculate_result(
                        trade.take_profit, index, timestamp, "TP_HIT"
                    )
                    closed_trades.append(trade)
            else:  # SHORT
                if high >= trade.stop_loss:
                    trade.calculate_result(
                        trade.stop_loss, index, timestamp, "SL_HIT"
                    )
                    closed_trades.append(trade)
                elif low <= trade.take_profit:
                    trade.calculate_result(
                        trade.take_profit, index, timestamp, "TP_HIT"
                    )
                    closed_trades.append(trade)

        return closed_trades

    # =========================================================================
    # Batch Execution
    # =========================================================================

    async def run_batch(
        self,
        step_size: int = 1,
        max_concurrent: int = 10
    ) -> AsyncGenerator[Dict, None]:
        """
        Run batch backtest with progress streaming.

        Args:
            step_size: Candles to advance per step
            max_concurrent: Max parallel agent calls

        Yields:
            Progress updates and results
        """
        await self.initialize()
        session = self._session

        if not session:
            yield {"error": "No active session"}
            return

        session.status = "RUNNING"
        session.started_at = datetime.utcnow()

        yield {
            "event": "started",
            "session_id": session.session_id,
            "total_candles": session.total_candles
        }

        try:
            index = 50  # Start after enough history

            while index < session.total_candles:
                # Check for trade exits first
                closed = self.check_trade_exits(index)

                if closed:
                    yield {
                        "event": "trades_closed",
                        "index": index,
                        "trades": [t.to_dict() for t in closed]
                    }

                # Run analysis
                try:
                    observation, decision = await self.analyze_ict_at_index(
                        index, mode="concise"
                    )

                    session.update_progress(index)

                    # Yield progress every 10 candles or on decisions
                    if index % 10 == 0 or decision.decision != "WAIT":
                        yield {
                            "event": "progress",
                            "index": index,
                            "progress": session.progress,
                            "decision": decision.decision,
                            "skipped": decision.skipped,
                            "total_decisions": len(session.decisions),
                            "total_trades": len(session.trades)
                        }

                except Exception as e:
                    logger.error(f"Error at index {index}: {e}")
                    yield {"event": "error", "index": index, "error": str(e)}

                index += step_size

                # Rate limiting - small delay between calls
                await asyncio.sleep(0.01)

            # Close any remaining open trades
            for trade in session.trades:
                if trade.result == TradeResult.OPEN:
                    candles = self.get_candles_at_index(session.total_candles - 1)
                    if candles.get("ltf"):
                        last_candle = candles["ltf"][-1]
                        time_str = last_candle["time"]
                        if time_str.endswith("Z"):
                            time_str = time_str[:-1]
                        if "+00:00" in time_str:
                            time_str = time_str.split("+")[0]
                        try:
                            timestamp = datetime.fromisoformat(time_str)
                        except ValueError:
                            timestamp = datetime.now()
                        trade.calculate_result(
                            last_candle["close"],
                            session.total_candles - 1,
                            timestamp,
                            "END_OF_DATA"
                        )

            # Finalize session
            session.finalize()

            # Save session
            path = self.save_session(session)

            yield {
                "event": "completed",
                "session_id": session.session_id,
                "performance": session.performance.to_dict(),
                "saved_to": path
            }

        except Exception as e:
            session.status = "ERROR"
            yield {"event": "error", "error": str(e)}
            raise

    async def run_ict_batch(
        self,
        step_size: int = 1,
        max_concurrent: int = 10
    ) -> AsyncGenerator[Dict, None]:
        """
        Run batch backtest using the new ICT Architecture with progress streaming.
        
        Uses the full ICT pipeline:
        - Event-based observer
        - Context manager with memory
        - Phase detection (PO3)
        - Decision validator (veto layer)
        
        Args:
            step_size: Candles to advance per step (on LTF)
            max_concurrent: Max parallel agent calls (not used yet)
            
        Yields:
            Progress updates and results
        """
        await self.initialize()
        session = self._session

        if not session:
            yield {"error": "No active session"}
            return

        session.status = "RUNNING"
        session.started_at = datetime.utcnow()

        yield {
            "event": "started",
            "session_id": session.session_id,
            "total_candles": session.total_candles,
            "strategy": "ICT Architecture"
        }

        try:
            index = 50  # Start after enough history
            vetoed_count = 0
            approved_count = 0

            while index < session.total_candles:
                # Check for trade exits first
                closed = self.check_trade_exits(index)

                if closed:
                    yield {
                        "event": "trades_closed",
                        "index": index,
                        "trades": [t.to_dict() for t in closed]
                    }

                # Run ICT analysis
                try:
                    observation, decision = await self.analyze_ict_at_index(
                        index, mode="concise"
                    )

                    # Track validation stats
                    if decision.extra:
                        if decision.extra.get("validated"):
                            approved_count += 1
                        else:
                            vetoed_count += 1

                    session.update_progress(index)

                    # Yield progress every 10 candles or on decisions
                    if index % 10 == 0 or decision.decision != "WAIT":
                        yield {
                            "event": "progress",
                            "index": index,
                            "progress": session.progress,
                            "decision": decision.decision,
                            "phase": decision.extra.get("phase") if decision.extra else None,
                            "validated": decision.extra.get("validated") if decision.extra else True,
                            "total_decisions": len(session.decisions),
                            "total_trades": len(session.trades),
                            "approved_count": approved_count,
                            "vetoed_count": vetoed_count
                        }

                except Exception as e:
                    logger.error(f"ICT analysis error at index {index}: {e}")
                    yield {"event": "error", "index": index, "error": str(e)}

                index += step_size

                # Rate limiting
                await asyncio.sleep(0.01)

            # Close any remaining open trades
            for trade in session.trades:
                if trade.result == TradeResult.OPEN:
                    candles = self.get_candles_at_index(session.total_candles - 1)
                    if candles.get("ltf"):
                        last_candle = candles["ltf"][-1]
                        time_str = last_candle["time"]
                        if time_str.endswith("Z"):
                            time_str = time_str[:-1]
                        if "+00:00" in time_str:
                            time_str = time_str.split("+")[0]
                        try:
                            timestamp = datetime.fromisoformat(time_str)
                        except ValueError:
                            timestamp = datetime.now()
                        trade.calculate_result(
                            last_candle["close"],
                            session.total_candles - 1,
                            timestamp,
                            "END_OF_DATA"
                        )

            # Finalize session
            session.finalize()

            # Save session
            path = self.save_session(session)

            yield {
                "event": "completed",
                "session_id": session.session_id,
                "strategy": "ICT Architecture",
                "performance": session.performance.to_dict(),
                "validation_stats": {
                    "approved": approved_count,
                    "vetoed": vetoed_count
                },
                "saved_to": path
            }

        except Exception as e:
            session.status = "ERROR"
            yield {"event": "error", "error": str(e)}
            raise

    # =========================================================================
    # Interactive Mode
    # =========================================================================

    async def step_forward(self, bars: int = 1) -> Dict:
        """
        Step forward in time machine mode.

        Returns analysis at the new position.
        """
        session = self._session
        if not session:
            return {"error": "No active session"}

        new_index = min(session.current_index + bars, session.total_candles - 1)
        session.update_progress(new_index)

        # Check trade exits
        closed = self.check_trade_exits(new_index)

        # Run analysis
        observation, decision = await self.analyze_ict_at_index(new_index, mode="verbose")

        return {
            "index": new_index,
            "progress": session.progress,
            "observation": observation.to_summary(),
            "decision": decision.to_dict(),
            "closed_trades": [t.to_dict() for t in closed]
        }

    def step_backward(self, bars: int = 1) -> Dict:
        """Step backward in time machine mode."""
        session = self._session
        if not session:
            return {"error": "No active session"}

        new_index = max(50, session.current_index - bars)  # Don't go before history
        session.update_progress(new_index)

        return {
            "index": new_index,
            "progress": session.progress
        }

    def jump_to(self, index: int) -> Dict:
        """Jump to specific index."""
        session = self._session
        if not session:
            return {"error": "No active session"}

        index = max(50, min(index, session.total_candles - 1))
        session.update_progress(index)

        return {
            "index": index,
            "progress": session.progress
        }

    def get_snapshot(self) -> Dict:
        """Get current time machine snapshot."""
        session = self._session
        if not session:
            return {"error": "No active session"}

        candles = self.get_candles_at_index(session.current_index)

        return {
            "session": session.to_dict(),
            "candles": {
                "htf": candles.get("htf", [])[-20:],  # Last 20 for chart
                "ltf": candles.get("ltf", [])[-50:]   # Last 50 for chart
            }
        }


# Singleton
_smart_backtest_service: Optional[SmartBacktestService] = None


async def get_smart_backtest_service() -> SmartBacktestService:
    """Get the smart backtest service singleton."""
    global _smart_backtest_service
    if _smart_backtest_service is None:
        _smart_backtest_service = SmartBacktestService()
        await _smart_backtest_service.initialize()
    return _smart_backtest_service
