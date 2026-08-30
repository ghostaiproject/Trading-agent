from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

from .broker import MarketSnapshot, Position


@dataclass
class TechnicalMetrics:
    """Comprehensive technical analysis metrics for a symbol."""

    symbol: str
    rsi: Optional[float]
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    bollinger_upper: Optional[float]
    bollinger_lower: Optional[float]
    macd: Optional[float]
    macd_signal: Optional[float]
    volatility_30d: Optional[float]
    momentum_rate: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]


@dataclass
class InvestmentScore:
    """Scoring system for investment decisions."""

    symbol: str
    technical_score: float
    momentum_score: float
    volatility_score: float
    risk_reward_score: float
    trend_strength: float
    overall_score: float
    rationale: List[str]


class TradingAnalyzer:
    """Advanced technical and fundamental analysis for trading decisions."""

    @staticmethod
    def compute_bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> tuple:
        """Compute Bollinger Bands (middle, upper, lower)."""
        if len(closes) < period:
            return None, None, None

        sma = MarketSnapshot.compute_sma(closes, period)
        if sma is None:
            return None, None, None

        recent_closes = closes[-period:]
        std = statistics.stdev(recent_closes)
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)

        return sma, upper, lower

    @staticmethod
    def compute_macd(closes: List[float]) -> tuple:
        """Compute MACD (12-day EMA - 26-day EMA) and signal line (9-day EMA of MACD)."""
        if len(closes) < 26:
            return None, None

        ema_12 = TradingAnalyzer._compute_ema(closes, 12)
        ema_26 = TradingAnalyzer._compute_ema(closes, 26)

        if ema_12 is None or ema_26 is None:
            return None, None

        macd = ema_12 - ema_26

        macd_values = []
        for i in range(max(12, 26), len(closes)):
            ema_12_val = TradingAnalyzer._compute_ema(closes[:i + 1], 12)
            ema_26_val = TradingAnalyzer._compute_ema(closes[:i + 1], 26)
            if ema_12_val is not None and ema_26_val is not None:
                macd_values.append(ema_12_val - ema_26_val)

        if len(macd_values) < 9:
            return macd, None

        signal_line = TradingAnalyzer._compute_ema(macd_values, 9)
        return macd, signal_line

    @staticmethod
    def _compute_ema(closes: List[float], period: int) -> Optional[float]:
        """Compute Exponential Moving Average."""
        if len(closes) < period:
            return None

        multiplier = 2.0 / (period + 1)
        ema = sum(closes[:period]) / period

        for close in closes[period:]:
            ema = close * multiplier + ema * (1 - multiplier)

        return ema

    @staticmethod
    def compute_volatility(closes: List[float], period: int = 30) -> Optional[float]:
        """Compute 30-day volatility (standard deviation of returns)."""
        if len(closes) < period:
            return None

        recent_closes = closes[-period:]
        returns = [(recent_closes[i] - recent_closes[i - 1]) / recent_closes[i - 1]
                   for i in range(1, len(recent_closes))]

        if not returns:
            return None

        return statistics.stdev(returns) * 100

    @staticmethod
    def compute_momentum(closes: List[float], period: int = 14) -> Optional[float]:
        """Compute momentum as percentage change over period."""
        if len(closes) < period:
            return None

        current = closes[-1]
        past = closes[-period - 1]

        if past == 0:
            return None

        return ((current - past) / past) * 100

    @staticmethod
    def compute_support_resistance(closes: List[float], lookback: int = 20) -> tuple:
        """Identify support and resistance levels from recent price action."""
        if len(closes) < lookback:
            recent = closes
        else:
            recent = closes[-lookback:]

        support = min(recent)
        resistance = max(recent)

        return support, resistance

    @staticmethod
    def compute_trend_strength(closes: List[float]) -> Optional[float]:
        """Score trend strength from -1 (strong downtrend) to +1 (strong uptrend)."""
        if len(closes) < 50:
            return None

        sma_20 = MarketSnapshot.compute_sma(closes, 20)
        sma_50 = MarketSnapshot.compute_sma(closes, 50)

        if sma_20 is None or sma_50 is None:
            return None

        current_price = closes[-1]

        above_20 = 1 if current_price > sma_20 else -1
        above_50 = 1 if current_price > sma_50 else -1
        sma_20_above_50 = 1 if sma_20 > sma_50 else -1

        strength = (above_20 + above_50 + sma_20_above_50) / 3.0
        return strength

    @staticmethod
    def analyze_symbol(snapshot: MarketSnapshot) -> TechnicalMetrics:
        """Generate comprehensive technical metrics for a symbol."""
        closes = snapshot.recent_closes

        rsi = snapshot.rsi if hasattr(snapshot, 'rsi') and snapshot.rsi is not None else MarketSnapshot.compute_rsi(closes)
        sma_20 = snapshot.sma_20 if hasattr(snapshot, 'sma_20') and snapshot.sma_20 is not None else MarketSnapshot.compute_sma(closes, 20)
        sma_50 = snapshot.sma_50 if hasattr(snapshot, 'sma_50') and snapshot.sma_50 is not None else MarketSnapshot.compute_sma(closes, 50)
        sma_200 = MarketSnapshot.compute_sma(closes, 200) if len(closes) >= 200 else None

        bb_mid, bb_upper, bb_lower = TradingAnalyzer.compute_bollinger_bands(closes, 20)
        macd, macd_signal = TradingAnalyzer.compute_macd(closes)
        volatility = TradingAnalyzer.compute_volatility(closes)
        momentum = TradingAnalyzer.compute_momentum(closes)
        support, resistance = TradingAnalyzer.compute_support_resistance(closes)

        return TechnicalMetrics(
            symbol=snapshot.symbol,
            rsi=rsi,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            bollinger_upper=bb_upper,
            bollinger_lower=bb_lower,
            macd=macd,
            macd_signal=macd_signal,
            volatility_30d=volatility,
            momentum_rate=momentum,
            support_level=support,
            resistance_level=resistance,
        )

    @staticmethod
    def score_investment(
        snapshot: MarketSnapshot,
        metrics: TechnicalMetrics,
        position: Optional[Position] = None,
        portfolio_volatility: Optional[float] = None,
    ) -> InvestmentScore:
        """Score a symbol as investment opportunity on scale of -10 (strong sell) to +10 (strong buy)."""
        rationale = []

        technical_score = 0.0
        momentum_score = 0.0
        volatility_score = 0.0
        risk_reward_score = 0.0

        if metrics.rsi is not None:
            if metrics.rsi < 30:
                technical_score += 3
                rationale.append(f"RSI {metrics.rsi:.1f} indicates oversold (bullish)")
            elif metrics.rsi > 70:
                technical_score -= 3
                rationale.append(f"RSI {metrics.rsi:.1f} indicates overbought (bearish)")
            else:
                technical_score += 1
                rationale.append(f"RSI {metrics.rsi:.1f} in neutral zone")

        if metrics.sma_20 is not None and metrics.sma_50 is not None:
            if metrics.sma_20 > metrics.sma_50:
                technical_score += 2
                rationale.append("20-day MA above 50-day MA (bullish)")
            else:
                technical_score -= 2
                rationale.append("20-day MA below 50-day MA (bearish)")

        if snapshot.last_price > 0 and metrics.support_level is not None:
            distance_to_support = ((snapshot.last_price - metrics.support_level) / snapshot.last_price) * 100
            if distance_to_support < 5:
                technical_score += 2
                rationale.append(f"Price near support ({distance_to_support:.1f}% above)")

        if metrics.momentum_rate is not None:
            if metrics.momentum_rate > 5:
                momentum_score += 3
                rationale.append(f"Strong upward momentum ({metrics.momentum_rate:.1f}%)")
            elif metrics.momentum_rate < -5:
                momentum_score -= 3
                rationale.append(f"Strong downward momentum ({metrics.momentum_rate:.1f}%)")
            else:
                momentum_score += 0.5
                rationale.append(f"Momentum flat ({metrics.momentum_rate:.1f}%)")

        if metrics.macd is not None and metrics.macd_signal is not None:
            if metrics.macd > metrics.macd_signal:
                momentum_score += 1
                rationale.append("MACD above signal line (bullish momentum)")
            else:
                momentum_score -= 1
                rationale.append("MACD below signal line (bearish momentum)")

        if metrics.volatility_30d is not None:
            if metrics.volatility_30d > 3:
                volatility_score -= 1.5
                rationale.append(f"High volatility ({metrics.volatility_30d:.1f}%) - riskier")
            elif metrics.volatility_30d < 1:
                volatility_score += 1
                rationale.append(f"Low volatility ({metrics.volatility_30d:.1f}%) - stable")

        if snapshot.last_price > 0 and metrics.resistance_level is not None and metrics.support_level is not None:
            distance_to_support = snapshot.last_price - metrics.support_level
            if distance_to_support > 0:
                risk_reward = (metrics.resistance_level - snapshot.last_price) / distance_to_support
                if risk_reward > 2:
                    risk_reward_score += 2
                    rationale.append(f"Good risk/reward ratio ({risk_reward:.2f}:1)")
                elif risk_reward > 1:
                    risk_reward_score += 1
                    rationale.append(f"Adequate risk/reward ratio ({risk_reward:.2f}:1)")
                else:
                    risk_reward_score -= 1
                    rationale.append(f"Poor risk/reward ratio ({risk_reward:.2f}:1)")
            else:
                risk_reward_score -= 1
                rationale.append("Price at or below support level")

        overall_score = (technical_score + momentum_score + volatility_score + risk_reward_score) / 2

        return InvestmentScore(
            symbol=snapshot.symbol,
            technical_score=min(10, max(-10, technical_score)),
            momentum_score=min(10, max(-10, momentum_score)),
            volatility_score=min(10, max(-10, volatility_score)),
            risk_reward_score=min(10, max(-10, risk_reward_score)),
            trend_strength=TradingAnalyzer.compute_trend_strength(snapshot.recent_closes) or 0.0,
            overall_score=min(10, max(-10, overall_score)),
            rationale=rationale,
        )

    @staticmethod
    def suggest_position_size(
        capital_available: float,
        volatility: Optional[float],
        risk_tolerance: float = 0.02,
    ) -> float:
        """Suggest position size based on volatility and risk tolerance.

        Uses volatility-adjusted position sizing: higher volatility -> smaller position.
        Risk tolerance is max % of capital to risk per trade (default 2%).
        """
        if volatility is None or volatility == 0:
            volatility = 2.0

        max_risk_amount = capital_available * risk_tolerance
        position_size = max_risk_amount / (volatility / 100.0)

        return min(position_size, capital_available * 0.1)
