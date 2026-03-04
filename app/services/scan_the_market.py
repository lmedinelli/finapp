from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.services.alphavantage_mcp import AlphaVantageMCPService
from app.services.chart_img import ChartImgService
from app.services.market_data import MarketDataService
from app.services.news import NewsService

FALLBACK_LOW_CAP_STOCKS: list[tuple[str, str]] = [
    ("SOFI", "SoFi Technologies"),
    ("RKLB", "Rocket Lab"),
    ("IONQ", "IonQ"),
    ("PLUG", "Plug Power"),
    ("LMND", "Lemonade"),
    ("ACHR", "Archer Aviation"),
    ("JOBY", "Joby Aviation"),
    ("UPST", "Upstart Holdings"),
    ("CLOV", "Clover Health"),
    ("SOUN", "SoundHound AI"),
    ("HIMS", "Hims & Hers Health"),
    ("RIOT", "Riot Platforms"),
    ("MARA", "MARA Holdings"),
    ("BITF", "Bitfarms"),
    ("CLSK", "CleanSpark"),
]


class ScanTheMarketService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.market_data = MarketDataService()
        self.news_service = NewsService()
        self.alphavantage = AlphaVantageMCPService()
        self.chart_img = ChartImgService()

    def scan(
        self,
        *,
        low_cap_max_usd: float | None = None,
        stock_limit: int | None = None,
        crypto_limit: int | None = None,
        include_ipo: bool = True,
        include_ico: bool = True,
        include_news: bool = True,
        exchanges: list[str] | None = None,
    ) -> dict[str, Any]:
        cap_max = low_cap_max_usd or self.settings.scan_market_low_cap_max_usd
        stock_target = max(1, min(stock_limit or self.settings.scan_market_stock_limit, 25))
        crypto_target = max(1, min(crypto_limit or self.settings.scan_market_crypto_limit, 25))

        warnings: list[str] = []
        sources: set[str] = {"yfinance"}
        exchange_list = exchanges or self._default_exchanges()

        stock_candidates = self._stock_candidates(exchange_list=exchange_list, warnings=warnings)
        stock_opportunities = self._scan_stocks(
            candidates=stock_candidates,
            low_cap_max_usd=cap_max,
            limit=stock_target,
        )
        for row in stock_opportunities:
            source_name = str(row.get("source", "")).strip().lower()
            if source_name:
                sources.add(source_name)

        crypto_opportunities, crypto_sources = self._scan_crypto(
            low_cap_max_usd=cap_max,
            limit=crypto_target,
            warnings=warnings,
        )
        if crypto_opportunities:
            sources.update(crypto_sources)

        ipo_watchlist: list[dict[str, Any]] = []
        ico_watchlist: list[dict[str, Any]] = []
        news_signals: list[dict[str, Any]] = []

        if include_news:
            news_signals = self._collect_news_signals(stock_opportunities, crypto_opportunities)
            if news_signals:
                sources.update({"serpapi", "alphavantage-news-sentiment"})

        if include_ipo:
            ipo_watchlist = self._theme_watchlist("IPO", "stock", category="ipo")
            if ipo_watchlist:
                sources.add("serpapi")
        if include_ico:
            ico_watchlist = self._theme_watchlist("ICO", "crypto", category="ico")
            if ico_watchlist:
                sources.add("serpapi")

        if not stock_opportunities:
            warnings.append("No stock opportunities matched current low-cap filters.")
        if not crypto_opportunities:
            warnings.append("No crypto opportunities matched current low-cap filters.")

        return {
            "scan_id": uuid4().hex,
            "generated_at": datetime.now(UTC),
            "low_cap_max_usd": float(cap_max),
            "stock_opportunities": stock_opportunities,
            "crypto_opportunities": crypto_opportunities,
            "ipo_watchlist": ipo_watchlist,
            "ico_watchlist": ico_watchlist,
            "news_signals": news_signals,
            "data_sources": sorted(sources),
            "warnings": warnings,
        }

    def _default_exchanges(self) -> list[str]:
        value = self.settings.scan_market_exchanges
        return [item.strip().upper() for item in value.split(",") if item.strip()]

    def _stock_candidates(
        self,
        *,
        exchange_list: list[str],
        warnings: list[str],
    ) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        exchange_hint = ",".join(exchange_list) if exchange_list else "default"
        warnings.append(
            "Chart-IMG symbol discovery is disabled (v2-only render policy). "
            f"Using curated stock universe for exchanges={exchange_hint}."
        )

        for symbol, name in FALLBACK_LOW_CAP_STOCKS:
            if symbol in seen:
                continue
            seen.add(symbol)
            rows.append((symbol, name, "fallback-watchlist"))

        return rows

    def _scan_stocks(
        self,
        *,
        candidates: list[tuple[str, str, str]],
        low_cap_max_usd: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        opportunities: list[dict[str, Any]] = []
        max_evaluations = min(45, max(limit * 6, 15))

        for symbol, name, source in candidates[:max_evaluations]:
            try:
                reference = self.market_data.fetch_reference_info(symbol=symbol, asset_type="stock")
                market_cap = float(reference.get("market_cap", 0.0))
                if market_cap <= 0.0 or market_cap > low_cap_max_usd:
                    continue

                history = self.market_data.fetch_history(
                    symbol=symbol,
                    asset_type="stock",
                    period="3mo",
                    interval="1d",
                )
                if history.empty or len(history) < 10:
                    continue

                close = history["close"].astype(float)
                volume = history["volume"].astype(float)
                latest_price = float(close.iloc[-1])
                prev_price = float(close.iloc[-2]) if len(close) > 1 else latest_price
                change_pct = ((latest_price / prev_price) - 1.0) * 100.0 if prev_price else 0.0
                momentum_30d = 0.0
                if len(close) > 30 and float(close.iloc[-31]) != 0.0:
                    momentum_30d = ((latest_price / float(close.iloc[-31])) - 1.0) * 100.0

                latest_volume = float(volume.iloc[-1]) if not volume.empty else 0.0
                avg_volume_20 = float(volume.tail(20).mean()) if not volume.empty else 0.0

                score = 0.0
                if momentum_30d > 15.0:
                    score += 2.0
                elif momentum_30d > 5.0:
                    score += 1.0
                if change_pct > 0.0:
                    score += 0.5
                if avg_volume_20 > 0.0 and latest_volume > (avg_volume_20 * 1.25):
                    score += 1.0
                if market_cap < (low_cap_max_usd * 0.25):
                    score += 1.0

                rationale = (
                    f"30d momentum {momentum_30d:+.1f}%, 1d change {change_pct:+.1f}%, "
                    f"market cap {market_cap:,.0f}."
                )
                opportunities.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "asset_type": "stock",
                        "market_cap": round(market_cap, 2),
                        "price": round(latest_price, 6),
                        "change_pct": round(change_pct, 3),
                        "volume": round(latest_volume, 2),
                        "momentum_30d": round(momentum_30d, 3),
                        "score": round(score, 3),
                        "rationale": rationale,
                        "source": source,
                    }
                )
            except Exception:
                continue

        opportunities.sort(
            key=lambda item: (float(item["score"]), float(item["momentum_30d"])),
            reverse=True,
        )
        return opportunities[:limit]

    def _scan_crypto(
        self,
        *,
        low_cap_max_usd: float,
        limit: int,
        warnings: list[str],
    ) -> tuple[list[dict[str, Any]], set[str]]:
        opportunities: list[dict[str, Any]] = []
        sources: set[str] = set()

        coinmarketcap_rows = self._scan_crypto_coinmarketcap(
            low_cap_max_usd=low_cap_max_usd,
            limit=limit,
            warnings=warnings,
        )
        if coinmarketcap_rows:
            opportunities.extend(coinmarketcap_rows)
            sources.add("coinmarketcap")

        if len(opportunities) < limit:
            coingecko_rows = self._scan_crypto_coingecko(
                low_cap_max_usd=low_cap_max_usd,
                limit=limit,
            )
            if coingecko_rows:
                sources.add("coingecko")
            for row in coingecko_rows:
                symbol = str(row.get("symbol", "")).upper()
                if any(str(item.get("symbol", "")).upper() == symbol for item in opportunities):
                    continue
                opportunities.append(row)

        opportunities.sort(
            key=lambda item: (float(item["score"]), float(item["momentum_30d"])),
            reverse=True,
        )
        return opportunities[:limit], sources

    def _scan_crypto_coinmarketcap(
        self,
        *,
        low_cap_max_usd: float,
        limit: int,
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        if not self.settings.coinmarketcap_api_key:
            warnings.append("COINMARKETCAP_API_KEY not set. Falling back to CoinGecko.")
            return []

        payload = self._coinmarketcap_get(
            "/cryptocurrency/listings/latest",
            params={
                "start": 1,
                "limit": 250,
                "convert": "USD",
                "sort": "market_cap",
                "sort_dir": "asc",
                "cryptocurrency_type": "all",
            },
        )
        if not isinstance(payload, dict):
            warnings.append("CoinMarketCap response was empty. Falling back to CoinGecko.")
            return []

        data = payload.get("data", [])
        if not isinstance(data, list):
            warnings.append("CoinMarketCap data field missing. Falling back to CoinGecko.")
            return []

        rows: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).upper().strip()
            name = str(item.get("name", "") or symbol)
            quote = item.get("quote", {})
            quote_usd = quote.get("USD", {}) if isinstance(quote, dict) else {}
            market_cap = float(quote_usd.get("market_cap") or 0.0)
            if market_cap <= 5_000_000.0 or market_cap > low_cap_max_usd:
                continue

            price = float(quote_usd.get("price") or 0.0)
            volume = float(quote_usd.get("volume_24h") or 0.0)
            change_24h = float(quote_usd.get("percent_change_24h") or 0.0)
            change_7d = float(quote_usd.get("percent_change_7d") or 0.0)
            change_30d = float(quote_usd.get("percent_change_30d") or 0.0)
            cmc_rank = int(item.get("cmc_rank") or 0)
            is_active = int(item.get("is_active") or 1)
            if is_active == 0:
                continue

            score = 0.0
            if change_30d > 25.0:
                score += 2.0
            elif change_30d > 8.0:
                score += 1.0
            if change_7d > 0.0:
                score += 0.5
            if change_24h > 0.0:
                score += 0.5
            if volume > market_cap * 0.05:
                score += 1.0
            if cmc_rank > 0 and cmc_rank <= 200:
                score += 0.5

            rationale = (
                f"CMC rank {cmc_rank}, 30d {change_30d:+.1f}%, "
                f"7d {change_7d:+.1f}%, 24h {change_24h:+.1f}%."
            )
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "asset_type": "crypto",
                    "market_cap": round(market_cap, 2),
                    "price": round(price, 8),
                    "change_pct": round(change_24h, 3),
                    "volume": round(volume, 2),
                    "momentum_30d": round(change_30d, 3),
                    "score": round(score, 3),
                    "rationale": rationale,
                    "source": "coinmarketcap",
                }
            )

        rows.sort(
            key=lambda item: (float(item["score"]), float(item["momentum_30d"])),
            reverse=True,
        )
        return rows[: max(limit, 12)]

    def _scan_crypto_coingecko(self, *, low_cap_max_usd: float, limit: int) -> list[dict[str, Any]]:
        markets = self._coingecko_get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_asc",
                "per_page": 200,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h,30d",
            },
        )
        if not isinstance(markets, list):
            return []

        trending_symbols: set[str] = set()
        trending_payload = self._coingecko_get("/search/trending", params={})
        if isinstance(trending_payload, dict):
            coins = trending_payload.get("coins", [])
            if isinstance(coins, list):
                for item in coins:
                    coin = item.get("item", {}) if isinstance(item, dict) else {}
                    symbol = str(coin.get("symbol", "")).upper().strip()
                    if symbol:
                        trending_symbols.add(symbol)

        rows: list[dict[str, Any]] = []
        for item in markets:
            if not isinstance(item, dict):
                continue
            market_cap = float(item.get("market_cap") or 0.0)
            if market_cap <= 5_000_000.0 or market_cap > low_cap_max_usd:
                continue
            symbol = str(item.get("symbol", "")).upper()
            name = str(item.get("name", "") or symbol)
            price = float(item.get("current_price") or 0.0)
            volume = float(item.get("total_volume") or 0.0)
            change_24h = float(item.get("price_change_percentage_24h") or 0.0)
            momentum_30d = float(item.get("price_change_percentage_30d_in_currency") or 0.0)

            score = 0.0
            if symbol in trending_symbols:
                score += 1.5
            if momentum_30d > 20.0:
                score += 2.0
            elif momentum_30d > 8.0:
                score += 1.0
            if change_24h > 0.0:
                score += 0.5
            if volume > market_cap * 0.05:
                score += 1.0

            rationale = (
                f"30d momentum {momentum_30d:+.1f}%, 24h change {change_24h:+.1f}%, "
                f"market cap {market_cap:,.0f}."
            )
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "asset_type": "crypto",
                    "market_cap": round(market_cap, 2),
                    "price": round(price, 8),
                    "change_pct": round(change_24h, 3),
                    "volume": round(volume, 2),
                    "momentum_30d": round(momentum_30d, 3),
                    "score": round(score, 3),
                    "rationale": rationale,
                    "source": "coingecko",
                }
            )

        rows.sort(
            key=lambda item: (float(item["score"]), float(item["momentum_30d"])),
            reverse=True,
        )
        return rows[:limit]

    def _collect_news_signals(
        self,
        stock_opportunities: list[dict[str, Any]],
        crypto_opportunities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        stock_theme = self.news_service.fetch_news(
            symbol="small cap",
            asset_type="stock",
            limit=min(6, self.settings.scan_market_news_limit),
        )
        for item in stock_theme:
            rows.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "source": str(item.get("source", "")),
                    "published_at": str(item.get("published_at", "")),
                    "sentiment_label": "neutral",
                    "sentiment_score": 0.0,
                    "category": "stock",
                }
            )

        crypto_theme = self.news_service.fetch_news(
            symbol="new crypto listing",
            asset_type="crypto",
            limit=min(6, self.settings.scan_market_news_limit),
        )
        for item in crypto_theme:
            rows.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "source": str(item.get("source", "")),
                    "published_at": str(item.get("published_at", "")),
                    "sentiment_label": "neutral",
                    "sentiment_score": 0.0,
                    "category": "crypto",
                }
            )

        for item in stock_opportunities[:3]:
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            alpha_news = self.alphavantage.get_news_sentiment(symbol=symbol, limit=3)
            for news_item in alpha_news:
                rows.append(
                    {
                        "title": str(news_item.get("title", "")),
                        "url": str(news_item.get("url", "")),
                        "source": str(news_item.get("source", "")),
                        "published_at": str(news_item.get("time_published", "")),
                        "sentiment_label": str(
                            news_item.get("overall_sentiment_label", "neutral")
                        ).lower(),
                        "sentiment_score": float(news_item.get("overall_sentiment_score") or 0.0),
                        "category": "stock",
                    }
                )

        for item in crypto_opportunities[:2]:
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            alpha_news = self.alphavantage.get_news_sentiment(symbol=symbol, limit=2)
            for news_item in alpha_news:
                rows.append(
                    {
                        "title": str(news_item.get("title", "")),
                        "url": str(news_item.get("url", "")),
                        "source": str(news_item.get("source", "")),
                        "published_at": str(news_item.get("time_published", "")),
                        "sentiment_label": str(
                            news_item.get("overall_sentiment_label", "neutral")
                        ).lower(),
                        "sentiment_score": float(news_item.get("overall_sentiment_score") or 0.0),
                        "category": "crypto",
                    }
                )

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = (str(row.get("url", "")) or str(row.get("title", ""))).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped[: self.settings.scan_market_news_limit]

    def _theme_watchlist(
        self,
        keyword: str,
        asset_type: str,
        *,
        category: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        items = self.news_service.fetch_news(
            symbol=keyword,
            asset_type=asset_type,
            limit=min(6, self.settings.scan_market_news_limit),
        )
        for item in items:
            rows.append(
                {
                    "title": str(item.get("title", "")),
                    "url": str(item.get("url", "")),
                    "source": str(item.get("source", "")),
                    "published_at": str(item.get("published_at", "")),
                    "sentiment_label": "neutral",
                    "sentiment_score": 0.0,
                    "category": category,
                }
            )
        return rows

    def _coingecko_get(self, path: str, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        headers: dict[str, str] = {"accept": "application/json"}
        if self.settings.coingecko_api_key:
            headers["x-cg-pro-api-key"] = self.settings.coingecko_api_key

        base = self.settings.coingecko_base_url.rstrip("/")
        url = f"{base}{path if path.startswith('/') else f'/{path}'}"
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=20.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return {}
        try:
            payload = response.json()
        except ValueError:
            return {}
        if isinstance(payload, (dict, list)):
            return payload
        return {}

    def _coinmarketcap_get(
        self,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        api_key = self.settings.coinmarketcap_api_key
        if not api_key:
            return {}

        headers = {
            "Accept": "application/json",
            "X-CMC_PRO_API_KEY": api_key,
        }
        base = self.settings.coinmarketcap_base_url.rstrip("/")
        url = f"{base}{path if path.startswith('/') else f'/{path}'}"
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=20.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return {}
        try:
            payload = response.json()
        except ValueError:
            return {}
        if isinstance(payload, (dict, list)):
            return payload
        return {}
