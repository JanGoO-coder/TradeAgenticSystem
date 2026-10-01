"""Session sub-agent using strict UTC killzone windows."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.hub.tools import get_session_window


class SessionAgent:
    """Classify UTC session context and kill zone status."""

    name = "session_agent"

    def run(self, *, utc_now: datetime) -> Dict[str, Any]:
        status = get_session_window(utc_now)
        volatility_profile = (
            "high" if status["session"] in {"London kill zone", "NY kill zone"} else "low"
        )
        return {
            "agent": self.name,
            "session": status["session"],
            "in_killzone": bool(status["in_killzone"]),
            "volatility_profile": volatility_profile,
            "windows": status["windows"],
        }
