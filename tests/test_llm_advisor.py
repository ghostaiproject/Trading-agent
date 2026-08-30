from types import SimpleNamespace
from unittest.mock import MagicMock

from trading_agent.broker import AccountState, MarketSnapshot
from trading_agent.llm_advisor import LLMAdvisor, TradeDecision, TradeProposal


def test_get_trade_decision_calls_parse_and_returns_parsed_output():
    expected = TradeDecision(
        proposals=[TradeProposal(symbol="SHOP", action="hold", quantity=0, confidence=0.5, rationale="no signal")]
    )
    client = MagicMock()
    client.messages.parse.return_value = SimpleNamespace(parsed_output=expected)

    advisor = LLMAdvisor(client, "claude-opus-5")
    account = AccountState(net_liquidation=10000.0, cash_balance=4000.0, buying_power=8000.0)
    snapshots = {"SHOP": MarketSnapshot(symbol="SHOP", last_price=100.0, bid=99.9, ask=100.1, recent_closes=[98, 99, 100])}

    result = advisor.get_trade_decision(account, {}, snapshots)

    assert result == expected
    _, kwargs = client.messages.parse.call_args
    assert kwargs["model"] == "claude-opus-5"
    assert kwargs["output_format"] is TradeDecision
    assert "SHOP" in kwargs["messages"][0]["content"]


def test_build_prompt_includes_positions_and_snapshots():
    account = AccountState(net_liquidation=10000.0, cash_balance=4000.0, buying_power=8000.0)
    snapshots = {"SHOP": MarketSnapshot(symbol="SHOP", last_price=100.0, bid=99.9, ask=100.1, recent_closes=[98, 99, 100])}

    prompt = LLMAdvisor._build_prompt(account, {}, snapshots)

    assert "Net liquidation value: 10000.00" in prompt
    assert "none" in prompt
    assert "SHOP" in prompt
    assert "100.00" in prompt
