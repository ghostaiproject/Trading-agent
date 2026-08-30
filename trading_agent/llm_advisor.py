from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from .analysis import TradingAnalyzer
from .broker import AccountState, MarketSnapshot, Position

SYSTEM_PROMPT = """You are a sophisticated equity trading analyst for a self-directed Canadian \
retail investor. Each cycle you receive comprehensive market analysis data and propose trades \
based on technical merit, risk/reward analysis, momentum, and trend strength.

Your Analysis Toolkit:
- RSI: Overbought (>70) / oversold (<30) detection
- Moving Averages: Trend direction and momentum (20/50/200-day)
- Bollinger Bands: Volatility and price extremes
- MACD: Momentum and trend confirmation
- Support/Resistance: Key price levels and breakout opportunities
- Volatility: Risk assessment and position sizing
- Momentum: Rate of change and trending strength
- Investment Scoring: Composite score integrating all signals (-10 to +10)

Decision Rules:
1. Prefer high-scoring investment opportunities (score > 5 = strong buy, < -5 = strong sell)
2. Look for confluence: multiple signals aligning (e.g., RSI oversold + price at support + bullish MACD)
3. Size positions based on volatility: high volatility = smaller positions, low volatility = can go larger
4. Risk/Reward: Only trade when reward is at least 1.5x the risk
5. Trend Strength: Trade in direction of established trends (20 > 50 > 200 day MAs)
6. Momentum Confirmation: Use MACD and rate of change to confirm new moves
7. Default to "hold" on conflicting signals or low conviction

Execution Guardrails:
- Never propose a "sell" for a symbol you don't hold
- Never propose a "buy" exceeding available cash
- Position sizing reflects volatility (quantified in suggestions provided)
- Confidence reflects signal strength: high when multiple indicators align, low when conflicting
- A human reviews every proposal, so make rationale concrete and specific

You are not a licensed financial advisor; this is a decision-support tool only.
You have learned from past trading outcomes; leverage that history to improve future trades.
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
            f"Net liquidation value: ${account.net_liquidation:,.2f}",
            f"Cash balance: ${account.cash_balance:,.2f}",
            f"Buying power: ${account.buying_power:,.2f}",
            "",
            "Current positions:",
        ]

        portfolio_value = sum(pos.market_value for pos in positions.values()) if positions else 0
        if positions:
            for pos in positions.values():
                pnl = pos.market_value - (pos.quantity * pos.avg_cost)
                pnl_pct = (pnl / (pos.quantity * pos.avg_cost) * 100) if pos.avg_cost > 0 else 0
                lines.append(
                    f"- {pos.symbol}: {pos.quantity} shares @ ${pos.avg_cost:.2f}, "
                    f"current ${pos.market_price:.2f}, value ${pos.market_value:,.2f} "
                    f"(P&L: ${pnl:+.2f}, {pnl_pct:+.1f}%)"
                )
        else:
            lines.append("- none")

        if portfolio_value > 0:
            exposure_pct = (portfolio_value / account.net_liquidation) * 100
            lines.append(f"Total portfolio exposure: {exposure_pct:.1f}%")

        lines.append("")
        lines.append("=" * 80)
        lines.append("ADVANCED MARKET ANALYSIS - PER SYMBOL")
        lines.append("=" * 80)

        for snap in snapshots.values():
            lines.append("")
            lines.append(f"📊 {snap.symbol}")
            lines.append(f"Price: ${snap.last_price:.2f} | Bid: ${snap.bid:.2f} | Ask: ${snap.ask:.2f}")

            metrics = TradingAnalyzer.analyze_symbol(snap)
            score = TradingAnalyzer.score_investment(snap, metrics, positions.get(snap.symbol))

            lines.append("")
            lines.append("Technical Indicators:")
            if metrics.rsi is not None:
                rsi_status = "OVERSOLD" if metrics.rsi < 30 else "OVERBOUGHT" if metrics.rsi > 70 else "neutral"
                lines.append(f"  • RSI(14): {metrics.rsi:.1f} ({rsi_status})")

            if metrics.sma_20 is not None:
                lines.append(f"  • 20-day MA: ${metrics.sma_20:.2f}")
            if metrics.sma_50 is not None:
                lines.append(f"  • 50-day MA: ${metrics.sma_50:.2f}")

            if metrics.bollinger_upper is not None and metrics.bollinger_lower is not None:
                position_in_band = (
                    (snap.last_price - metrics.bollinger_lower) /
                    (metrics.bollinger_upper - metrics.bollinger_lower) * 100
                ) if metrics.bollinger_upper > metrics.bollinger_lower else 50
                lines.append(f"  • Bollinger Upper: ${metrics.bollinger_upper:.2f} | Lower: ${metrics.bollinger_lower:.2f} | Position: {position_in_band:.0f}%")

            if metrics.macd is not None:
                macd_status = "BULLISH" if metrics.macd > (metrics.macd_signal or 0) else "BEARISH"
                lines.append(f"  • MACD: {metrics.macd:.4f} | Signal: {metrics.macd_signal:.4f} ({macd_status})")

            lines.append("")
            lines.append("Momentum & Volatility:")
            if metrics.momentum_rate is not None:
                lines.append(f"  • 14-day Momentum: {metrics.momentum_rate:+.2f}%")
            if metrics.volatility_30d is not None:
                vol_status = "HIGH" if metrics.volatility_30d > 3 else "LOW" if metrics.volatility_30d < 1 else "NORMAL"
                lines.append(f"  • 30-day Volatility: {metrics.volatility_30d:.2f}% ({vol_status})")

            lines.append("")
            lines.append("Price Levels & Trend:")
            if metrics.support_level is not None and metrics.resistance_level is not None:
                lines.append(f"  • Support: ${metrics.support_level:.2f} | Resistance: ${metrics.resistance_level:.2f}")
                range_width = metrics.resistance_level - metrics.support_level
                if range_width > 0:
                    price_position = (snap.last_price - metrics.support_level) / range_width * 100
                    lines.append(f"  • Price position in range: {price_position:.0f}%")

            if score.trend_strength is not None:
                trend_text = "STRONG UPTREND" if score.trend_strength > 0.5 else "STRONG DOWNTREND" if score.trend_strength < -0.5 else "Mixed/Consolidating"
                lines.append(f"  • Trend: {trend_text} (strength: {score.trend_strength:+.2f})")

            lines.append("")
            lines.append(f"💡 INVESTMENT SCORE: {score.overall_score:+.1f}/10")
            lines.append(f"   Technical: {score.technical_score:+.1f} | Momentum: {score.momentum_score:+.1f} | "
                        f"Volatility: {score.volatility_score:+.1f} | Risk/Reward: {score.risk_reward_score:+.1f}")
            lines.append("")
            lines.append("Analysis:")
            for point in score.rationale:
                lines.append(f"  • {point}")

            position_rec = TradingAnalyzer.suggest_position_size(
                account.cash_balance,
                metrics.volatility_30d
            )
            lines.append(f"  • Suggested max position: ${position_rec:,.2f}")

        if historical_performance:
            lines.append("")
            lines.append("=" * 80)
            lines.append("HISTORICAL PERFORMANCE (Learn from past trades)")
            lines.append("=" * 80)
            for entry in historical_performance.get("recent_outcomes", []):
                lines.append(f"{entry}")

        return "\n".join(lines)
