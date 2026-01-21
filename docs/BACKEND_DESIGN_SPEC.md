# Backend Design Specification
## ICT Agentic Trading Platform — FastAPI Backend

> **Scope**: This document defines the backend architecture for hosting the ICT Trading Agent as a black-box core engine, exposing it via REST/WebSocket APIs for frontend consumption.

---

## 1. Project Structure Options

### Option A: Layered Monolith (Recommended for MVP)

```
backend/
├── app/
│   ├── api/                    # HTTP & WebSocket endpoints
│   │   ├── v1/
│   │   │   ├── analysis.py     # Trade analysis endpoints
│   │   │   ├── config.py       # Configuration endpoints
│   │   │   ├── audit.py        # Decision logs & history
│   │   │   ├── execution.py    # Execution control (future)
│   │   │   └── websocket.py    # Real-time updates
│   │   └── deps.py             # Dependency injection
│   │
│   ├── core/                   # Application core
│   │   ├── config.py           # Environment & settings
│   │   ├── security.py         # Auth & rate limiting
│   │   └── exceptions.py       # Custom exceptions
│   │
│   ├── agent/                  # Agent orchestration layer
│   │   ├── engine.py           # LangGraph agent wrapper
│   │   ├── lifecycle.py        # Agent state management
│   │   └── adapters/           # Input/output adapters
│   │
│   ├── domain/                 # Domain models (Pydantic)
│   │   ├── requests.py         # API request schemas
│   │   ├── responses.py        # API response schemas
│   │   └── enums.py            # Shared enumerations
│   │
│   ├── persistence/            # Data layer (optional)
│   │   ├── repositories/       # Database abstractions
│   │   └── models/             # ORM models
│   │
│   └── execution/              # Execution adapters (future)
│       ├── brokers/            # Broker-specific adapters
│       └── simulation.py       # Paper trading engine
│
├── tests/
├── main.py
└── pyproject.toml
```

### Option B: Modular Microservices (For Scale)

| Service | Responsibility |
|---------|---------------|
| `api-gateway` | Request routing, auth, rate limiting |
| `agent-service` | Core agent orchestration |
| `audit-service` | Decision logging, compliance |
| `execution-service` | Broker integration, order management |
| `config-service` | Dynamic configuration management |

### Option C: Serverless Functions (For Cost Optimization)

- Each endpoint as independent AWS Lambda / GCP Cloud Function
- Queue-based agent invocation for async workloads
- Best for low-frequency, burst trading scenarios

> **Recommendation**: Start with **Option A** for MVP, extract services incrementally as complexity grows.

---

## 2. API Design — Complete Endpoint Catalog

### 2.1 Core Analysis Endpoints

#### `POST /api/v1/analyze`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Run single trade analysis on market snapshot |
| **Input** | `MarketSnapshot` (symbol, timestamp, OHLCV bars, account balance, risk %) |
| **Output** | `TradeSetupResponse` (status, setup, checklist, explanation) |
| **Sync/Async** | Sync (< 500ms expected) |
| **Required** | Yes — primary endpoint |

#### `POST /api/v1/analyze/batch`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Analyze multiple snapshots in one request |
| **Input** | Array of `MarketSnapshot` |
| **Output** | Array of `TradeSetupResponse` |
| **Sync/Async** | Async with polling or webhook callback |
| **Required** | Optional — for scanner mode |

#### `POST /api/v1/analyze/stream` (WebSocket)
| Attribute | Value |
|-----------|-------|
| **Purpose** | Continuous analysis on live price feed |
| **Input** | WebSocket connection with streaming OHLCV |
| **Output** | Real-time `TradeSetupResponse` events |
| **Sync/Async** | Streaming |
| **Required** | Optional — for live monitoring |

---

### 2.2 Rule Introspection Endpoints

#### `GET /api/v1/rules`
| Attribute | Value |
|-----------|-------|
| **Purpose** | List all rules in the ICT Rulebook |
| **Input** | None (or filter by category) |
| **Output** | Array of `RuleDefinition` (id, name, description, category) |
| **Required** | Optional — for transparency |

#### `POST /api/v1/explain`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Explain why a trade was/was not taken |
| **Input** | `TradeSetupResponse` or analysis ID |
| **Output** | `ExplanationTree` (rule-by-rule pass/fail with reasons) |
| **Required** | Recommended — builds trust |

