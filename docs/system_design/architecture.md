# Agentic Trading System Architecture

## 1. High-Level Overview

The system adopts a **Hierarchical Supervisor Architecture** to ensure clear separation of concerns, traceability, and robust decision-making.

**Core Hierarchy:**
1.  **Trader (User)**: Sets high-level goals and constraints (e.g., "Run backtest on EURUSD for 2024 with 2.5 RR").
2.  **Main Agent (Orchestrator)**: The central brain. Receives goals, maintains state, delegates tasks, and synthesizes results. It does *not* do heavy analysis or execution itself.
3.  **Strategy Agent (Analyst)**: Pure reasoning engine. Analyzes market context (News, Timezone, Killzones, Session levels) and returns structured analysis. Does NOT execute.
4.  **Worker Agent (Executor)**: The interface to the world. Fetches candle data, computes PD arrays, executes trades. Has no strategic opinion.

```
                         ┌─────────────┐
                         │   Trader    │
                         │   (User)    │
                         └──────┬──────┘
                                │ Goals & Constraints
                                ▼
                    ┌───────────────────────┐
                    │      Main Agent       │
                    │    (Orchestrator)     │
                    │  • State Management   │
                    │  • Delegation Logic   │
                    │  • Risk Policy        │
                    │  • Final Approval     │
                    └───────┬───────┬───────┘
                            │       │
           ┌────────────────┘       └────────────────┐
           │ Analysis Request                        │ Execution Request
           ▼                                         ▼
┌──────────────────────┐                ┌──────────────────────┐
│   Strategy Agent     │                │    Worker Agent      │
│     (Analyst)        │                │    (Executor)        │
├──────────────────────┤                ├──────────────────────┤
│ • News Analysis      │                │ • Candle Data Fetch  │
│ • Timezone/Sessions  │                │ • PD Array Compute   │
│ • Killzone H/L       │                │ • Strategy Patterns  │
│ • Silverbullet       │                │ • Order Execution    │
│ • PDH/PDL Levels     │                │ • Position Mgmt      │
│ • Swing H/L (M/L/NY) │                │ • File I/O           │
│ • Fundamentals       │                │                      │
└──────────────────────┘                └──────────────────────┘
```

---

## 2. Agent Responsibilities (Detailed)

### 🤖 Main Agent (The Orchestrator)
**Goal:** Manage the lifecycle of a trading session.

| Responsibility | Description |
|:---------------|:------------|
| **State Management** | Tracks session state: `IDLE → ANALYZING → DECIDING → EXECUTING → MONITORING` |
| **Clock Control** | In simulation, advances time candle-by-candle |
| **Delegation Router** | Decides which agent to invoke based on current phase |
| **Risk Policy** | Enforces account-level rules (max drawdown, position limits, R:R thresholds) |
| **Signal Synthesis** | Combines Strategy analysis with Worker data to form trade decisions |
| **Final Approval** | Last checkpoint before any trade execution |
| **Logging** | Records all inter-agent messages for replay |

**Decision Tree:**
```
IF state == IDLE:
    → Parse Trader goal → Transition to ANALYZING

IF state == ANALYZING:
    → Request snapshot from Worker
    → Send snapshot to Strategy for context analysis
    → Receive MarketContext (Bias, Environment, Levels)
    → If environment == "GO": Transition to DECIDING
    → Else: Log reason, wait for next tick

IF state == DECIDING:
    → Request setup scan from Worker (using Strategy context)
    → Evaluate signal confidence, R:R, checklist
    → If passes: Transition to EXECUTING
    → Else: Log reason, return to ANALYZING

IF state == EXECUTING:
    → Command Worker to place order
    → Receive ExecutionReceipt
    → Transition to MONITORING (or back to ANALYZING)
```

---

### 🧠 Strategy Agent (The Analyst)
**Goal:** Provide market context and environment assessment. Does NOT find patterns—that's Worker's job.

