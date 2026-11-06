import pytest

from trading_agent.analysis import TradingAnalyzer, InvestmentScore
from trading_agent.broker import MarketSnapshot, Position


@pytest.fixture
def uptrend_closes():
    """Simulated uptrending price series."""
    return [100.0 + i * 0.5 for i in range(50)]


@pytest.fixture
def downtrend_closes():
    """Simulated downtrending price series."""
    return [100.0 - i * 0.5 for i in range(50)]


@pytest.fixture
def sideways_closes():
    """Simulated sideways trading price series."""
    return [100.0 + (5 if i % 2 == 0 else -5) for i in range(50)]


def test_bollinger_bands_basic():
    closes = [100.0 + i for i in range(30)]
    mid, upper, lower = TradingAnalyzer.compute_bollinger_bands(closes, 20)

    assert mid is not None
    assert upper is not None
    assert lower is not None
    assert upper > mid
    assert mid > lower


def test_bollinger_bands_insufficient_data():
    closes = [100.0, 101.0, 102.0]
    mid, upper, lower = TradingAnalyzer.compute_bollinger_bands(closes, 20)

    assert mid is None
    assert upper is None
    assert lower is None


def test_macd_basic():
    closes = list(range(100, 150))
    macd, signal = TradingAnalyzer.compute_macd(closes)

    assert macd is not None


def test_macd_insufficient_data():
    closes = [100.0, 101.0]
    macd, signal = TradingAnalyzer.compute_macd(closes)

    assert macd is None


def test_volatility_uptrend(uptrend_closes):
    vol = TradingAnalyzer.compute_volatility(uptrend_closes)

    assert vol is not None
    assert vol > 0


def test_volatility_sideways(sideways_closes):
    vol_sideways = TradingAnalyzer.compute_volatility(sideways_closes)

    assert vol_sideways is not None


def test_momentum_uptrend(uptrend_closes):
    momentum = TradingAnalyzer.compute_momentum(uptrend_closes, 14)

    assert momentum is not None
    assert momentum > 0


def test_momentum_downtrend(downtrend_closes):
    momentum = TradingAnalyzer.compute_momentum(downtrend_closes, 14)

    assert momentum is not None
    assert momentum < 0


def test_support_resistance():
    closes = [100.0, 105.0, 102.0, 110.0, 98.0, 112.0, 101.0, 115.0]
    support, resistance = TradingAnalyzer.compute_support_resistance(closes)

    assert support == min(closes)
    assert resistance == max(closes)


def test_trend_strength_uptrend(uptrend_closes):
    strength = TradingAnalyzer.compute_trend_strength(uptrend_closes)

    assert strength is not None
    assert strength > 0


def test_trend_strength_downtrend(downtrend_closes):
    strength = TradingAnalyzer.compute_trend_strength(downtrend_closes)

    assert strength is not None
    assert strength < 0


def test_analyze_symbol(uptrend_closes):
    snap = MarketSnapshot(
        symbol="TEST",
        last_price=uptrend_closes[-1],
        bid=uptrend_closes[-1] - 0.1,
        ask=uptrend_closes[-1] + 0.1,
        recent_closes=uptrend_closes,
    )

    metrics = TradingAnalyzer.analyze_symbol(snap)

    assert metrics.symbol == "TEST"
    assert metrics.rsi is not None
    assert metrics.sma_20 is not None
    assert metrics.sma_50 is not None


def test_score_investment_strong_buy(uptrend_closes):
    snap = MarketSnapshot(
        symbol="TEST",
        last_price=uptrend_closes[-1],
        bid=uptrend_closes[-1] - 0.1,
        ask=uptrend_closes[-1] + 0.1,
        recent_closes=uptrend_closes,
    )

    metrics = TradingAnalyzer.analyze_symbol(snap)
    score = TradingAnalyzer.score_investment(snap, metrics)

    assert score.overall_score > 0
    assert len(score.rationale) > 0


def test_score_investment_strong_sell(downtrend_closes):
    snap = MarketSnapshot(
        symbol="TEST",
        last_price=downtrend_closes[-1],
        bid=downtrend_closes[-1] - 0.1,
        ask=downtrend_closes[-1] + 0.1,
        recent_closes=downtrend_closes,
    )

    metrics = TradingAnalyzer.analyze_symbol(snap)
    score = TradingAnalyzer.score_investment(snap, metrics)

    assert score.trend_strength < 0
    assert len(score.rationale) > 0


def test_suggest_position_size_basic():
    size = TradingAnalyzer.suggest_position_size(10000, volatility=2.0, risk_tolerance=0.02)

    assert size > 0
    assert size <= 10000


def test_suggest_position_size_high_volatility():
    # Higher volatility should suggest smaller position sizes
    # Using very small position to avoid hitting caps
    size_low_vol = TradingAnalyzer.suggest_position_size(1000, volatility=0.05, risk_tolerance=0.01)
    size_high_vol = TradingAnalyzer.suggest_position_size(1000, volatility=0.5, risk_tolerance=0.01)

    assert size_high_vol <= size_low_vol


def test_suggest_position_size_no_volatility():
    size = TradingAnalyzer.suggest_position_size(10000, volatility=None, risk_tolerance=0.02)

    assert size > 0
