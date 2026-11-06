# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An LLM-assisted trading agent for Canadian equities, trading live through
Interactive Brokers (IBKR) with a human-approval gate on every order. See
`README.md` for the full pipeline description and setup steps.

**This can place real trades with real money.** Any change to `trading_agent/risk.py`,
the `DRY_RUN` default in `trading_agent/config.py`, or the approval flow in
`trading_agent/approval.py` needs extra scrutiny — these are the safety
boundaries, not incidental code.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # installs runtime deps + pytest

pytest                                 # run the full test suite
pytest tests/test_risk.py              # single file
pytest tests/test_risk.py::test_daily_trade_limit_is_enforced  # single test

python -m trading_agent.main           # one decision cycle
python -m trading_agent.main --loop --interval 900   # repeat every 15 min
```

There is no lint/format tooling configured yet. Tests are pure unit tests
(risk logic, config parsing, LLM advisor request/response shape via mocks) —
none of them touch a live broker or the Anthropic API. There's no automated
coverage of the IBKR integration itself; it requires a running TWS/IB Gateway
instance, so verify changes to `broker.py` manually against a paper account.

## Architecture

Six modules, wired together by `trading_agent/main.py::run_cycle`, run once
per cycle in this order:

1. **`broker.py` (`IBKRBroker`)** — owns the `ib_async` connection to
   TWS/IB Gateway. Pulls `AccountState`, `Position`s, and `MarketSnapshot`s
   (last/bid/ask + 30 days of daily closes) for the configured watchlist, and
   submits orders. Each `MarketSnapshot` now includes computed technical
   indicators (RSI, 20-day/50-day moving averages). `place_order` is a no-op
   (returns `None`, contacts nothing) whenever `settings.dry_run` is true — this
   is the mechanism, not just documentation, that keeps dry-run safe.
2. **`llm_advisor.py` (`LLMAdvisor`)** — builds one text prompt from the
   account/positions/snapshots/technical indicators/historical performance and
   calls `client.messages.parse(..., output_format=TradeDecision)` against
   `claude-opus-5`, guaranteeing a structured `TradeDecision` (one
   `TradeProposal` per watchlist symbol, incl. holds) back — no manual JSON
   parsing. Optionally fetches real-time market intelligence (news, earnings,
   analyst ratings) via web search for each symbol to enrich the context.
3. **`risk.py` (`RiskManager`)** — the real gatekeeper. Every non-hold
   proposal is checked against hard limits (max order value, max position
   value, cash on hand, held quantity for sells, total exposure %, daily
   trade count) *independent of what the LLM said*. This check runs even in
   dry-run, so dry-run logs reflect what would have been rejected live too.
4. **`approval.py` (`ConsoleApprover`)** — blocks on a terminal `y/N` prompt
   per proposal that passes risk checks. There is currently no non-interactive
   approval path by design; if one is ever added, treat it as a safety-policy
   decision, not a refactor.
5. **`trade_log.py` (`TradeLog`)** — appends every proposal, risk result,
   human decision, and order outcome as one JSON line to
   `logs/decisions-<UTC date>.jsonl`. This is the audit trail if something
   goes wrong; new event types should go through `TradeLog.record`, not a
   separate logging path.
6. **`trade_journal.py` (`TradeJournal`)** — tracks trade predictions vs
   actual outcomes in `logs/trade-journal.jsonl`, enabling the agent to learn
   from its own historical performance. The journal is queried at the start
   of each cycle to provide Claude with recent P&L results and win rates,
   shaping future decisions. Each prediction records entry price and confidence;
   outcomes are recorded as they close with P&L and performance metrics.

`config.py` (`Settings.from_env`) is the single source of truth for all
tunables (loaded via `python-dotenv` from `.env`); nothing else should read
`os.environ` directly. `WatchlistEntry` parsing (`SYMBOL:CURRENCY:EXCHANGE:
PRIMARY_EXCHANGE`, defaulting to a TSX-listed CAD stock) lives there too.

Claude now sees comprehensive market analysis including:
- **Price Data**: Current price, bid/ask spreads, 30-day history
- **Technical Indicators**: RSI, moving averages (20/50/200-day), Bollinger Bands, MACD
- **Volatility & Momentum**: 30-day volatility, 14-day momentum, trend strength
- **Price Levels**: Support/resistance, price position in trading range
- **Investment Scoring**: Composite -10 to +10 score integrating all signals
- **Risk/Reward Analysis**: Automatic assessment of upside vs downside
- **Position Sizing**: Volatility-adjusted position size suggestions
- **Historical Performance**: Win rates and P&L from past trades
- **Real-time Intelligence**: Optional news, earnings, analyst ratings via web search

The prompt encourages Claude to look for confluence (multiple signals aligning),
trade with the trend, size positions based on volatility, and only take trades
with favorable risk/reward ratios. Claude learns from its own outcomes to improve.
