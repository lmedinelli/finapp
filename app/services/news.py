from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.config import get_settings


class NewsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def fetch_news(
        self,
        symbol: str,
        asset_type: str = "stock",
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        api_key = self.settings.serpapi_api_key
        if not api_key:
            return []

        query = self._build_query(symbol=symbol, asset_type=asset_type)
        max_items = limit if limit is not None else self.settings.news_max_items

        params: dict[str, str | int] = {
            "engine": "google_news",
            "q": query,
            "api_key": api_key,
            "num": int(max_items),
            "hl": "en",
        }

        try:
            response = httpx.get(self.settings.serpapi_endpoint, params=params, timeout=15.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        items = payload.get("news_results", [])
        if not isinstance(items, list):
            return []

        headlines: list[dict[str, str]] = []
        for raw_item in items[:max_items]:
            if not isinstance(raw_item, dict):
                continue
            title = str(raw_item.get("title", "")).strip()
            if not title:
                continue
            source_data = raw_item.get("source")
            if isinstance(source_data, dict):
                source = str(source_data.get("name", ""))
            else:
                source = str(source_data or "")
            headlines.append(
                {
                    "title": title,
                    "url": str(raw_item.get("link", "")),
                    "source": source,
                    "published_at": str(raw_item.get("date", "")),
                }
            )
        return headlines

    @staticmethod
    def sentiment_summary(headlines: Iterable[dict[str, str]]) -> dict[str, float | str | int]:
        positive_words = {
            "beat",
            "beats",
            "growth",
            "surge",
            "record",
            "upgrade",
            "bullish",
            "rally",
            "expansion",
            "profit",
            "strong",
            "partnership",
        }
        negative_words = {
            "miss",
            "misses",
            "drop",
            "downgrade",
            "bearish",
            "lawsuit",
            "decline",
            "investigation",
            "weak",
            "risk",
            "loss",
            "warning",
        }

        score = 0.0
        counted = 0
        for item in headlines:
            title = item.get("title", "").lower()
            if not title:
                continue
            counted += 1
            positive_hits = sum(1 for word in positive_words if word in title)
            negative_hits = sum(1 for word in negative_words if word in title)
            score += float(positive_hits - negative_hits)

        normalized = 0.0 if counted == 0 else max(min(score / counted, 1.0), -1.0)
        label = "neutral"
        if normalized > 0.15:
            label = "positive"
        elif normalized < -0.15:
            label = "negative"

        return {
            "score": round(normalized, 3),
            "label": label,
            "sample_size": counted,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _build_query(symbol: str, asset_type: str) -> str:
        symbol_norm = symbol.upper()
        if asset_type == "crypto":
            return f"{symbol_norm} crypto market"
        if asset_type == "etf":
            return f"{symbol_norm} ETF market"
        return f"{symbol_norm} stock market"
