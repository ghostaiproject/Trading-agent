from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict

import anthropic

from .approval import ConsoleApprover
from .broker import IBKRBroker
from .config import Settings
from .llm_advisor import LLMAdvisor
from .risk import RiskManager
from .trade_log import TradeLog
from .trade_journal import TradeJournal


def run_cycle(
    broker: IBKRBroker,
    advisor: LLMAdvisor,
    risk_mgr: RiskManager,
    approver: ConsoleApprover,
    log: TradeLog,
    journal: TradeJournal,
    settings: Settings,
) -> None:
    entries_by_symbol = {entry.symbol: entry for entry in settings.watchlist}

    account = broker.get_account_state()
    positions = broker.get_positions()
    snapshots = {entry.symbol: broker.get_market_snapshot(entry) for entry in settings.watchlist}

    log.record({"event": "cycle_start", "account": vars(account)})

    historical_performance = {
        "recent_outcomes": [journal.format_for_prompt()],
    }

    decision = advisor.get_trade_decision(account, positions, snapshots, historical_performance)

    for proposal in decision.proposals:
        log.record({"event": "proposal", "proposal": proposal.model_dump()})

        if proposal.action != "hold":
            journal.record_prediction(proposal, {prop.symbol: {"last_price": prop.last_price} for prop in snapshots.values()})

        if proposal.action == "hold":
            print(f"{proposal.symbol}: hold ({proposal.rationale})")
            continue

        snapshot = snapshots.get(proposal.symbol)
        reference_price = snapshot.last_price if snapshot else 0.0
        risk_result = risk_mgr.evaluate(proposal, account, positions, reference_price)
        log.record(
            {
                "event": "risk_result",
                "symbol": proposal.symbol,
                "approved": risk_result.approved,
                "reason": risk_result.reason,
            }
        )

        if not risk_result.approved:
            print(f"{proposal.symbol}: rejected by risk manager - {risk_result.reason}")
            continue

        if not approver.confirm(proposal, risk_result):
            log.record({"event": "human_rejected", "symbol": proposal.symbol})
            print(f"{proposal.symbol}: rejected by human")
            continue

        entry = entries_by_symbol[proposal.symbol]
        trade = broker.place_order(entry, proposal.action, proposal.quantity, proposal.order_type, proposal.limit_price)
        risk_mgr.record_trade()
        log.record(
            {
                "event": "order_submitted",
                "symbol": proposal.symbol,
                "action": proposal.action,
                "quantity": proposal.quantity,
                "dry_run": settings.dry_run,
                "trade": str(trade) if trade else None,
            }
        )
        print(f"{proposal.symbol}: order submitted ({'DRY RUN' if settings.dry_run else 'LIVE'})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-assisted trading agent for Canadian equities via Interactive Brokers"
    )
    parser.add_argument("--loop", action="store_true", help="Run continuously instead of a single cycle")
    parser.add_argument("--interval", type=int, default=900, help="Seconds between cycles when --loop is set")
    args = parser.parse_args()

    settings = Settings.from_env()

    if settings.dry_run:
        print("DRY RUN mode: no live orders will be submitted. Set DRY_RUN=false to trade for real.")
    else:
        print("LIVE mode: approved trades WILL be submitted to your broker.")

    broker = IBKRBroker(settings)
    broker.connect()

    client = anthropic.Anthropic()
    advisor = LLMAdvisor(client, settings.llm_model)
    risk_mgr = RiskManager(settings)
    approver = ConsoleApprover()
    log = TradeLog()
    journal = TradeJournal()

    last_reset_day = datetime.now(timezone.utc).date()

    try:
        while True:
            today = datetime.now(timezone.utc).date()
            if today != last_reset_day:
                risk_mgr.reset_daily_counter()
                last_reset_day = today

            try:
                run_cycle(broker, advisor, risk_mgr, approver, log, journal, settings)
            except Exception as exc:  # noqa: BLE001 - keep the loop alive across cycles
                log.record({"event": "error", "message": str(exc)})
                print(f"Error during cycle: {exc}", file=sys.stderr)

            if not args.loop:
                break

            print(f"Sleeping {args.interval}s until next cycle...")
            time.sleep(args.interval)
    finally:
        broker.disconnect()


if __name__ == "__main__":
    main()
