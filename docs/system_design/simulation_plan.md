# Simulation & Backtesting Plan

## Vision

A **"Glass Box" simulation** where the user can watch the system think.
Unlike traditional backtesters that just show equity curves, this system records the **Conversation Log** between agents to explain *why* a trade was taken or skipped.

**Key Differentiators:**
- Full visibility into agent reasoning at every tick
- Replayable decision trails for post-analysis
- Dynamic rule injection without code changes
- Real-time pause/step/resume controls

---

## 1. Simulation Architecture

### 1.1 The Virtual Clock

The **Main Agent** acts as the Timekeeper, controlling the flow of simulated time.

```python
class VirtualClock:
    """Controls time progression in backtesting mode."""

    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        base_timeframe: str = "5M"
    ):
        self.current = start_time
        self.end = end_time
        self.base_timeframe = base_timeframe
        self.tick_count = 0
        self.paused = False

        # Timeframe to minutes mapping
        self._tf_minutes = {
            "1M": 1, "5M": 5, "15M": 15, "30M": 30,
            "1H": 60, "4H": 240, "1D": 1440
        }

    def advance(self, bars: int = 1) -> datetime:
        """Move forward by N candles of base timeframe."""
        if self.paused:
            return self.current

        minutes = self._tf_minutes[self.base_timeframe] * bars
        self.current = min(
            self.current + timedelta(minutes=minutes),
            self.end
        )
        self.tick_count += bars
        return self.current

    def is_complete(self) -> bool:
        return self.current >= self.end

    def progress_percent(self) -> float:
        total = (self.end - self.start).total_seconds()
        elapsed = (self.current - self.start).total_seconds()
        return (elapsed / total) * 100 if total > 0 else 100
```

### 1.2 Simulation Loop

```
┌─────────────────────────────────────────────────────────────┐
│                    SIMULATION LOOP                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐ │
│  │  START  │───>│  TICK    │───>│ ANALYZE  │───>│ DECIDE │ │
│  └─────────┘    └────┬─────┘    └──────────┘    └───┬────┘ │
│                      │                              │       │
│                      │         ┌──────────┐        │       │
│                      │         │ EXECUTE  │<───────┘       │
│                      │         └────┬─────┘                │
│                      │              │                      │
│                      │         ┌────▼─────┐                │
│                      └─────────│  LOG     │                │
│                                └────┬─────┘                │
│                                     │                      │
│                      ┌──────────────┴──────────────┐       │
│                      │                             │       │
│                      ▼                             ▼       │
│               [Continue?]                    [Complete]    │
│                      │                             │       │
│                      └─────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Per-Tick Process:**
1. **TICK**: Clock advances by 1 candle, new data becomes "visible"
2. **ANALYZE**: Main requests snapshot → Worker delivers → Strategy analyzes context
3. **DECIDE**: Main evaluates environment + setup → Approve/Reject trade
4. **EXECUTE**: If approved, Worker places order
5. **LOG**: All messages and decisions recorded
6. **REPEAT**: Until clock reaches end time

### 1.3 Data Visibility Window

The simulation respects **temporal causality**—agents only see data up to `current_time`:

```python
class DataVisibilityManager:
    """Ensures agents cannot see future data."""

    def __init__(self, full_dataset: pd.DataFrame):
        self.full_data = full_dataset
        self.current_time = None

    def get_visible_data(
        self,
        current_time: datetime,
        lookback_bars: int = 200
    ) -> pd.DataFrame:
        """Return only data visible at this point in time."""
        self.current_time = current_time

        # Filter to only past data
        visible = self.full_data[self.full_data['time'] <= current_time]

        # Limit lookback to prevent memory issues
        return visible.tail(lookback_bars)

    def validate_no_future_leak(self, requested_time: datetime) -> bool:
        """Safety check to prevent lookahead bias."""
        return requested_time <= self.current_time
```

---

## 2. State Management

### 2.1 Simulation State Schema

```python
class SimulationState(BaseModel):
    """Complete state at any point in simulation."""

    # Identity
    simulation_id: str
    symbol: str
    start_time: datetime
    end_time: datetime

    # Clock
    current_time: datetime
    tick_number: int

    # Account
    initial_balance: float
    current_balance: float
    equity: float  # balance + unrealized P&L
    margin_used: float

    # Positions
    open_positions: List[Position]
    pending_orders: List[PendingOrder]

    # History
    closed_trades: List[ClosedTrade]

    # Metrics (Running)
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    win_count: int
    loss_count: int
    max_drawdown: float
    max_equity: float

    # Context Cache (from last analysis)
    last_context: Optional[MarketContext]
    last_setup: Optional[TradeSetup]

    # Configuration
    config: SimulationConfig
