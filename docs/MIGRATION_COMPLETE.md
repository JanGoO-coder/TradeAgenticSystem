# ICT Hierarchical Agent System - Migration Complete

## Summary

The trading agent system has been successfully migrated from a linear LangGraph pipeline to a **hierarchical 3-agent architecture** as specified in `docs/system_design/architecture.md`.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         MAIN AGENT                          │
│              (Orchestrator + State Machine)                 │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │  IDLE   │→ │ANALYZING │→ │ DECIDING │→ │  EXECUTING  │  │
│  └─────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│       ↑                                         ↓          │
│       └─────────── MONITORING ←─────────────────┘          │
└─────────────────────────────────────────────────────────────┘
              ↓                           ↓
    ┌─────────────────┐         ┌─────────────────┐
    │ STRATEGY AGENT  │         │  WORKER AGENT   │
    │   (Analyst)     │         │   (Executor)    │
    └─────────────────┘         └─────────────────┘
```

---

## New Files Created

### Rules Configuration
| File | Purpose |
|------|---------|
| `rules/config.yaml` | YAML-based rules configuration with all ICT trading parameters |
| `agent/src/rules_config.py` | RulesConfig models, RulesManager singleton with hot-reload |

### Communication Protocol
| File | Purpose |
|------|---------|
| `agent/src/protocol.py` | MessageEnvelope, ActionType enum, MessageLog, TickLog for audit trail |

### State Models
| File | Purpose |
|------|---------|
| `agent/src/state.py` | SessionState, MarketContext, TradeSetup, VirtualClock, enums |

### Strategy Agent
| File | Purpose |
|------|---------|
| `agent/src/strategy_agent/__init__.py` | Package exports |
| `agent/src/strategy_agent/models.py` | MarketContextRequest, MarketContextResponse |
| `agent/src/strategy_agent/tools.py` | Analysis functions (bias, killzones, levels) |
| `agent/src/strategy_agent/agent.py` | StrategyAgent class with analyze() and handle_message() |

### Worker Agent
| File | Purpose |
|------|---------|
| `agent/src/worker_agent/__init__.py` | Package exports |
| `agent/src/worker_agent/models.py` | SetupScanRequest, ExecutionRequest, etc. |
| `agent/src/worker_agent/tools.py` | Pattern detection functions (ICT models) |
| `agent/src/worker_agent/agent.py` | WorkerAgent class with scan_setups() and execute_trade() |

### Main Agent
| File | Purpose |
|------|---------|
| `agent/src/main_agent/__init__.py` | Package exports |
| `agent/src/main_agent/agent.py` | MainAgent orchestrator with state machine |

### Backend Integration
| File | Purpose |
|------|---------|
| `agent/src/graph_new.py` | Backward-compatible entry point |
| `backend/app/agent/engine_new.py` | TradingAgentEngine wrapper |
| `backend/app/api/v1/rules.py` | Hot-reload API endpoints |

---

## Key Features

### 1. State Machine
The Main Agent operates through defined phases:
- **IDLE**: Waiting for next tick
- **ANALYZING**: Requesting context from Strategy Agent
- **DECIDING**: Evaluating setups from Worker Agent
- **EXECUTING**: Placing trades via Worker Agent
- **MONITORING**: Managing open positions

### 2. Virtual Clock
For backtest mode, the Main Agent controls time:
```python
clock = VirtualClock(start_time, end_time, "5M")
clock.advance(1)  # Move forward by 1 candle
```

### 3. Hot-Reload Rules
Rules can be updated at runtime without restart:
```bash
# API endpoint
POST /api/v1/rules/reload

# Python
from src import reload_rules
success, message = reload_rules()
```

### 4. Message Audit Trail
All inter-agent communication is logged for replay:
```python
message_log = agent.message_log
messages = message_log.get_all()
```

### 5. Entry Models Supported
- **ICT 2022 Model**: Displacement → FVG → Entry
- **FVG Entry**: Fair Value Gap retracement
- **OTE**: Optimal Trade Entry (61.8-79% fib)
- **Silverbullet**: Time-window based entry

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/rules` | GET | Get current rules configuration |
| `/api/v1/rules/reload` | POST | Hot-reload rules from file |
| `/api/v1/rules/session` | GET | Get session-level rules |
| `/api/v1/rules/audit-trail` | GET | Get reload history |

---

## Usage Example

```python
from src import MainAgent, load_rules
from datetime import datetime

# Load rules
load_rules("rules/config.yaml")

# Create agent
agent = MainAgent()

# Initialize session
session = agent.initialize_session(
    symbol="EURUSD",
    mode="BACKTEST",
    start_time=datetime(2024, 1, 1, 8, 0),
    end_time=datetime(2024, 1, 31, 22, 0)
)

# Run tick
result = agent.run_tick(
    timeframe_bars={"H1": [...], "M15": [...], "M5": [...]},
    economic_calendar=[...]
)

print(f"Phase: {result['phase']}")
print(f"Context: {result['context']}")
print(f"Setup: {result['setup']}")
```

---

## Testing

Run integration tests:
```bash
cd agent
python test_integration.py
```

All 6 tests should pass:
- ✅ Rules Loading
- ✅ Agent Instantiation
- ✅ Session Initialization
- ✅ Tick Execution
- ✅ Message Logging
- ✅ Hot-Reload

---

## Migration Notes

### Breaking Changes
- Old `graph.py` and `nodes.py` replaced by hierarchical architecture
- State models completely redesigned
- Protocol changed to message-based system

### Backward Compatibility
- `engine_new.py` wraps the new architecture with the old interface
- Legacy imports still work but may show deprecation warnings

### Next Steps
1. Replace `engine.py` with `engine_new.py` after validation
2. Update frontend to use new state models
3. Implement "Glass Box" replay visualization using TickLog
4. Add more entry model implementations

---

## File Structure After Migration

```
agent/
├── src/
│   ├── __init__.py           # Package exports
│   ├── graph_new.py          # Backward-compatible entry
│   ├── protocol.py           # Message protocol
│   ├── rules_config.py       # Rules with hot-reload
│   ├── state.py              # State models
│   ├── main_agent/
│   │   ├── __init__.py
│   │   └── agent.py          # Main orchestrator
│   ├── strategy_agent/
│   │   ├── __init__.py
│   │   ├── agent.py          # Strategy analyst
│   │   ├── models.py
│   │   └── tools.py
│   └── worker_agent/
│       ├── __init__.py
│       ├── agent.py          # Worker executor
│       ├── models.py
│       └── tools.py
├── test_integration.py       # Integration tests
└── requirements.txt

rules/
├── config.yaml               # Trading rules
└── README.md

backend/
├── app/
│   ├── agent/
│   │   ├── engine.py         # Legacy (to be replaced)
│   │   └── engine_new.py     # New hierarchical wrapper
│   └── api/v1/
│       └── rules.py          # Hot-reload endpoints
```

---

## Author
Implementation completed following the architecture specification in `docs/system_design/architecture.md`.

Date: 2025-01-XX
