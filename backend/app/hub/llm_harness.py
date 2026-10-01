"""Minimal LLM arbitration harness for high-probability candidates only."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.services.llm_service import get_llm_service


class HubLLMHarness:
    """Build compact prompts and enforce strict JSON output parsing."""

    def __init__(self) -> None:
        self._llm = get_llm_service()

    def _compact_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": payload.get("symbol"),
            "bias": payload.get("bias"),
            "draw": payload.get("draw"),
            "session": payload.get("session"),
            "candidate": payload.get("candidate"),
            "confluences": payload.get("confluences", [])[:8],
            "vetoes": payload.get("vetoes", [])[:6],
            "pois": payload.get("pois", [])[:3],
        }

    async def arbitrate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        compact = self._compact_payload(payload)
        prompt = (
            "Return ONLY JSON with keys status, reason, confidence. "
            "status must be one of pending|active|no-trade. "
            "Use no-trade when vetoes are non-empty.\n"
            + json.dumps(compact, ensure_ascii=True)
        )

        response = await self._llm.generate(prompt=prompt, mode="concise", temperature=0.1)
        parsed = response.get("parsed")
        if isinstance(parsed, dict):
            status = str(parsed.get("status", "pending"))
            if status not in {"pending", "active", "no-trade"}:
                status = "pending"
            return {
                "status": status,
                "reason": str(parsed.get("reason", "LLM arbitration")),
                "confidence": float(parsed.get("confidence", 0.5)),
            }

        return {"status": "pending", "reason": "LLM parse fallback", "confidence": 0.5}
