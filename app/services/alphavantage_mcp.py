from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx

from app.core.config import get_settings


class AlphaVantageMCPService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_global_quote(self, symbol: str) -> dict[str, Any]:
        ticker = self._normalize_symbol(symbol)
        payload = self._request("GLOBAL_QUOTE", symbol=ticker)
        block = payload.get("Global Quote")
        if not isinstance(block, dict) or not block:
            return {}

        return {
            "symbol": str(block.get("01. symbol", ticker.upper())),
            "price": self._to_float(block.get("05. price")),
            "change_percent": self._to_percent(block.get("10. change percent")),
            "volume": self._to_float(block.get("06. volume")),
            "latest_trading_day": str(block.get("07. latest trading day", "")),
        }

    def get_time_series_daily(
        self,
        symbol: str,
        outputsize: str = "compact",
    ) -> list[dict[str, float | str]]:
        ticker = self._normalize_symbol(symbol)
        payload = self._request("TIME_SERIES_DAILY", symbol=ticker, outputsize=outputsize)
        block = payload.get("Time Series (Daily)")
        if not isinstance(block, dict):
            return []

        rows: list[dict[str, float | str]] = []
        for date, values in block.items():
            if not isinstance(values, dict):
                continue
            rows.append(
                {
                    "date": str(date),
                    "open": self._to_float(values.get("1. open")),
                    "high": self._to_float(values.get("2. high")),
                    "low": self._to_float(values.get("3. low")),
                    "close": self._to_float(values.get("4. close")),
                    "volume": self._to_float(values.get("5. volume")),
                }
            )
        rows.sort(key=lambda item: str(item["date"]))
        if self.settings.alphavantage_daily_points > 0:
            return rows[-self.settings.alphavantage_daily_points :]
        return rows

    def get_news_sentiment(
        self,
        symbol: str,
        topics: str = "",
        limit: int | None = None,
    ) -> list[dict[str, float | str]]:
        ticker = self._normalize_symbol(symbol)
        params: dict[str, str | int] = {"tickers": ticker}
        if topics:
            params["topics"] = topics
        payload = self._request("NEWS_SENTIMENT", **params)
        block = payload.get("feed")
        if not isinstance(block, list):
            return []

        max_items = limit if limit is not None else self.settings.alphavantage_news_items
        rows: list[dict[str, float | str]] = []
        for item in block[:max_items]:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "source": str(item.get("source", "")),
                    "time_published": str(item.get("time_published", "")),
                    "overall_sentiment_score": self._to_float(item.get("overall_sentiment_score")),
                    "overall_sentiment_label": str(item.get("overall_sentiment_label", "neutral")),
                    "summary": str(item.get("summary", "")),
                }
            )
        return rows

    def get_market_context(self, symbol: str, topics: str = "") -> dict[str, Any]:
        ticker = self._normalize_symbol(symbol)
        quote_payload = self._request("GLOBAL_QUOTE", symbol=ticker)
        daily_payload = self._request("TIME_SERIES_DAILY", symbol=ticker, outputsize="compact")
        news_payload = self._request("NEWS_SENTIMENT", tickers=ticker, topics=topics)

        quote = self._parse_quote_payload(ticker, quote_payload)
        candles = self._parse_daily_payload(daily_payload)
        if self.settings.alphavantage_daily_points > 0:
            candles = candles[-self.settings.alphavantage_daily_points :]
        news = self._parse_news_payload(news_payload, limit=self.settings.alphavantage_news_items)
        trend = self._build_trend(candles)
        warnings = self._collect_warnings([quote_payload, daily_payload, news_payload])
        return {
            "symbol": ticker.upper(),
            "quote": quote or None,
            "trend": trend or None,
            "candles": candles,
            "news": news,
            "source": "alphavantage-mcp",
            "warnings": warnings,
        }

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        typo_map = {"APPL": "AAPL"}
        normalized = typo_map.get(normalized, normalized)
        if normalized.endswith("-USD"):
            return normalized.split("-")[0]
        return normalized

    def _request(self, function: str, **kwargs: str | int) -> dict[str, Any]:
        mcp_payload = self._request_mcp(function=function, **kwargs)
        if self._has_data_for_function(function, mcp_payload):
            return mcp_payload

        rest_payload = self._request_rest(function=function, **kwargs)
        if self._has_data_for_function(function, rest_payload):
            return rest_payload

        return rest_payload or mcp_payload

    def _request_mcp(self, function: str, **kwargs: str | int) -> dict[str, Any]:
        api_key = self.settings.alphavantage_api_key
        if not api_key:
            return {"Error Message": "AlphaVantage API key is missing."}

        params: dict[str, str | int] = {"function": function}
        params.update(kwargs)
        if not self._mcp_url_contains_apikey():
            params["apikey"] = api_key

        try:
            response = httpx.get(
                self.settings.alphavantage_mcp_url,
                params=params,
                timeout=self.settings.alphavantage_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {"Error Message": f"AlphaVantage MCP request failed: {exc!s}"}

        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return payload

    def _request_rest(self, function: str, **kwargs: str | int) -> dict[str, Any]:
        api_key = self.settings.alphavantage_api_key
        if not api_key:
            return {"Error Message": "AlphaVantage API key is missing."}

        params: dict[str, str | int] = {"function": function, "apikey": api_key}
        params.update(kwargs)

        try:
            response = httpx.get(
                self.settings.alphavantage_rest_url,
                params=params,
                timeout=self.settings.alphavantage_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {"Error Message": f"AlphaVantage REST request failed: {exc!s}"}

        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return payload

    def _mcp_url_contains_apikey(self) -> bool:
        parsed = urlsplit(self.settings.alphavantage_mcp_url)
        return "apikey" in parse_qs(parsed.query)

    def _has_data_for_function(self, function: str, payload: dict[str, Any]) -> bool:
        if not payload:
            return False
        if function == "GLOBAL_QUOTE":
            quote_block = self._extract_quote_block(payload)
            return isinstance(quote_block, dict) and bool(quote_block)
        if function == "TIME_SERIES_DAILY":
            daily_block = self._extract_daily_block(payload)
            return isinstance(daily_block, dict) and bool(daily_block)
        if function == "NEWS_SENTIMENT":
            news_block = self._extract_news_block(payload)
            return isinstance(news_block, list) and len(news_block) > 0
        return False

    def _parse_quote_payload(self, ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
        block = self._extract_quote_block(payload)
        if not isinstance(block, dict) or not block:
            return {}
        return {
            "symbol": str(block.get("01. symbol", ticker.upper())),
            "price": self._to_float(block.get("05. price")),
            "change_percent": self._to_percent(block.get("10. change percent")),
            "volume": self._to_float(block.get("06. volume")),
            "latest_trading_day": str(block.get("07. latest trading day", "")),
        }

    def _parse_daily_payload(self, payload: dict[str, Any]) -> list[dict[str, float | str]]:
        block = self._extract_daily_block(payload)
        if not isinstance(block, dict):
            return []

        rows: list[dict[str, float | str]] = []
        for date, values in block.items():
            if not isinstance(values, dict):
                continue
            rows.append(
                {
                    "date": str(date),
                    "open": self._to_float(values.get("1. open")),
                    "high": self._to_float(values.get("2. high")),
                    "low": self._to_float(values.get("3. low")),
                    "close": self._to_float(values.get("4. close")),
                    "volume": self._to_float(values.get("5. volume")),
                }
            )
        rows.sort(key=lambda item: str(item["date"]))
        return rows

    def _parse_news_payload(
        self,
        payload: dict[str, Any],
        limit: int,
    ) -> list[dict[str, float | str]]:
        block = self._extract_news_block(payload)
        if not isinstance(block, list):
            return []

        rows: list[dict[str, float | str]] = []
        for item in block[:limit]:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "source": str(item.get("source", "")),
                    "time_published": str(item.get("time_published", "")),
                    "overall_sentiment_score": self._to_float(item.get("overall_sentiment_score")),
                    "overall_sentiment_label": str(item.get("overall_sentiment_label", "neutral")),
                    "summary": str(item.get("summary", "")),
                }
            )
        return rows

    def _collect_warnings(self, payloads: list[dict[str, Any]]) -> list[str]:
        warnings: list[str] = []
        seen: set[str] = set()
        warning_keys = {"note", "information", "error message", "error_message", "message"}
        for payload in payloads:
            for key, value in self._walk_key_values(payload):
                if key.lower() in warning_keys and value:
                    text = str(value).strip()
                    if text and text not in seen:
                        seen.add(text)
                        warnings.append(text)
        return warnings

    def _extract_quote_block(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        direct_keys = ("Global Quote", "global_quote", "quote")
        block = self._extract_dict_by_keys(payload, direct_keys)
        if isinstance(block, dict) and block:
            return block
        return None

    def _extract_daily_block(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        direct_keys = (
            "Time Series (Daily)",
            "Time Series Daily",
            "time_series_daily",
            "daily",
        )
        block = self._extract_dict_by_keys(payload, direct_keys)
        if isinstance(block, dict) and self._is_time_series_block(block):
            return block

        for _, value in self._walk_key_values(payload):
            if isinstance(value, dict) and self._is_time_series_block(value):
                return value
        return None

    def _extract_news_block(self, payload: dict[str, Any]) -> list[Any] | None:
        direct_keys = ("feed", "news", "news_sentiment")
        block = self._extract_list_by_keys(payload, direct_keys)
        if isinstance(block, list):
            return block
        return None

    def _extract_dict_by_keys(
        self,
        payload: dict[str, Any],
        keys: tuple[str, ...],
    ) -> dict[str, Any] | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        for _, value in self._walk_key_values(payload):
            if isinstance(value, dict):
                for key in keys:
                    nested_value = value.get(key)
                    if isinstance(nested_value, dict):
                        return nested_value
        return None

    def _extract_list_by_keys(
        self,
        payload: dict[str, Any],
        keys: tuple[str, ...],
    ) -> list[Any] | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        for _, value in self._walk_key_values(payload):
            if isinstance(value, dict):
                for key in keys:
                    nested_value = value.get(key)
                    if isinstance(nested_value, list):
                        return nested_value
        return None

    def _walk_key_values(self, payload: dict[str, Any]) -> list[tuple[str, Any]]:
        queue: list[tuple[str, Any, int]] = [("", payload, 0)]
        flattened: list[tuple[str, Any]] = []
        max_depth = 4

        while queue:
            _, current, depth = queue.pop(0)
            if not isinstance(current, dict) or depth > max_depth:
                continue
            for key, value in current.items():
                flattened.append((str(key), value))
                if isinstance(value, dict):
                    queue.append((str(key), value, depth + 1))
        return flattened

    @staticmethod
    def _is_time_series_block(block: dict[str, Any]) -> bool:
        if not block:
            return False
        first_key, first_value = next(iter(block.items()))
        if not isinstance(first_value, dict):
            return False
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(first_key)):
            return False

        normalized_keys = {str(key).lower() for key in first_value.keys()}
        has_open = any("open" in key or key.startswith("1.") for key in normalized_keys)
        has_close = any("close" in key or key.startswith("4.") for key in normalized_keys)
        return has_open and has_close

    @staticmethod
    def _build_trend(candles: list[dict[str, float | str]]) -> dict[str, float | str]:
        if len(candles) < 2:
            return {}
        closes = [float(item["close"]) for item in candles if "close" in item]
        if len(closes) < 2:
            return {}

        last = closes[-1]
        base = closes[-30] if len(closes) >= 30 else closes[0]
        change_pct_30d = ((last / base) - 1.0) * 100 if base else 0.0
        sma_20 = sum(closes[-20:]) / min(20, len(closes))
        sma_50 = sum(closes[-50:]) / min(50, len(closes))

        direction = "sideways"
        if sma_20 > sma_50 and change_pct_30d > 0:
            direction = "uptrend"
        elif sma_20 < sma_50 and change_pct_30d < 0:
            direction = "downtrend"

        return {
            "direction": direction,
            "change_pct_30d": round(change_pct_30d, 3),
            "sma_20": round(sma_20, 4),
            "sma_50": round(sma_50, 4),
        }

    @staticmethod
    def _to_float(raw: Any) -> float:
        try:
            return float(str(raw).replace(",", ""))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_percent(raw: Any) -> float:
        text = str(raw).strip().replace("%", "")
        try:
            return float(text)
        except (TypeError, ValueError):
            return 0.0
