"""Deterministic tool wrappers for the hub with required function names."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.mt5_service import get_mt5_service
from app.tools.liquidity import identify_liquidity_pools
from app.tools.pd_arrays import detect_fvg, detect_order_blocks
from app.tools.structure import detect_mss


def _normalize_tf(timeframe: str) -> str:
    tf = (timeframe or "").upper()
    aliases = {
        "D": "1D",
        "H1": "1H",
        "H4": "4H",
        "M15": "15M",
        "M5": "5M",
        "M1": "1M",
    }
    return aliases.get(tf, tf)


def utc_to_est_hhmm(utc_now: datetime) -> str:
    """Approximate EST HH:MM from UTC timestamp."""

    est_hour = (utc_now.hour - 5) % 24
    return f"{est_hour:02d}:{utc_now.minute:02d}"


def get_candles(symbol: str, timeframe: str, n: int) -> List[Dict[str, Any]]:
    """Fetch candles from MT5 with normalized timeframe."""

    mt5 = get_mt5_service()
    tf = _normalize_tf(timeframe)
    if not mt5.is_connected and mt5.is_available:
        mt5.connect()
    return mt5.get_latest_bars(symbol, tf, n)


def find_fvg(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find active and historical fair value gaps."""

    fvgs = detect_fvg(candles)
    unmitigated = [f for f in fvgs if not f.get("filled", False)]
    return {
        "count": len(fvgs),
        "unmitigated_fvg": unmitigated,
        "all": fvgs,
    }


def find_ob(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find order blocks with consistent output naming."""

    obs = detect_order_blocks(candles)
    bullish = [ob for ob in obs if ob.get("type") == "BULLISH_OB"]
    bearish = [ob for ob in obs if ob.get("type") == "BEARISH_OB"]
    return {
        "count": len(obs),
        "bullish_ob": bullish,
        "bearish_ob": bearish,
        "all": obs,
    }


def find_liquidity(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find buy/sell-side liquidity pools and nearest draw targets."""

    pools = identify_liquidity_pools(candles)
    bsl = pools.get("buy_side_liquidity", [])
    ssl = pools.get("sell_side_liquidity", [])
    return {
        "BSL": bsl,
        "SSL": ssl,
        "draw_target": {
            "buy_side": bsl[0] if bsl else None,
            "sell_side": ssl[0] if ssl else None,
        },
        "observation": pools.get("observation", ""),
    }


def detect_bos_choch(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Detect MSS-compatible structure events mapped to BOS/CHoCH naming."""

    mss = detect_mss(candles)
    if not mss:
        return {"event": None, "direction": None, "details": None}

    mss_type = mss.get("type", "")
    direction = "bullish" if "BULLISH" in mss_type else "bearish"
    return {
        "event": "CHOCH",
        "direction": direction,
        "details": mss,
    }


def get_session_window(utc_now: datetime) -> Dict[str, Any]:
    """Return strict UTC kill-zone status for London/NY windows."""

    hour = utc_now.hour
    minute = utc_now.minute

    london = (hour > 2 or (hour == 2 and minute >= 0)) and (hour < 5)
    ny = (hour > 7 or (hour == 7 and minute >= 0)) and (hour < 10)

    if london:
        name = "London kill zone"
    elif ny:
        name = "NY kill zone"
    else:
        name = "outside-killzone"

    return {
        "session": name,
        "in_killzone": london or ny,
        "utc": utc_now.isoformat() + "Z",
        "windows": {
            "london": {"start": "02:00", "end": "05:00"},
            "ny": {"start": "07:00", "end": "10:00"},
        },
    }


def calculate_position_size(balance: float, risk_pct: float, sl_pips: float) -> float:
    """Simple deterministic FX lot-size approximation."""

    if balance <= 0 or risk_pct <= 0 or sl_pips <= 0:
        return 0.0

    risk_amount = balance * (risk_pct / 100.0)
    pip_value_per_lot = 10.0
    lots = risk_amount / (sl_pips * pip_value_per_lot)
    return round(max(lots, 0.0), 4)


def log_trade(journal_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility wrapper; actual persistence is handled by HubJournal."""

    return {"accepted": True, "journal_entry": journal_entry}
