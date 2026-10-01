from datetime import datetime

import pytest

from app.domain.hub import HubDecisionRequest
from app.hub.master_agent import MasterTradingAgent


def _bars(start: float, count: int, step: float = 0.0002):
    bars = []
    price = start
    for i in range(count):
        close = price + step
        bars.append(
            {
                "timestamp": f"2026-01-01T00:{i:02d}:00Z",
                "open": round(price, 5),
                "high": round(max(price, close) + 0.0001, 5),
                "low": round(min(price, close) - 0.0001, 5),
                "close": round(close, 5),
                "volume": 100 + i,
            }
        )
        price = close
    return bars


@pytest.mark.asyncio
async def test_master_agent_returns_hub_decision_schema() -> None:
    agent = MasterTradingAgent()

    payload = HubDecisionRequest(
        symbol="EURUSD",
        timestamp=datetime(2026, 1, 1, 2, 30, 0),
        account_balance=10_000.0,
        risk_pct=0.5,
        timeframe_bars={
            "D1": _bars(1.08, 120, 0.0003),
            "H4": _bars(1.09, 120, 0.0002),
            "1H": _bars(1.10, 120, 0.00015),
            "15M": _bars(1.11, 160, 0.00008),
            "5M": _bars(1.115, 200, 0.00003),
            "1M": _bars(1.116, 240, 0.00001),
        },
    )

    decision = await agent.decision_cycle(payload)

    assert decision.symbol == "EURUSD"
    assert decision.status in {"pending", "active", "no-trade"}
    assert isinstance(decision.confluences, list)
    assert isinstance(decision.vetoes, list)
    assert decision.call_metrics.subagent_calls >= 0
    assert isinstance(decision.llm_called, bool)
    assert decision.session in {"London kill zone", "NY kill zone", "outside-killzone"}


@pytest.mark.asyncio
async def test_master_agent_reuses_cached_decision_on_same_markers() -> None:
    agent = MasterTradingAgent()
    bars = _bars(1.10, 120, 0.0001)

    payload = HubDecisionRequest(
        symbol="EURUSD",
        timestamp=datetime(2026, 1, 1, 2, 45, 0),
        timeframe_bars={
            "D1": bars,
            "H4": bars,
            "1H": bars,
            "15M": bars,
            "5M": bars,
            "1M": bars,
        },
        account_balance=10_000.0,
    )

    first = await agent.decision_cycle(payload)
    second = await agent.decision_cycle(payload)

    assert first.symbol == second.symbol
    assert second.cache_hit is True
    assert second.call_metrics.cache_hits >= 1
