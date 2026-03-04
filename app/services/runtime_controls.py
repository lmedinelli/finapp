from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.chart_img import ChartImgService


class RuntimeControlsService:
    _BOOL_KEYS = {"chart_img_enforce_limits"}
    _INT_KEYS = {
        "chart_img_max_width",
        "chart_img_max_height",
        "chart_img_max_studies",
        "chart_img_daily_limit",
    }
    _FLOAT_KEYS = {"chart_img_rate_limit_per_sec", "chart_img_timeout_seconds"}
    _STRING_KEYS = {
        "openai_model",
        "openai_admin_model_candidates",
        "alert_divergence_15m_mode",
        "chart_img_api_version",
        "chart_img_v1_advanced_chart_path",
        "chart_img_v2_advanced_chart_path",
        "chart_img_v3_advanced_chart_path",
        "chart_img_exchanges_path",
        "chart_img_symbols_path",
        "chart_img_search_path",
    }
    _VALID_CHART_VERSIONS = {"v2"}

    def __init__(self) -> None:
        self.settings = get_settings()
        self._ensure_runtime_tables()

    def apply_runtime_overrides(self) -> dict[str, Any]:
        config = self._base_runtime_config()
        overrides = self._read_runtime_overrides()
        for key, raw_value in overrides.items():
            if key not in config:
                continue
            parsed = self._parse_runtime_value(key, raw_value)
            if parsed is not None:
                config[key] = parsed

        self._apply_config_to_settings(config)
        return config

    def get_runtime_config(self) -> dict[str, Any]:
        config = self.apply_runtime_overrides()
        candidates = self._model_candidates_from_csv(
            str(config.get("openai_admin_model_candidates", ""))
        )
        usage = self.chart_img_usage_stats()
        return {
            "openai_model": str(config["openai_model"]),
            "openai_model_candidates": candidates,
            "alert_divergence_15m_mode": str(config["alert_divergence_15m_mode"]),
            "chart_img_api_version": str(config["chart_img_api_version"]),
            "chart_img_v1_advanced_chart_path": str(config["chart_img_v1_advanced_chart_path"]),
            "chart_img_v2_advanced_chart_path": str(config["chart_img_v2_advanced_chart_path"]),
            "chart_img_v3_advanced_chart_path": str(config["chart_img_v3_advanced_chart_path"]),
            "chart_img_timeout_seconds": float(config["chart_img_timeout_seconds"]),
            "chart_img_max_width": int(config["chart_img_max_width"]),
            "chart_img_max_height": int(config["chart_img_max_height"]),
            "chart_img_max_studies": int(config["chart_img_max_studies"]),
            "chart_img_rate_limit_per_sec": float(config["chart_img_rate_limit_per_sec"]),
            "chart_img_daily_limit": int(config["chart_img_daily_limit"]),
            "chart_img_enforce_limits": bool(config["chart_img_enforce_limits"]),
            "chart_img_calls_today": int(usage["calls_today"]),
            "chart_img_remaining_today": int(usage["remaining_today"]),
            "chart_img_last_request_at": usage["last_request_at"],
            "updated_at": self._runtime_last_updated(),
        }

    def update_runtime_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        if not updates:
            return self.get_runtime_config()

        current = self.apply_runtime_overrides()
        normalized: dict[str, str] = {}
        for key, value in updates.items():
            if key not in current:
                continue
            parsed = self._coerce_update_value(key=key, value=value)
            if parsed is None:
                continue
            current[key] = parsed
            normalized[key] = self._serialize_runtime_value(key=key, value=parsed)

        if normalized:
            conn = self._connect_admin_db()
            if conn is not None:
                try:
                    self._ensure_runtime_tables(conn)
                    for key, value in normalized.items():
                        conn.execute(
                            "INSERT INTO runtime_config(key, value, updated_at) "
                            "VALUES(?, ?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                            "updated_at=excluded.updated_at",
                            (key, value, datetime.now(UTC).isoformat()),
                        )
                    conn.commit()
                finally:
                    conn.close()

        self._apply_config_to_settings(current)
        return self.get_runtime_config()

    def list_openai_models(self) -> dict[str, Any]:
        config = self.get_runtime_config()
        configured_model = str(config["openai_model"])
        candidate_models = list(config["openai_model_candidates"])
        models: list[str] = []
        error: str | None = None

        api_key = self.settings.openai_api_key
        if api_key:
            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key, base_url=self.settings.openai_base_url or None)
                rows = client.models.list()
                for item in rows.data:
                    model_id = str(getattr(item, "id", "")).strip()
                    if model_id:
                        models.append(model_id)
            except Exception as exc:
                error = str(exc)
        else:
            error = "Missing OPENAI_API_KEY."

        merged = sorted(set(models + candidate_models))
        return {
            "configured_model": configured_model,
            "models": merged,
            "available_count": len(merged),
            "contains_gpt_5_3": any("5.3" in model for model in merged),
            "fetched_at": datetime.now(UTC),
            "error": error,
        }

    def probe_openai_model(self, model: str) -> dict[str, Any]:
        selected = model.strip()
        if not selected:
            return {
                "success": False,
                "target": "openai_model",
                "model": "",
                "latency_ms": 0.0,
                "detail": "Model is required.",
            }
        if not self.settings.openai_api_key:
            return {
                "success": False,
                "target": "openai_model",
                "model": selected,
                "latency_ms": 0.0,
                "detail": "Missing OPENAI_API_KEY.",
            }

        started = time.perf_counter()
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url or None,
            )
            try:
                response = client.responses.create(
                    model=selected,
                    input="Reply only with: OK",
                    max_output_tokens=32,
                )
                output_text = str(getattr(response, "output_text", "")).strip()
                latency = round((time.perf_counter() - started) * 1000.0, 2)
                return {
                    "success": True,
                    "target": "openai_model",
                    "model": selected,
                    "latency_ms": latency,
                    "detail": output_text or "OpenAI model probe succeeded.",
                }
            except Exception:
                completion = client.chat.completions.create(
                    model=selected,
                    messages=[{"role": "user", "content": "Reply only with: OK"}],
                    temperature=0,
                )
                output_text = str(completion.choices[0].message.content or "").strip()
                latency = round((time.perf_counter() - started) * 1000.0, 2)
                return {
                    "success": True,
                    "target": "openai_model",
                    "model": selected,
                    "latency_ms": latency,
                    "detail": output_text or "OpenAI model probe succeeded.",
                }
        except Exception as exc:
            latency = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "success": False,
                "target": "openai_model",
                "model": selected,
                "latency_ms": latency,
                "detail": str(exc),
            }

    def probe_chart_img(
        self,
        *,
        symbol: str,
        asset_type: str,
        interval: str = "1D",
    ) -> dict[str, Any]:
        started = time.perf_counter()
        chart_service = ChartImgService()
        try:
            result = chart_service.render_candle_image(
                symbol=symbol,
                asset_type=asset_type,
                interval=interval,
                width=int(self.settings.chart_img_max_width),
                height=int(self.settings.chart_img_max_height),
                studies=["sma_20", "rsi_14", "macd"][
                    : max(1, int(self.settings.chart_img_max_studies))
                ],
            )
            latency = round((time.perf_counter() - started) * 1000.0, 2)
            raw_size = len(result.get("image_base64", ""))
            return {
                "success": True,
                "target": "chart_img",
                "model": "",
                "latency_ms": latency,
                "detail": (
                    f"{result.get('source', 'chart-img')} OK "
                    f"symbol={result.get('tradingview_symbol', '')} "
                    f"base64_len={raw_size}"
                ),
            }
        except ValueError as exc:
            latency = round((time.perf_counter() - started) * 1000.0, 2)
            return {
                "success": False,
                "target": "chart_img",
                "model": "",
                "latency_ms": latency,
                "detail": str(exc),
            }

    def chart_img_usage_stats(self) -> dict[str, Any]:
        conn = self._connect_admin_db()
        if conn is None:
            return {
                "calls_today": 0,
                "remaining_today": int(self.settings.chart_img_daily_limit),
                "last_request_at": None,
            }
        try:
            self._ensure_runtime_tables(conn)
            start_dt = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(days=1)
            row = conn.execute(
                (
                    "SELECT COUNT(*) FROM chart_img_usage_log "
                    "WHERE created_at >= ? AND created_at < ?"
                ),
                (start_dt.isoformat(), end_dt.isoformat()),
            ).fetchone()
            calls_today = int(row[0]) if row and row[0] is not None else 0
            last_row = conn.execute(
                "SELECT created_at FROM chart_img_usage_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            last_request_at = str(last_row[0]) if last_row and last_row[0] else None
        except sqlite3.Error:
            calls_today = 0
            last_request_at = None
        finally:
            conn.close()

        daily_limit = max(1, int(self.settings.chart_img_daily_limit))
        remaining = max(0, daily_limit - calls_today)
        return {
            "calls_today": calls_today,
            "remaining_today": remaining,
            "last_request_at": last_request_at,
        }

    def _runtime_last_updated(self) -> str | None:
        conn = self._connect_admin_db()
        if conn is None:
            return None
        try:
            self._ensure_runtime_tables(conn)
            row = conn.execute("SELECT MAX(updated_at) FROM runtime_config").fetchone()
            if row and row[0]:
                return str(row[0])
            return None
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    def _base_runtime_config(self) -> dict[str, Any]:
        return {
            "openai_model": str(self.settings.openai_model),
            "openai_admin_model_candidates": str(self.settings.openai_admin_model_candidates),
            "alert_divergence_15m_mode": str(self.settings.alert_divergence_15m_mode),
            "chart_img_api_version": "v2",
            "chart_img_v1_advanced_chart_path": str(self.settings.chart_img_v1_advanced_chart_path),
            "chart_img_v2_advanced_chart_path": str(self.settings.chart_img_v2_advanced_chart_path),
            "chart_img_v3_advanced_chart_path": str(self.settings.chart_img_v3_advanced_chart_path),
            "chart_img_exchanges_path": str(self.settings.chart_img_exchanges_path),
            "chart_img_symbols_path": str(self.settings.chart_img_symbols_path),
            "chart_img_search_path": str(self.settings.chart_img_search_path),
            "chart_img_timeout_seconds": float(self.settings.chart_img_timeout_seconds),
            "chart_img_max_width": int(self.settings.chart_img_max_width),
            "chart_img_max_height": int(self.settings.chart_img_max_height),
            "chart_img_max_studies": int(self.settings.chart_img_max_studies),
            "chart_img_rate_limit_per_sec": float(self.settings.chart_img_rate_limit_per_sec),
            "chart_img_daily_limit": int(self.settings.chart_img_daily_limit),
            "chart_img_enforce_limits": bool(self.settings.chart_img_enforce_limits),
        }

    def _apply_config_to_settings(self, config: dict[str, Any]) -> None:
        for key, value in config.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.settings.chart_img_api_version = "v2"
        selected_path = str(self.settings.chart_img_v2_advanced_chart_path)
        self.settings.chart_img_advanced_chart_path = selected_path

    def _read_runtime_overrides(self) -> dict[str, str]:
        conn = self._connect_admin_db()
        if conn is None:
            return {}
        try:
            self._ensure_runtime_tables(conn)
            rows = conn.execute("SELECT key, value FROM runtime_config").fetchall()
            return {str(key): str(value) for key, value in rows}
        except sqlite3.Error:
            return {}
        finally:
            conn.close()

    def _coerce_update_value(self, *, key: str, value: Any) -> Any | None:
        if key in self._STRING_KEYS:
            text = str(value).strip()
            if key == "chart_img_api_version":
                return "v2"
            if key == "alert_divergence_15m_mode":
                mode = text.lower()
                if mode in {"conservative", "balanced", "aggressive"}:
                    return mode
                return "balanced"
            return text
        if key in self._INT_KEYS:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return None
            if key in {"chart_img_max_width", "chart_img_max_height"}:
                return max(300, parsed)
            if key == "chart_img_max_studies":
                return max(1, min(parsed, 25))
            if key == "chart_img_daily_limit":
                return max(1, parsed)
            return parsed
        if key in self._FLOAT_KEYS:
            try:
                parsed_float = float(value)
            except (TypeError, ValueError):
                return None
            if key == "chart_img_rate_limit_per_sec":
                return max(0.1, parsed_float)
            if key == "chart_img_timeout_seconds":
                return max(5.0, parsed_float)
            return parsed_float
        if key in self._BOOL_KEYS:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "on"}
        return None

    def _parse_runtime_value(self, key: str, raw_value: str) -> Any | None:
        return self._coerce_update_value(key=key, value=raw_value)

    @staticmethod
    def _serialize_runtime_value(*, key: str, value: Any) -> str:
        if key in RuntimeControlsService._BOOL_KEYS:
            return "true" if bool(value) else "false"
        return str(value)

    @staticmethod
    def _model_candidates_from_csv(raw_csv: str) -> list[str]:
        rows = [item.strip() for item in raw_csv.split(",") if item.strip()]
        return sorted(set(rows))

    def _connect_admin_db(self) -> sqlite3.Connection | None:
        db_path = Path(self.settings.admin_db_path)
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(str(db_path))
        except Exception:
            return None

    def _ensure_runtime_tables(self, conn: sqlite3.Connection | None = None) -> None:
        owns_conn = conn is None
        connection = conn if conn is not None else self._connect_admin_db()
        if connection is None:
            return
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS runtime_config("
                "key TEXT PRIMARY KEY, "
                "value TEXT NOT NULL, "
                "updated_at TEXT NOT NULL"
                ")"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS chart_img_usage_log("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "created_at TEXT NOT NULL, "
                "endpoint TEXT NOT NULL, "
                "status_code INTEGER NOT NULL, "
                "api_version TEXT NOT NULL, "
                "note TEXT DEFAULT ''"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_runtime_config_updated_at "
                "ON runtime_config(updated_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_chart_img_usage_created_at "
                "ON chart_img_usage_log(created_at)"
            )
            connection.commit()
        finally:
            if owns_conn:
                connection.close()
