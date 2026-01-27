# ICT Agentic Trading System

An AI-powered trading analysis platform implementing ICT (Inner Circle Trader) concepts using LangGraph agents and a modern web dashboard.

## 🏗️ Project Structure

```
TradeAgenticSystem/
├── agent/              # LangGraph trading agent
│   └── src/            # Core agent logic (graph, nodes, tools)
├── backend/            # FastAPI REST API server
├── frontend/           # Next.js React dashboard
├── docs/               # Documentation
└── rules/              # ICT trading rulebook
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- MetaTrader 5 (optional, for live data)

### Backend Setup
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Access
- **Dashboard:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Multi-Timeframe Analysis** | 1H, 15M, 5M chart analysis |
| **ICT Pattern Detection** | FVG, Order Blocks, Liquidity Sweeps |
| **Kill Zone Trading** | London & NY session filtering |
| **Risk Management** | Auto position sizing with R:R targets |
| **Backtest Mode** | Historical data simulation |
| **Live Mode** | Real-time MT5 data streaming |

## 📊 Data Modes

All data modes use MT5 (MetaTrader 5) as the data source:

| Mode | Description |
|------|-------------|
| **Historical** | MT5 historical data fetch for one-time analysis |
| **Backtest** | MT5 data playback for strategy testing |
| **Live** | Real-time MT5 stream for production trading |

> **Note:** MetaTrader 5 terminal must be running for all data features to work.

## 🛠️ Tech Stack

- **Agent:** LangGraph, LangChain
- **Backend:** FastAPI, Pydantic, WebSockets
- **Frontend:** Next.js 14, React Query, Tailwind CSS
- **Data:** MetaTrader 5 (required)

## 📁 Key Files

| File | Purpose |
|------|---------|
| `agent/src/graph.py` | LangGraph workflow definition |
| `agent/src/nodes.py` | Agent node implementations |
| `agent/src/tools.py` | ICT analysis tools |
| `backend/app/main.py` | FastAPI application |
| `frontend/src/app/page.tsx` | Main dashboard |

## 📜 License

MIT
