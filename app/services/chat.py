from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from app.core.config import get_settings
from app.db.admin import SessionLocal
from app.repositories.chat_memory_repo import ChatMemoryRepository
from app.services.activity_log import ActivityLogService
from app.services.alphavantage_mcp import AlphaVantageMCPService
from app.services.analytics import AnalyticsService
from app.services.market_data import MarketDataService
from app.services.recommendation import RecommendationService
from app.services.scan_the_market import ScanTheMarketService


class ChatService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.analytics = AnalyticsService()
        self.market_data = MarketDataService()
        self.recommendation = RecommendationService()
        self.alphavantage = AlphaVantageMCPService()
        self.scanner = ScanTheMarketService()
        self.activity_log = ActivityLogService()

    def respond(
        self,
        message: str,
        symbol: str | None,
        asset_type: str,
        risk_profile: str,
        session_id: str | None = None,
        include_news: bool = True,
        include_alpha_context: bool = True,
        include_merged_news_sentiment: bool = False,
    ) -> dict:
        active_session_id = session_id or uuid4().hex
        workflow_steps: list[str] = []
        memory_messages = self._load_memory(active_session_id)
        self._save_memory(active_session_id, "user", message)

        if self._is_scan_request(message):
            workflow_steps.append("workflow:scan_the_market")
            scan_data = self.scanner.scan()
            workflow_steps.append("tool:scan_the_market")
            for source in scan_data.get("data_sources", []):
                source_text = str(source).strip().lower()
                if source_text:
                    workflow_steps.append(f"tool:{source_text}")
            answer = self._build_scan_answer(scan_data)
            workflow_steps.append("llm:fallback")
            self._save_memory(active_session_id, "assistant", answer)
            self.activity_log.log_market_scan(trigger_source="chat", payload=scan_data)

            scan_news = scan_data.get("news_signals", [])
            news_items: list[dict[str, str]] = []
            if isinstance(scan_news, list):
                for item in scan_news[:8]:
                    if not isinstance(item, dict):
                        continue
                    news_items.append(
                        {
                            "title": str(item.get("title", "")),
                            "url": str(item.get("url", "")),
                            "source": str(item.get("source", "")),
                            "published_at": str(item.get("published_at", "")),
                        }
                    )

            return {
                "session_id": active_session_id,
                "symbol": "SCAN",
                "asset_type": asset_type,
                "answer": answer,
                "inferred_horizon": "both",
                "recommendation": None,
                "analysis": None,
                "news": news_items,
                "market_context": None,
                "market_scan": scan_data,
                "disclaimer": "Decision support only. This is not financial advice.",
                "workflow_steps": workflow_steps,
            }

        resolved_symbol = self._resolve_symbol(
            message=message,
            symbol=symbol,
            asset_type=asset_type,
        )
        if not resolved_symbol:
            raise ValueError("Could not infer symbol. Please provide a ticker like AAPL or BTC.")
        workflow_steps.append(f"symbol_resolved:{resolved_symbol.upper()}")

        normalized_symbol = self.market_data.normalize_symbol(resolved_symbol, asset_type)
        analysis = self._compute_or_ingest(normalized_symbol, asset_type, workflow_steps)
        recommendation = self.recommendation.recommend(
            symbol=normalized_symbol,
            risk_profile=risk_profile,
            asset_type=asset_type,
            include_news=include_news,
        )
        workflow_steps.append("tool:recommendation")
        market_context: dict | None = None
        if include_alpha_context:
            market_context = self.alphavantage.get_market_context(normalized_symbol)
            has_context = (
                market_context.get("quote")
                or market_context.get("trend")
                or market_context.get("news")
            )
            if has_context:
                workflow_steps.append("tool:alphavantage_context")
            else:
                market_context = None

        merged_news = recommendation["news"]
        if include_merged_news_sentiment:
            merged_news = self._merge_news_items(
                serp_news=recommendation["news"],
                alpha_news=((market_context or {}).get("news") or []),
            )
            merged_sentiment = self._merge_sentiment_scores(
                serp_sentiment=recommendation.get("news_sentiment", {}),
                alpha_news=((market_context or {}).get("news") or []),
            )
            recommendation["news"] = merged_news
            recommendation["news_sentiment"] = merged_sentiment
            workflow_steps.append("tool:merged_news_sentiment")

        horizon = self._infer_horizon(message)
        workflow_steps.append(f"horizon:{horizon}")
        support_resistance_request = self._is_support_resistance_request(message)
        risk_request = self._is_risk_request(message)
        if support_resistance_request:
            workflow_steps.append("intent:support_resistance")
        if risk_request:
            workflow_steps.append("intent:risk_assessment")

        if support_resistance_request:
            answer = self._build_support_resistance_answer(
                symbol=normalized_symbol,
                analysis=analysis,
                market_context=market_context,
                recommendation=recommendation,
            )
            workflow_steps.append("llm:bypass_support_resistance")
        else:
            llm_answer = self._generate_llm_answer(
                message=message,
                memory_messages=memory_messages,
                symbol=normalized_symbol,
                asset_type=asset_type,
                risk_profile=risk_profile,
                analysis=analysis,
                recommendation=recommendation,
                market_context=market_context,
                workflow_steps=workflow_steps,
            )
            if llm_answer:
                answer = llm_answer
            elif risk_request:
                answer = self._build_risk_answer(
                    symbol=normalized_symbol,
                    recommendation=recommendation,
                    analysis=analysis,
                    market_context=market_context,
                )
            else:
                answer = self._build_answer(
                    message=message,
                    symbol=normalized_symbol,
                    horizon=horizon,
                    recommendation=recommendation,
                    analysis=analysis,
                    market_context=market_context,
                )
            if llm_answer:
                workflow_steps.append("llm:openai")
            else:
                workflow_steps.append("llm:fallback")

        self._save_memory(active_session_id, "assistant", answer)
        self.activity_log.log_recommendation(
            source="chat",
            session_id=active_session_id,
            request_message=message,
            symbol=normalized_symbol,
            asset_type=asset_type,
            risk_profile=risk_profile,
            answer_text=answer,
            workflow_steps=workflow_steps,
            recommendation=recommendation,
            analysis=analysis,
            market_context=market_context,
        )

        return {
            "session_id": active_session_id,
            "symbol": normalized_symbol,
            "asset_type": asset_type,
            "answer": answer,
            "inferred_horizon": horizon,
            "recommendation": recommendation,
            "analysis": analysis,
            "news": merged_news,
            "market_context": market_context,
            "market_scan": None,
            "disclaimer": "Decision support only. This is not financial advice.",
            "workflow_steps": workflow_steps,
        }

    def _resolve_symbol(self, *, message: str, symbol: str | None, asset_type: str) -> str | None:
        inferred = self._infer_symbol(message, asset_type)
        if inferred:
            if symbol and inferred.upper() != symbol.upper():
                return inferred
            if not symbol:
                return inferred
        return symbol

    def _compute_or_ingest(
        self,
        symbol: str,
        asset_type: str,
        workflow_steps: list[str],
    ) -> dict[str, float | str]:
        try:
            result = self.analytics.compute(symbol)
            workflow_steps.append("tool:analysis_local")
            return result
        except ValueError:
            ingest_result = self.market_data.ingest(symbol=symbol, asset_type=asset_type)
            workflow_steps.append(f"tool:ingest inserted={ingest_result.get('inserted', 0)}")
            try:
                return self.analytics.compute(symbol)
            except ValueError as exc:
                raise ValueError(
                    f"No local data available for {symbol}. Ingestion returned insufficient data."
                ) from exc

    def _load_memory(self, session_id: str) -> list[dict[str, str]]:
        with SessionLocal() as session:
            repo = ChatMemoryRepository(session)
            rows = repo.list_recent(
                session_id=session_id,
                limit=self.settings.agent_memory_messages,
            )
        return [{"role": row.role, "content": row.content} for row in rows]

    def _save_memory(self, session_id: str, role: str, content: str) -> None:
        with SessionLocal() as session:
            repo = ChatMemoryRepository(session)
            repo.add_entry(session_id=session_id, role=role, content=content)

    def _generate_llm_answer(
        self,
        message: str,
        memory_messages: list[dict[str, str]],
        symbol: str,
        asset_type: str,
        risk_profile: str,
        analysis: dict[str, float | str],
        recommendation: dict,
        market_context: dict | None,
        workflow_steps: list[str],
    ) -> str:
        if not self.settings.openai_api_key:
            return ""

        try:
            from openai import OpenAI
        except Exception as exc:
            workflow_steps.append(f"llm:import_error:{exc.__class__.__name__}")
            return ""

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url or None,
        )
        news_items = recommendation.get("news", [])
        compact_context = {
            "symbol": symbol,
            "asset_type": asset_type,
            "risk_profile": risk_profile,
            "analysis": analysis,
            "short_term": recommendation.get("short_term"),
            "long_term": recommendation.get("long_term"),
            "news_sentiment": recommendation.get("news_sentiment"),
            "news_top_items": news_items[:4],
            "alphavantage": {
                "quote": (market_context or {}).get("quote"),
                "trend": (market_context or {}).get("trend"),
                "news_top_items": ((market_context or {}).get("news") or [])[:4],
                "latest_closes": [
                    item.get("close")
                    for item in ((market_context or {}).get("candles") or [])[-5:]
                ],
            },
            "workflow_steps": workflow_steps,
        }

        system_prompt = (
            "You are a financial decision-support assistant. "
            "Be practical and specific. Use available tool context numbers directly. "
            "Respond with: Summary, Key Drivers, Levels/Triggers, and Risk Note. "
            "Never claim certainty and never present financial advice."
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in memory_messages:
            role = item.get("role", "")
            content = item.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content[-1200:]})
        memory_text = "\n".join(
            f"{item['role']}: {item['content']}" for item in messages[1:][-6:]
        )
        user_prompt = (
            f"Tool context JSON:\n{json.dumps(compact_context, default=str)}\n\n"
            f"Recent conversation:\n{memory_text or '(none)'}\n\n"
            f"User question:\n{message}"
        )

        candidate_models = self._llm_candidate_models()
        preferred_model = str(self.settings.openai_model).strip()

        for model_name in candidate_models:
            try:
                workflow_steps.append(f"llm:responses_attempt:{model_name}")
                response = client.responses.create(
                    model=model_name,
                    input=f"{system_prompt}\n\n{user_prompt}",
                    max_output_tokens=700,
                )
                output_text = self._extract_responses_text(response)
                if output_text:
                    workflow_steps.append(f"llm:responses_success:{model_name}")
                    if model_name != preferred_model:
                        workflow_steps.append(f"llm:model_fallback:{preferred_model}->{model_name}")
                    return output_text
                workflow_steps.append(f"llm:responses_empty:{model_name}")
            except Exception as exc:
                workflow_steps.append(f"llm:responses_error:{model_name}:{exc.__class__.__name__}")

        chat_messages = messages[:]
        chat_messages.append(
            {
                "role": "system",
                "content": f"Tool context JSON: {json.dumps(compact_context, default=str)}",
            }
        )
        chat_messages.append({"role": "user", "content": message})

        for model_name in candidate_models[:4]:
            try:
                workflow_steps.append(f"llm:chat_completions_attempt:{model_name}")
                chat_response = client.chat.completions.create(
                    model=model_name,
                    messages=cast(Any, chat_messages),
                )
                output_text = self._extract_chat_text(chat_response)
                if output_text:
                    workflow_steps.append(f"llm:chat_completions_success:{model_name}")
                    if model_name != preferred_model:
                        workflow_steps.append(f"llm:model_fallback:{preferred_model}->{model_name}")
                    return output_text
                workflow_steps.append(f"llm:chat_completions_empty:{model_name}")
            except Exception as exc:
                workflow_steps.append(
                    f"llm:chat_completions_error:{model_name}:{exc.__class__.__name__}"
                )

        return ""

    def _llm_candidate_models(self) -> list[str]:
        candidates: list[str] = []
        preferred = str(self.settings.openai_model).strip()
        if preferred:
            candidates.append(preferred)

        raw_csv = str(self.settings.openai_admin_model_candidates).strip()
        if raw_csv:
            for item in raw_csv.split(","):
                model = item.strip()
                if model:
                    candidates.append(model)

        candidates.extend(["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"])
        deduped: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        return deduped[:10]

    @staticmethod
    def _extract_responses_text(response: Any) -> str:
        output_text = str(getattr(response, "output_text", "")).strip()
        if output_text:
            return output_text

        output_items = getattr(response, "output", None)
        if not isinstance(output_items, list):
            return ""

        parts: list[str] = []
        for item in output_items:
            if isinstance(item, dict):
                content_items = item.get("content")
            else:
                content_items = getattr(item, "content", None)
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                if isinstance(content, dict):
                    text_value = content.get("text", "")
                else:
                    text_value = getattr(content, "text", "")
                text = str(text_value).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _extract_chat_text(chat_response: Any) -> str:
        choices = getattr(chat_response, "choices", None)
        if not isinstance(choices, list) or not choices:
            return ""
        message = getattr(choices[0], "message", None)
        if message is None:
            return ""
        content_any = getattr(message, "content", "")
        if isinstance(content_any, str):
            return content_any.strip()
        if isinstance(content_any, list):
            parts: list[str] = []
            for item in content_any:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                else:
                    text = str(getattr(item, "text", "")).strip()
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()
        return ""

    @staticmethod
    def _infer_symbol(message: str, asset_type: str) -> str | None:
        candidates = re.findall(r"\b[A-Z]{2,6}(?:-[A-Z]{2,6})?\b", message)
        if not candidates:
            return None
        best = str(candidates[0])
        if asset_type == "crypto" and "-" not in best:
            return f"{best}-USD"
        return best

    @staticmethod
    def _is_scan_request(message: str) -> bool:
        lowered = message.lower()
        tokens = [
            "scan the market",
            "scan market",
            "scanthemarket",
            "low cap gems",
            "find gems",
            "new ipo",
            "new ico",
            "future stocks",
            "future crypto",
            "coinmarketcap",
            "coin market cap",
            "market scan",
        ]
        return any(token in lowered for token in tokens) or bool(re.search(r"\bcmc\b", lowered))

    @staticmethod
    def _build_scan_answer(scan_data: dict[str, Any]) -> str:
        stocks = scan_data.get("stock_opportunities", [])
        crypto = scan_data.get("crypto_opportunities", [])
        ipo = scan_data.get("ipo_watchlist", [])
        ico = scan_data.get("ico_watchlist", [])
        warnings = scan_data.get("warnings", [])

        stock_text = "No stock matches."
        if isinstance(stocks, list) and stocks:
            top = stocks[:3]
            stock_text = ", ".join(
                [
                    f"{str(item.get('symbol', ''))} ({float(item.get('score', 0.0)):.1f})"
                    for item in top
                    if isinstance(item, dict)
                ]
            )

        crypto_text = "No crypto matches."
        if isinstance(crypto, list) and crypto:
            top = crypto[:3]
            crypto_text = ", ".join(
                [
                    f"{str(item.get('symbol', ''))} ({float(item.get('score', 0.0)):.1f})"
                    for item in top
                    if isinstance(item, dict)
                ]
            )

        ipo_count = len(ipo) if isinstance(ipo, list) else 0
        ico_count = len(ico) if isinstance(ico, list) else 0
        warning_text = ""
        if isinstance(warnings, list) and warnings:
            warning_text = f" Warnings: {str(warnings[0])}"
        sources = scan_data.get("data_sources", [])
        source_text = ""
        if isinstance(sources, list) and sources:
            source_text = f" Sources: {', '.join([str(item) for item in sources[:4]])}."

        return (
            "ScanTheMarket complete. "
            f"Top low-cap stocks: {stock_text}. "
            f"Top low-cap crypto: {crypto_text}. "
            f"IPO signals={ipo_count}, ICO signals={ico_count}."
            f"{source_text}{warning_text}"
        )

    @staticmethod
    def _infer_horizon(message: str) -> Literal["short_term", "long_term", "both"]:
        lowered = message.lower()
        short_tokens = ["short", "week", "swing", "intraday", "tomorrow"]
        has_short = any(token in lowered for token in short_tokens)
        has_long = any(token in lowered for token in ["long", "month", "year", "invest", "hold"])
        if has_short and has_long:
            return "both"
        if has_short:
            return "short_term"
        if has_long:
            return "long_term"
        return "both"

    @staticmethod
    def _is_support_resistance_request(message: str) -> bool:
        lowered = message.lower()
        support_tokens = ["support", "resistance", "key levels", "price levels", "s/r"]
        return any(token in lowered for token in support_tokens)

    @staticmethod
    def _is_risk_request(message: str) -> bool:
        lowered = message.lower()
        tokens = [
            "risk",
            "risks",
            "risk factors",
            "drawdown",
            "downside",
            "volatility risk",
        ]
        return any(token in lowered for token in tokens)

    @staticmethod
    def _build_support_resistance_answer(
        symbol: str,
        analysis: dict[str, float | str],
        market_context: dict | None,
        recommendation: dict[str, Any],
    ) -> str:
        latest = float(analysis.get("latest_close", 0.0))
        support_60d = float(analysis.get("support_60d", 0.0))
        resistance_60d = float(analysis.get("resistance_60d", 0.0))
        rsi = float(analysis.get("rsi_14", 0.0))
        vol = float(analysis.get("volatility_30d", 0.0))
        short_action = str((recommendation.get("short_term") or {}).get("action", "hold")).upper()
        long_action = str((recommendation.get("long_term") or {}).get("action", "hold")).upper()

        quote = (market_context or {}).get("quote", {})
        live_text = ""
        if quote:
            live_price = float(quote.get("price", 0.0))
            live_change = float(quote.get("change_percent", 0.0))
            live_text = f" Live={live_price:.2f} ({live_change:+.2f}%)."

        return (
            f"{symbol} key levels: Support(60d)={support_60d:.2f}, "
            f"Resistance(60d)={resistance_60d:.2f}, Latest={latest:.2f}.{live_text} "
            f"Context: RSI14={rsi:.1f}, Vol30d={vol:.1%}, "
            f"Short-term={short_action}, Long-term={long_action}. "
            "Decision support only, not financial advice."
        )

    @staticmethod
    def _build_risk_answer(
        symbol: str,
        recommendation: dict[str, Any],
        analysis: dict[str, float | str],
        market_context: dict | None = None,
    ) -> str:
        latest = float(analysis.get("latest_close", 0.0))
        support = float(analysis.get("support_60d", 0.0))
        resistance = float(analysis.get("resistance_60d", 0.0))
        vol = float(analysis.get("volatility_30d", 0.0))
        rsi = float(analysis.get("rsi_14", 50.0))
        macd = float(analysis.get("macd", 0.0))
        macd_signal = float(analysis.get("macd_signal", 0.0))
        short = recommendation.get("short_term", {})
        long = recommendation.get("long_term", {})
        news = recommendation.get("news_sentiment", {})

        support_gap_pct = ((latest / support) - 1.0) * 100.0 if support > 0 else 0.0
        resistance_gap_pct = ((resistance / latest) - 1.0) * 100.0 if latest > 0 else 0.0
        volatility_label = "high" if vol >= 0.35 else "moderate" if vol >= 0.2 else "low"
        rsi_label = "overbought" if rsi >= 70 else "oversold" if rsi <= 30 else "neutral"
        momentum_label = "bearish" if macd < macd_signal else "bullish"

        quote = (market_context or {}).get("quote", {})
        quote_text = ""
        if quote:
            live_price = float(quote.get("price", 0.0))
            live_change = float(quote.get("change_percent", 0.0))
            quote_text = f" Live={live_price:.2f} ({live_change:+.2f}%)."

        return (
            f"{symbol} risk review: "
            f"Volatility={volatility_label} ({vol:.1%}), RSI14={rsi:.1f} ({rsi_label}), "
            f"MACD momentum={momentum_label}. "
            f"Support={support:.2f} ({support_gap_pct:.2f}% below), "
            f"Resistance={resistance:.2f} ({resistance_gap_pct:.2f}% above). "
            f"Current stances: short-term={str(short.get('action', 'hold')).upper()} "
            f"({float(short.get('confidence', 0.0)):.0%}), "
            f"long-term={str(long.get('action', 'hold')).upper()} "
            f"({float(long.get('confidence', 0.0)):.0%}), "
            f"news={str(news.get('label', 'neutral')).upper()}.{quote_text} "
            "Decision support only, not financial advice."
        )

    @staticmethod
    def _build_answer(
        message: str,
        symbol: str,
        horizon: Literal["short_term", "long_term", "both"],
        recommendation: dict,
        analysis: dict[str, float | str],
        market_context: dict | None = None,
    ) -> str:
        short = recommendation["short_term"]
        long = recommendation["long_term"]
        news = recommendation["news_sentiment"]
        latest = float(analysis["latest_close"])
        vol = float(analysis["volatility_30d"])
        rsi = float(analysis["rsi_14"])
        support_60d = float(analysis.get("support_60d", 0.0))
        resistance_60d = float(analysis.get("resistance_60d", 0.0))
        macd = float(analysis.get("macd", 0.0))
        macd_signal = float(analysis.get("macd_signal", 0.0))
        sma_20 = float(analysis.get("sma_20", 0.0))
        sma_50 = float(analysis.get("sma_50", 0.0))
        sma_200 = float(analysis.get("sma_200", 0.0))
        momentum_30d = float(analysis.get("momentum_30d", 0.0))
        momentum_90d = float(analysis.get("momentum_90d", 0.0))
        quote = (market_context or {}).get("quote", {})
        trend = (market_context or {}).get("trend", {})
        quote_text = ""
        if quote:
            price = float(quote.get("price", 0.0))
            change_pct = float(quote.get("change_percent", 0.0))
            quote_text = f" Live={price:.2f} ({change_pct:+.2f}%)."
        trend_text = ""
        if trend:
            trend_text = f" External trend={trend.get('direction', 'sideways')}."

        rsi_label = "overbought" if rsi >= 70 else "oversold" if rsi <= 30 else "neutral"
        macd_label = "bullish" if macd >= macd_signal else "bearish"
        trend_stack = (
            "uptrend"
            if latest >= sma_20 >= sma_50
            else "downtrend"
            if latest <= sma_20 <= sma_50
            else "mixed"
        )
        support_gap_pct = ((latest / support_60d) - 1.0) * 100.0 if support_60d > 0 else 0.0
        resistance_gap_pct = ((resistance_60d / latest) - 1.0) * 100.0 if latest > 0 else 0.0

        if horizon == "short_term":
            return (
                f"{symbol} short-term outlook (1-4 weeks): {short['action'].upper()} "
                f"(confidence {short['confidence']:.0%}). "
                f"Signals: trend_stack={trend_stack}, RSI14={rsi:.1f} ({rsi_label}), "
                f"MACD={macd_label}, momentum30d={momentum_30d:+.2%}, vol30d={vol:.1%}. "
                f"Levels: support60d={support_60d:.2f} ({support_gap_pct:.2f}% gap), "
                f"resistance60d={resistance_60d:.2f} ({resistance_gap_pct:.2f}% gap). "
                f"News sentiment={news['label']}.{quote_text}{trend_text}"
            )
        if horizon == "long_term":
            return (
                f"{symbol} long-term outlook (6-12+ months): {long['action'].upper()} "
                f"(confidence {long['confidence']:.0%}). "
                f"Trend: signal_long_term={analysis['signal_long_term']}, "
                f"latest={latest:.2f}, SMA50={sma_50:.2f}, SMA200={sma_200:.2f}, "
                f"momentum90d={momentum_90d:+.2%}, vol30d={vol:.1%}. "
                f"Risk context: RSI14={rsi:.1f} ({rsi_label}), MACD={macd_label}, "
                f"news={news['label']}.{quote_text}{trend_text}"
            )

        style_hint = "balanced"
        lowered = message.lower()
        if "2 week" in lowered or "2 weeks" in lowered:
            style_hint = "2-week tactical"
        elif "12 month" in lowered or "12 months" in lowered or "1 year" in lowered:
            style_hint = "12-month strategic"

        return (
            f"{symbol} {style_hint} view: short-term={short['action'].upper()} "
            f"({short['confidence']:.0%}), long-term={long['action'].upper()} "
            f"({long['confidence']:.0%}). "
            f"Drivers: latest={latest:.2f}, trend_stack={trend_stack}, "
            f"SMA20={sma_20:.2f}, SMA50={sma_50:.2f}, RSI14={rsi:.1f} ({rsi_label}), "
            f"MACD={macd_label}, vol30d={vol:.1%}, news={news['label']}. "
            f"Levels: support60d={support_60d:.2f}, resistance60d={resistance_60d:.2f}."
            f"{quote_text}{trend_text}"
        )

    @staticmethod
    def _merge_news_items(
        serp_news: list[dict[str, Any]],
        alpha_news: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        seen: set[str] = set()

        for item in serp_news:
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            key = (url or title).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "title": title,
                    "url": url,
                    "source": str(item.get("source", "")),
                    "published_at": str(item.get("published_at", "")),
                }
            )

        for item in alpha_news:
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            key = (url or title).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "title": title,
                    "url": url,
                    "source": str(item.get("source", "")),
                    "published_at": str(item.get("time_published", "")),
                }
            )

        return merged

    @staticmethod
    def _merge_sentiment_scores(
        serp_sentiment: dict[str, Any],
        alpha_news: list[dict[str, Any]],
    ) -> dict[str, Any]:
        serp_score = float(serp_sentiment.get("score", 0.0))
        serp_size = int(serp_sentiment.get("sample_size", 0))

        alpha_scores: list[float] = []
        for item in alpha_news:
            raw = item.get("overall_sentiment_score")
            try:
                if raw is None:
                    continue
                alpha_scores.append(float(str(raw)))
            except (TypeError, ValueError):
                continue
        alpha_size = len(alpha_scores)
        alpha_score = sum(alpha_scores) / alpha_size if alpha_scores else 0.0

        total_size = serp_size + alpha_size
        if total_size == 0:
            merged_score = 0.0
        else:
            merged_score = ((serp_score * serp_size) + (alpha_score * alpha_size)) / total_size

        label = "neutral"
        if merged_score > 0.15:
            label = "positive"
        elif merged_score < -0.15:
            label = "negative"

        return {
            "score": round(merged_score, 3),
            "label": label,
            "sample_size": total_size,
            "generated_at": datetime.now(UTC).isoformat(),
        }
