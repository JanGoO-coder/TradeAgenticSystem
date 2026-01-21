# Frontend Design Specification
## ICT Agentic Trading Platform — shadcn/ui Dashboard

> **Scope**: This document defines the frontend architecture for a trader-grade dashboard that wraps the ICT Trading Agent, combining structured panels with conversational AI interaction patterns.

---

## 1. UI Philosophy

### 1.1 Core Principles

| Principle | Description |
|-----------|-------------|
| **Trader Control** | Human always has final say; agent advises, trader decides |
| **Transparency** | Every decision is explainable; no black-box outputs |
| **Progressive Automation** | Start manual, earn trust, enable automation gradually |
| **Cognitive Efficiency** | Surface what matters, hide what doesn't |
| **Safety First** | Multiple confirmation layers before any real action |

### 1.2 Why shadcn/ui + assistant-ui

| Technology | Benefit |
|------------|---------|
| **shadcn/ui** | Production-ready components; full customization via copy-paste; excellent dark mode; consistent design language |
| **assistant-ui patterns** | Conversational UX for complex queries; natural language explanations; reduces learning curve |
| **Hybrid model** | Best of both: structured dashboards for monitoring, chat for exploration and "why" questions |

### 1.3 Design Stance

```
┌─────────────────────────────────────────────────────────────┐
│                    INFORMATION HIERARCHY                     │
├─────────────────────────────────────────────────────────────┤
│  CRITICAL    │ Current position, P&L, kill switches        │
│  HIGH        │ Active setup, HTF bias, session status       │
│  MEDIUM      │ Confluence details, rule states              │
│  LOW         │ Historical data, configuration               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Screens — Complete Catalog

### 2.1 Dashboard Overview (Home)

**Purpose**: Single-glance status of the trading system

| Component | Content |
|-----------|---------|
| Mode Badge | ANALYSIS / SIMULATION / LIVE |
| Session Clock | Current session, kill zone status, countdown |
| HTF Bias Card | 1H bias with confidence meter |
| Active Setup Card | Current TRADE_NOW setup or WAIT reason |
| P&L Summary | Today, week, month (if executing) |
| Quick Actions | Analyze Now, View History, Settings |

---

### 2.2 Live Session Monitor

**Purpose**: Real-time monitoring during active trading sessions

| Component | Content |
|-----------|---------|
| Session Timeline | Visual timeline of London/NY/Asia with current position |
| Kill Zone Indicator | Active/inactive with countdown |
| News Ticker | Upcoming high-impact events |
| Live Bias Feed | HTF/LTF bias updates as they occur |
| Setup Queue | Pending setups awaiting confirmation |
| Recent Decisions | Last 5 analysis results |

---

### 2.3 Trade Setup Viewer

**Purpose**: Deep-dive into a specific trade setup

| Component | Content |
|-----------|---------|
| Setup Header | Name, type, symbol, timestamp |
| Entry/Exit Visualizer | Price levels with annotations |
| Checklist Panel | All 7 checklist items with pass/fail |
| Confluence Meter | 0-10 score with breakdown |
| Rule Reference List | Clickable rule IDs with definitions |
| Action Buttons | Approve / Reject / Modify / Simulate |

---

### 2.4 Rule Explanation Panel

**Purpose**: Understand why a trade was/was not taken

| Component | Content |
|-----------|---------|
| Decision Tree | Hierarchical view of rule evaluation |
| Pass/Fail Icons | Green/red indicators per rule |
| Blocking Rules | Highlighted rules that caused WAIT/NO_TRADE |
| "What If" Toggle | See what would change if a rule passed |
| Rule Documentation | Full rule text from ICT_Rulebook |

---

### 2.5 HTF/LTF Bias Visualization

**Purpose**: Visual representation of market structure

| Component | Content |
|-----------|---------|
| 1H Structure Chart | Swing highs/lows annotated |
| 15M Alignment View | LTF structure vs HTF bias |
| Bias History | Recent bias changes with timestamps |
| Structure Labels | HH/HL or LH/LL annotations |
| Displacement Markers | Highlighted displacement candles |

---

### 2.6 Kill Zone & Session Clock

**Purpose**: Time-based trading constraint visibility

| Component | Content |
|-----------|---------|
| World Clock | London, NY, Sydney times |
| Kill Zone Bars | Visual bars showing active zones |
| Session Boundaries | Clear markers for session opens |
| Countdown Timers | Time until next zone starts/ends |
| Holiday Calendar | Bank holiday warnings |

---

### 2.7 Risk Calculator Panel

**Purpose**: Position sizing and risk visualization

| Component | Content |
|-----------|---------|
| Account Balance | Current balance display |
| Risk Percentage Slider | 0.5% - 3% with presets |
| Stop Distance Input | Pips or price level |
| Position Size Output | Calculated lots/units |
| R:R Calculator | Visual risk-reward ratio |
| Max Loss Display | Dollar amount at risk |

---

### 2.8 Agent Confidence & Confluence Meter

**Purpose**: Trust calibration for automation decisions

| Component | Content |
|-----------|---------|
| Confidence Gauge | 0-100% circular meter |
| Confluence Breakdown | 10-point checklist visualization |
| Historical Accuracy | Win rate at this confidence level |
| Automation Threshold | Visual marker for auto-execute cutoff |
| Trend Indicator | Is confidence rising or falling? |

---

### 2.9 Manual Approve/Reject Panel

**Purpose**: Human-in-the-loop decision gate

| Component | Content |
|-----------|---------|
| Setup Summary | Key details of proposed trade |
| Approve Button | With confirmation dialog |
| Reject Button | With optional reason input |
| Modify Option | Adjust entry/SL/TP before approval |
| Timer | Optional auto-reject after N seconds |
| One-Click Options | Quick approve with current settings |

---

### 2.10 Trade History & Replay

**Purpose**: Historical analysis and learning

| Component | Content |
|-----------|---------|
| History Table | Filterable list of all decisions |
| Outcome Column | Win/Loss/Pending for executed trades |
| Replay Button | Re-run analysis with historical data |
| Comparison View | Side-by-side analysis vs actual outcome |
| Export Options | CSV, JSON export |
| Performance Charts | Equity curve, win rate over time |

---

### 2.11 Settings & Configuration

**Purpose**: System configuration management

| Section | Options |
|---------|---------|
| Risk Settings | Risk %, max trades, R:R minimum |
| Time Settings | Timezone, kill zone preferences |
| Rule Toggles | Strictness levels per rule category |
| Notification Settings | Alerts, sounds, email |
| Execution Mode | ANALYSIS / SIMULATION / EXECUTION |
| API Keys | Broker connections (future) |
| Appearance | Theme, layout preferences |

---

### 2.12 Debug / Advanced View

**Purpose**: Power user diagnostics

| Component | Content |
|-----------|---------|
| Agent State Inspector | Raw state object view |
| Node Trace | LangGraph node execution log |
| API Request Log | Recent API calls |
| Performance Metrics | Response times, error rates |
| Configuration Dump | Current config as JSON |
| Manual Override | Force specific agent states |

---

## 3. Interaction Models

### 3.1 Option A: Button-Driven (Traditional)

| Pros | Cons |
|------|------|
| Familiar to traders | Limited expressiveness |
| Fast for common actions | Requires learning UI layout |
| Predictable behavior | Can't ask "why" questions |

**Best for**: Experienced users who know what they want

---

### 3.2 Option B: Chat-Driven (assistant-ui Style)

| Pros | Cons |
|------|------|
| Natural language queries | Slower for simple actions |
| Great for explanations | Requires typing |
| Discoverable features | Unpredictable responses |

**Example Interactions**:
- "Why didn't we take that EURUSD setup?"
- "Show me all trades where Rule 3.4 triggered"
- "What's the current HTF bias for GBPUSD?"
- "Explain the confluence score"

**Best for**: New users, learning mode, complex queries

---

### 3.3 Option C: Hybrid (Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│                    STRUCTURED PANELS                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ Session     │ │ Active      │ │ Confluence  │            │
│  │ Status      │ │ Setup       │ │ Meter       │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
├─────────────────────────────────────────────────────────────┤
│                    CHAT PANEL (Collapsible)                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ You: Why is the bias neutral?                           ││
│  │ Agent: The 1H structure is unclear because...           ││
│  └─────────────────────────────────────────────────────────┘│
│  [Type a message...]                                   [Send]│
└─────────────────────────────────────────────────────────────┘
```

