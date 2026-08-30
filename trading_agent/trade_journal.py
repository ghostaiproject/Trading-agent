from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .llm_advisor import TradeProposal


class TradeJournal:
    """Track trade predictions vs actual outcomes to enable learning and performance analysis."""

    def __init__(self, journal_dir: str = "logs"):
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.journal_dir / "trade-journal.jsonl"

    def record_prediction(self, proposal: TradeProposal, snapshots: Dict[str, Any]) -> None:
        """Record a trade prediction when the proposal is made."""
        entry = {
            "event": "prediction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": proposal.symbol,
            "action": proposal.action,
            "quantity": proposal.quantity,
            "confidence": proposal.confidence,
            "rationale": proposal.rationale,
            "entry_price": snapshots.get(proposal.symbol, {}).get("last_price", 0.0),
        }
        with self.journal_path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def record_outcome(self, symbol: str, action: str, quantity: int, entry_price: float, exit_price: float) -> None:
        """Record the outcome of a trade after it closes."""
        entry = {
            "event": "outcome",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": (exit_price - entry_price) * quantity if action == "buy" else (entry_price - exit_price) * quantity,
        }
        with self.journal_path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def get_recent_outcomes(self, days: int = 30, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve recent prediction-outcome pairs to inform future decisions."""
        if not self.journal_path.exists():
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        predictions = {}
        outcomes = []

        with self.journal_path.open() as f:
            for line in f:
                entry = json.loads(line)
                if entry["event"] == "prediction":
                    symbol = entry["symbol"]
                    if symbol not in predictions:
                        predictions[symbol] = []
                    predictions[symbol].append(entry)
                elif entry["event"] == "outcome":
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if entry_time > cutoff:
                        outcomes.append(entry)

        recent = []
        for outcome in outcomes[-limit:]:
            symbol = outcome["symbol"]
            matching_predictions = [p for p in predictions.get(symbol, [])
                                   if datetime.fromisoformat(p["timestamp"]) < entry_time]
            if matching_predictions:
                pred = matching_predictions[-1]
                pnl_pct = (outcome["pnl"] / (outcome["entry_price"] * outcome["quantity"]) * 100
                          if outcome["entry_price"] > 0 else 0)
                recent.append({
                    "symbol": symbol,
                    "prediction": pred["action"],
                    "confidence": pred["confidence"],
                    "rationale": pred["rationale"],
                    "outcome_pnl": outcome["pnl"],
                    "outcome_pnl_pct": pnl_pct,
                    "correct": self._was_correct(pred, outcome),
                })

        return recent

    @staticmethod
    def _was_correct(prediction: Dict[str, Any], outcome: Dict[str, Any]) -> bool:
        """Determine if a prediction was correct based on the outcome."""
        action = prediction["action"]
        pnl = outcome["pnl"]

        if action == "buy":
            return pnl > 0
        elif action == "sell":
            return pnl > 0
        else:
            return True

    def get_performance_summary(self, days: int = 30) -> Dict[str, Any]:
        """Summarize recent trading performance."""
        outcomes = self.get_recent_outcomes(days=days, limit=100)

        if not outcomes:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": 0.0,
            }

        total_pnl = sum(o["outcome_pnl"] for o in outcomes)
        correct = sum(1 for o in outcomes if o["correct"])
        win_rate = correct / len(outcomes) * 100 if outcomes else 0

        return {
            "total_trades": len(outcomes),
            "win_rate": win_rate,
            "avg_pnl": total_pnl / len(outcomes) if outcomes else 0,
            "total_pnl": total_pnl,
        }

    def format_for_prompt(self, days: int = 30) -> str:
        """Format recent performance for inclusion in LLM prompt."""
        outcomes = self.get_recent_outcomes(days=days, limit=10)

        if not outcomes:
            return "No recent prediction history available."

        lines = []
        for outcome in outcomes:
            status = "✓" if outcome["correct"] else "✗"
            pnl_str = f"+${outcome['outcome_pnl']:.2f}" if outcome["outcome_pnl"] > 0 else f"-${abs(outcome['outcome_pnl']):.2f}"
            lines.append(
                f"{status} {outcome['symbol']} {outcome['prediction'].upper()}: "
                f"confidence {outcome['confidence']:.0%}, P&L {pnl_str} ({outcome['outcome_pnl_pct']:.1f}%)"
            )

        summary = self.get_performance_summary(days=days)
        lines.append(f"\nRecent performance: {summary['win_rate']:.1f}% win rate, "
                    f"${summary['total_pnl']:.2f} total P&L over {summary['total_trades']} trades")

        return "\n".join(lines)
