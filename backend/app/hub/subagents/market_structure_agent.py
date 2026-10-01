"""Market structure sub-agent (deterministic, schema-only output)."""
from __future__ import annotations

from typing import Any, Dict, List

from app.tools.bias import get_htf_bias
from app.tools.structure import get_market_structure


class MarketStructureAgent:
    """Detect HTF trend and BOS/CHoCH-style context."""

    name = "market_structure_agent"

    def run(
        self,
        *,
        candles_d1: List[Dict[str, Any]],
        candles_h4: List[Dict[str, Any]],
        candles_h1: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        d1 = get_market_structure(candles_d1) if candles_d1 else {"structure": "UNCLEAR"}
        h4 = get_market_structure(candles_h4) if candles_h4 else {"structure": "UNCLEAR"}
        h1 = get_market_structure(candles_h1) if candles_h1 else {"structure": "UNCLEAR"}

        htf = get_htf_bias(candles_h1) if candles_h1 else {"bias": "NEUTRAL", "confidence": 0.0}

        return {
            "agent": self.name,
            "bias": (htf.get("bias") or "NEUTRAL").lower(),
            "bias_confidence": float(htf.get("confidence", 0.0)),
            "structures": {
                "D1": d1.get("structure", "UNCLEAR"),
                "H4": h4.get("structure", "UNCLEAR"),
                "H1": h1.get("structure", "UNCLEAR"),
            },
            "last_structure_event": h1.get("structure", "UNCLEAR"),
        }
