from trading_agent.config import Settings, WatchlistEntry, _parse_watchlist


def test_parse_watchlist_defaults_to_cad_tsx():
    entries = _parse_watchlist("SHOP")
    assert entries == [WatchlistEntry("SHOP", "CAD", "SMART", "TSE")]


def test_parse_watchlist_full_entry():
    entries = _parse_watchlist("AAPL:USD:SMART:NASDAQ")
    assert entries == [WatchlistEntry("AAPL", "USD", "SMART", "NASDAQ")]


def test_parse_watchlist_multiple_entries_and_whitespace():
    entries = _parse_watchlist(" SHOP , AAPL:USD:SMART:NASDAQ ")
    assert entries == [
        WatchlistEntry("SHOP", "CAD", "SMART", "TSE"),
        WatchlistEntry("AAPL", "USD", "SMART", "NASDAQ"),
    ]


def test_settings_from_env_defaults_are_safe(monkeypatch):
    for key in [
        "IB_HOST", "IB_PORT", "IB_CLIENT_ID", "MARKET_DATA_TYPE", "WATCHLIST",
        "LLM_MODEL", "MAX_ORDER_VALUE", "MAX_POSITION_VALUE", "MAX_DAILY_TRADES",
        "MAX_TOTAL_EXPOSURE_PCT", "DRY_RUN",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = Settings.from_env()

    assert settings.dry_run is True
    assert settings.ib_port == 7497  # TWS paper trading port
    assert settings.watchlist == [WatchlistEntry("SHOP", "CAD", "SMART", "TSE")]


def test_settings_from_env_respects_overrides(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("MAX_DAILY_TRADES", "3")

    settings = Settings.from_env()

    assert settings.dry_run is False
    assert settings.max_daily_trades == 3
