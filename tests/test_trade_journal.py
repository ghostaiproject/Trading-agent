import json
from pathlib import Path

import pytest

from trading_agent.llm_advisor import TradeProposal
from trading_agent.trade_journal import TradeJournal


@pytest.fixture
def journal(tmp_path):
    journal = TradeJournal(journal_dir=str(tmp_path))
    yield journal


def test_record_prediction(journal):
    proposal = TradeProposal(symbol="SHOP", action="buy", quantity=10, confidence=0.8, rationale="test")
    snapshots = {"SHOP": {"last_price": 100.0}}

    journal.record_prediction(proposal, snapshots)

    with journal.journal_path.open() as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == "prediction"
        assert entry["symbol"] == "SHOP"
        assert entry["action"] == "buy"
        assert entry["confidence"] == 0.8


def test_record_outcome(journal):
    journal.record_outcome("SHOP", "buy", 10, 100.0, 105.0)

    with journal.journal_path.open() as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == "outcome"
        assert entry["symbol"] == "SHOP"
        assert entry["pnl"] == 50.0  # (105 - 100) * 10


def test_get_performance_summary_empty(journal):
    summary = journal.get_performance_summary()
    assert summary["total_trades"] == 0
    assert summary["win_rate"] == 0.0


def test_get_performance_summary_with_data(journal):
    proposal = TradeProposal(symbol="SHOP", action="buy", quantity=10, confidence=0.8, rationale="test")
    snapshots = {"SHOP": {"last_price": 100.0}}
    journal.record_prediction(proposal, snapshots)
    journal.record_outcome("SHOP", "buy", 10, 100.0, 105.0)

    summary = journal.get_performance_summary(days=30)
    assert summary["total_trades"] == 1
    assert summary["total_pnl"] == 50.0


def test_was_correct_buy_positive_pnl(journal):
    prediction = {"action": "buy"}
    outcome = {"pnl": 50.0}
    assert TradeJournal._was_correct(prediction, outcome) is True


def test_was_correct_buy_negative_pnl(journal):
    prediction = {"action": "buy"}
    outcome = {"pnl": -50.0}
    assert TradeJournal._was_correct(prediction, outcome) is False


def test_format_for_prompt_no_history(journal):
    result = journal.format_for_prompt()
    assert "No recent prediction history available" in result


def test_format_for_prompt_with_data(journal):
    proposal = TradeProposal(symbol="SHOP", action="buy", quantity=10, confidence=0.8, rationale="test")
    snapshots = {"SHOP": {"last_price": 100.0}}
    journal.record_prediction(proposal, snapshots)
    journal.record_outcome("SHOP", "buy", 10, 100.0, 105.0)

    result = journal.format_for_prompt()
    assert "SHOP" in result
    assert "BUY" in result