| Responsibility | ICT Rules | Output |
|:---------------|:----------|:-------|
| **News Analysis** | 8.4 | `NewsStatus`: CLEAR / BLOCKED (with event details) |
| **Timezone Management** | 8.1 | `CurrentSession`: ASIA / LONDON / NEW_YORK / OFF_HOURS |
| **Killzone High/Low** | 8.1+ | Price levels formed during active killzones |
| **Silverbullet Windows** | 6.6 | `SilverbulletStatus`: ACTIVE / INACTIVE (10-11 AM, 2-3 PM EST) |
| **PDH/PDL Levels** | 3.1 | Previous Day High/Low price levels |
| **Swing Highs/Lows** | 2.1 | Midnight Open, London H/L, NY H/L, Asian H/L |
| **Fundamentals** | 9.x | COT positioning, DXY correlation (future) |
| **HTF Bias** | 1.1 | `Bias`: BULLISH / BEARISH / NEUTRAL with confidence |

**Output Schema:**
```json
{
  "bias": {
    "direction": "BULLISH",
    "confidence": 0.85,
    "rationale": "1H showing HH/HL structure with displacement"
  },
  "environment": {
    "status": "GO",
    "session": "NEW_YORK",
    "killzone_active": true,
    "news_clear": true,
    "silverbullet_active": true,
    "blocked_reasons": []
  },
  "levels": {
    "pdh": 1.0850,
    "pdl": 1.0780,
    "midnight_open": 1.0815,
    "asian_high": 1.0835,
    "asian_low": 1.0795,
    "london_high": 1.0848,
    "london_low": 1.0790,
    "killzone_high": 1.0845,
    "killzone_low": 1.0802
  }
}
```

---

### 🛠️ Worker Agent (The Executor)
**Goal:** Fetch data, compute patterns, and execute trades. Zero strategic opinion.

| Responsibility | Description |
|:---------------|:------------|
| **Candle Data Fetch** | Retrieve OHLCV for requested timeframes (1H, 15M, 5M, 1M) |
| **PD Array Computation** | Calculate FVGs, OBs, Breakers, Premium/Discount zones |
| **Pattern Scanning** | Detect: Liquidity Sweeps, MSS, Displacement, OTE levels |
| **Strategy Execution** | Apply specific models: ICT 2022, Silverbullet, OTE Entry |
| **Order Execution** | Place/Modify/Cancel orders via broker API |
| **Position Management** | Track open positions, manage SL/TP adjustments |
| **File I/O** | Read/write simulation state, logs, trade journals |

**Key Tools:**
```python
# Data Tools
get_candles(symbol, timeframe, start, end) -> List[Candle]
get_news_calendar(date_range) -> List[NewsEvent]

# Analysis Tools (Computational, not Strategic)
find_swing_points(candles, lookback) -> List[SwingPoint]
find_fvg(candles) -> List[FVG]
find_liquidity_sweep(candles, swings) -> List[Sweep]
calculate_pd_zone(candles) -> PDZone
calculate_ote_zone(swing_high, swing_low) -> OTEZone
detect_mss(candles, swings) -> Optional[MSS]
detect_displacement(candles) -> Optional[Displacement]

# Execution Tools
execute_order(symbol, side, qty, type, sl, tp) -> ExecutionReceipt
modify_position(position_id, sl, tp) -> ModifyReceipt
close_position(position_id) -> CloseReceipt
get_open_positions() -> List[Position]

# Simulation Tools
advance_time(bars) -> NewTimestamp
save_state(state) -> Confirmation
load_state(checkpoint) -> State
```

---

## 3. Communication Protocol

### Message Envelope
All inter-agent communication uses a standardized envelope:
```json
{
  "id": "msg_001",
  "timestamp": "2024-01-15T10:00:00Z",
  "from": "Main",
  "to": "Strategy",
  "action": "ANALYZE_CONTEXT",
  "payload": { },
  "correlation_id": "session_abc123"
}
```

### Action Types by Agent

