from __future__ import annotations

from typing import Tuple

from .config import Settings
from .llm_advisor import TradeProposal
from .risk import RiskResult


class ConsoleApprover:
    """Blocks on a terminal y/N prompt before any trade is allowed to execute.

    Orders at or under `settings.auto_approve_below` skip the interactive
    prompt and are approved automatically (default: 0, meaning this is off
    and every non-hold trade always prompts). Auto-approval only ever skips
    the human y/N - it never skips the risk manager, which has already
    evaluated and approved the trade before `confirm` is called.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def confirm(
        self,
        proposal: TradeProposal,
        risk_result: RiskResult,
        reference_price: float,
    ) -> Tuple[bool, str]:
        """Returns (approved, method). method is "auto_threshold" or "human"."""
        order_value = proposal.quantity * reference_price
        threshold = self.settings.auto_approve_below

        if threshold > 0 and order_value <= threshold:
            print(
                f"\n{proposal.symbol}: {proposal.action.upper()} {proposal.quantity} "
                f"(${order_value:,.2f}) auto-approved - at or under your "
                f"${threshold:,.2f} auto-approve threshold"
            )
            return True, "auto_threshold"

        print("\n" + "=" * 60)
        print(f"Proposed {proposal.action.upper()} {proposal.quantity} {proposal.symbol}")
        suffix = f" @ {proposal.limit_price:.2f}" if proposal.limit_price else ""
        print(f"Order type: {proposal.order_type}{suffix}")
        print(f"Order value: ${order_value:,.2f}")
        print(f"Confidence: {proposal.confidence:.0%}")
        print(f"Rationale: {proposal.rationale}")
        print(f"Risk check: {risk_result.reason}")
        print("=" * 60)
        answer = input("Approve this trade? [y/N]: ").strip().lower()
        return answer in ("y", "yes"), "human"
