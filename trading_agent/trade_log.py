from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class TradeLog:
    """Append-only JSONL audit trail: one file per UTC day, one line per event."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _path(self) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"decisions-{day}.jsonl"

    def record(self, event: Dict[str, Any]) -> None:
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
        with self._path().open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
