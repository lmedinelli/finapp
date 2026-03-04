from __future__ import annotations

import base64
import logging
import re
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_RATE_LIMIT_LOCK = threading.Lock()
_LAST_CHART_IMG_REQUEST_TS = 0.0


class ChartImgService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def render_candle_image(
        self,
        symbol: str,
        asset_type: str,
        interval: str = "1D",
        theme: str = "dark",
        width: int = 800,
        height: int = 600,
        studies: list[str] | None = None,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        api_key = self.settings.chart_img_api_key
        if not api_key:
            raise ValueError("Chart-IMG API key is missing. Configure CHART_IMG_API_KEY in .env.")

        tradingview_symbol = self.resolve_tradingview_symbol(
            symbol=symbol,
            asset_type=asset_type,
            exchange=exchange,
        )
        max_studies = max(1, int(self.settings.chart_img_max_studies))
        mapped_studies = self._map_studies(studies or [])[:max_studies]
        max_width = max(400, int(self.settings.chart_img_max_width))
        max_height = max(300, int(self.settings.chart_img_max_height))
        payload: dict[str, Any] = {
            "symbol": tradingview_symbol,
            "interval": interval,
            "theme": theme,
            "width": int(max(400, min(width, max_width))),
            "height": int(max(300, min(height, max_height))),
        }
        if mapped_studies:
            payload["studies"] = mapped_studies

        try:
            image_bytes, content_type = self._post_chart(payload=payload, api_key=api_key)
            studies_applied = [item.get("name", "") for item in mapped_studies]
        except ValueError as exc:
            if mapped_studies:
                logger.warning(
                    "Chart-IMG failed with studies for %s (%s). Retrying without studies.",
                    tradingview_symbol,
                    exc,
                )
                payload.pop("studies", None)
                image_bytes, content_type = self._post_chart(payload=payload, api_key=api_key)
                studies_applied = []
            else:
                raise

        return {
            "symbol": symbol.upper(),
            "asset_type": asset_type,
            "tradingview_symbol": tradingview_symbol,
            "interval": interval,
            "theme": theme,
            "width": int(payload["width"]),
            "height": int(payload["height"]),
            "studies_requested": studies or [],
            "studies_applied": studies_applied,
            "content_type": content_type.split(";")[0].strip(),
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "source": (
                f"chart-img:{self._active_api_version()}:"
                f"{self._active_advanced_chart_path()}"
            ),
        }

    def list_exchanges(self) -> list[dict[str, Any]]:
        payload = self._get_json(self.settings.chart_img_exchanges_path)
        items = self._payload_items(payload)
        if not isinstance(items, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                code = str(
                    item.get("code")
                    or item.get("id")
                    or item.get("exchange")
                    or item.get("name")
                    or ""
                ).upper()
                name = str(item.get("name") or item.get("exchange") or code).strip()
                if not code:
                    continue
                rows.append(
                    {
                        "name": name,
                        "code": code,
                    }
                )
            elif isinstance(item, str):
                code = item.strip().upper()
                rows.append({"name": code, "code": code})
        return rows

    def list_symbols(self, exchange: str) -> list[dict[str, Any]]:
        payload = self._get_json(self.settings.chart_img_symbols_path.format(exchange=exchange))
        items = self._payload_items(payload)
        if not isinstance(items, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                symbol = str(
                    item.get("symbol")
                    or item.get("ticker")
                    or item.get("code")
                    or item.get("name")
                    or ""
                ).upper()
                if not symbol:
                    continue
                resolved_exchange = str(
                    item.get("exchange")
                    or item.get("exchange_id")
                    or item.get("exchangeId")
                    or exchange
                ).upper()
                rows.append(
                    {
                        "symbol": symbol,
                        "description": str(item.get("description", "") or item.get("name", "")),
                        "exchange": resolved_exchange,
                        "full_symbol": str(
                            item.get("full_symbol")
                            or item.get("fullSymbol")
                            or f"{resolved_exchange}:{symbol}"
                        ),
                    }
                )
            elif isinstance(item, str):
                rows.append(
                    {
                        "symbol": item.strip().upper(),
                        "description": "",
                        "exchange": exchange.upper(),
                        "full_symbol": f"{exchange.upper()}:{item.strip().upper()}",
                    }
                )
        return rows

    def search_symbols(self, query: str) -> list[dict[str, Any]]:
        clean = query.strip().upper()
        if not clean:
            return []
        path = self.settings.chart_img_search_path.format(query=clean)
        payload = self._get_json(path)
        items = self._payload_items(payload)
        if not isinstance(items, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).upper()
            exchange = str(item.get("exchange", "")).upper()
            full_symbol = str(item.get("full_symbol") or item.get("fullSymbol") or "")
            if not full_symbol and symbol and exchange:
                full_symbol = f"{exchange}:{symbol}"
            rows.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "description": str(item.get("description", "")),
                    "full_symbol": full_symbol,
                }
            )
        return rows

    def resolve_tradingview_symbol(
        self,
        symbol: str,
        asset_type: str,
        exchange: str | None = None,
    ) -> str:
        clean = symbol.strip().upper()
        if ":" in clean:
            return clean

        if exchange:
            return f"{exchange.upper()}:{clean}"
        if asset_type == "crypto":
            crypto = clean.replace("-USD", "")
            return f"BINANCE:{crypto}USDT"
        if asset_type == "etf":
            return f"AMEX:{clean}"
        return f"NASDAQ:{clean}"

    def _default_exchanges(self, *, asset_type: str) -> list[str]:
        if asset_type == "crypto":
            return ["BINANCE", "COINBASE", "KRAKEN"]
        if asset_type == "etf":
            return ["AMEX", "NASDAQ", "NYSE"]
        return ["NASDAQ", "NYSE", "AMEX"]

    def _get_json(self, path: str) -> dict[str, Any] | list[Any]:
        api_key = self.settings.chart_img_api_key
        if not api_key:
            return {}
        if not self._preflight_usage(endpoint=path):
            return {}

        headers = {"x-api-key": api_key, "Accept": "application/json"}
        try:
            response = httpx.get(
                self._url(path),
                headers=headers,
                timeout=self.settings.chart_img_timeout_seconds,
            )
            self._record_usage(endpoint=path, status_code=response.status_code)
            if response.status_code in {401, 403}:
                response = httpx.get(
                    self._url(path),
                    params={"key": api_key},
                    headers={"Accept": "application/json"},
                    timeout=self.settings.chart_img_timeout_seconds,
                )
                self._record_usage(endpoint=path, status_code=response.status_code)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._record_usage(
                endpoint=path,
                status_code=0,
                note=f"httpx:{type(exc).__name__}",
            )
            return {}

        try:
            payload = response.json()
        except ValueError:
            return {}
        if isinstance(payload, (dict, list)):
            return payload
        return {}

    def _url(self, path: str) -> str:
        base = self.settings.chart_img_base_url.rstrip("/")
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{base}{normalized}"

    def _post_chart(self, payload: dict[str, Any], api_key: str) -> tuple[bytes, str]:
        active_path = self._active_advanced_chart_path()
        url = self._url(active_path)
        headers = {"Content-Type": "application/json", "Accept": "image/png,application/json"}
        attempts = [
            ({"x-api-key": api_key, **headers}, None),
            (headers, {"key": api_key}),
        ]
        last_error: str | None = None
        response: httpx.Response | None = None

        for request_headers, request_params in attempts:
            if not self._preflight_usage(endpoint=active_path):
                last_error = self._daily_limit_error()
                continue
            try:
                response = httpx.post(
                    url,
                    params=request_params,
                    json=payload,
                    headers=request_headers,
                    timeout=self.settings.chart_img_timeout_seconds,
                )
                self._record_usage(endpoint=active_path, status_code=response.status_code)
            except httpx.HTTPError as exc:
                last_error = f"Chart-IMG request failed: {exc!s}"
                self._record_usage(
                    endpoint=active_path,
                    status_code=0,
                    note=f"httpx:{type(exc).__name__}",
                )
                continue

            if response.status_code == 403 and self._apply_resolution_fallback(
                response=response,
                payload=payload,
            ):
                if not self._preflight_usage(endpoint=active_path):
                    last_error = self._daily_limit_error()
                    continue
                try:
                    response = httpx.post(
                        url,
                        params=request_params,
                        json=payload,
                        headers=request_headers,
                        timeout=self.settings.chart_img_timeout_seconds,
                    )
                    self._record_usage(endpoint=active_path, status_code=response.status_code)
                except httpx.HTTPError as exc:
                    last_error = f"Chart-IMG request failed: {exc!s}"
                    self._record_usage(
                        endpoint=active_path,
                        status_code=0,
                        note=f"httpx:{type(exc).__name__}",
                    )
                    continue

            try:
                response.raise_for_status()
                break
            except httpx.HTTPError as exc:
                last_error = self._http_error_message(exc, response)
                response = None
                continue

        if response is None:
            detail = last_error or "Chart-IMG request failed."
            raise ValueError(detail)

        content_type = response.headers.get("content-type", "image/png")
        if "application/json" in content_type.lower():
            try:
                body = response.json()
            except ValueError:
                body = {}
            candidate_url = str(body.get("url", "") or body.get("imageUrl", "")).strip()
            if candidate_url:
                fetched = self._download_image(candidate_url)
                if fetched:
                    return fetched, "image/png"
            details = (
                str(body.get("message", ""))
                or str(body.get("error", ""))
                or "Chart-IMG returned a JSON payload without image bytes."
            )
            raise ValueError(details)

        if not response.content:
            raise ValueError("Chart-IMG returned an empty image payload.")
        return response.content, content_type

    def _active_api_version(self) -> str:
        # Runtime policy: Chart-IMG render integration is pinned to v2.
        return "v2"

    def _active_advanced_chart_path(self) -> str:
        legacy = str(getattr(self.settings, "chart_img_advanced_chart_path", "")).strip()
        return str(
            self.settings.chart_img_v2_advanced_chart_path
            or legacy
            or "/v2/tradingview/advanced-chart"
        )

    def _apply_resolution_fallback(
        self,
        *,
        response: httpx.Response,
        payload: dict[str, Any],
    ) -> bool:
        limit = self._extract_resolution_limit(response)
        if limit is None:
            return False
        limit_width, limit_height = limit
        current_width = int(payload.get("width", 800))
        current_height = int(payload.get("height", 600))
        new_width = max(400, min(current_width, limit_width))
        new_height = max(300, min(current_height, limit_height))
        if (new_width, new_height) == (current_width, current_height):
            return False
        payload["width"] = new_width
        payload["height"] = new_height
        logger.info(
            "Chart-IMG resolution fallback applied: %sx%s -> %sx%s",
            current_width,
            current_height,
            new_width,
            new_height,
        )
        return True

    @staticmethod
    def _extract_resolution_limit(response: httpx.Response) -> tuple[int, int] | None:
        text = ChartImgService._response_text(response)
        if not text:
            return None
        match = re.search(r"(\d{3,4})\s*[xX]\s*(\d{3,4})", text)
        if not match:
            return None
        width, height = int(match.group(1)), int(match.group(2))
        if width < 400 or height < 300:
            return None
        return width, height

    @staticmethod
    def _response_text(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                message = str(payload.get("message") or payload.get("error") or "").strip()
                if message:
                    return message
        except ValueError:
            pass
        return response.text if hasattr(response, "text") else ""

    @staticmethod
    def _http_error_message(exc: httpx.HTTPError, response: httpx.Response | None) -> str:
        if response is not None:
            detail = ChartImgService._response_text(response)
            if detail:
                return detail
        return f"Chart-IMG request failed: {exc!s}"

    def _preflight_usage(self, *, endpoint: str) -> bool:
        if not bool(self.settings.chart_img_enforce_limits):
            return True
        self._wait_for_rate_window()
        limit = max(1, int(self.settings.chart_img_daily_limit))
        today_calls = self._count_calls_today()
        if today_calls >= limit:
            logger.warning(
                "Chart-IMG daily limit reached (%s). Skipping endpoint=%s",
                limit,
                endpoint,
            )
            return False
        return True

    def _daily_limit_error(self) -> str:
        limit = max(1, int(self.settings.chart_img_daily_limit))
        used = self._count_calls_today()
        return (
            "Chart-IMG daily limit reached. "
            f"Used={used} limit={limit}. "
            "Wait for reset or raise plan quota."
        )

    def _wait_for_rate_window(self) -> None:
        per_sec = float(self.settings.chart_img_rate_limit_per_sec)
        if per_sec <= 0:
            return
        min_gap = 1.0 / per_sec
        global _LAST_CHART_IMG_REQUEST_TS
        with _RATE_LIMIT_LOCK:
            now = time.monotonic()
            elapsed = now - _LAST_CHART_IMG_REQUEST_TS
            wait_for = min_gap - elapsed
            if wait_for > 0:
                time.sleep(wait_for)
            _LAST_CHART_IMG_REQUEST_TS = time.monotonic()

    def _count_calls_today(self) -> int:
        conn = self._usage_conn()
        if conn is None:
            return 0
        try:
            self._ensure_usage_table(conn)
            start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            row = conn.execute(
                (
                    "SELECT COUNT(*) FROM chart_img_usage_log "
                    "WHERE created_at >= ? AND created_at < ?"
                ),
                (start.isoformat(), end.isoformat()),
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except sqlite3.Error:
            return 0
        finally:
            conn.close()

    def _record_usage(
        self,
        *,
        endpoint: str,
        status_code: int,
        note: str | None = None,
    ) -> None:
        conn = self._usage_conn()
        if conn is None:
            return
        try:
            self._ensure_usage_table(conn)
            conn.execute(
                "INSERT INTO chart_img_usage_log("
                "created_at, endpoint, status_code, api_version, note"
                ") VALUES(?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(),
                    endpoint[:200],
                    int(status_code),
                    self._active_api_version(),
                    (note or "")[:240],
                ),
            )
            conn.commit()
        except sqlite3.Error:
            return
        finally:
            conn.close()

    def _usage_conn(self) -> sqlite3.Connection | None:
        path = Path(self.settings.admin_db_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(str(path))
        except Exception:
            return None

    @staticmethod
    def _ensure_usage_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chart_img_usage_log("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "created_at TEXT NOT NULL, "
            "endpoint TEXT NOT NULL, "
            "status_code INTEGER NOT NULL, "
            "api_version TEXT NOT NULL, "
            "note TEXT DEFAULT ''"
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chart_img_usage_created_at "
            "ON chart_img_usage_log(created_at)"
        )
        conn.commit()

    def _download_image(self, url: str) -> bytes:
        try:
            response = httpx.get(url, timeout=self.settings.chart_img_timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError:
            return b""
        return response.content or b""

    @staticmethod
    def _payload_items(payload: dict[str, Any] | list[Any]) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("payload", "data", "items", "results", "symbols", "exchanges"):
            item = payload.get(key)
            if isinstance(item, list):
                return item
        return []

    @staticmethod
    def _map_studies(metrics: list[str]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add_study(name: str, input_values: dict[str, Any] | None = None) -> None:
            key = f"{name}:{input_values or {}}"
            if key in seen:
                return
            seen.add(key)
            row: dict[str, Any] = {"name": name}
            if input_values:
                row["input"] = input_values
            mapped.append(row)

        for metric in metrics:
            item = metric.strip().lower()
            if not item:
                continue
            if item.startswith("sma_"):
                window = ChartImgService._suffix_window(item, default=20)
                add_study("Moving Average", {"length": window})
                continue
            if item.startswith("ema_"):
                window = ChartImgService._suffix_window(item, default=20)
                add_study("Moving Average Exponential", {"length": window})
                continue
            if item.startswith("rsi_"):
                window = ChartImgService._suffix_window(item, default=14)
                add_study("Relative Strength Index", {"length": window})
                continue
            if item == "macd" or item == "macd_signal":
                add_study("Moving Average Convergence Divergence")
                continue
            if item.startswith("bb_"):
                add_study("Bollinger Bands", {"length": 20})
                continue
            if item == "atr_14":
                add_study("Average True Range", {"length": 14})
                continue
            if item == "volume":
                add_study("Volume")
                continue
            if item == "adx_14":
                add_study("Average Directional Index", {"length": 14})
                continue
            if item == "obv":
                add_study("On Balance Volume")
                continue
            if item == "mfi_14":
                add_study("Money Flow Index", {"length": 14})
                continue
            if item in {"stoch_k_14", "stoch_d_14"}:
                add_study("Stochastic", {"length": 14})
                continue
            if item == "cci_20":
                add_study("Commodity Channel Index", {"length": 20})
                continue
            if item == "williams_r_14":
                add_study("Williams %R", {"length": 14})
                continue
            if item == "roc_10":
                add_study("Rate of Change", {"length": 10})
                continue
            if item == "vwma_20":
                add_study("Volume Weighted Moving Average", {"length": 20})

        return mapped

    @staticmethod
    def _suffix_window(metric: str, default: int) -> int:
        try:
            return max(2, int(metric.rsplit("_", 1)[-1]))
        except (TypeError, ValueError):
            return default