**Implementation**: Docked chat panel that can be expanded/collapsed, with quick-action buttons above it.

---

### 3.4 Option D: Command Palette (Power Users)

**Trigger**: Cmd+K / Ctrl+K

**Commands**:
- `analyze EURUSD` — Run analysis
- `explain last` — Explain last decision
- `set risk 1.5%` — Change risk setting
- `show history 7d` — View last 7 days
- `mode simulation` — Switch mode

**Best for**: Keyboard-centric power users

---

### 3.5 Confirmation Models

| Level | Use Case | UX |
|-------|----------|-----|
| **Zero-Click** | Viewing data | Instant |
| **One-Click** | Approve high-confidence setup | Single button |
| **Two-Step** | Approve medium-confidence | Button + confirm dialog |
| **Multi-Step** | Enable live execution | Wizard with multiple confirmations |
| **Time-Delayed** | Irreversible actions | "Cancel within 5 seconds" |

---

## 4. Visualization Options

### 4.1 Chart Overlays

| Overlay | Description |
|---------|-------------|
| PD Array Zones | Premium/Discount shading |
| FVG Rectangles | Fair Value Gap boxes |
| OTE Zone | 62-79% retracement band |
| Swing Points | Fractal markers |
| Liquidity Levels | EQH/EQL lines |
| Session Boxes | Kill zone boundaries |

