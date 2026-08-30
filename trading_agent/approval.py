from __future__ import annotations

from .llm_advisor import TradeProposal
from .risk import RiskResult


class ConsoleApprover:
    """Blocks on a terminal y/N prompt before any trade is allowed to execute."""

    def confirm(self, proposal: TradeProposal, risk_result: RiskResult) -> bool:
        print("\n" + "=" * 60)
        print(f"Proposed {proposal.action.upper()} {proposal.quantity} {proposal.symbol}")
        suffix = f" @ {proposal.limit_price:.2f}" if proposal.limit_price else ""
        print(f"Order type: {proposal.order_type}{suffix}")
        print(f"Confidence: {proposal.confidence:.0%}")
        print(f"Rationale: {proposal.rationale}")
        print(f"Risk check: {risk_result.reason}")
        print("=" * 60)
        answer = input("Approve this trade? [y/N]: ").strip().lower()
        return answer in ("y", "yes")
