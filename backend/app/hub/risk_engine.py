"""Hard risk guards for the agentic ICT hub."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.config import get_settings


@dataclass
class RiskEvaluation:
    """Risk evaluation output for a decision cycle."""

    allowed: bool
    vetoes: List[str]
    risk_pct: float
    max_concurrent_trades: int
    current_concurrent_trades: int
    rr_minimum: float


class PropFirmRiskEngine:
    """Enforces hard risk constraints and no-trade locks."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._day_start_balance: Dict[str, float] = {}
        self._peak_balance: Dict[str, float] = {}
        self._session_loss_lock: Dict[str, bool] = {}

    @staticmethod
    def _symbol_tokens(symbol: str) -> set[str]:
        s = (symbol or "").upper()
        if len(s) >= 6 and s[:3].isalpha() and s[3:6].isalpha():
            return {s[:3], s[3:6]}
        return {s} if s else set()

    def _effective_concurrency(self, open_trades: List[Dict[str, Any]]) -> int:
        groups: List[set[str]] = []
        for trade in open_trades:
            tokens = self._symbol_tokens(str(trade.get("symbol", "")))
            if not tokens:
                continue
            merged = False
            for group in groups:
                if group.intersection(tokens):
                    group.update(tokens)
                    merged = True
                    break
            if not merged:
                groups.append(set(tokens))
        return len(groups)

    def evaluate_cycle(
        self,
        *,
        symbol: str,
        account_balance: float,
        open_trades: List[Dict[str, Any]],
    ) -> RiskEvaluation:
        vetoes: List[str] = []
        if symbol not in self._day_start_balance:
            self._day_start_balance[symbol] = account_balance

        if symbol not in self._peak_balance:
            self._peak_balance[symbol] = account_balance

        self._peak_balance[symbol] = max(self._peak_balance[symbol], account_balance)

        if self._session_loss_lock.get(symbol, False):
            vetoes.append("session_cooldown_after_loss")

        current_concurrent = self._effective_concurrency(open_trades)
        if current_concurrent >= self.settings.hub_max_concurrent_trades:
            vetoes.append("max_concurrent_trades_reached")

        day_start = self._day_start_balance[symbol]
        day_dd = ((day_start - account_balance) / day_start) * 100 if day_start > 0 else 0.0
        if day_dd >= self.settings.hub_daily_loss_limit_pct:
            vetoes.append("daily_loss_limit_halt")

        peak = self._peak_balance[symbol]
        global_dd = ((peak - account_balance) / peak) * 100 if peak > 0 else 0.0
        if global_dd >= self.settings.hub_total_drawdown_limit_pct:
            vetoes.append("global_drawdown_limit_halt")

        return RiskEvaluation(
            allowed=len(vetoes) == 0,
            vetoes=vetoes,
            risk_pct=self.settings.hub_risk_per_trade_pct,
            max_concurrent_trades=self.settings.hub_max_concurrent_trades,
            current_concurrent_trades=current_concurrent,
            rr_minimum=self.settings.hub_rr_minimum,
        )

    def enforce_rr(self, rr: Optional[float]) -> Optional[str]:
        if rr is None:
            return "rr_missing"
        if rr < self.settings.hub_rr_minimum:
            return "rr_below_minimum"
        return None

    def compute_effective_risk_pct(self, account_balance: float, base_risk_pct: Optional[float]) -> float:
        desired = base_risk_pct if base_risk_pct is not None else self.settings.hub_risk_per_trade_pct
        desired = min(desired, self.settings.hub_risk_cap_pct)

        peak = max(self._peak_balance.values()) if self._peak_balance else account_balance
        if peak > 0:
            progress_pct = ((account_balance - peak) / peak) * 100
        else:
            progress_pct = 0.0

        # Scale down near target if configured threshold is exceeded.
        if abs(progress_pct) <= self.settings.hub_scale_down_threshold_pct:
            desired = min(desired, self.settings.hub_risk_per_trade_pct)

        return desired

    def reset_symbol(self, symbol: str, *, balance: Optional[float] = None) -> None:
        if balance is not None:
            self._day_start_balance[symbol] = balance
            self._peak_balance[symbol] = balance
        else:
            self._day_start_balance.pop(symbol, None)
            self._peak_balance.pop(symbol, None)
        self._session_loss_lock.pop(symbol, None)

    def set_session_loss_lock(self, symbol: str, enabled: bool) -> None:
        self._session_loss_lock[symbol] = enabled
