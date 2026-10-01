"""FVG/POI sub-agent (deterministic, schema-only output)."""
from __future__ import annotations

from typing import Any, Dict, List

from app.hub.tools import find_fvg, find_ob


class FVGPOIAgent:
    """Detect active FVG/OB/Breaker-style POIs and rank them."""

    name = "fvg_poi_agent"

    def run(
        self,
        *,
        candles_h4: List[Dict[str, Any]],
        candles_h1: List[Dict[str, Any]],
        candles_m15: List[Dict[str, Any]],
        bias: str,
    ) -> Dict[str, Any]:
        merged: List[Dict[str, Any]] = []
        for tf_name, candles in (("H4", candles_h4), ("H1", candles_h1), ("M15", candles_m15)):
            if not candles:
                continue
            fvgs = find_fvg(candles)
            obs = find_ob(candles)

            for fvg in fvgs.get("unmitigated_fvg", [])[:5]:
                direction = "bullish" if "BULLISH" in str(fvg.get("type", "")) else "bearish"
                rank = 100 if direction == bias else 60
                merged.append(
                    {
                        "kind": "FVG",
                        "timeframe": tf_name,
                        "direction": direction,
                        "top": fvg.get("top"),
                        "bottom": fvg.get("bottom"),
                        "midpoint": fvg.get("midpoint"),
                        "score": rank,
                    }
                )

            for ob in obs.get("all", [])[:5]:
                direction = "bullish" if "BULLISH" in str(ob.get("type", "")) else "bearish"
                rank = 90 if direction == bias else 55
                merged.append(
                    {
                        "kind": "OB",
                        "timeframe": tf_name,
                        "direction": direction,
                        "top": ob.get("high"),
                        "bottom": ob.get("low"),
                        "midpoint": ((ob.get("high", 0.0) + ob.get("low", 0.0)) / 2.0),
                        "score": rank,
                    }
                )

        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return {
            "agent": self.name,
            "active_pois": merged[:10],
            "top_poi": merged[0] if merged else None,
        }