---

### 4.2 Confluence Scoring Visualizations

| Option | Description |
|--------|-------------|
| **Radar Chart** | 7-axis spider diagram |
| **Progress Bars** | Horizontal bars per factor |
| **Pie Chart** | Contribution breakdown |
| **Traffic Lights** | Red/Yellow/Green per check |
| **Numeric Stack** | "+2 +1 +2 +1 +1 = 7/10" |

---

### 4.3 Decision Timeline

```
[10:00] HTF Bias: BULLISH
    │
[10:15] Gatekeeper: PASS (in Kill Zone)
    │
[10:30] Sniper: FVG detected at 1.0950
    │
[10:32] Risk Calc: 1.5 lots, R:R 2.5
    │
[10:33] → TRADE_NOW (awaiting approval)
    │
[10:35] ✓ APPROVED by user
```

---

### 4.4 Rule Trace Trees

```
Trade Decision: NO_TRADE
│
├─ ✓ HTF Bias Exists (Rule 1.1)
│   └─ BULLISH
│
├─ ✓ Kill Zone Active (Rule 8.1)
│   └─ NY Session
│
├─ ✗ LTF Alignment (Rule 1.2) ← BLOCKING
│   └─ 15M structure is BEARISH
│
└─ (Remaining rules not evaluated)
```

---

## 5. Component Architecture

### 5.1 Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│ HEADER: Mode | Session | Quick Actions | User               │
├────────────────┬─────────────────────────────────────────────┤
│                │                                              │
│   SIDEBAR      │              MAIN CONTENT                   │
│   Navigation   │              (varies by screen)             │
│                │                                              │
│   - Dashboard  │                                              │
│   - Monitor    │                                              │
│   - History    │                                              │
│   - Settings   │                                              │
│                │                                              │
├────────────────┴─────────────────────────────────────────────┤
│ CHAT DOCK (collapsible): Assistant UI interface              │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Component Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| **Display** | Show data | BiasCard, ConfluenceMeter, SetupCard |
| **Input** | Capture user input | RiskSlider, SymbolSelector, TimeframePicker |
| **Action** | Trigger operations | ApproveButton, AnalyzeButton, ModeToggle |
| **Feedback** | Communicate status | Toast, Alert, ProgressBar |
| **Layout** | Structure content | Panel, Tabs, Accordion |

### 5.3 State Management Options

| Option | Use Case |
|--------|----------|
| **React Context** | Simple, low-frequency state |
| **Zustand** | Medium complexity, good DX |
| **TanStack Query** | Server state, caching |
| **Jotai** | Atomic, granular updates |

**Recommendation**: TanStack Query for API data + Zustand for UI state

---

## 6. Responsive Design

| Breakpoint | Layout |
|------------|--------|
| Desktop (1200px+) | Full 3-column layout |
| Tablet (768-1199px) | Collapsible sidebar |
| Mobile (< 768px) | Bottom nav, stacked cards |

**Mobile Considerations**:
- Simplified dashboard with key metrics only
- Swipe gestures for approve/reject
- Push notifications for TRADE_NOW alerts

---

## 7. Accessibility

| Requirement | Implementation |
|-------------|----------------|
| Keyboard Navigation | Full tab navigation, hotkeys |
| Screen Reader | ARIA labels on all interactive elements |
| Color Contrast | WCAG AA compliance |
| Motion | Respect prefers-reduced-motion |
| Text Scaling | Support up to 200% zoom |

---

## 8. Theming

| Theme | Use Case |
|-------|----------|
| **Dark (Default)** | Trading standard, reduces eye strain |
| **Light** | User preference, print-friendly |
| **High Contrast** | Accessibility, bright environments |
| **Trading Terminal** | Black background, neon accents |

---

*End of Frontend Design Specification*
