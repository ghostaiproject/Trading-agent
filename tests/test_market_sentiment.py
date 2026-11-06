import pytest

from trading_agent.market_sentiment import (
    MarketSentimentAnalyzer,
    NewsCategory,
    NewsSentiment,
)


class TestNewsCategoryDetection:
    def test_detect_earnings_news(self):
        headlines = [
            "Apple beats Q4 earnings estimates",
            "Tesla misses revenue guidance",
            "Intel raises quarterly profit forecast",
        ]
        for headline in headlines:
            category = MarketSentimentAnalyzer._detect_category(headline)
            assert category == NewsCategory.EARNINGS

    def test_detect_fed_policy_news(self):
        headlines = [
            "Federal Reserve raises interest rates by 0.5%",
            "Fed signals rate cuts ahead",
            "Jerome Powell hints at policy shift",
        ]
        for headline in headlines:
            category = MarketSentimentAnalyzer._detect_category(headline)
            assert category == NewsCategory.FED_POLICY

    def test_detect_economic_data_news(self):
        headlines = [
            "Jobs report shows stronger than expected employment",
            "CPI inflation beats expectations at 3.2%",
            "GDP growth accelerates to 2.5%",
        ]
        for headline in headlines:
            category = MarketSentimentAnalyzer._detect_category(headline)
            assert category == NewsCategory.ECONOMIC_DATA

    def test_detect_geopolitical_news(self):
        headlines = [
            "Russia-Ukraine tensions escalate",
            "China imposes new tariffs on US goods",
            "NATO responds to military conflict",
        ]
        for headline in headlines:
            category = MarketSentimentAnalyzer._detect_category(headline)
            assert category == NewsCategory.GEOPOLITICAL

    def test_detect_macro_shock_news(self):
        headlines = [
            "Global pandemic triggers market crash",
            "Stock market crashes in historic black swan event",
            "Bank bankruptcy leads to emergency action",
        ]
        for headline in headlines:
            category = MarketSentimentAnalyzer._detect_category(headline)
            assert category == NewsCategory.MACRO_SHOCK


class TestSentimentDetection:
    def test_detect_very_positive_sentiment(self):
        headlines = [
            "Apple stock soars on record earnings",
            "Tesla surges after beating estimates",
        ]
        for headline in headlines:
            sentiment = MarketSentimentAnalyzer._detect_sentiment(headline)
            assert sentiment == NewsSentiment.VERY_POSITIVE

    def test_detect_positive_sentiment(self):
        headlines = [
            "Market rises on positive economic data",
            "Tech stocks rally after strong earnings",
        ]
        for headline in headlines:
            sentiment = MarketSentimentAnalyzer._detect_sentiment(headline)
            assert sentiment == NewsSentiment.POSITIVE

    def test_detect_very_negative_sentiment(self):
        headlines = [
            "Market crashes on pandemic fears",
            "Bank collapses trigger financial crisis",
        ]
        for headline in headlines:
            sentiment = MarketSentimentAnalyzer._detect_sentiment(headline)
            assert sentiment == NewsSentiment.VERY_NEGATIVE

    def test_detect_negative_sentiment(self):
        headlines = [
            "Stock falls after missing guidance",
            "Investors concerned about rate hikes",
        ]
        for headline in headlines:
            sentiment = MarketSentimentAnalyzer._detect_sentiment(headline)
            assert sentiment == NewsSentiment.NEGATIVE

    def test_detect_neutral_sentiment(self):
        headline = "Company announces quarterly results in line with expectations"
        sentiment = MarketSentimentAnalyzer._detect_sentiment(headline)
        assert sentiment == NewsSentiment.NEUTRAL


class TestAssetDetection:
    def test_detect_single_symbol(self):
        headline = "Apple stock soars on earnings beat"
        assets = MarketSentimentAnalyzer._detect_affected_assets(headline)
        assert "AAPL" in assets or len(assets) > 0

    def test_detect_multiple_symbols(self):
        headline = "AAPL and MSFT both beat earnings today"
        assets = MarketSentimentAnalyzer._detect_affected_assets(headline)
        assert len(assets) >= 2

    def test_detect_market_indices(self):
        headline = "S&P 500 reaches all-time high on positive sentiment"
        assets = MarketSentimentAnalyzer._detect_affected_assets(headline)
        assert "SPY" in assets or "SPX" in assets or len(assets) > 0


