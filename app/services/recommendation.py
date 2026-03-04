from __future__ import annotations

from typing import Any

from app.services.analytics import AnalyticsService
from app.services.news import NewsService


class RecommendationService:
    def __init__(self) -> None:
        self.analytics = AnalyticsService()
        self.news = NewsService()

    def recommend(
        self,
        symbol: str,
        risk_profile: str,
        asset_type: str,
        include_news: bool = True,
    ) -> dict[str, Any]:
        metrics = self.analytics.compute(symbol)
        news_items = (
            self.news.fetch_news(symbol=symbol, asset_type=asset_type) if include_news else []
        )
        news_sentiment = self.news.sentiment_summary(news_items)

        vol = float(metrics["volatility_30d"])
        mom_30d = float(metrics["momentum_30d"])
        mom_90d = float(metrics["momentum_90d"])
        rsi_14 = float(metrics["rsi_14"])
        short_signal = str(metrics["signal_short_term"])
        long_signal = str(metrics["signal_long_term"])
        news_score = float(news_sentiment["score"])

        short = self._score_horizon(
            horizon="short_term",
            signal=short_signal,
            momentum=mom_30d,
            volatility=vol,
            rsi_14=rsi_14,
            news_score=news_score,
            risk_profile=risk_profile,
        )
        long = self._score_horizon(
            horizon="long_term",
            signal=long_signal,
            momentum=mom_90d,
            volatility=vol,
            rsi_14=rsi_14,
            news_score=news_score,
            risk_profile=risk_profile,
        )

        rationale = (
            f"short_signal={short_signal}, long_signal={long_signal}, momentum_30d={mom_30d:.2%}, "
            f"momentum_90d={mom_90d:.2%}, volatility_30d={vol:.2%}, news={news_sentiment['label']}."
        )

        return {
            "symbol": symbol.upper(),
            "recommendation": short["action"],
            "confidence": short["confidence"],
            "rationale": rationale,
            "short_term": short,
            "long_term": long,
            "news_sentiment": news_sentiment,
            "news": news_items,
            "technical_snapshot": metrics,
            "disclaimer": "Decision support only. This is not financial advice.",
        }

    def _score_horizon(
        self,
        horizon: str,
        signal: str,
        momentum: float,
        volatility: float,
        rsi_14: float,
        news_score: float,
        risk_profile: str,
    ) -> dict[str, str | float]:
        score = 0.0

        if signal == "bullish":
            score += 2.0
        elif signal == "bearish":
            score -= 2.0

        score += max(min(momentum * 10, 1.5), -1.5)

        if horizon == "short_term":
            if 45 <= rsi_14 <= 70:
                score += 0.4
            elif rsi_14 > 78:
                score -= 0.8
            elif rsi_14 < 30:
                score += 0.4
            score += news_score * 1.0
        else:
            score += news_score * 0.4

        if volatility > 0.55:
            score -= 0.8
        elif volatility > 0.40:
            score -= 0.4

        if risk_profile == "conservative":
            score -= max((volatility - 0.25) * 2, 0.0)
        elif risk_profile == "aggressive":
            score += 0.25

        action = "hold"
        if score >= 1.3:
            action = "buy"
        elif score <= -1.3:
            action = "reduce"

        confidence = min(max(0.52 + (abs(score) * 0.08), 0.52), 0.90)
        rationale = (
            f"horizon={horizon}, signal={signal}, momentum={momentum:.2%}, rsi_14={rsi_14:.1f}, "
            f"volatility_30d={volatility:.2%}, "
            f"news_score={news_score:.2f}, risk_profile={risk_profile}."
        )

        return {
            "action": action,
            "confidence": round(confidence, 2),
            "rationale": rationale,
        }