```

### 2.2 Checkpoint System

```python
class CheckpointManager:
    """Save/restore simulation state for replay and debugging."""

    def __init__(self, simulation_id: str, checkpoint_dir: Path):
        self.simulation_id = simulation_id
        self.checkpoint_dir = checkpoint_dir / simulation_id
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        state: SimulationState,
        checkpoint_name: Optional[str] = None
    ) -> Path:
        """Save state to disk."""
        name = checkpoint_name or f"tick_{state.tick_number}"
        path = self.checkpoint_dir / f"{name}.json"
        path.write_text(state.model_dump_json(indent=2))
        return path

    def load_checkpoint(self, checkpoint_name: str) -> SimulationState:
        """Restore state from disk."""
        path = self.checkpoint_dir / f"{checkpoint_name}.json"
        return SimulationState.model_validate_json(path.read_text())

    def list_checkpoints(self) -> List[str]:
        """List available checkpoints."""
        return [p.stem for p in self.checkpoint_dir.glob("*.json")]

    def auto_checkpoint_interval(self, state: SimulationState) -> bool:
        """Save checkpoint every N ticks or on trade events."""
        # Checkpoint every 100 ticks
        if state.tick_number % 100 == 0:
            return True
        # Checkpoint on trade execution
        if state.last_setup and state.last_setup.executed:
            return True
        return False
```

---

## 3. Traceability: The "Why" System

### 3.1 Thought Event Log

Every agent interaction produces a **ThoughtEvent**:

```python
class ThoughtEvent(BaseModel):
    """A single logged event in the simulation."""

    # Timing
    tick: int
    simulation_time: datetime
    wall_time: datetime = Field(default_factory=datetime.utcnow)

    # Source
    agent: Literal["Main", "Strategy", "Worker", "System"]

    # Event Type
    event_type: Literal[
        # Analysis Events
        "SNAPSHOT_REQUESTED",
        "SNAPSHOT_DELIVERED",
        "CONTEXT_REQUESTED",
        "CONTEXT_DELIVERED",
        "SETUP_SCAN_REQUESTED",
        "SETUP_FOUND",
        "NO_SETUP_FOUND",

        # Decision Events
        "TRADE_PROPOSED",
        "TRADE_APPROVED",
        "TRADE_REJECTED",
        "RISK_CHECK_PASSED",
        "RISK_CHECK_FAILED",

        # Execution Events
        "ORDER_SUBMITTED",
        "ORDER_FILLED",
        "ORDER_REJECTED",
        "POSITION_OPENED",
        "POSITION_CLOSED",
        "STOP_LOSS_HIT",
        "TAKE_PROFIT_HIT",

        # System Events
        "TICK_ADVANCED",
        "CHECKPOINT_SAVED",
        "ERROR_OCCURRED",
        "SIMULATION_COMPLETE"
    ]

    # Content
    summary: str  # Human-readable one-liner
    details: Dict[str, Any]  # Structured data
    rationale: Optional[str]  # Agent's reasoning (if applicable)

    # References
    related_events: List[str] = []  # IDs of related events
    snapshot_ref: Optional[str]  # Reference to data snapshot
