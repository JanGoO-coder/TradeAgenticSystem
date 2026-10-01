"""Decision and trade lifecycle journal for the hub."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from app.core.config import get_settings


class HubJournal:
    """Simple JSONL journal storage for hub decisions."""

    def __init__(self) -> None:
        settings = get_settings()
        self._root = Path(settings.backtest_sessions_dir).parent / "hub_journal"
        self._root.mkdir(parents=True, exist_ok=True)

    def _symbol_file(self, symbol: str) -> Path:
        safe_symbol = symbol.replace("/", "_").replace("\\", "_")
        return self._root / f"{safe_symbol}.jsonl"

    def log(self, symbol: str, entry: Dict[str, Any]) -> str:
        journal_id = entry.get("journal_id") or str(uuid4())[:12]
        payload = {
            "journal_id": journal_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "symbol": symbol,
            **entry,
        }
        path = self._symbol_file(symbol)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        return journal_id

    def get_entries(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        path = self._symbol_file(symbol)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        out: List[Dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(out))

    def reset_symbol(self, symbol: str) -> None:
        path = self._symbol_file(symbol)
        if path.exists():
            path.unlink()
