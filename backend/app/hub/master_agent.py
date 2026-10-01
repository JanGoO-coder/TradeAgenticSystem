"""Master trading agent orchestrator for the agentic ICT hub."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.domain.hub import (
    HubCallMetrics,
    HubDecisionRequest,
    HubDecisionResponse,
)
from app.hub.journal import HubJournal
from app.hub.llm_harness import HubLLMHarness
from app.hub.risk_engine import PropFirmRiskEngine
from app.hub.state import SessionStateCompact
from app.hub.subagents.entry_confirmation_agent import EntryConfirmationAgent
from app.hub.subagents.fvg_poi_agent import FVGPOIAgent
from app.hub.subagents.liquidity_agent import LiquidityAgent
from app.hub.subagents.market_structure_agent import MarketStructureAgent
from app.hub.subagents.session_agent import SessionAgent
from app.hub.tools import calculate_position_size, get_candles


class MasterTradingAgent:
    """Single decision-maker that coordinates deterministic sub-agents and LLM gating."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._state: Dict[str, SessionStateCompact] = {}

        self.market_structure_agent = MarketStructureAgent()
        self.liquidity_agent = LiquidityAgent()
        self.fvg_poi_agent = FVGPOIAgent()
        self.session_agent = SessionAgent()
        self.entry_confirmation_agent = EntryConfirmationAgent()

        self.risk_engine = PropFirmRiskEngine()
        self.llm_harness = HubLLMHarness()
        self.journal = HubJournal()

    def _get_state(self, symbol: str) -> SessionStateCompact:
        if symbol not in self._state:
            self._state[symbol] = SessionStateCompact(symbol=symbol)
        return self._state[symbol]

    @staticmethod
    def _utc_now(ts: Optional[datetime]) -> datetime:
        if ts is None:
            return datetime.utcnow()
        if ts.tzinfo is not None:
            return ts.astimezone(timezone.utc).replace(tzinfo=None)
        return ts

    @staticmethod
    def _normalize_bars(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for c in candles:
            item = dict(c)
            if "time" not in item and "timestamp" in item:
                item["time"] = item["timestamp"]
            if "timestamp" not in item and "time" in item:
                item["timestamp"] = item["time"]
            normalized.append(item)
        return normalized

    @staticmethod
    def _latest_marker(candles: List[Dict[str, Any]]) -> str:
        if not candles:
            return ""
        last = candles[-1]
        marker = last.get("time") or last.get("timestamp")
        if marker is None:
            return ""
        return str(marker)

    def _collect_timeframes(self, request: HubDecisionRequest) -> Dict[str, List[Dict[str, Any]]]:
        source = request.timeframe_bars or {}
        aliases = {
            "1D": ["1D", "D1", "D"],
            "4H": ["4H", "H4"],
            "1H": ["1H", "H1"],
            "15M": ["15M", "M15"],
            "5M": ["5M", "M5"],
            "1M": ["1M", "M1"],
        }
        defaults = {
            "1D": 80,
            "4H": 120,
            "1H": self.settings.htf_bar_count,
            "15M": self.settings.ltf_bar_count,
            "5M": self.settings.micro_bar_count,
            "1M": max(120, self.settings.micro_bar_count * 2),
        }

        out: Dict[str, List[Dict[str, Any]]] = {}
        for tf, keys in aliases.items():
            bars: List[Dict[str, Any]] = []
            for key in keys:
                if key in source and source[key]:
                    bars = self._normalize_bars(source[key])
                    break
            if not bars:
                bars = self._normalize_bars(get_candles(request.symbol, tf, int(defaults[tf])))
            out[tf] = bars
        return out

    @staticmethod
    def _hash_payload(payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _current_price(candles: Dict[str, List[Dict[str, Any]]]) -> float:
        for tf in ("1M", "5M", "15M", "1H", "4H", "1D"):
            bars = candles.get(tf, [])
            if bars:
                return float(bars[-1].get("close", 0.0) or 0.0)
        return 0.0

    @staticmethod
    def _poi_label(poi: Optional[Dict[str, Any]]) -> Optional[str]:
        if not poi:
            return None
        tf = poi.get("timeframe", "M15")
        kind = poi.get("kind", "POI")
        top = poi.get("top")
        bottom = poi.get("bottom")
        if top is None or bottom is None:
            return f"{tf} {kind}"
        low = min(float(top), float(bottom))
        high = max(float(top), float(bottom))
        return f"{tf} {kind} {low:.5f}-{high:.5f}"

    @staticmethod
    def _build_draw_label(bias: str, draw_target: Optional[Dict[str, Any]]) -> str:
        if not draw_target:
            return "none"
        if bias == "bullish":
            target = draw_target.get("buy_side")
            if target and target.get("price") is not None:
                return f"BSL at {float(target['price']):.5f}"
        elif bias == "bearish":
            target = draw_target.get("sell_side")
            if target and target.get("price") is not None:
                return f"SSL at {float(target['price']):.5f}"
        side = draw_target.get("buy_side") or draw_target.get("sell_side")
        if side and side.get("price") is not None:
            return f"Liquidity at {float(side['price']):.5f}"
        return "none"

    @staticmethod
    def _candidate_from_poi(poi: Dict[str, Any], bias: str, rr_target: float) -> Dict[str, float]:
        top = float(poi.get("top") or poi.get("midpoint") or 0.0)
        bottom = float(poi.get("bottom") or poi.get("midpoint") or 0.0)
        if top == 0.0 and bottom == 0.0:
            return {"entry": 0.0, "sl": 0.0, "tp": 0.0, "rr": 0.0, "sl_pips": 0.0}

        entry = float(poi.get("midpoint") or ((top + bottom) / 2.0))
        low = min(top, bottom)
        high = max(top, bottom)
        buffer_price = 0.0002

        if bias == "bullish":
            sl = low - buffer_price
            risk = entry - sl
            tp = entry + (risk * rr_target)
        else:
            sl = high + buffer_price
            risk = sl - entry
            tp = entry - (risk * rr_target)

        rr = abs(tp - entry) / abs(entry - sl) if entry != sl else 0.0
        sl_pips = abs(entry - sl) * 10000
        return {
            "entry": round(entry, 5),
            "sl": round(sl, 5),
            "tp": round(tp, 5),
            "rr": round(rr, 2),
            "sl_pips": round(sl_pips, 2),
        }

    @staticmethod
    def _to_open_trade_dicts(open_trades: List[Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for t in open_trades:
            if hasattr(t, "model_dump"):
                out.append(t.model_dump())
            elif isinstance(t, dict):
                out.append(t)
        return out

    @staticmethod
    def _manage_open_trades(open_trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        for trade in open_trades:
            current_price = trade.get("current_price")
            entry = trade.get("entry")
            sl = trade.get("stop_loss")
            direction = trade.get("direction")
            if current_price is None or entry is None or sl is None or direction not in {"LONG", "SHORT"}:
                continue

            risk = abs(float(entry) - float(sl))
            if risk <= 0:
                continue

            if direction == "LONG":
                r_multiple = (float(current_price) - float(entry)) / risk
            else:
                r_multiple = (float(entry) - float(current_price)) / risk

            if r_multiple >= 1.0 and not trade.get("moved_to_be", False):
                actions.append(
                    {
                        "symbol": trade.get("symbol"),
                        "action": "move_sl_to_be",
                        "trigger_r": round(r_multiple, 2),
                    }
                )
            if r_multiple >= 2.0 and not trade.get("trailing_active", False):
                actions.append(
                    {
                        "symbol": trade.get("symbol"),
                        "action": "activate_trailing",
                        "trigger_r": round(r_multiple, 2),
                    }
                )
        return actions

    def _run_subagent_cached(
        self,
        *,
        state: SessionStateCompact,
        metrics: HubCallMetrics,
        cache_key: str,
        marker: str,
        fn,
    ) -> Dict[str, Any]:
        entry = state.get_subagent_cache(cache_key)
        if entry and entry.get("marker") == marker:
            metrics.cache_hits += 1
            return entry.get("result", {})

        metrics.cache_misses += 1
        metrics.subagent_calls += 1
        result = fn()
        state.set_subagent_cache(cache_key, {"marker": marker, "result": result})
        return result

    async def decision_cycle(self, request: HubDecisionRequest) -> HubDecisionResponse:
        """Execute one strict master-agent decision cycle."""

        state = self._get_state(request.symbol)
        candles = self._collect_timeframes(request)
        markers = {tf: self._latest_marker(bars) for tf, bars in candles.items()}
        metrics = HubCallMetrics()

        state_changed = request.force_recompute or state.last_decision_output is None
        for tf, marker in markers.items():
            if marker and state.last_candle_time_by_tf.get(tf) != marker:
                state_changed = True

        if not state_changed and state.last_decision_output:
            cached = HubDecisionResponse(**state.last_decision_output)
            cached.cache_hit = True
            cached.call_metrics.cache_hits += 1
            return cached

        utc_now = self._utc_now(request.timestamp)
        current_price = self._current_price(candles)
        open_trades = self._to_open_trade_dicts(request.open_trades)
        open_trade_actions = self._manage_open_trades(open_trades)

        session = self._run_subagent_cached(
            state=state,
            metrics=metrics,
            cache_key="session_agent",
            marker=utc_now.strftime("%Y%m%d%H%M"),
            fn=lambda: self.session_agent.run(utc_now=utc_now),
        )

        risk_eval = self.risk_engine.evaluate_cycle(
            symbol=request.symbol,
            account_balance=request.account_balance,
            open_trades=open_trades,
        )
        risk_pct = self.risk_engine.compute_effective_risk_pct(
            request.account_balance,
            request.risk_pct,
        )

        vetoes = list(risk_eval.vetoes)
        confluences: List[str] = []

        if session.get("in_killzone"):
            confluences.append("killzone_valid")
        else:
            vetoes.append("outside_utc_killzone")

        if vetoes:
            response = HubDecisionResponse(
                symbol=request.symbol,
                timestamp=utc_now.isoformat() + "Z",
                bias=state.bias,
                draw=state.draw_target or "none",
                poi=None,
                entry=None,
                sl=None,
                tp=None,
                rr=None,
                size=None,
                session=session.get("session", "outside-killzone"),
                status="no-trade",
                reason="Hard veto: risk/session gate failed",
                confluences=confluences,
                vetoes=vetoes,
                llm_called=False,
                cache_hit=False,
                call_metrics=metrics,
                metadata={
                    "open_trade_management": open_trade_actions,
                    "risk": {
                        "risk_pct": risk_pct,
                        "current_concurrent": risk_eval.current_concurrent_trades,
                    },
                },
            )
            journal_id = self.journal.log(request.symbol, response.model_dump())
            response.journal_id = journal_id
            state.last_decision_output = response.model_dump()
            state.last_decision_hash = self._hash_payload(
                {
                    "status": response.status,
                    "reason": response.reason,
                    "vetoes": response.vetoes,
                    "session": response.session,
                }
            )
            for tf, marker in markers.items():
                if marker:
                    state.update_candle_time(tf, marker)
            return response

        structure_marker = "|".join(markers.get(tf, "") for tf in ("1D", "4H", "1H"))
        structure = self._run_subagent_cached(
            state=state,
            metrics=metrics,
            cache_key="market_structure_agent",
            marker=structure_marker,
            fn=lambda: self.market_structure_agent.run(
                candles_d1=candles["1D"],
                candles_h4=candles["4H"],
                candles_h1=candles["1H"],
            ),
        )

        state.bias = structure.get("bias", "neutral")
        state.last_structure_event = structure.get("last_structure_event")

        bias = structure.get("bias", "neutral")
        if bias in {"bullish", "bearish"}:
            confluences.append("htf_bias_confirmed")
        else:
            vetoes.append("htf_bias_unconfirmed")

        liquidity_marker = "|".join(markers.get(tf, "") for tf in ("1H", "15M"))
        liquidity = self._run_subagent_cached(
            state=state,
            metrics=metrics,
            cache_key="liquidity_agent",
            marker=liquidity_marker,
            fn=lambda: self.liquidity_agent.run(candles_h1=candles["1H"], candles_m15=candles["15M"]),
        )

        draw_target = liquidity.get("draw_target")
        draw_label = self._build_draw_label(bias, draw_target)
        state.draw_target = draw_label
        if draw_label != "none":
            confluences.append("liquidity_draw_identified")
        else:
            vetoes.append("liquidity_draw_missing")

        poi_marker = "|".join(markers.get(tf, "") for tf in ("4H", "1H", "15M")) + f"|{bias}"
        poi_pack = self._run_subagent_cached(
            state=state,
            metrics=metrics,
            cache_key="fvg_poi_agent",
            marker=poi_marker,
            fn=lambda: self.fvg_poi_agent.run(
                candles_h4=candles["4H"],
                candles_h1=candles["1H"],
                candles_m15=candles["15M"],
                bias=bias,
            ),
        )
        top_poi = poi_pack.get("top_poi")
        state.active_pois = poi_pack.get("active_pois", [])

        if top_poi:
            confluences.append("poi_aligned")
        else:
            vetoes.append("poi_missing")

        candidate = (
            self._candidate_from_poi(top_poi, bias, self.settings.hub_rr_minimum)
            if top_poi
            else {"entry": None, "sl": None, "tp": None, "rr": None, "sl_pips": None}
        )

        rr_veto = self.risk_engine.enforce_rr(candidate.get("rr") if isinstance(candidate, dict) else None)
        if rr_veto:
            vetoes.append(rr_veto)
        else:
            confluences.append("rr_gate_passed")

        entry_marker = "|".join(markers.get(tf, "") for tf in ("5M", "1M")) + f"|{top_poi.get('timeframe') if top_poi else ''}"
        entry_confirmation = self._run_subagent_cached(
            state=state,
            metrics=metrics,
            cache_key="entry_confirmation_agent",
            marker=entry_marker,
            fn=lambda: self.entry_confirmation_agent.run(
                candles_m5=candles["5M"],
                candles_m1=candles["1M"],
                poi=top_poi,
                bias=bias,
            ),
        )

        if entry_confirmation.get("displacement"):
            confluences.append("displacement_detected")
        else:
            vetoes.append("displacement_missing")

        if entry_confirmation.get("mitigation"):
            confluences.append("poi_mitigation_seen")

        trigger_valid = bool(entry_confirmation.get("trigger_valid"))

        sl_pips = float(candidate.get("sl_pips") or 0.0)
        size = (
            calculate_position_size(
                balance=request.account_balance,
                risk_pct=risk_pct,
                sl_pips=sl_pips,
            )
            if sl_pips > 0
            else None
        )

        poi_label = self._poi_label(top_poi)
        llm_called = False
        status: str
        reason: str

        if vetoes:
            status = "no-trade"
            reason = "Hard veto: deterministic gates failed"
        elif not trigger_valid:
            status = "pending"
            reason = "Waiting for displacement/mitigation trigger at POI"
        else:
            llm_called = True
            metrics.llm_calls += 1
            llm_result = await self.llm_harness.arbitrate(
                {
                    "symbol": request.symbol,
                    "bias": bias,
                    "draw": draw_label,
                    "session": session.get("session"),
                    "candidate": candidate,
                    "confluences": confluences,
                    "vetoes": vetoes,
                    "pois": state.active_pois,
                }
            )
            status = llm_result.get("status", "active")
            reason = llm_result.get("reason", "Candidate validated")
            if status == "no-trade":
                vetoes.append("llm_consistency_veto")
            if status == "active":
                confluences.append("entry_trigger_confirmed")

        response = HubDecisionResponse(
            symbol=request.symbol,
            timestamp=utc_now.isoformat() + "Z",
            bias=bias,
            draw=draw_label,
            poi=poi_label,
            entry=candidate.get("entry"),
            sl=candidate.get("sl"),
            tp=candidate.get("tp"),
            rr=candidate.get("rr"),
            size=size,
            session=session.get("session", "outside-killzone"),
            status=status,  # type: ignore[arg-type]
            reason=reason,
            confluences=confluences,
            vetoes=vetoes,
            llm_called=llm_called,
            cache_hit=False,
            call_metrics=metrics,
            metadata={
                "risk": {
                    "risk_pct": risk_pct,
                    "rr_minimum": self.settings.hub_rr_minimum,
                    "daily_limit_pct": self.settings.hub_daily_loss_limit_pct,
                    "total_drawdown_limit_pct": self.settings.hub_total_drawdown_limit_pct,
                },
                "subagents": {
                    "session": session,
                    "structure": structure,
                    "liquidity": {
                        "draw_target": draw_target,
                        "equal_highs": len(liquidity.get("equal_highs", [])),
                        "equal_lows": len(liquidity.get("equal_lows", [])),
                    },
                    "entry_confirmation": entry_confirmation,
                },
                "open_trade_management": open_trade_actions,
            },
        )

        decision_hash = self._hash_payload(
            {
                "bias": response.bias,
                "draw": response.draw,
                "poi": response.poi,
                "status": response.status,
                "vetoes": response.vetoes,
                "markers": markers,
            }
        )

        response.metadata["state_hash"] = decision_hash
        journal_id = self.journal.log(request.symbol, response.model_dump())
        response.journal_id = journal_id

        state.last_decision_output = response.model_dump()
        state.last_decision_hash = decision_hash
        state.risk_lock = len(vetoes) > 0 and any("limit" in v for v in vetoes)
        state.in_killzone = bool(session.get("in_killzone"))
        state.open_trades = open_trades
        for tf, marker in markers.items():
            if marker:
                state.update_candle_time(tf, marker)

        return response

    def get_state(self, symbol: str) -> Dict[str, Any]:
        return self._get_state(symbol).to_dict()

    def get_journal(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self.journal.get_entries(symbol, limit=limit)

    def reset_symbol(self, symbol: str, balance: Optional[float] = None) -> Dict[str, Any]:
        if symbol in self._state:
            del self._state[symbol]
        self.journal.reset_symbol(symbol)
        self.risk_engine.reset_symbol(symbol, balance=balance)
        return {"symbol": symbol, "reset": True}


_master_agent: Optional[MasterTradingAgent] = None


async def get_master_agent() -> MasterTradingAgent:
    """Hub master-agent singleton."""

    global _master_agent
    if _master_agent is None:
        _master_agent = MasterTradingAgent()
    return _master_agent
