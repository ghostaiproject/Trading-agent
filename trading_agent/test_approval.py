from unittest.mock import patch

import pytest

from trading_agent.approval import ConsoleApprover
from trading_agent.config import Settings, WatchlistEntry
from trading_agent.llm_advisor import TradeProposal
from trading_agent.risk import RiskResult


def make_settings(auto_approve_below: float = 0.0) -> Settings:
    return Settings(
        ib_host="127.0.0.1",
        ib_port=7497,
        ib_client_id=7,
        market_data_type=3,
        watchlist=[WatchlistEntry("SHOP")],
        llm_model="claude-opus-5",
        max_order_value=2000.0,
        max_position_value=5000.0,
        max_daily_trades=5,
        max_total_exposure_pct=50.0,
        dry_run=True,
        auto_approve_below=auto_approve_below,
    )


def make_proposal(quantity: int = 5) -> TradeProposal:
    return TradeProposal(symbol="SHOP", action="buy", quantity=quantity, confidence=0.7, rationale="test")


def test_threshold_disabled_by_default_always_prompts():
    approver = ConsoleApprover(make_settings(auto_approve_below=0.0))
    with patch("builtins.input", return_value="y") as mock_input:
        approved, method = approver.confirm(make_proposal(5), RiskResult(True, "ok"), reference_price=10.0)

    assert approved is True
    assert method == "human"
    mock_input.assert_called_once()


def test_order_under_threshold_auto_approves_without_prompting():
    # order value = 5 * 10.0 = 50.0, under the 100.0 threshold
    approver = ConsoleApprover(make_settings(auto_approve_below=100.0))
    with patch("builtins.input") as mock_input:
        approved, method = approver.confirm(make_proposal(5), RiskResult(True, "ok"), reference_price=10.0)

    assert approved is True
    assert method == "auto_threshold"
    mock_input.assert_not_called()


def test_order_exactly_at_threshold_auto_approves():
    # order value = 5 * 10.0 = 50.0, threshold is inclusive
    approver = ConsoleApprover(make_settings(auto_approve_below=50.0))
    with patch("builtins.input") as mock_input:
        approved, method = approver.confirm(make_proposal(5), RiskResult(True, "ok"), reference_price=10.0)

    assert approved is True
    assert method == "auto_threshold"
    mock_input.assert_not_called()


def test_order_over_threshold_still_prompts_and_can_be_rejected():
    # order value = 5 * 10.0 = 50.0, over the 10.0 threshold
    approver = ConsoleApprover(make_settings(auto_approve_below=10.0))
    with patch("builtins.input", return_value="n") as mock_input:
        approved, method = approver.confirm(make_proposal(5), RiskResult(True, "ok"), reference_price=10.0)

    assert approved is False
    assert method == "human"
    mock_input.assert_called_once()


def test_negative_threshold_behaves_as_disabled():
    approver = ConsoleApprover(make_settings(auto_approve_below=-5.0))
    with patch("builtins.input", return_value="y") as mock_input:
        approved, method = approver.confirm(make_proposal(5), RiskResult(True, "ok"), reference_price=10.0)

    assert method == "human"
    mock_input.assert_called_once()
