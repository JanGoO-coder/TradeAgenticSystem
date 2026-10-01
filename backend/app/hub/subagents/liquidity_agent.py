"""Liquidity sub-agent (deterministic, schema-only output)."""
from __future__ import annotations

from typing import Any, Dict, List

from app.hub.tools import find_liquidity
from app.tools.liquidity import find_equal_highs_lows


class LiquidityAgent:
    """Map BSL/SSL pools, equal highs/lows and draw targets."""

    name = "liquidity_agent"

    def run(self, *, candles_h1: List[Dict[str, Any]], candles_m15: List[Dict[str, Any]]) -> Dict[str, Any]:
        source = candles_m15 or candles_h1
        pools = find_liquidity(source)
        eql = find_equal_highs_lows(source)

        return {
            "agent": self.name,
            "BSL": pools.get("BSL", []),
            "SSL": pools.get("SSL", []),
            "equal_highs": eql.get("equal_highs", []),
            "equal_lows": eql.get("equal_lows", []),
            "draw_target": pools.get("draw_target"),
        }
