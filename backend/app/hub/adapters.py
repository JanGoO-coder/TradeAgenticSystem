"""Adapters between hub-native and legacy API response contracts."""
from __future__ import annotations

from typing import Any, Dict, List

from app.domain.hub import HubDecisionResponse


def hub_to_legacy_response(hub_decision: HubDecisionResponse) -> Dict[str, Any]:
    """Map hub decision output into legacy TradeSetupResponse-like shape."""

    status_map = {
        "active": "TRADE_NOW",
        "pending": "WAIT",
        "no-trade": "NO_TRADE",
    }
    status = status_map.get(hub_decision.status, "NO_TRADE")

    confluences = list(hub_decision.confluences)
    vetoes = list(hub_decision.vetoes)
    all_refs: List[str] = (confluences + vetoes)[:10]

    confluence_score = min(10, len(confluences) + (2 if hub_decision.status == "active" else 0))
    risk_meta = hub_decision.metadata.get("risk", {}) if isinstance(hub_decision.metadata, dict) else {}
    risk_pct = float(risk_meta.get("risk_pct", 0.5))

    return {
        "symbol": hub_decision.symbol,
        "timestamp": hub_decision.timestamp,
        "status": status,
        "reason_short": hub_decision.reason,
        "htf_bias": {
            "value": str(hub_decision.bias or "neutral").upper(),
            "rule_refs": ["1.1"],
        },
        "ltf_alignment": {
            "timeframe": "15M",
            "alignment": "ALIGNED" if "poi_aligned" in confluences else "NOT_ALIGNED",
            "rule_refs": ["1.2"],
        },
        "setup": {
            "name": "ICT_HUB_SETUP" if hub_decision.poi else "NO_SETUP",
            "type": "ICT_HUB",
            "entry_price": hub_decision.entry,
            "entry_type": "LIMIT" if hub_decision.entry is not None else None,
            "stop_loss": hub_decision.sl,
            "take_profit": [hub_decision.tp] if hub_decision.tp is not None else None,
            "invalidation_point": hub_decision.sl,
            "is_counter_trend": False,
            "confluence_score": confluence_score,
            "rule_refs": all_refs,
        },
        "risk": {
            "account_balance": float(risk_meta.get("account_balance", 10000.0)),
            "risk_pct": risk_pct,
            "position_size": float(hub_decision.size or 0.0),
            "rr": hub_decision.rr,
        },
        "checklist": {
            "htf_bias_exists": "htf_bias_confirmed" in confluences,
            "ltf_mss": "displacement_detected" in confluences,
            "pd_alignment": "poi_aligned" in confluences,
            "liquidity_sweep_detected": "liquidity_draw_identified" in confluences,
            "session_ok": "killzone_valid" in confluences and "outside_utc_killzone" not in vetoes,
            "news_ok": not any("news" in v for v in vetoes),
            "rr_minimum_met": "rr_gate_passed" in confluences,
        },
        "explanation": hub_decision.reason,
        "graph_nodes_triggered": all_refs,
        "confidence": 0.85 if hub_decision.status == "active" else 0.6 if hub_decision.status == "pending" else 0.35,
    }
