"""Compact per-symbol state and cache for the hub."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SessionStateCompact:
    """Compact state object used by the master hub agent."""

    symbol: str
    bias: str = "neutral"
    last_structure_event: Optional[str] = None
    active_pois: List[Dict[str, Any]] = field(default_factory=list)
    draw_target: Optional[str] = None
    in_killzone: bool = False
    risk_lock: bool = False
    open_trades: List[Dict[str, Any]] = field(default_factory=list)
    last_decision_hash: str = ""
    last_decision_output: Optional[Dict[str, Any]] = None
    last_candle_time_by_tf: Dict[str, str] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    # Internal caches
    tool_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    subagent_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def update_candle_time(self, timeframe: str, candle_time: str) -> None:
        self.last_candle_time_by_tf[timeframe] = candle_time
        self.last_updated = datetime.utcnow().isoformat() + "Z"

    def cache_key(self, key: str, tf: Optional[str], marker: Optional[str]) -> str:
        if tf and marker:
            return f"{key}:{tf}:{marker}"
        if tf:
            return f"{key}:{tf}"
        return key

    def get_tool_cache(self, key: str) -> Optional[Dict[str, Any]]:
        return self.tool_cache.get(key)

    def set_tool_cache(self, key: str, value: Dict[str, Any]) -> None:
        self.tool_cache[key] = value

    def get_subagent_cache(self, key: str) -> Optional[Dict[str, Any]]:
        return self.subagent_cache.get(key)

    def set_subagent_cache(self, key: str, value: Dict[str, Any]) -> None:
        self.subagent_cache[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "bias": self.bias,
            "last_structure_event": self.last_structure_event,
            "active_pois": self.active_pois,
            "draw_target": self.draw_target,
            "in_killzone": self.in_killzone,
            "risk_lock": self.risk_lock,
            "open_trades": self.open_trades,
            "last_decision_hash": self.last_decision_hash,
            "has_last_decision": self.last_decision_output is not None,
            "last_candle_time_by_tf": self.last_candle_time_by_tf,
            "last_updated": self.last_updated,
            "tool_cache_keys": list(self.tool_cache.keys()),
            "subagent_cache_keys": list(self.subagent_cache.keys()),
        }