```

### 3.2 Conversation Log Format

The full conversation log is a sequence of ThoughtEvents:

```json
{
  "simulation_id": "sim_eurusd_2024_001",
  "created_at": "2026-01-23T10:00:00Z",
  "config": {
    "symbol": "EURUSD",
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z",
    "initial_balance": 100000
  },
  "events": [
    {
      "tick": 1,
      "simulation_time": "2024-01-02T07:00:00Z",
      "agent": "System",
      "event_type": "TICK_ADVANCED",
      "summary": "Simulation started at NY Open",
      "details": {"candles_visible": 200}
    },
    {
      "tick": 1,
      "simulation_time": "2024-01-02T07:00:00Z",
      "agent": "Main",
      "event_type": "SNAPSHOT_REQUESTED",
      "summary": "Requesting market data",
      "details": {"timeframes": ["1H", "15M", "5M"]}
    },
    {
      "tick": 1,
      "simulation_time": "2024-01-02T07:00:00Z",
      "agent": "Worker",
      "event_type": "SNAPSHOT_DELIVERED",
      "summary": "Delivered 500 candles across 3 timeframes",
      "details": {"1H": 200, "15M": 200, "5M": 100},
      "snapshot_ref": "snap_tick1"
    },
    {
      "tick": 1,
      "simulation_time": "2024-01-02T07:00:00Z",
      "agent": "Strategy",
      "event_type": "CONTEXT_DELIVERED",
      "summary": "Bullish bias detected, NY Kill Zone active",
      "details": {
        "bias": "BULLISH",
        "confidence": 0.82,
        "environment": "GO",
        "session": "NEW_YORK",
        "pdh": 1.0850,
        "pdl": 1.0780
      },
      "rationale": "1H structure shows HH/HL. Price swept Asian low and now returning. PDL at 1.0780 provides clear invalidation."
    },
    {
      "tick": 1,
      "simulation_time": "2024-01-02T07:05:00Z",
      "agent": "Worker",
      "event_type": "SETUP_FOUND",
      "summary": "ICT 2022 Buy detected at 1.0815",
      "details": {
        "model": "ICT_2022",
        "entry": 1.0815,
        "stop_loss": 1.0775,
        "take_profit": 1.0895,
        "risk_reward": 2.0,
        "confidence": 0.85
      },
      "rationale": "SSL sweep at Asian low + displacement candle + return to FVG at 1.0815. Entry at FVG midpoint."
    },
    {
      "tick": 1,
      "simulation_time": "2024-01-02T07:05:00Z",
      "agent": "Main",
      "event_type": "TRADE_APPROVED",
      "summary": "All checks passed. Executing long at 1.0815",
      "details": {
        "checklist": {
          "bias_aligned": true,
          "environment_go": true,
          "rr_valid": true,
          "confidence_threshold": true,
          "position_limit_ok": true
        }
      },
      "rationale": "Setup aligns with bullish bias. R:R of 2.0 meets minimum. No conflicting positions. Proceeding."
    },
    {
      "tick": 1,
      "simulation_time": "2024-01-02T07:05:00Z",
      "agent": "Worker",
      "event_type": "POSITION_OPENED",
      "summary": "Long position opened at 1.0815",
      "details": {
        "position_id": "pos_001",
        "entry_price": 1.0815,
        "size": 1.5,
        "stop_loss": 1.0775,
        "take_profit": 1.0895,
        "risk_amount": 600
      }
    }
  ]
}
```

### 3.3 UI Visualization Spec

The Frontend can render this log as an interactive timeline:

```
┌──────────────────────────────────────────────────────────────────┐
│  SIMULATION REPLAY: EURUSD Jan 2024                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [▶ Play] [⏸ Pause] [⏭ Step] [Speed: 1x ▼]  Progress: ████░ 75% │
│                                                                  │
│  ┌────────────────────────────────┬─────────────────────────────┐│
│  │         CHART                  │     AGENT CONVERSATION      ││
│  │                                │                             ││
│  │    [Candlestick Chart]        │  🤖 Main: "Requesting data" ││
│  │                                │  🛠️ Worker: "500 candles"   ││
│  │    ▲ Entry @ 1.0815           │  🧠 Strategy: "BULLISH bias" ││
│  │    │                          │    └─ "HH/HL on 1H..."      ││
│  │    │                          │  🛠️ Worker: "ICT 2022 found" ││
│  │    ◄─── Asian Low Sweep       │    └─ Entry: 1.0815         ││
│  │                                │  🤖 Main: "Approved ✓"      ││
│  │                                │  🛠️ Worker: "Position open" ││
│  │                                │                             ││
│  └────────────────────────────────┴─────────────────────────────┘│
│                                                                  │
│  Click any candle to see the conversation at that moment         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Dynamic Rulebook (The "How")

### 4.1 Rule Configuration File

Users can modify strategy rules without code changes:

