from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings
from app.db.timeseries import get_connection


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value


class AdminToolsService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.project_root = Path(__file__).resolve().parents[2]

    def db_summary(self) -> dict[str, Any]:
        admin_db_path = Path(self.settings.admin_db_path)
        timeseries_db_path = Path(self.settings.timeseries_db_path)

        admin_tables: list[dict[str, int | str]] = []
        sqlite_connection: sqlite3.Connection | None = None
        if admin_db_path.exists():
            try:
                sqlite_connection = sqlite3.connect(str(admin_db_path))
                table_rows = sqlite_connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                for (table_name,) in table_rows:
                    if str(table_name).startswith("sqlite_"):
                        continue
                    safe_name = str(table_name).replace('"', '""')
                    count_row = sqlite_connection.execute(
                        f'SELECT COUNT(*) FROM "{safe_name}"'  # noqa: S608
                    ).fetchone()
                    count = int(count_row[0]) if count_row else 0
                    admin_tables.append({"table": str(table_name), "rows": count})
            except sqlite3.Error:
                admin_tables = []
            finally:
                try:
                    if sqlite_connection is not None:
                        sqlite_connection.close()
                except Exception:
                    pass

        timeseries_rows = 0
        timeseries_symbols = 0
        latest_price_timestamp: str | None = None
        duck_connection = None
        if timeseries_db_path.exists():
            try:
                duck_connection = get_connection()
                row_count = duck_connection.execute("SELECT COUNT(*) FROM prices").fetchone()
                symbol_count = duck_connection.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM prices"
                ).fetchone()
                latest_timestamp = duck_connection.execute(
                    "SELECT MAX(timestamp) FROM prices"
                ).fetchone()
                timeseries_rows = int(row_count[0]) if row_count else 0
                timeseries_symbols = int(symbol_count[0]) if symbol_count else 0
                raw_latest = latest_timestamp[0] if latest_timestamp else None
                latest_price_timestamp = str(raw_latest) if raw_latest else None
            except Exception:
                timeseries_rows = 0
                timeseries_symbols = 0
                latest_price_timestamp = None
            finally:
                try:
                    if duck_connection is not None:
                        duck_connection.close()
                except Exception:
                    pass

        return {
            "admin_db_path": str(admin_db_path),
            "admin_db_exists": admin_db_path.exists(),
            "admin_tables": admin_tables,
            "timeseries_db_path": str(timeseries_db_path),
            "timeseries_db_exists": timeseries_db_path.exists(),
            "timeseries_rows": timeseries_rows,
            "timeseries_symbols": timeseries_symbols,
            "latest_price_timestamp": latest_price_timestamp,
            "checked_at": datetime.now(UTC),
        }

    def run_test_suite(
        self,
        suite: Literal["smoke", "unit", "integration", "all"],
    ) -> dict[str, Any]:
        if not self.settings.admin_enable_test_runner:
            return {
                "suite": suite,
                "status": "disabled",
                "command": "",
                "duration_seconds": 0.0,
                "output_tail": "Admin test runner is disabled by configuration.",
                "exit_code": None,
                "ran_at": datetime.now(UTC),
            }

        targets = self._resolve_test_targets(suite)
        command = [sys.executable, "-m", "pytest", *targets]
        started = time.perf_counter()

        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.settings.admin_test_timeout_seconds,
                check=False,
            )
            duration = round(time.perf_counter() - started, 3)
            output = f"{result.stdout}\n{result.stderr}".strip()
            output_tail = "\n".join(output.splitlines()[-80:])
            status: Literal["passed", "failed"] = "passed" if result.returncode == 0 else "failed"
            return {
                "suite": suite,
                "status": status,
                "command": " ".join(command),
                "duration_seconds": duration,
                "output_tail": output_tail,
                "exit_code": int(result.returncode),
                "ran_at": datetime.now(UTC),
            }
        except subprocess.TimeoutExpired as exc:
            duration = round(time.perf_counter() - started, 3)
            text_output = f"{_as_text(exc.stdout)}\n{_as_text(exc.stderr)}".strip()
            output_tail = "\n".join(text_output.splitlines()[-80:])
            return {
                "suite": suite,
                "status": "timeout",
                "command": " ".join(command),
                "duration_seconds": duration,
                "output_tail": output_tail,
                "exit_code": None,
                "ran_at": datetime.now(UTC),
            }
        except Exception as exc:
            duration = round(time.perf_counter() - started, 3)
            return {
                "suite": suite,
                "status": "error",
                "command": " ".join(command),
                "duration_seconds": duration,
                "output_tail": str(exc),
                "exit_code": None,
                "ran_at": datetime.now(UTC),
            }

    @staticmethod
    def _resolve_test_targets(
        suite: Literal["smoke", "unit", "integration", "all"],
    ) -> list[str]:
        if suite == "unit":
            return ["tests/unit"]
        if suite == "integration":
            return ["tests/integration"]
        if suite == "all":
            return ["tests"]
        return [
            "tests/integration/test_health.py",
            "tests/integration/test_integrations_status_api.py",
        ]

    def run_db_query(
        self,
        target_db: Literal["admin", "timeseries"],
        sql: str,
        limit: int,
    ) -> dict[str, Any]:
        self._validate_read_query(sql)
        cap = max(1, min(limit, 2000))
        wrapped_sql = f"SELECT * FROM ({sql.strip().rstrip(';')}) AS q LIMIT {cap}"

        columns: list[str] = []
        rows: list[list[str | float | int | bool | None]] = []

        if target_db == "admin":
            sqlite_conn = sqlite3.connect(self.settings.admin_db_path)
            try:
                cursor = sqlite_conn.execute(wrapped_sql)
                columns = [str(item[0]) for item in (cursor.description or [])]
                raw_rows = cursor.fetchall()
                rows = [self._serialize_row(item) for item in raw_rows]
            finally:
                sqlite_conn.close()
        else:
            duck_conn = get_connection()
            try:
                relation = duck_conn.execute(wrapped_sql)
                columns = [str(item[0]) for item in (relation.description or [])]
                raw_rows = relation.fetchall()
                rows = [self._serialize_row(item) for item in raw_rows]
            finally:
                duck_conn.close()

        truncated = len(rows) >= cap
        return {
            "target_db": target_db,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "executed_at": datetime.now(UTC),
        }

    def read_logs(
        self,
        *,
        level: Literal["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "ALL",
        limit: int = 250,
    ) -> dict[str, Any]:
        log_path = Path(self.settings.log_file_path)
        max_lines = max(10, min(limit, 5000))
        configured = str(self.settings.log_level).upper()
        if configured not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            configured = "INFO"

        if not log_path.exists():
            return {
                "configured_level": configured,
                "active_level_filter": level,
                "log_file_path": str(log_path),
                "file_exists": False,
                "line_count": 0,
                "returned_count": 0,
                "lines": [],
                "read_at": datetime.now(UTC),
            }

        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            content = []

        filtered = content
        if level != "ALL":
            token = f" {level} "
            filtered = [line for line in content if token in line]

        selected = filtered[-max_lines:]
        return {
            "configured_level": configured,
            "active_level_filter": level,
            "log_file_path": str(log_path),
            "file_exists": True,
            "line_count": len(filtered),
            "returned_count": len(selected),
            "lines": selected,
            "read_at": datetime.now(UTC),
        }

    @staticmethod
    def _validate_read_query(sql: str) -> None:
        text = sql.strip()
        lowered = text.lower()
        if not lowered.startswith("select") and not lowered.startswith("with"):
            raise ValueError("Only SELECT or WITH read-only queries are allowed.")
        forbidden_tokens = [
            "insert ",
            "update ",
            "delete ",
            "drop ",
            "alter ",
            "create ",
            "replace ",
            "truncate ",
            "attach ",
            "detach ",
            "pragma ",
            "vacuum ",
        ]
        if any(token in lowered for token in forbidden_tokens):
            raise ValueError("Write operations are not allowed in admin query mode.")
        if ";" in text.rstrip(";"):
            raise ValueError("Multiple SQL statements are not allowed.")

    @staticmethod
    def _serialize_row(row: tuple[Any, ...]) -> list[str | float | int | bool | None]:
        serialized: list[str | float | int | bool | None] = []
        for item in row:
            if item is None:
                serialized.append(None)
            elif isinstance(item, (str, float, int, bool)):
                serialized.append(item)
            else:
                serialized.append(str(item))
        return serialized
