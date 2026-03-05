import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN_BOOTSTRAP_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin-test-password")


def _admin_headers() -> dict[str, str]:
    response = client.post(
        "/v1/admin/auth/login",
        json={"username": ADMIN_BOOTSTRAP_USERNAME, "password": ADMIN_BOOTSTRAP_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_db_summary_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.admin_tools_service,
        "db_summary",
        lambda: {
            "admin_db_path": "data/admin/admin.db",
            "admin_db_exists": True,
            "admin_tables": [{"table": "chat_memory", "rows": 10}],
            "timeseries_db_path": "data/timeseries/market.duckdb",
            "timeseries_db_exists": True,
            "timeseries_rows": 250,
            "timeseries_symbols": 4,
            "latest_price_timestamp": "2026-03-02 10:00:00",
            "checked_at": "2026-03-02T10:00:00",
        },
    )

    response = client.get("/v1/admin/db/summary", headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["timeseries_rows"] == 250
    assert body["admin_tables"][0]["table"] == "chat_memory"


def test_admin_run_tests_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.admin_tools_service,
        "run_test_suite",
        lambda suite: {
            "suite": suite,
            "status": "passed",
            "command": "pytest tests/integration/test_health.py",
            "duration_seconds": 1.2,
            "output_tail": "1 passed",
            "exit_code": 0,
            "ran_at": "2026-03-02T10:00:00",
        },
    )

    response = client.post(
        "/v1/admin/tests/run",
        json={"suite": "smoke"},
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suite"] == "smoke"
    assert body["status"] == "passed"


def test_admin_db_query_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.admin_tools_service,
        "run_db_query",
        lambda target_db, sql, limit: {
            "target_db": target_db,
            "columns": ["symbol", "close"],
            "rows": [["AAPL", 200.0]],
            "row_count": 1,
            "truncated": False,
            "executed_at": "2026-03-02T10:00:00",
        },
    )

    response = client.post(
        "/v1/admin/db/query",
        json={"target_db": "timeseries", "sql": "SELECT * FROM prices", "limit": 50},
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["target_db"] == "timeseries"
    assert body["row_count"] == 1


def test_admin_logs_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.admin_tools_service,
        "read_logs",
        lambda level, limit: {
            "configured_level": "INFO",
            "active_level_filter": level,
            "log_file_path": "data/logs/app.log",
            "file_exists": True,
            "line_count": 2,
            "returned_count": 2,
            "lines": [
                "2026-03-03 10:00:00 INFO [app.main] startup",
                "2026-03-03 10:00:01 WARNING [app.services.news] no data",
            ],
            "read_at": "2026-03-03T10:00:01",
        },
    )

    response = client.get(
        "/v1/admin/logs",
        params={"level": "WARNING", "limit": 200},
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["active_level_filter"] == "WARNING"
    assert body["returned_count"] == 2


def test_admin_runtime_config_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.runtime_controls_service,
        "get_runtime_config",
        lambda: {
            "openai_model": "gpt-5",
            "openai_model_candidates": ["gpt-5", "gpt-4.1"],
            "alert_divergence_15m_mode": "aggressive",
            "chart_img_api_version": "v2",
            "chart_img_v1_advanced_chart_path": "/v1/tradingview/advanced-chart",
            "chart_img_v2_advanced_chart_path": "/v2/tradingview/advanced-chart",
            "chart_img_v3_advanced_chart_path": "",
            "chart_img_timeout_seconds": 25.0,
            "chart_img_max_width": 800,
            "chart_img_max_height": 600,
            "chart_img_max_studies": 3,
            "chart_img_rate_limit_per_sec": 1.0,
            "chart_img_daily_limit": 50,
            "chart_img_enforce_limits": True,
            "chart_img_calls_today": 12,
            "chart_img_remaining_today": 38,
            "chart_img_last_request_at": "2026-03-03T12:00:00+00:00",
            "updated_at": "2026-03-03T12:00:01+00:00",
        },
    )

    response = client.get("/v1/admin/runtime/config", headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["openai_model"] == "gpt-5"
    assert body["alert_divergence_15m_mode"] == "aggressive"
    assert body["chart_img_api_version"] == "v2"


def test_admin_runtime_update_and_probe_endpoints(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.runtime_controls_service,
        "update_runtime_config",
        lambda updates: {
            "openai_model": updates.get("openai_model", "gpt-4.1"),
            "openai_model_candidates": ["gpt-5", "gpt-4.1"],
            "alert_divergence_15m_mode": updates.get("alert_divergence_15m_mode", "balanced"),
            "chart_img_api_version": updates.get("chart_img_api_version", "v2"),
            "chart_img_v1_advanced_chart_path": "/v1/tradingview/advanced-chart",
            "chart_img_v2_advanced_chart_path": "/v2/tradingview/advanced-chart",
            "chart_img_v3_advanced_chart_path": "",
            "chart_img_timeout_seconds": 25.0,
            "chart_img_max_width": 800,
            "chart_img_max_height": 600,
            "chart_img_max_studies": 3,
            "chart_img_rate_limit_per_sec": 1.0,
            "chart_img_daily_limit": 50,
            "chart_img_enforce_limits": True,
            "chart_img_calls_today": 0,
            "chart_img_remaining_today": 50,
            "chart_img_last_request_at": None,
            "updated_at": "2026-03-03T12:00:01+00:00",
        },
    )
    monkeypatch.setattr(
        api_router.runtime_controls_service,
        "list_openai_models",
        lambda: {
            "configured_model": "gpt-5",
            "models": ["gpt-5", "gpt-4.1"],
            "available_count": 2,
            "contains_gpt_5_3": False,
            "fetched_at": "2026-03-03T12:00:00+00:00",
            "error": None,
        },
    )
    monkeypatch.setattr(
        api_router.runtime_controls_service,
        "probe_openai_model",
        lambda model: {
            "success": True,
            "target": "openai_model",
            "model": model,
            "latency_ms": 30.2,
            "detail": "OK",
        },
    )
    monkeypatch.setattr(
        api_router.runtime_controls_service,
        "probe_chart_img",
        lambda symbol, asset_type, interval: {
            "success": True,
            "target": "chart_img",
            "model": "",
            "latency_ms": 45.1,
            "detail": f"chart probe {symbol} {asset_type} {interval}",
        },
    )

    runtime_update = client.post(
        "/v1/admin/runtime/config",
        json={
            "openai_model": "gpt-5",
            "alert_divergence_15m_mode": "aggressive",
            "chart_img_api_version": "v2",
        },
        headers=_admin_headers(),
    )
    assert runtime_update.status_code == 200
    assert runtime_update.json()["openai_model"] == "gpt-5"
    assert runtime_update.json()["alert_divergence_15m_mode"] == "aggressive"

    models_response = client.get("/v1/admin/openai/models", headers=_admin_headers())
    assert models_response.status_code == 200
    assert "gpt-5" in models_response.json()["models"]

    openai_probe = client.post(
        "/v1/admin/openai/probe",
        json={"model": "gpt-5"},
        headers=_admin_headers(),
    )
    assert openai_probe.status_code == 200
    assert openai_probe.json()["success"] is True

    chart_probe = client.post(
        "/v1/admin/chart-img/probe",
        json={"symbol": "AAPL", "asset_type": "stock", "interval": "1D"},
        headers=_admin_headers(),
    )
    assert chart_probe.status_code == 200
    assert chart_probe.json()["target"] == "chart_img"


def test_admin_users_endpoint_access() -> None:
    response = client.get("/v1/admin/users", headers=_admin_headers())
    assert response.status_code == 200
    body = response.json()
    assert any(item["username"] == "admin" for item in body)


def test_admin_db_tables_endpoint() -> None:
    response = client.get(
        "/v1/admin/db/tables",
        params={"target_db": "admin"},
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    tables = response.json()
    assert isinstance(tables, list)
    assert "admin_users" in tables