```yaml
# rules/active_rules.yaml

meta:
  version: "1.0"
  description: "ICT 2022 Model - NY Session Only"
  last_modified: "2026-01-23"

# Bias Configuration
bias:
  timeframe: "1H"
  method: "structure"  # structure | displacement | combined
  neutral_threshold: 0.4  # Below this confidence = NEUTRAL

# Environment Rules
environment:
  killzones:
    enabled: true
    allowed: ["NEW_YORK"]  # ASIA, LONDON, NEW_YORK
    # Remove "LONDON" to test NY-only strategy

  news_filter:
    enabled: true
    buffer_minutes: 60
    impact_levels: ["HIGH"]  # HIGH, MEDIUM, LOW

  silverbullet:
    enabled: true
    windows:
      - start: "10:00"
        end: "11:00"
        timezone: "America/New_York"
      - start: "14:00"
        end: "15:00"
        timezone: "America/New_York"

# Entry Models
entry_models:
  ict_2022:
    enabled: true
    priority: 1
    require_displacement: true
    fvg_entry: "midpoint"  # top | midpoint | bottom

  ote:
    enabled: true
    priority: 2
    fib_range: [0.62, 0.79]

  fvg_only:
    enabled: false
    priority: 3

# Risk Management
risk:
  min_rr: 2.0
  max_rr: 5.0  # Reject if RR seems too good (likely error)
  risk_per_trade: 0.01  # 1% of balance
  max_daily_loss: 0.03  # 3% of balance
  max_open_positions: 3

# Session Levels
levels:
  track_pdh_pdl: true
  track_asian_range: true
  track_london_range: true
  track_midnight_open: true
```

### 4.2 Rule Injection Mechanism

```python
class RuleEngine:
    """Loads and applies dynamic rules at runtime."""

    def __init__(self, rules_path: Path):
        self.rules_path = rules_path
        self.rules = self._load_rules()
        self._last_modified = rules_path.stat().st_mtime

    def _load_rules(self) -> Dict[str, Any]:
        """Load rules from YAML file."""
        with open(self.rules_path) as f:
            return yaml.safe_load(f)

    def check_for_updates(self) -> bool:
        """Hot-reload rules if file changed."""
        current_mtime = self.rules_path.stat().st_mtime
        if current_mtime > self._last_modified:
            self.rules = self._load_rules()
            self._last_modified = current_mtime
            return True
        return False

    def get_strategy_context(self) -> str:
        """Generate context string for Strategy Agent prompt."""
        rules = self.rules

        context = f"""
## Active Trading Rules

### Bias
- Timeframe: {rules['bias']['timeframe']}
- Method: {rules['bias']['method']}

### Environment
- Kill Zones: {', '.join(rules['environment']['killzones']['allowed'])}
- News Buffer: {rules['environment']['news_filter']['buffer_minutes']} minutes
- Silverbullet: {'Enabled' if rules['environment']['silverbullet']['enabled'] else 'Disabled'}

### Entry Models (by priority)
{self._format_entry_models(rules['entry_models'])}

### Risk Parameters
- Minimum R:R: {rules['risk']['min_rr']}
- Risk per Trade: {rules['risk']['risk_per_trade'] * 100}%
- Max Daily Loss: {rules['risk']['max_daily_loss'] * 100}%
"""
        return context

    def _format_entry_models(self, models: Dict) -> str:
        """Format enabled entry models as list."""
        enabled = [
            (name, cfg['priority'])
            for name, cfg in models.items()
            if cfg['enabled']
        ]
        enabled.sort(key=lambda x: x[1])
        return '\n'.join(f"  {i+1}. {name}" for i, (name, _) in enumerate(enabled))
```

---

## 5. Performance Metrics

### 5.1 Running Metrics (Calculated Each Tick)

```python
class SimulationMetrics(BaseModel):
    """Performance metrics updated during simulation."""

    # Basic Stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0

    # P&L
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0

    # Ratios
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_rr_achieved: float = 0.0

    # Risk Metrics
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    max_consecutive_losses: int = 0
    current_consecutive_losses: int = 0

    # Equity Curve
    peak_equity: float = 0.0
    current_equity: float = 0.0

    # Time-based
    avg_trade_duration: timedelta = timedelta()
    longest_trade: timedelta = timedelta()

    def update_on_trade_close(self, trade: ClosedTrade, equity: float):
        """Update metrics when a trade closes."""
        self.total_trades += 1

        if trade.pnl > 0:
            self.winning_trades += 1
            self.gross_profit += trade.pnl
            self.current_consecutive_losses = 0
        elif trade.pnl < 0:
            self.losing_trades += 1
            self.gross_loss += abs(trade.pnl)
            self.current_consecutive_losses += 1
            self.max_consecutive_losses = max(
                self.max_consecutive_losses,
                self.current_consecutive_losses
            )
        else:
            self.breakeven_trades += 1

        self.net_profit = self.gross_profit - self.gross_loss
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        self.profit_factor = self.gross_profit / self.gross_loss if self.gross_loss > 0 else float('inf')

        # Drawdown
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity
        drawdown = self.peak_equity - equity
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
            self.max_drawdown_percent = (drawdown / self.peak_equity) * 100
```

