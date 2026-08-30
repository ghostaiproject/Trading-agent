from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


@dataclass(frozen=True)
class WatchlistEntry:
    """One tradeable instrument. Defaults assume a Canadian equity on the TSX."""

    symbol: str
    currency: str = "CAD"
    exchange: str = "SMART"
    primary_exchange: str = "TSE"


def _parse_watchlist(raw: str) -> List[WatchlistEntry]:
    """Parses `WATCHLIST=SHOP:CAD:SMART:TSE,AAPL:USD:SMART:NASDAQ`."""
    entries = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        symbol = parts[0]
        currency = parts[1] if len(parts) > 1 and parts[1] else "CAD"
        exchange = parts[2] if len(parts) > 2 and parts[2] else "SMART"
        default_primary = "TSE" if currency == "CAD" else ""
        primary_exchange = parts[3] if len(parts) > 3 and parts[3] else default_primary
        entries.append(WatchlistEntry(symbol, currency, exchange, primary_exchange))
    return entries


@dataclass(frozen=True)
class Settings:
    ib_host: str
    ib_port: int
    ib_client_id: int
    market_data_type: int
    watchlist: List[WatchlistEntry]
    llm_model: str
    max_order_value: float
    max_position_value: float
    max_daily_trades: int
    max_total_exposure_pct: float
    dry_run: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            ib_host=os.getenv("IB_HOST", "127.0.0.1"),
            # 7497 = TWS paper trading, 7496 = TWS live, 4002 = IB Gateway paper, 4001 = IB Gateway live
            ib_port=_get_int("IB_PORT", 7497),
            ib_client_id=_get_int("IB_CLIENT_ID", 7),
            # 1 = live market data, 3 = delayed (no market data subscription required)
            market_data_type=_get_int("MARKET_DATA_TYPE", 3),
            watchlist=_parse_watchlist(os.getenv("WATCHLIST", "SHOP:CAD:SMART:TSE")),
            llm_model=os.getenv("LLM_MODEL", "claude-opus-5"),
            max_order_value=_get_float("MAX_ORDER_VALUE", 2000.0),
            max_position_value=_get_float("MAX_POSITION_VALUE", 5000.0),
            max_daily_trades=_get_int("MAX_DAILY_TRADES", 5),
            max_total_exposure_pct=_get_float("MAX_TOTAL_EXPOSURE_PCT", 50.0),
            # Safe by default: no real order reaches the broker until DRY_RUN=false is set explicitly.
            dry_run=_get_bool("DRY_RUN", True),
        )