#### `GET /api/v1/rules/{rule_id}/examples`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Show historical examples of rule triggering |
| **Input** | Rule ID |
| **Output** | Array of annotated trade examples |
| **Required** | Optional — for learning mode |

---

### 2.3 Session & Time Endpoints

#### `GET /api/v1/session/current`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Get current session info (London/NY/Asia) |
| **Input** | Optional timezone override |
| **Output** | `SessionInfo` (name, kill_zone_active, time_remaining) |
| **Required** | Yes — for dashboard display |

#### `GET /api/v1/killzone/status`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Check if currently inside a Kill Zone |
| **Input** | Symbol (optional for pair-specific zones) |
| **Output** | `KillZoneStatus` (active, session, next_zone_start) |
| **Required** | Yes — for gating decisions |

#### `GET /api/v1/calendar`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Fetch upcoming economic events |
| **Input** | Timeframe (next N hours), currencies filter |
| **Output** | Array of `EconomicEvent` |
| **Required** | Yes — for news rule |

---

### 2.4 Risk & Account Configuration

#### `GET /api/v1/config/risk`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Get current risk configuration |
| **Output** | `RiskConfig` (risk_pct, max_trades, rr_minimum, etc.) |

#### `PUT /api/v1/config/risk`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Update risk configuration |
| **Input** | Partial `RiskConfig` update |
| **Output** | Updated `RiskConfig` |

#### `GET /api/v1/account`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Get account balance and equity |
| **Output** | `AccountInfo` (balance, equity, margin, open_positions) |

#### `PUT /api/v1/account`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Update account configuration (for simulation) |
| **Input** | `AccountConfig` |

---

### 2.5 Execution Control Endpoints

#### `POST /api/v1/execute`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Execute a trade setup (future) |
| **Input** | `TradeSetupResponse` + execution token |
| **Output** | `ExecutionResult` (order_id, status, fill_price) |
| **Required** | Future — requires explicit enable |

#### `POST /api/v1/execute/simulate`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Simulate execution without real orders |
| **Input** | `TradeSetupResponse` |
| **Output** | `SimulationResult` (hypothetical fill, slippage estimate) |
| **Required** | Recommended — for paper trading |

#### `POST /api/v1/execute/cancel`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Cancel pending order |
| **Input** | Order ID |
| **Output** | Cancellation confirmation |

#### `GET /api/v1/mode`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Get current operation mode |
| **Output** | `ANALYSIS_ONLY` / `SIMULATION` / `EXECUTION` |

#### `PUT /api/v1/mode`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Switch operation mode |
| **Input** | Target mode + confirmation token |
| **Output** | Mode change confirmation |

---

### 2.6 Audit & Decision Logging

#### `GET /api/v1/audit/decisions`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Retrieve decision log history |
| **Input** | Filters (date range, symbol, status) |
| **Output** | Paginated array of `DecisionLog` |

#### `GET /api/v1/audit/decisions/{id}`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Get full details of a specific decision |
| **Output** | Complete `DecisionLog` with all rule traces |

#### `GET /api/v1/audit/metrics`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Get aggregated performance metrics |
| **Input** | Date range, grouping |
| **Output** | `PerformanceMetrics` (win rate, avg RR, rule hit rates) |

---

### 2.7 Agent State & Health

#### `GET /api/v1/agent/health`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Check agent availability |
| **Output** | Health status, last analysis time, error count |

#### `GET /api/v1/agent/state`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Inspect current agent state |
| **Output** | Current bias, active setups, pending decisions |

#### `POST /api/v1/agent/reset`
| Attribute | Value |
|-----------|-------|
| **Purpose** | Reset agent state (clear session data) |
| **Input** | Confirmation token |
| **Output** | Reset confirmation |

---

## 3. Configuration & Governance Options

### 3.1 Risk Profile Options

| Option | Description | Use Case |
|--------|-------------|----------|
| **Fixed Percentage** | Risk X% per trade (default 1%) | Standard ICT approach |
| **Dynamic Kelly** | Adjust based on win rate / edge | Advanced traders |
| **Tiered by Confidence** | Higher confidence → higher risk | Scaling with conviction |
| **Per-Session Cap** | Max risk per session regardless of trades | Drawdown protection |
| **Equity Curve Scaling** | Reduce risk during drawdowns | Capital preservation |

### 3.2 Trade Frequency Controls