class TestConfidenceCalculation:
    def test_high_confidence_earnings(self):
        headline = "Apple crushes Q4 earnings estimates with 15% EPS beat"
        category = NewsCategory.EARNINGS
        sentiment = NewsSentiment.VERY_POSITIVE
        confidence = MarketSentimentAnalyzer._calculate_confidence(
            headline, category, sentiment
        )
        assert confidence > 0.7

    def test_low_confidence_vague_headline(self):
        headline = "Stock moves"
        category = NewsCategory.COMPANY_NEWS
        sentiment = NewsSentiment.NEUTRAL
        confidence = MarketSentimentAnalyzer._calculate_confidence(
            headline, category, sentiment
        )
        assert confidence < 0.7


class TestNewsEventAnalysis:
    def test_analyze_earnings_beat(self):
        headline = "Microsoft crushes Q3 earnings with strong cloud growth"
        event = MarketSentimentAnalyzer.analyze_news(headline)

        assert event.category == NewsCategory.EARNINGS
        assert event.sentiment == NewsSentiment.VERY_POSITIVE
        assert event.impact_magnitude > 0
        assert event.confidence > 0.6

    def test_analyze_fed_rate_hike(self):
        headline = "Fed raises rates by 0.75% in surprise move"
        event = MarketSentimentAnalyzer.analyze_news(headline)

        assert event.category == NewsCategory.FED_POLICY
        assert event.impact_magnitude < 0

    def test_analyze_earnings_miss(self):
        headline = "Intel misses earnings and cuts 2024 guidance"
        event = MarketSentimentAnalyzer.analyze_news(headline)

        assert event.category == NewsCategory.EARNINGS
        assert event.sentiment == NewsSentiment.NEGATIVE
        assert event.impact_magnitude < 0


class TestMarketResponsePrediction:
    def test_predict_positive_news_impact(self):
        headline = "Apple stock soars after beating earnings estimates"
        current_price = 150.0
        prediction = MarketSentimentAnalyzer.predict_market_response(headline, current_price)

        assert prediction["expected_impact_pct"] > 0
        assert prediction["expected_price"] > current_price
        assert prediction["confidence"] > 0.5

    def test_predict_negative_news_impact(self):
        headline = "Tesla misses earnings forecast as deliveries collapse"
        current_price = 250.0
        prediction = MarketSentimentAnalyzer.predict_market_response(headline, current_price)

        assert prediction["expected_impact_pct"] < 0
        assert prediction["expected_price"] < current_price

    def test_volatility_adjustment(self):
        headline = "Apple beats earnings expectations with strong iPhone sales"
        current_price = 400.0

        pred_low_vol = MarketSentimentAnalyzer.predict_market_response(
            headline, current_price, current_volatility=0.5
        )
        pred_high_vol = MarketSentimentAnalyzer.predict_market_response(
            headline, current_price, current_volatility=3.5
        )

        # High volatility should amplify the move
        assert abs(pred_high_vol["expected_impact_pct"]) > abs(pred_low_vol["expected_impact_pct"])


class TestMarketRecoveryPatterns:
    def test_mild_shock_recovery(self):
        recovery = MarketSentimentAnalyzer.analyze_market_recovery_pattern(-3.0)
        assert "1-2 weeks" in recovery

    def test_moderate_shock_recovery(self):
        recovery = MarketSentimentAnalyzer.analyze_market_recovery_pattern(-8.0)
        assert "2-4 weeks" in recovery

    def test_severe_shock_recovery(self):
        recovery = MarketSentimentAnalyzer.analyze_market_recovery_pattern(-15.0)
        assert "4-12 weeks" in recovery

    def test_systemic_crisis_recovery(self):
        recovery = MarketSentimentAnalyzer.analyze_market_recovery_pattern(-25.0, is_systemic=True)
        assert "3-6" in recovery or "months" in recovery


class TestMarketStrengthScoring:
    def test_very_strong_market(self):
        strength, description = MarketSentimentAnalyzer.score_market_strength(
            price_momentum=15, vol_regime="low", sentiment_reading=0.8
        )
        assert strength == "Very Strong"

    def test_very_weak_market(self):
        strength, description = MarketSentimentAnalyzer.score_market_strength(
            price_momentum=-15, vol_regime="high", sentiment_reading=-0.8
        )
        assert strength == "Very Weak"

    def test_neutral_market(self):
        strength, description = MarketSentimentAnalyzer.score_market_strength(
            price_momentum=2, vol_regime="normal", sentiment_reading=0.1
        )
        assert strength in ["Neutral", "Strong", "Weak"]
