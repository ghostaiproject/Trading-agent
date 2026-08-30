from __future__ import annotations

from typing import Dict, List, Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from .broker import AccountState, MarketSnapshot, Position

SYSTEM_PROMPT = """You are a cautious equity trading analyst for a self-directed Canadian \
retail investor. Each cycle you review account state, current positions, and recent \
price data for a fixed watchlist, then propose trades.

Rules:
- Default to "hold" unless the data clearly supports a trade.
- Never propose a "sell" for a symbol the account does not currently hold.
- Never propose a "buy" whose cost would exceed the available cash balance.
- Prefer smaller, risk-aware position sizes over large, concentrated bets.
- A human reviews every proposal before anything executes, so make the rationale \
concrete and specific to the data you were given, and call out what would change \
your mind.
- You are not a licensed financial advisor; this is a decision-support tool only.

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
    ) -> TradeDecision:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": self._build_prompt(account, positions, snapshots)}],
            output_format=TradeDecision,
        )
        return response.parsed_output

    @staticmethod
    def _build_prompt(
        account: AccountState,
        positions: Dict[str, Position],
        snapshots: Dict[str, MarketSnapshot],
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
        lines.append("Watchlist snapshots:")
        for snap in snapshots.values():
            closes = ", ".join(f"{c:.2f}" for c in snap.recent_closes[-10:])
            lines.append(
                f"- {snap.symbol}: last {snap.last_price:.2f}, bid {snap.bid:.2f}, "
                f"ask {snap.ask:.2f}, recent closes [{closes}]"
            )

        return "\n".join(lines)