| Setting | Options |
|---------|---------|
| `max_trades_per_session` | 1, 2, 3, unlimited |
| `max_trades_per_day` | 1-10, unlimited |
| `cooldown_after_loss` | 0, 15min, 30min, 1h, session |
| `consecutive_loss_limit` | 2, 3, 5, unlimited |

### 3.3 Rule Strictness Toggles

| Rule Category | Strict Mode | Relaxed Mode |
|--------------|-------------|--------------|
| Kill Zone | Only trade inside KZ | Trade outside with warning |
| News Filter | Block all high impact | Allow with reduced size |
| Counter-Trend | Require 1H MSS | Allow with higher confluence |
| R:R Minimum | Enforce 1:2 | Allow 1:1.5 with high confluence |
| HTF Unclear | Strict WAIT | Allow LTF-only setups |

### 3.4 Execution Mode Options

| Mode | Behavior |
|------|----------|
| `ANALYSIS_ONLY` | No execution, only outputs setups |
| `SIMULATION` | Paper trading with simulated fills |
| `APPROVAL_REQUIRED` | Real execution after manual approval |
| `SEMI_AUTO` | Auto-execute high-confidence only |
| `FULL_AUTO` | Execute all valid setups (dangerous) |

---

## 4. Agent Lifecycle & Safety Controls

### 4.1 Pre-Trade Validation Layers

```
[Market Snapshot]
       ↓
[Schema Validation] → Reject malformed input
       ↓
[Rate Limiter] → Prevent spam
       ↓
[Mode Check] → Block if ANALYSIS_ONLY
       ↓
[Daily Limit Check] → Block if max trades reached
       ↓
[Drawdown Check] → Block if equity below threshold
       ↓
[Agent Analysis] → Core engine
       ↓
[Post-Analysis Validation]
       ↓
[Confidence Threshold] → Require minimum confidence
       ↓
[Approval Gate] → Manual or auto based on mode
       ↓
[Execution]
```

### 4.2 Kill Switch Options

| Trigger | Action |
|---------|--------|
| Daily loss limit hit | Pause all execution |
| API error rate > threshold | Switch to ANALYSIS_ONLY |
| Broker connection lost | Queue pending, alert user |
| News surge detected | Pause for N minutes |
| Manual override | Immediate halt |

### 4.3 Confidence Thresholds

| Confidence Level | Recommended Action |
|-----------------|-------------------|
| 0.0 - 0.3 | NO_TRADE |
| 0.3 - 0.5 | WAIT for better setup |
| 0.5 - 0.7 | TRADE with manual approval |
| 0.7 - 0.9 | TRADE (auto-eligible) |
| 0.9 - 1.0 | HIGH CONVICTION (auto-execute if enabled) |

### 4.4 Mode Transition Rules

| From → To | Requirement |
|-----------|-------------|
| ANALYSIS → SIMULATION | None |
| SIMULATION → ANALYSIS | None |
| SIMULATION → EXECUTION | Confirmation + broker connection |
| EXECUTION → SIMULATION | Confirmation (close open positions first) |
| ANY → EMERGENCY_STOP | Immediate, no confirmation |

---

## 5. Persistence Options

### Option A: In-Memory Only (MVP)
- No persistence between restarts
- Suitable for single-session use

### Option B: SQLite (Lightweight)
- Local file-based storage
- Good for single-user, local deployment

### Option C: PostgreSQL (Production)
- Full ACID compliance
- Suitable for multi-user, cloud deployment

### Option D: TimescaleDB (Time-Series Optimized)
- Best for storing OHLCV data and decision logs
- Efficient for analytics queries

### Recommended Schema Entities
- `decisions` — All trade analysis results
- `executions` — Order history
- `config_snapshots` — Configuration audit trail
- `sessions` — Session boundaries and summaries

---

## 6. Authentication & Security Options

| Approach | Use Case |
|----------|----------|
| API Key | Single user, local deployment |
| JWT Tokens | Multi-user, session-based |
| OAuth2 | Third-party integrations |
| mTLS | Broker-to-backend communication |

### Rate Limiting
- Analysis endpoint: 60 req/min
- Configuration endpoints: 10 req/min
- Execution endpoints: 5 req/min

---

## 7. Deployment Options

| Environment | Stack |
|-------------|-------|
| Local Development | Uvicorn + SQLite |
| Docker Compose | FastAPI + PostgreSQL + Redis |
| Kubernetes | Full microservices deployment |
| Serverless | AWS Lambda + API Gateway + DynamoDB |

---

*End of Backend Design Specification*
