from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from .broker import AccountState, MarketSnapshot, Position

SYSTEM_PROMPT = """You are a cautious equity trading analyst for a self-directed Canadian \
retail investor. Each cycle you review account state, current positions, recent \
price data, technical indicators, and market intelligence for a fixed watchlist, then propose trades.

Rules:
- Default to "hold" unless the data clearly supports a trade.
- Never propose a "sell" for a symbol the account does not currently hold.
- Never propose a "buy" whose cost would exceed the available cash balance.
- Prefer smaller, risk-aware position sizes over large, concentrated bets.
- A human reviews every proposal before anything executes, so make the rationale \
concrete and specific to the data you were given, and call out what would change \
your mind.
- You are not a licensed financial advisor; this is a decision-support tool only.
- You have access to recent market intelligence (news, earnings, analyst ratings) \
to inform your decisions.
- Consider technical indicators (moving averages, RSI) alongside fundamental data.
- Learn from your own historical performance to improve future decisions.

Respond with exactly one proposal per symbol in the watchlist, including "hold" \
proposals.
"""


class TradeProposal(BaseModel):
    symbol: str
    action: Literal["buy", "sell", "hold"]
    quantity: int = Field(ge=0)
    order_type: Literal["market", "limit"] = "market"
    limit_price: Optional[float] = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class TradeDecision(BaseModel):
    proposals: List[TradeProposal]


class LLMAdvisor:
    def __init__(self, client: anthropic.Anthropic, model: str):
        self.client = client
        self.model = model

    def get_trade_decision(
        self,
        account: AccountState,
        positions: Dict[str, Position],
        snapshots: Dict[str, MarketSnapshot],
        historical_performance: Optional[Dict[str, Any]] = None,
    ) -> TradeDecision:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": self._build_prompt(account, positions, snapshots, historical_performance),
            }],
            output_format=TradeDecision,
        )
        return response.parsed_output

    @staticmethod
    def _fetch_market_intelligence(client: anthropic.Anthropic, symbol: str) -> str:
        """Fetch recent news and analyst commentary for a symbol using web search."""
        try:
            response = client.messages.create(
                model="claude-opus-5",
                max_tokens=500,
                tools=[
                    {
                        "type": "web_search",
                        "name": "web_search",
                    }
                ],
                messages=[{
                    "role": "user",
                    "content": f"Search for recent news, earnings, and analyst ratings for {symbol} stock. "
                              f"Focus on the most recent developments from the last week.",
                }],
            )

            intelligence = []
            for block in response.content:
                if hasattr(block, "text"):
                    intelligence.append(block.text)

            return "\n".join(intelligence) if intelligence else f"No recent news found for {symbol}"
        except Exception:
            return f"Could not fetch market intelligence for {symbol}"

    @staticmethod
    def _build_prompt(
        account: AccountState,
        positions: Dict[str, Position],
        snapshots: Dict[str, MarketSnapshot],
        historical_performance: Optional[Dict[str, Any]] = None,
    ) -> str:
        lines = [
            f"Net liquidation value: {account.net_liquidation:.2f}",
            f"Cash balance: {account.cash_balance:.2f}",
            f"Buying power: {account.buying_power:.2f}",
            "",
            "Current positions:",
        ]

        if positions:
            for pos in positions.values():
                lines.append(
                    f"- {pos.symbol}: {pos.quantity} shares @ avg cost {pos.avg_cost:.2f}, "
                    f"market price {pos.market_price:.2f}, market value {pos.market_value:.2f}"
                )
        else:
            lines.append("- none")

        lines.append("")
        lines.append("Watchlist snapshots and technical indicators:")
        for snap in snapshots.values():
            closes = ", ".join(f"{c:.2f}" for c in snap.recent_closes[-10:])
            lines.append(
                f"- {snap.symbol}: last {snap.last_price:.2f}, bid {snap.bid:.2f}, ask {snap.ask:.2f}"
            )

            if hasattr(snap, "rsi") and snap.rsi is not None:
                lines.append(f"  RSI(14): {snap.rsi:.2f}")
            if hasattr(snap, "sma_20") and snap.sma_20 is not None:
                lines.append(f"  20-day MA: {snap.sma_20:.2f}")
            if hasattr(snap, "sma_50") and snap.sma_50 is not None:
                lines.append(f"  50-day MA: {snap.sma_50:.2f}")

            lines.append(f"  Recent closes [{closes}]")

            if hasattr(snap, "market_intelligence") and snap.market_intelligence:
                lines.append(f"  Market intelligence: {snap.market_intelligence}")

        if historical_performance:
            lines.append("")
            lines.append("Historical performance (recent decisions vs outcomes):")
            for entry in historical_performance.get("recent_outcomes", []):
                lines.append(f"- {entry}")

        return "\n".join(lines)
