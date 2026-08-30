import pytest

from trading_agent.broker import MarketSnapshot


def test_compute_rsi_basic():
    closes = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28]
    rsi = MarketSnapshot.compute_rsi(closes, period=14)

    assert rsi is not None
    assert 0 <= rsi <= 100


def test_compute_rsi_insufficient_data():
    closes = [100.0, 101.0, 102.0]
    rsi = MarketSnapshot.compute_rsi(closes, period=14)
    assert rsi is None


def test_compute_rsi_uptrend():
    closes = [100.0 + i for i in range(20)]
    rsi = MarketSnapshot.compute_rsi(closes, period=14)
    assert rsi is not None
    assert rsi > 70


def test_compute_rsi_downtrend():
    closes = [100.0 - i for i in range(20)]
    rsi = MarketSnapshot.compute_rsi(closes, period=14)
    assert rsi is not None
    assert rsi < 30


def test_compute_sma_basic():
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0,
              110.0, 111.0, 112.0, 113.0, 114.0, 115.0, 116.0, 117.0, 118.0, 119.0]
    sma_20 = MarketSnapshot.compute_sma(closes, 20)

    assert sma_20 is not None
    assert sma_20 == 109.5


def test_compute_sma_20_from_30_closes():
    closes = list(range(100, 130))
    sma_20 = MarketSnapshot.compute_sma(closes, 20)

    assert sma_20 is not None
    assert sma_20 == sum(range(110, 130)) / 20


def test_compute_sma_insufficient_data():
    closes = [100.0, 101.0]
    sma_20 = MarketSnapshot.compute_sma(closes, 20)
    assert sma_20 is None


def test_market_snapshot_with_indicators():
    closes = [100.0 + i for i in range(30)]
    snap = MarketSnapshot(
        symbol="TEST",
        last_price=130.0,
        bid=129.5,
        ask=130.5,
        recent_closes=closes,
        rsi=MarketSnapshot.compute_rsi(closes),
        sma_20=MarketSnapshot.compute_sma(closes, 20),
        sma_50=MarketSnapshot.compute_sma(closes, 50),
    )

    assert snap.rsi is not None
    assert snap.sma_20 is not None
    assert snap.sma_50 is None