| From → To | Action | Purpose |
|:----------|:-------|:--------|
| Main → Worker | `GET_SNAPSHOT` | Request OHLCV + News data |
| Main → Worker | `SCAN_SETUPS` | Find patterns given Strategy context |
| Main → Worker | `EXECUTE_ORDER` | Place a trade |
| Main → Worker | `ADVANCE_TIME` | Move simulation forward |
| Main → Strategy | `ANALYZE_CONTEXT` | Get bias, environment, levels |
| Strategy → Main | `CONTEXT_RESULT` | Return MarketContext |
| Worker → Main | `SNAPSHOT_RESULT` | Return market data |
| Worker → Main | `SETUP_RESULT` | Return detected patterns |
| Worker → Main | `EXECUTION_RECEIPT` | Confirm trade placed |

### Interaction Flow (Complete Cycle)

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌────────┐
│ Trader  │     │  Main   │     │ Strategy │     │ Worker │
└────┬────┘     └────┬────┘     └────┬─────┘     └────┬───┘
     │               │               │                │
     │ "Backtest     │               │                │
     │  EURUSD"      │               │                │
     │──────────────>│               │                │
     │               │               │                │
     │               │ GET_SNAPSHOT  │                │
     │               │───────────────────────────────>│
     │               │               │                │
     │               │               │  OHLCV + News  │
     │               │<───────────────────────────────│
     │               │               │                │
     │               │ ANALYZE_CONTEXT               │
     │               │──────────────>│                │
     │               │               │                │
     │               │ CONTEXT_RESULT│                │
     │               │<──────────────│                │
     │               │               │                │
     │               │ SCAN_SETUPS (with context)    │
     │               │───────────────────────────────>│
     │               │               │                │
     │               │               │  SETUP_RESULT  │
     │               │<───────────────────────────────│
     │               │               │                │
     │               │ [Main evaluates risk/RR]      │
     │               │               │                │
     │               │ EXECUTE_ORDER │                │
     │               │───────────────────────────────>│
     │               │               │                │
     │               │               │ EXEC_RECEIPT   │
     │               │<───────────────────────────────│
     │               │               │                │
     │ Trade Result  │               │                │
     │<──────────────│               │                │
```

---

## 4. Rulebook Integration (ICT Rules Mapping)

The **Strategy Agent** owns context/environment rules. The **Worker Agent** owns pattern/execution rules.

| ICT Rule | Category | Responsible Agent | Implementation |
|:---------|:---------|:------------------|:---------------|
| 1.1 HTF Bias | Market Structure | Strategy | `analyze_bias()` |
| 1.1.1 Neutral Bias | Market Structure | Strategy | Identify range-bound conditions |
| 2.1 Swing Points | Structure | Worker | `find_swing_points()` |
| 2.2 Displacement | Structure | Worker | `detect_displacement()` |
| 2.3 MSS | Structure | Worker | `detect_mss()` |
| 3.1 PDH/PDL | Liquidity Levels | Strategy | Session level tracking |
| 3.4 Liquidity Sweep | Liquidity | Worker | `find_liquidity_sweep()` |
| 5.1 Premium/Discount | PD Arrays | Worker | `calculate_pd_zone()` |
| 5.2 FVG | PD Arrays | Worker | `find_fvg()` |
| 6.1 OTE | Entry Models | Worker | `calculate_ote_zone()` |
| 6.5 ICT 2022 | Entry Models | Worker | `scan_ict_2022_model()` |
| 6.6 Silverbullet | Entry Models | Strategy + Worker | Time window (S) + Pattern (W) |
| 7.1 Position Sizing | Risk | Main | Policy enforcement |
| 7.2 R:R Validation | Risk | Main | Minimum 2:1 threshold |
| 8.1 Kill Zones | Time | Strategy | `check_killzone()` |
| 8.4 News Filter | Time | Strategy | `check_news_clearance()` |

---

## 5. State Model

### Session State (Managed by Main)
```python
class SessionState(BaseModel):
    # Identity
    session_id: str
    symbol: str
    mode: Literal["LIVE", "BACKTEST"]

    # Clock
    current_time: datetime
    simulation_speed: float = 1.0  # Candles per second in replay

    # Phase
    phase: Literal["IDLE", "ANALYZING", "DECIDING", "EXECUTING", "MONITORING"]

    # Context (from Strategy)
    market_context: Optional[MarketContext]

    # Detected Setup (from Worker)
    current_setup: Optional[TradeSetup]

    # Positions
    open_positions: List[Position]
    closed_trades: List[ClosedTrade]

    # Metrics
    balance: float
    equity: float
    total_pnl: float
    win_count: int
    loss_count: int

    # Audit Trail
    message_log: List[AgentMessage]
