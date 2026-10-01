"""Entry confirmation sub-agent for M5/M1 trigger checks."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.hub.tools import detect_bos_choch
from app.tools.structure import detect_displacement


class EntryConfirmationAgent:
    """Validate displacement + local trigger in lower timeframes."""

    name = "entry_confirmation_agent"

    def run(
        self,
        *,
        candles_m5: List[Dict[str, Any]],
        candles_m1: List[Dict[str, Any]],
        poi: Optional[Dict[str, Any]],
        bias: str,
    ) -> Dict[str, Any]:
        source = candles_m5 or candles_m1
        if not source:
            return {
                "agent": self.name,
                "trigger_valid": False,
                "displacement": False,
                "structure_event": None,
                "mitigation": False,
            }

        structure = detect_bos_choch(source)
        disp = detect_displacement(source)
        displacement = len(disp) > 0

        current_price = float(source[-1].get("close", 0.0))
        mitigation = False
        if poi and poi.get("top") is not None and poi.get("bottom") is not None:
            low = min(float(poi["bottom"]), float(poi["top"]))
            high = max(float(poi["bottom"]), float(poi["top"]))
            mitigation = low <= current_price <= high

        structure_ok = structure.get("direction") == bias if structure.get("direction") else False
        trigger_valid = bool(displacement and mitigation and structure_ok)

        return {
            "agent": self.name,
            "trigger_valid": trigger_valid,
            "displacement": displacement,
            "structure_event": structure,
            "mitigation": mitigation,
            "current_price": current_price,
        }
