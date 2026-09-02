"""Read-only FastAPI server for the trading dashboard.

Serves account state, positions, and decision logs to a frontend.
Runs independently of the trading loop — safe to restart without affecting trades.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .broker import IBKRBroker, AccountState, Position
from .config import Settings

app = FastAPI(title="Trading Agent Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings.from_env()
log_dir = Path("logs")


class DashboardState(BaseModel):
    timestamp: str
    account: Dict[str, float]
    positions: Dict[str, Dict[str, Any]]
    recent_decisions: List[Dict[str, Any]]


class CachedBrokerData:
    """Lazy-load broker data and cache it to avoid hammering IBKR."""

    def __init__(self):
        self.broker: Optional[IBKRBroker] = None
        self.last_update = 0.0
        self.cache_ttl = 30  # seconds

    def ensure_connected(self):
        if self.broker is None:
            self.broker = IBKRBroker(settings)
            try:
                self.broker.connect()
            except Exception as e:
                print(f"Warning: could not connect to broker: {e}")
                self.broker = None

    def get_account_and_positions(self) -> tuple[Optional[AccountState], Optional[Dict[str, Position]]]:
        now = time.time()
        if now - self.last_update < self.cache_ttl:
            if hasattr(self, '_cached_account') and hasattr(self, '_cached_positions'):
                return self._cached_account, self._cached_positions

        self.ensure_connected()
        if self.broker is None:
            return None, None

        try:
            account = self.broker.get_account_state()
            positions = self.broker.get_positions()
            self._cached_account = account
            self._cached_positions = positions
            self.last_update = now
            return account, positions
        except Exception as e:
            print(f"Error fetching broker data: {e}")
            return None, None


broker_cache = CachedBrokerData()


def read_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Read the most recent N lines from today's decision log."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"decisions-{day}.jsonl"

    if not log_file.exists():
        return []

    lines = []
    try:
        with log_file.open("r") as f:
            lines = [json.loads(line) for line in f.readlines()]
    except Exception as e:
        print(f"Error reading logs: {e}")
        return []

    return lines[-limit:]


@app.get("/api/state", response_model=DashboardState)
def get_dashboard_state() -> DashboardState:
    """Return current account state, positions, and recent decisions."""
    account, positions = broker_cache.get_account_and_positions()

    account_dict = {}
    if account:
        account_dict = {
            "net_liquidation": account.net_liquidation,
            "cash_balance": account.cash_balance,
            "buying_power": account.buying_power,
        }

    positions_dict = {}
    if positions:
        positions_dict = {
            sym: {
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "market_price": pos.market_price,
                "market_value": pos.market_value,
            }
            for sym, pos in positions.items()
        }

    recent_decisions = read_recent_logs(limit=100)

    return DashboardState(
        timestamp=datetime.now(timezone.utc).isoformat(),
        account=account_dict,
        positions=positions_dict,
        recent_decisions=recent_decisions,
    )


@app.get("/api/health")
def health():
    """Liveness check."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn

    print("Starting dashboard API on http://127.0.0.1:8000")
    print("Logs will be tailed from:", log_dir)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