### 5.2 Final Report Schema

```json
{
  "simulation_id": "sim_eurusd_2024_001",
  "completed_at": "2026-01-23T15:30:00Z",
  "duration_seconds": 45.2,

  "configuration": {
    "symbol": "EURUSD",
    "period": "2024-01-01 to 2024-01-31",
    "initial_balance": 100000,
    "rules_version": "1.0"
  },

  "summary": {
    "final_balance": 102450.00,
    "net_profit": 2450.00,
    "net_profit_percent": 2.45,
    "total_trades": 15,
    "win_rate": 0.60,
    "profit_factor": 1.85,
    "max_drawdown": 1200.00,
    "max_drawdown_percent": 1.18
  },

  "trades": [
    {
      "id": "trade_001",
      "entry_time": "2024-01-02T07:05:00Z",
      "exit_time": "2024-01-02T09:45:00Z",
      "direction": "LONG",
      "entry_price": 1.0815,
      "exit_price": 1.0895,
      "size": 1.5,
      "pnl": 1200.00,
      "rr_achieved": 2.0,
      "model": "ICT_2022",
      "exit_reason": "TAKE_PROFIT"
    }
  ],

  "by_model": {
    "ICT_2022": {"trades": 8, "win_rate": 0.625, "net_pnl": 1800},
    "OTE": {"trades": 5, "win_rate": 0.60, "net_pnl": 500},
    "SILVERBULLET": {"trades": 2, "win_rate": 0.50, "net_pnl": 150}
  },

  "by_session": {
    "NEW_YORK": {"trades": 15, "win_rate": 0.60, "net_pnl": 2450}
  },

  "log_file": "logs/sim_eurusd_2024_001.json"
}
```

---

## 6. Implementation Roadmap

### Phase 1: Core Loop (Week 1-2)
- [ ] Implement `VirtualClock` class
- [ ] Build `DataVisibilityManager` with lookahead protection
- [ ] Create basic simulation loop in Main Agent
- [ ] Implement `ThoughtEvent` logging

### Phase 2: State Management (Week 2-3)
- [ ] Define complete `SimulationState` model
- [ ] Build `CheckpointManager` for save/restore
- [ ] Add position tracking and P&L calculation
- [ ] Implement running metrics calculation

### Phase 3: Traceability (Week 3-4)
- [ ] Complete JSON log format specification
- [ ] Add rationale capture to all agent responses
- [ ] Build log export functionality
- [ ] Create CLI replay tool

### Phase 4: Rule Engine (Week 4-5)
- [ ] Design YAML rule schema
- [ ] Implement `RuleEngine` with hot-reload
- [ ] Add rule validation
- [ ] Test dynamic rule changes during simulation

### Phase 5: Frontend Integration (Week 5-6)
- [ ] Build replay API endpoints
- [ ] Create conversation timeline component
- [ ] Sync chart with conversation log
- [ ] Add candle-click to show reasoning

---

## 7. Testing Strategy

### Unit Tests
```python
def test_virtual_clock_advances_correctly():
    clock = VirtualClock(
        start_time=datetime(2024, 1, 1, 0, 0),
        end_time=datetime(2024, 1, 1, 1, 0),
        base_timeframe="5M"
    )
    clock.advance(1)
    assert clock.current == datetime(2024, 1, 1, 0, 5)
    assert clock.tick_count == 1

def test_data_visibility_prevents_future_leak():
    manager = DataVisibilityManager(full_dataset)
    visible = manager.get_visible_data(datetime(2024, 1, 1, 10, 0))

    # Should not contain any data after 10:00
    assert visible['time'].max() <= datetime(2024, 1, 1, 10, 0)

def test_checkpoint_save_restore():
    manager = CheckpointManager("test_sim", Path("/tmp"))
    state = SimulationState(...)

    manager.save_checkpoint(state, "test_checkpoint")
    restored = manager.load_checkpoint("test_checkpoint")

    assert restored == state
```

### Integration Tests
- Full simulation run with known historical data
- Verify trade entries match expected patterns
- Validate final metrics against manual calculation
- Test pause/resume maintains state correctly

### Regression Tests
- Compare new simulation results against baseline
- Alert on significant metric deviations
- Track rule changes that affect performance
