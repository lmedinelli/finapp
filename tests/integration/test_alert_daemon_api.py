import os
from types import SimpleNamespace

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


def test_alert_daemon_admin_endpoints(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "get_status",
        lambda: {
            "is_enabled": True,
            "is_running": True,
            "frequency_seconds": 3600,
            "cron_hint": "0 * * * *",
            "next_run_at": "2026-03-03T13:00:00+00:00",
            "last_started_at": "2026-03-03T12:00:00+00:00",
            "last_heartbeat_at": "2026-03-03T12:00:10+00:00",
            "last_cycle_started_at": "2026-03-03T12:00:00+00:00",
            "last_cycle_finished_at": "2026-03-03T12:00:04+00:00",
            "last_cycle_status": "success",
            "last_error": None,
            "run_count": 12,
            "triggered_count": 7,
            "analyzed_count": 1234,
            "active_instance_id": "inst-1",
            "latest_cycle_id": "cycle-1",
            "latest_cycle_steps": ["step-a", "step-b"],
            "checked_at": "2026-03-03T12:00:11+00:00",
        },
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "run_cycle",
        lambda trigger_source="manual": {
            "cycle_id": "cycle-manual-1",
            "trigger_source": trigger_source,
            "status": "success",
            "symbols_count": 5,
            "subscriptions_evaluated": 9,
            "rules_evaluated": 24,
            "alerts_triggered": 2,
            "analysis_rows_written": 150,
            "started_at": "2026-03-03T12:00:00+00:00",
            "finished_at": "2026-03-03T12:00:04+00:00",
            "next_run_at": "2026-03-03T13:00:00+00:00",
            "steps": ["done"],
            "error": None,
        },
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "start_background_loop",
        lambda: {
            "is_enabled": True,
            "is_running": True,
            "frequency_seconds": 3600,
            "cron_hint": "0 * * * *",
            "next_run_at": None,
            "last_started_at": None,
            "last_heartbeat_at": None,
            "last_cycle_started_at": None,
            "last_cycle_finished_at": None,
            "last_cycle_status": "idle",
            "last_error": None,
            "run_count": 0,
            "triggered_count": 0,
            "analyzed_count": 0,
            "active_instance_id": "inst-1",
            "latest_cycle_id": None,
            "latest_cycle_steps": [],
            "checked_at": "2026-03-03T12:00:11+00:00",
        },
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "stop_background_loop",
        lambda: {
            "is_enabled": True,
            "is_running": False,
            "frequency_seconds": 3600,
            "cron_hint": "0 * * * *",
            "next_run_at": None,
            "last_started_at": None,
            "last_heartbeat_at": None,
            "last_cycle_started_at": None,
            "last_cycle_finished_at": None,
            "last_cycle_status": "idle",
            "last_error": None,
            "run_count": 0,
            "triggered_count": 0,
            "analyzed_count": 0,
            "active_instance_id": None,
            "latest_cycle_id": None,
            "latest_cycle_steps": [],
            "checked_at": "2026-03-03T12:00:11+00:00",
        },
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "list_rules",
        lambda include_inactive=False: [
            SimpleNamespace(
                id=1,
                rule_key="buy_ema",
                name="BUY EMA",
                description="desc",
                category="technical",
                asset_type="any",
                timeframe="1h",
                horizon="short_term",
                action="buy",
                severity="high",
                priority=10,
                expression_json="{}",
                data_requirements=None,
                is_active=True,
                created_at="2026-03-03T12:00:00+00:00",
                updated_at="2026-03-03T12:00:00+00:00",
            )
        ],
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "list_cycles",
        lambda limit=50: [
            {
                "id": 1,
                "cycle_id": "cycle-1",
                "trigger_source": "daemon",
                "status": "success",
                "frequency_seconds": 3600,
                "symbols_count": 5,
                "subscriptions_evaluated": 9,
                "rules_evaluated": 24,
                "alerts_triggered": 2,
                "analysis_rows_written": 150,
                "started_at": "2026-03-03T12:00:00+00:00",
                "finished_at": "2026-03-03T12:00:04+00:00",
                "next_run_at": "2026-03-03T13:00:00+00:00",
                "instance_id": "inst-1",
                "error": None,
                "steps": ["a", "b"],
            }
        ],
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "list_triggers",
        lambda cycle_id=None, symbol=None, user_id=None, limit=200: [
            {
                "id": 1,
                "cycle_id": "cycle-1",
                "subscription_id": None,
                "rule_key": "buy_ema",
                "rule_name": "BUY EMA",
                "symbol": "AAPL",
                "asset_type": "stock",
                "timeframe": "1d",
                "action": "buy",
                "severity": "high",
                "title": "BUY signal",
                "message": "cross detected",
                "metric_value": None,
                "operator": None,
                "threshold": None,
                "deliver_to_user_id": None,
                "delivered": False,
                "created_at": "2026-03-03T12:00:04+00:00",
            }
        ],
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "list_analysis_snapshots",
        lambda cycle_id=None, symbol=None, limit=200: [
            {
                "cycle_id": "cycle-1",
                "analyzed_at": "2026-03-03T12:00:00+00:00",
                "symbol": "AAPL",
                "asset_type": "stock",
                "timeframe": "1d",
                "metric": "rsi_14",
                "metric_value": 52.1,
                "source": "alert_daemon",
                "meta_json": "{}",
            }
        ],
    )
    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "list_agent_events",
        lambda after_id=0, limit=25: [
            {
                "id": 4,
                "cycle_id": "cycle-1",
                "source": "alert_daemon",
                "event_type": "cycle_summary",
                "message": "cycle summary",
                "payload": "{}",
                "created_at": "2026-03-03T12:00:05+00:00",
            }
        ],
    )

    headers = _admin_headers()

    status = client.get("/v1/admin/alerts/daemon/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["is_running"] is True

    run = client.post(
        "/v1/admin/alerts/daemon/run",
        headers=headers,
        json={"trigger_source": "manual"},
    )
    assert run.status_code == 200
    assert run.json()["cycle_id"] == "cycle-manual-1"

    start = client.post("/v1/admin/alerts/daemon/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["is_running"] is True

    stop = client.post("/v1/admin/alerts/daemon/stop", headers=headers)
    assert stop.status_code == 200
    assert stop.json()["is_running"] is False

    rules = client.get("/v1/admin/alerts/daemon/rules", headers=headers)
    assert rules.status_code == 200
    assert rules.json()[0]["rule_key"] == "buy_ema"

    cycles = client.get("/v1/admin/alerts/daemon/cycles", headers=headers)
    assert cycles.status_code == 200
    assert cycles.json()[0]["cycle_id"] == "cycle-1"

    triggers = client.get("/v1/admin/alerts/daemon/triggers", headers=headers)
    assert triggers.status_code == 200
    assert triggers.json()[0]["symbol"] == "AAPL"
    filtered_triggers = client.get(
        "/v1/admin/alerts/daemon/triggers",
        headers=headers,
        params={"symbol": "AAPL", "user_id": 2},
    )
    assert filtered_triggers.status_code == 200

    snapshots = client.get("/v1/admin/alerts/daemon/snapshots", headers=headers)
    assert snapshots.status_code == 200
    assert snapshots.json()[0]["metric"] == "rsi_14"

    feed = client.get("/v1/admin/alerts/daemon/agent-feed", headers=headers)
    assert feed.status_code == 200
    assert feed.json()["items"][0]["id"] == 4


def test_alert_agent_feed_public_endpoint(monkeypatch) -> None:
    from app.api import router as api_router

    monkeypatch.setattr(
        api_router.alert_daemon_service,
        "list_agent_events",
        lambda after_id=0, limit=25: [
            {
                "id": 8,
                "cycle_id": "cycle-xyz",
                "source": "alert_daemon",
                "event_type": "trigger",
                "message": "AAPL BUY",
                "payload": "{}",
                "created_at": "2026-03-03T12:30:00+00:00",
            }
        ],
    )

    response = client.get("/v1/alerts/agent-feed", params={"after_id": 0, "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["next_after_id"] == 8
    assert body["items"][0]["event_type"] == "trigger"
