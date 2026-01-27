"""
Backtest Domain Models.

Data structures for backtesting sessions, decisions, and performance tracking.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Literal
from enum import Enum
import json
import uuid


class TradeResult(Enum):
    """Outcome of a hypothetical trade."""
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    OPEN = "OPEN"
    SKIPPED = "SKIPPED"


@dataclass
class BacktestDecision:
    """
    A single decision made during backtesting.
    """
    # Identity
    index: int  # Candle index when decision was made
    timestamp: datetime

    # Decision
    decision: Literal["TRADE", "WAIT", "NO_TRADE"]
    confidence: float
    brief_reason: str
    rule_citations: List[str]

    # Setup (if TRADE)
    setup: Optional[dict] = None  # {direction, entry, stop_loss, take_profit}

    # State
    observation_hash: str = ""
    price_at_decision: float = 0.0

    # Trade result (filled in later when outcome is known)
    result: Optional[TradeResult] = None
    result_pips: Optional[float] = None
    result_r: Optional[float] = None  # Result in R-multiples
    exit_price: Optional[float] = None
    exit_index: Optional[int] = None

    # Analysis meta
    latency_ms: int = 0
    skipped: bool = False  # True if skipped due to no state change

    def to_dict(self) -> dict:
        d = {
            "index": self.index,
            "timestamp": self.timestamp.isoformat(),
            "decision": self.decision,
            "confidence": self.confidence,
            "brief_reason": self.brief_reason,
            "rule_citations": self.rule_citations,
            "setup": self.setup,
            "observation_hash": self.observation_hash,
            "price_at_decision": self.price_at_decision,
            "result": self.result.value if self.result else None,
            "result_pips": self.result_pips,
            "result_r": self.result_r,
            "exit_price": self.exit_price,
            "exit_index": self.exit_index,
            "latency_ms": self.latency_ms,
            "skipped": self.skipped
        }
        return d


@dataclass
class BacktestTrade:
    """
    A hypothetical trade from backtesting.
    """
    # Identity
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    decision_index: int = 0  # Index of decision that triggered this trade

    # Trade details
    direction: Literal["LONG", "SHORT"] = "LONG"
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    # Entry
    entry_time: Optional[datetime] = None
    entry_index: int = 0

    # Exit
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_index: Optional[int] = None
    exit_reason: str = ""  # "TP_HIT", "SL_HIT", "MANUAL", "END_OF_DATA"

    # Result
    result: TradeResult = TradeResult.OPEN
    pnl_pips: float = 0.0
    pnl_r: float = 0.0  # P&L in R-multiples

    # Risk
    risk_pips: float = 0.0
    risk_r: float = 1.0  # Always 1R risked

    def calculate_result(self, exit_price: float, exit_index: int, exit_time: datetime, reason: str):
        """Calculate trade result when exit occurs."""
        self.exit_price = exit_price
        self.exit_index = exit_index
        self.exit_time = exit_time
        self.exit_reason = reason

        if self.direction == "LONG":
            self.pnl_pips = (exit_price - self.entry_price) * 10000
            self.risk_pips = (self.entry_price - self.stop_loss) * 10000
        else:  # SHORT
            self.pnl_pips = (self.entry_price - exit_price) * 10000
            self.risk_pips = (self.stop_loss - self.entry_price) * 10000

        if self.risk_pips > 0:
            self.pnl_r = self.pnl_pips / self.risk_pips

        if self.pnl_pips > 0.1:
            self.result = TradeResult.WIN
        elif self.pnl_pips < -0.1:
            self.result = TradeResult.LOSS
        else:
            self.result = TradeResult.BREAKEVEN

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "decision_index": self.decision_index,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "entry_index": self.entry_index,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "exit_index": self.exit_index,
            "exit_reason": self.exit_reason,
            "result": self.result.value,
            "pnl_pips": round(self.pnl_pips, 1),
            "pnl_r": round(self.pnl_r, 2),
            "risk_pips": round(self.risk_pips, 1)
        }


@dataclass
class BacktestPerformance:
    """
    Performance metrics for a backtest session.
    """
    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    # Win rate
    win_rate: float = 0.0

    # P&L
    total_pnl_pips: float = 0.0
    total_pnl_r: float = 0.0
    average_win_pips: float = 0.0
    average_loss_pips: float = 0.0
    average_win_r: float = 0.0
    average_loss_r: float = 0.0

    # Risk metrics
    profit_factor: float = 0.0
    expectancy_r: float = 0.0  # Expected R per trade
    max_drawdown_r: float = 0.0
    max_consecutive_losses: int = 0

    # Equity curve
    equity_curve: List[float] = field(default_factory=list)

    def calculate(self, trades: List[BacktestTrade]):
        """Calculate performance from list of closed trades."""
        closed_trades = [t for t in trades if t.result != TradeResult.OPEN]

        if not closed_trades:
            return

        self.total_trades = len(closed_trades)
        self.winning_trades = len([t for t in closed_trades if t.result == TradeResult.WIN])
        self.losing_trades = len([t for t in closed_trades if t.result == TradeResult.LOSS])
        self.breakeven_trades = len([t for t in closed_trades if t.result == TradeResult.BREAKEVEN])

        # Win rate
        if self.total_trades > 0:
            self.win_rate = self.winning_trades / self.total_trades

        # P&L
        self.total_pnl_pips = sum(t.pnl_pips for t in closed_trades)
        self.total_pnl_r = sum(t.pnl_r for t in closed_trades)

        wins = [t for t in closed_trades if t.result == TradeResult.WIN]
        losses = [t for t in closed_trades if t.result == TradeResult.LOSS]

        if wins:
            self.average_win_pips = sum(t.pnl_pips for t in wins) / len(wins)
            self.average_win_r = sum(t.pnl_r for t in wins) / len(wins)

        if losses:
            self.average_loss_pips = sum(t.pnl_pips for t in losses) / len(losses)
            self.average_loss_r = sum(t.pnl_r for t in losses) / len(losses)

        # Profit factor
        gross_profit = sum(t.pnl_pips for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_pips for t in losses)) if losses else 1
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Expectancy
        if self.total_trades > 0:
            self.expectancy_r = self.total_pnl_r / self.total_trades

        # Equity curve and drawdown
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        self.equity_curve = [0.0]

        for trade in closed_trades:
            equity += trade.pnl_r
            self.equity_curve.append(equity)

            if equity > peak:
                peak = equity

            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        self.max_drawdown_r = max_dd

        # Max consecutive losses
        consecutive = 0
        max_consecutive = 0

        for trade in closed_trades:
            if trade.result == TradeResult.LOSS:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                consecutive = 0

        self.max_consecutive_losses = max_consecutive

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "win_rate": round(self.win_rate, 3),
            "total_pnl_pips": round(self.total_pnl_pips, 1),
            "total_pnl_r": round(self.total_pnl_r, 2),
            "average_win_pips": round(self.average_win_pips, 1),
            "average_loss_pips": round(self.average_loss_pips, 1),
            "average_win_r": round(self.average_win_r, 2),
            "average_loss_r": round(self.average_loss_r, 2),
            "profit_factor": round(self.profit_factor, 2),
            "expectancy_r": round(self.expectancy_r, 3),
            "max_drawdown_r": round(self.max_drawdown_r, 2),
            "max_consecutive_losses": self.max_consecutive_losses,
            "equity_curve": [round(e, 2) for e in self.equity_curve]
        }


@dataclass
class BacktestSession:
    """
    A complete backtesting session.
    """
    # Identity
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Configuration
    symbol: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    htf_timeframe: str = "1H"
    ltf_timeframe: str = "15M"

    # Data source
    data_source: Literal["mt5"] = "mt5"  # Only MT5 supported - no sample data fallback

    # State
    status: Literal["CREATED", "RUNNING", "PAUSED", "COMPLETED", "ERROR"] = "CREATED"
    current_index: int = 0
    total_candles: int = 0
    progress: float = 0.0

    # Decisions and trades
    decisions: List[BacktestDecision] = field(default_factory=list)
    trades: List[BacktestTrade] = field(default_factory=list)

    # Performance
    performance: BacktestPerformance = field(default_factory=BacktestPerformance)

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Stats
    total_agent_calls: int = 0
    skipped_calls: int = 0
    total_latency_ms: int = 0

    # Last state hash for selective analysis
    last_state_hash: str = ""

    def add_decision(self, decision: BacktestDecision):
        """Add a decision to the session."""
        self.decisions.append(decision)

        if not decision.skipped:
            self.total_agent_calls += 1
            self.total_latency_ms += decision.latency_ms
        else:
            self.skipped_calls += 1

    def add_trade(self, trade: BacktestTrade):
        """Add a trade to the session."""
        self.trades.append(trade)

    def update_progress(self, index: int):
        """Update current position and progress."""
        self.current_index = index
        if self.total_candles > 0:
            self.progress = index / self.total_candles

    def finalize(self):
        """Finalize the session and calculate performance."""
        self.status = "COMPLETED"
        self.completed_at = datetime.utcnow()
        self.performance.calculate(self.trades)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "htf_timeframe": self.htf_timeframe,
            "ltf_timeframe": self.ltf_timeframe,
            "data_source": self.data_source,
            "status": self.status,
            "current_index": self.current_index,
            "total_candles": self.total_candles,
            "progress": round(self.progress, 3),
            "decisions_count": len(self.decisions),
            "trades_count": len(self.trades),
            "performance": self.performance.to_dict(),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_agent_calls": self.total_agent_calls,
            "skipped_calls": self.skipped_calls,
            "average_latency_ms": (
                self.total_latency_ms // self.total_agent_calls
                if self.total_agent_calls > 0 else 0
            )
        }

    def to_full_dict(self) -> dict:
        """Full export including all decisions and trades."""
        d = self.to_dict()
        d["decisions"] = [dec.to_dict() for dec in self.decisions]
        d["trades"] = [t.to_dict() for t in self.trades]
        return d

    def save(self, path: str):
        """Save session to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_full_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "BacktestSession":
        """Load session from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)

        session = cls(
            session_id=data["session_id"],
            symbol=data["symbol"],
            htf_timeframe=data["htf_timeframe"],
            ltf_timeframe=data["ltf_timeframe"],
            status=data["status"],
            current_index=data["current_index"],
            total_candles=data["total_candles"],
            progress=data["progress"]
        )

        if data.get("start_date"):
            session.start_date = datetime.fromisoformat(data["start_date"])
        if data.get("end_date"):
            session.end_date = datetime.fromisoformat(data["end_date"])
        if data.get("created_at"):
            session.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            session.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            session.completed_at = datetime.fromisoformat(data["completed_at"])

        session.total_agent_calls = data.get("total_agent_calls", 0)
        session.skipped_calls = data.get("skipped_calls", 0)
        session.total_latency_ms = data.get("total_latency_ms", 0)

        # Load decisions
        for dec_data in data.get("decisions", []):
            dec = BacktestDecision(
                index=dec_data["index"],
                timestamp=datetime.fromisoformat(dec_data["timestamp"]),
                decision=dec_data["decision"],
                confidence=dec_data["confidence"],
                brief_reason=dec_data["brief_reason"],
                rule_citations=dec_data["rule_citations"],
                setup=dec_data.get("setup"),
                observation_hash=dec_data.get("observation_hash", ""),
                price_at_decision=dec_data.get("price_at_decision", 0),
                latency_ms=dec_data.get("latency_ms", 0),
                skipped=dec_data.get("skipped", False)
            )
            if dec_data.get("result"):
                dec.result = TradeResult(dec_data["result"])
            session.decisions.append(dec)

        # Load trades
        for trade_data in data.get("trades", []):
            trade = BacktestTrade(
                trade_id=trade_data["trade_id"],
                decision_index=trade_data["decision_index"],
                direction=trade_data["direction"],
                entry_price=trade_data["entry_price"],
                stop_loss=trade_data["stop_loss"],
                take_profit=trade_data["take_profit"],
                entry_index=trade_data["entry_index"],
                result=TradeResult(trade_data["result"]),
                pnl_pips=trade_data["pnl_pips"],
                pnl_r=trade_data["pnl_r"],
                risk_pips=trade_data["risk_pips"]
            )
            if trade_data.get("entry_time"):
                trade.entry_time = datetime.fromisoformat(trade_data["entry_time"])
            if trade_data.get("exit_time"):
                trade.exit_time = datetime.fromisoformat(trade_data["exit_time"])
            if trade_data.get("exit_price"):
                trade.exit_price = trade_data["exit_price"]
            if trade_data.get("exit_index"):
                trade.exit_index = trade_data["exit_index"]
            trade.exit_reason = trade_data.get("exit_reason", "")
            session.trades.append(trade)

        # Recalculate performance
        session.performance.calculate(session.trades)

        return session
