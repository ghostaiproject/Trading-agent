# Trading-agent

An LLM-assisted trading agent for Canadian equities. It connects to Interactive
Brokers, asks Claude to review your account, positions, and watchlist each
cycle, runs every proposal through hard risk limits, and then requires your
explicit approval before anything is submitted to your broker.

**This places real trades with real money once `DRY_RUN=false` is set.** Read
the whole README before doing that, and test thoroughly against an IBKR paper
trading account first.

## How it works

1. **Broker (`trading_agent/broker.py`)** — connects to TWS or IB Gateway via
   `ib_async`, pulls account state, current positions, and recent price data
   for your watchlist. Computes technical indicators (RSI, 20-day and 50-day
   moving averages) from 30 days of historical closes to give Claude better
   context. When not in dry-run, submits orders.
2. **LLM advisor (`trading_agent/llm_advisor.py`)** — sends a rich snapshot to
   Claude (`claude-opus-5` by default), including account state, positions,
   price data, technical indicators, recent trading performance from the
   journal, and optionally real-time market intelligence (news, earnings,
   analyst ratings fetched via web search). Returns one structured trade
   proposal per watchlist symbol (`buy`/`sell`/`hold`, quantity, order type,
   confidence, rationale).
3. **Risk manager (`trading_agent/risk.py`)** — independently checks every
   non-hold proposal against hard limits (max order value, max position
   value, available cash, held quantity for sells, total exposure %, and a
   daily trade cap) before it can go any further. This runs regardless of
   what the LLM says.
4. **Human approval (`trading_agent/approval.py`)** — prints the proposal and
   the risk check result, then blocks on a `y/N` prompt in the terminal.
   Nothing executes without an explicit yes.
5. **Trade log (`trading_agent/trade_log.py`)** — appends every proposal, risk
   result, human decision, and order outcome to a daily JSONL file under
   `logs/`.
6. **Trade journal (`trading_agent/trade_journal.py`)** — tracks all trade
   predictions and their outcomes, computing win rates and P&L metrics that
   feed back into Claude's next decision. This creates a closed loop where
   Claude learns from its own historical performance.

`trading_agent/main.py` wires these together into a cycle, optionally
repeating on an interval with `--loop`.

## Setup

1. Install [TWS or IB Gateway](https://www.interactivebrokers.ca/en/trading/tws.php)
   and enable the API (Configuration → API → Settings → Enable ActiveX and
   Socket Clients). Use a **paper trading account** first.
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements-dev.txt`
4. `cp .env.example .env` and fill in your watchlist and risk limits. Leave
   `DRY_RUN=true` until you've reviewed real behavior.
5. Set Anthropic credentials: either `ANTHROPIC_API_KEY` in `.env`, or
   `ant auth login`.

## Running

```bash
# one decision cycle
python -m trading_agent.main

# repeat every 15 minutes
python -m trading_agent.main --loop --interval 900
```

## Testing

```bash
pytest
```

Tests cover the risk manager's limit logic, watchlist/settings parsing, and
the LLM advisor's request/response shape (mocked — no live API or broker
calls). There's no automated coverage of the IBKR integration itself since it
requires a running TWS/Gateway instance; verify that manually against a paper
account.

## Claude as an Investing Nerd

The agent is designed to make Claude a sophisticated investing analyst, not just a price-following bot:

- **Technical Analysis**: RSI (Relative Strength Index) and moving averages (20-day, 50-day) are computed for each symbol and passed to Claude. Claude uses these to identify overbought/oversold conditions and trend direction.
- **Market Intelligence**: Optional web search integration fetches real-time news, earnings announcements, and analyst ratings for each watchlist symbol. Claude can reason over recent market sentiment and fundamental developments.
- **Performance Learning**: The trade journal tracks every prediction vs. its outcome (entry price, exit price, P&L), and recent results are fed back into Claude's next decision. Claude learns from its own wins and losses, adjusting confidence and strategy over time.
- **Adaptive Prompting**: The system prompt encourages Claude to consider all these data sources holistically—price action, technicals, news, and its own track record—before proposing trades.

To enable web search, the `_fetch_market_intelligence` method in `llm_advisor.py` can be called for each symbol before building the prompt. This adds real-time context but may increase API latency.

## Configuration

See `.env.example` for every setting. The ones that matter most for safety:

- `DRY_RUN` — while `true` (default), proposals still go through the LLM,
  risk checks, and human approval, but no order reaches the broker.
- `MAX_ORDER_VALUE`, `MAX_POSITION_VALUE`, `MAX_DAILY_TRADES`,
  `MAX_TOTAL_EXPOSURE_PCT` — hard caps enforced by the risk manager,
  independent of the LLM's own judgment.
- `IB_PORT` — defaults to TWS's paper trading port (`7497`); switch
  deliberately to a live port (`7496`/`4001`) only when you're ready.
- `WATCHLIST` — comma-separated `SYMBOL:CURRENCY:EXCHANGE:PRIMARY_EXCHANGE`
  entries; trailing fields are optional and default to a TSX-listed CAD
  stock (`CAD:SMART:TSE`).

## Disclaimer

This is a decision-support tool, not financial advice. The LLM's analysis is
based solely on the price data and account state it's given each cycle — it
has no news, fundamentals, or broader market context unless you extend it to
provide that. You are responsible for every trade you approve.
