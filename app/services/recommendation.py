from app.services.analytics import AnalyticsService


class RecommendationService:
    def __init__(self) -> None:
        self.analytics = AnalyticsService()

    def recommend(self, symbol: str, risk_profile: str, asset_type: str) -> dict[str, str | float]:
        metrics = self.analytics.compute(symbol)

        signal = str(metrics["signal"])
        vol = float(metrics["volatility_30d"])
        mom = float(metrics["momentum_30d"])

        recommendation = "hold"
        confidence = 0.55

        if signal == "bullish" and mom > 0.05:
            recommendation = "buy"
            confidence = 0.70
        if signal == "bearish" and mom < -0.05:
            recommendation = "reduce"
            confidence = 0.72

        if risk_profile == "conservative" and vol > 0.35 and recommendation == "buy":
            recommendation = "hold"
            confidence = 0.58

        rationale = (
            f"Signal={signal}, momentum_30d={mom:.2%}, volatility_30d={vol:.2%}, "
            f"risk_profile={risk_profile}, asset_type={asset_type}."
        )

        return {
            "symbol": symbol.upper(),
            "recommendation": recommendation,
            "confidence": round(confidence, 2),
            "rationale": rationale,
        }