```

### Market Context (Produced by Strategy)
```python
class MarketContext(BaseModel):
    # Bias Assessment
    bias: BiasAssessment

    # Environment Check
    environment: EnvironmentStatus

    # Key Levels
    levels: SessionLevels

    # Timestamp
    analyzed_at: datetime
    valid_until: datetime  # Context expires after N candles
```

### Trade Setup (Produced by Worker)
```python
class TradeSetup(BaseModel):
    # Model Identification
    model_name: str  # "ICT_2022", "OTE", "SILVERBULLET", "FVG_ENTRY"

    # Entry Details
    entry_price: float
    entry_type: Literal["LIMIT", "MARKET"]
    direction: Literal["LONG", "SHORT"]

    # Risk Management
    stop_loss: float
    take_profit: float
    risk_reward: float

    # Validation
    confidence: float  # 0.0 - 1.0
    confluence_factors: List[str]
    rationale: str

    # Timing
    detected_at: datetime
    valid_until: datetime
```

---

## 6. Backtesting & Simulation

### Virtual Clock System
```python
class VirtualClock:
    def __init__(self, start_time: datetime, end_time: datetime):
        self.current = start_time
        self.end = end_time
        self.timeframe = "5M"  # Base tick interval

    def advance(self, bars: int = 1) -> datetime:
        """Move forward by N candles"""
        delta = timedelta(minutes=5 * bars)
        self.current = min(self.current + delta, self.end)
        return self.current

    def is_complete(self) -> bool:
        return self.current >= self.end
```

### Conversation Replay
Every interaction is logged for "Glass Box" visualization:
```json
{
  "tick": 42,
  "time": "2024-01-15T10:15:00Z",
  "events": [
    {"agent": "Worker", "action": "SNAPSHOT_DELIVERED", "data_points": 500},
    {"agent": "Strategy", "action": "CONTEXT_ANALYZED", "bias": "BULLISH", "env": "GO"},
    {"agent": "Worker", "action": "SETUP_FOUND", "model": "ICT_2022", "conf": 0.87},
    {"agent": "Main", "action": "TRADE_APPROVED", "reason": "All checks passed"},
    {"agent": "Worker", "action": "ORDER_EXECUTED", "entry": 1.0520, "sl": 1.0500}
  ]
}
```

### Rule Injection (Dynamic Strategy)
Strategy Agent reads rules from `rules.md` at runtime:
```markdown
# Active Rules (Editable at Runtime)
- bias_timeframe: 1H
- entry_timeframe: 5M
- killzones: [LONDON, NEW_YORK]
- min_rr: 2.0
- news_buffer_minutes: 60
- silverbullet_enabled: true
```

---

## 7. Error Handling & Recovery

| Error Type | Handler | Recovery Action |
|:-----------|:--------|:----------------|
| Data fetch timeout | Worker → Main | Retry 3x, then skip tick |
| Invalid order params | Worker → Main | Reject with error details |
| Strategy analysis error | Strategy → Main | Return NEUTRAL bias, WAIT status |
| Broker rejection | Worker → Main | Log exact error, notify Trader |
| State corruption | Main | Rollback to last checkpoint |

---

## 8. Future Extensions

| Extension | Description | Impact |
|:----------|:------------|:-------|
| **Multi-Symbol Scanner** | Worker scans multiple pairs in parallel | New "Scanner" sub-agent |
| **Sentiment Agent** | COT data, retail positioning | Feeds into Strategy context |
| **Journal Agent** | Auto-generate trade journals | Post-execution documentation |
| **ML Confidence Booster** | Historical pattern recognition | Enhances setup confidence scores |
| **Risk Aggregator** | Portfolio-level exposure management | Cross-symbol correlation checks |
