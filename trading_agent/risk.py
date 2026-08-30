from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .broker import AccountState, Position
from .config import Settings
from .llm_advisor import TradeProposal


@dataclass
class RiskResult:
    approved: bool
    reason: str


class RiskManager:
    """Applies hard position-sizing and exposure limits to every non-hold proposal.

    This runs regardless of what the LLM says - it is the last line of defense
    before a proposal ever reaches the human approval step.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._trades_today = 0

    def reset_daily_counter(self) -> None:
        self._trades_today = 0

    def record_trade(self) -> None:
        self._trades_today += 1

    def evaluate(
        self,
        proposal: TradeProposal,
        account: AccountState,
        positions: Dict[str, Position],
        reference_price: float,
    ) -> RiskResult:
        if proposal.action == "hold":
            return RiskResult(True, "hold requires no risk check")

        if proposal.quantity <= 0:
            return RiskResult(False, "quantity must be positive for a buy or sell")

        if reference_price <= 0:
            return RiskResult(False, "no valid reference price available for this symbol")

        if self._trades_today >= self.settings.max_daily_trades:
            return RiskResult(False, f"daily trade limit of {self.settings.max_daily_trades} reached")

        order_value = proposal.quantity * reference_price

        if order_value > self.settings.max_order_value:
            return RiskResult(
                False,
                f"order value {order_value:.2f} exceeds max order value {self.settings.max_order_value:.2f}",
            )

        if proposal.action == "sell":
            held = positions.get(proposal.symbol)
            available = held.quantity if held else 0
            if proposal.quantity > available:
                return RiskResult(
                    False,
                    f"cannot sell {proposal.quantity} shares of {proposal.symbol}; only {available} held",
                )
            return RiskResult(True, "sell within held quantity")

        # action == "buy"
        if order_value > account.cash_balance:
            return RiskResult(
                False,
                f"order value {order_value:.2f} exceeds available cash {account.cash_balance:.2f}",
            )

        held = positions.get(proposal.symbol)
        existing_value = held.market_value if held else 0.0
        projected_value = existing_value + order_value
        if projected_value > self.settings.max_position_value:
            return RiskResult(
                False,
                f"projected position value {projected_value:.2f} exceeds max position value "
                f"{self.settings.max_position_value:.2f}",
            )

        projected_exposure = sum(p.market_value for p in positions.values()) + order_value
        if account.net_liquidation > 0:
            exposure_pct = 100 * projected_exposure / account.net_liquidation
            if exposure_pct > self.settings.max_total_exposure_pct:
                return RiskResult(
                    False,
                    f"projected total exposure {exposure_pct:.1f}% exceeds max "
                    f"{self.settings.max_total_exposure_pct:.1f}%",
                )

        return RiskResult(True, "within risk limits")
