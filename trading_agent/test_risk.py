import pytest

from trading_agent.broker import AccountState, Position
from trading_agent.config import Settings, WatchlistEntry
from trading_agent.llm_advisor import TradeProposal
from trading_agent.risk import RiskManager


@pytest.fixture
def settings():
    return Settings(
        ib_host="127.0.0.1",
        ib_port=7497,
        ib_client_id=7,
        market_data_type=3,
        watchlist=[WatchlistEntry("SHOP")],
        llm_model="claude-opus-5",
        max_order_value=2000.0,
        max_position_value=5000.0,
        max_daily_trades=2,
        max_total_exposure_pct=50.0,
        dry_run=True,
        auto_approve_below=0.0,
    )


@pytest.fixture
def account():
    return AccountState(net_liquidation=10000.0, cash_balance=4000.0, buying_power=8000.0)


def make_proposal(action="buy", quantity=10, symbol="SHOP"):
    return TradeProposal(symbol=symbol, action=action, quantity=quantity, confidence=0.7, rationale="test")


def test_hold_always_passes(settings, account):
    risk_mgr = RiskManager(settings)
    result = risk_mgr.evaluate(make_proposal(action="hold", quantity=0), account, {}, reference_price=100.0)
    assert result.approved


def test_buy_within_limits_is_approved(settings, account):
    risk_mgr = RiskManager(settings)
    result = risk_mgr.evaluate(make_proposal(quantity=10), account, {}, reference_price=100.0)
    assert result.approved


def test_buy_exceeding_max_order_value_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    # 30 * 100 = 3000 > max_order_value of 2000
    result = risk_mgr.evaluate(make_proposal(quantity=30), account, {}, reference_price=100.0)
    assert not result.approved
    assert "max order value" in result.reason


def test_buy_exceeding_cash_balance_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    # 19 * 100 = 1900 < max_order_value, but > 4000 cash is fine; force scarcity via low cash
    account.cash_balance = 500.0
    result = risk_mgr.evaluate(make_proposal(quantity=10), account, {}, reference_price=100.0)
    assert not result.approved
    assert "available cash" in result.reason


def test_buy_exceeding_max_position_value_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    positions = {"SHOP": Position(symbol="SHOP", quantity=40, avg_cost=100.0, market_price=100.0, market_value=4000.0)}
    # existing 4000 + new 1000 = 5000, at the edge; push over with quantity 15 => 1500
    result = risk_mgr.evaluate(make_proposal(quantity=15), account, positions, reference_price=100.0)
    assert not result.approved
    assert "max position value" in result.reason


def test_buy_exceeding_total_exposure_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    positions = {"SHOP": Position(symbol="SHOP", quantity=40, avg_cost=100.0, market_price=100.0, market_value=4000.0)}
    account.net_liquidation = 10000.0
    # projected exposure 4000 + 1000 = 5000 = 50%, still fine; bump to 60% with more shares
    result = risk_mgr.evaluate(make_proposal(quantity=19), account, positions, reference_price=100.0)
    assert not result.approved
    assert "exposure" in result.reason or "max position value" in result.reason


def test_sell_more_than_held_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    positions = {"SHOP": Position(symbol="SHOP", quantity=5, avg_cost=100.0, market_price=100.0, market_value=500.0)}
    result = risk_mgr.evaluate(make_proposal(action="sell", quantity=10), account, positions, reference_price=100.0)
    assert not result.approved
    assert "only 5 held" in result.reason


def test_sell_within_held_quantity_is_approved(settings, account):
    risk_mgr = RiskManager(settings)
    positions = {"SHOP": Position(symbol="SHOP", quantity=10, avg_cost=100.0, market_price=100.0, market_value=1000.0)}
    result = risk_mgr.evaluate(make_proposal(action="sell", quantity=5), account, positions, reference_price=100.0)
    assert result.approved


def test_sell_with_no_position_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    result = risk_mgr.evaluate(make_proposal(action="sell", quantity=5), account, {}, reference_price=100.0)
    assert not result.approved
    assert "only 0 held" in result.reason


def test_daily_trade_limit_is_enforced(settings, account):
    risk_mgr = RiskManager(settings)
    risk_mgr.record_trade()
    risk_mgr.record_trade()  # max_daily_trades is 2
    result = risk_mgr.evaluate(make_proposal(quantity=5), account, {}, reference_price=100.0)
    assert not result.approved
    assert "daily trade limit" in result.reason


def test_reset_daily_counter_clears_limit(settings, account):
    risk_mgr = RiskManager(settings)
    risk_mgr.record_trade()
    risk_mgr.record_trade()
    risk_mgr.reset_daily_counter()
    result = risk_mgr.evaluate(make_proposal(quantity=5), account, {}, reference_price=100.0)
    assert result.approved


def test_missing_reference_price_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    result = risk_mgr.evaluate(make_proposal(quantity=5), account, {}, reference_price=0.0)
    assert not result.approved
    assert "reference price" in result.reason


def test_non_positive_quantity_is_rejected(settings, account):
    risk_mgr = RiskManager(settings)
    result = risk_mgr.evaluate(make_proposal(quantity=0), account, {}, reference_price=100.0)
    assert not result.approved
