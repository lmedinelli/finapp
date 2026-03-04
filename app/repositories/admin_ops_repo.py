from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.admin import (
    AdminUser,
    AlertAgentEvent,
    AlertDaemonCycle,
    AlertDaemonState,
    AlertRule,
    AlertSubscription,
    AlertTriggerLog,
    MarketScanLog,
    RecommendationLog,
)


class AdminOpsRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_recommendation_log(
        self,
        *,
        source: str,
        session_id: str | None,
        request_message: str | None,
        symbol: str,
        asset_type: str,
        risk_profile: str,
        short_action: str,
        short_confidence: float,
        long_action: str,
        long_confidence: float,
        answer_text: str | None,
        workflow_steps: str | None,
        recommendation_payload: str | None,
        analysis_payload: str | None,
        market_context_payload: str | None,
    ) -> RecommendationLog:
        row = RecommendationLog(
            source=source,
            session_id=session_id,
            request_message=request_message,
            symbol=symbol,
            asset_type=asset_type,
            risk_profile=risk_profile,
            short_action=short_action,
            short_confidence=short_confidence,
            long_action=long_action,
            long_confidence=long_confidence,
            answer_text=answer_text,
            workflow_steps=workflow_steps,
            recommendation_payload=recommendation_payload,
            analysis_payload=analysis_payload,
            market_context_payload=market_context_payload,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def create_market_scan_log(
        self,
        *,
        scan_id: str,
        trigger_source: str,
        low_cap_max_usd: float,
        stock_count: int,
        crypto_count: int,
        ipo_count: int,
        ico_count: int,
        payload: str | None,
        warnings: str | None,
        data_sources: str | None,
    ) -> MarketScanLog:
        row = MarketScanLog(
            scan_id=scan_id,
            trigger_source=trigger_source,
            low_cap_max_usd=low_cap_max_usd,
            stock_count=stock_count,
            crypto_count=crypto_count,
            ipo_count=ipo_count,
            ico_count=ico_count,
            payload=payload,
            warnings=warnings,
            data_sources=data_sources,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_alert_subscriptions(
        self,
        *,
        user_id: int | None = None,
        active_only: bool = False,
    ) -> list[tuple[AlertSubscription, str]]:
        stmt = (
            select(AlertSubscription, AdminUser.username)
            .join(AdminUser, AlertSubscription.user_id == AdminUser.id)
            .order_by(AlertSubscription.created_at.desc(), AlertSubscription.id.desc())
        )
        if user_id is not None:
            stmt = stmt.where(AlertSubscription.user_id == user_id)
        if active_only:
            stmt = stmt.where(AlertSubscription.is_active.is_(True))
        rows = self.session.execute(stmt).all()
        result: list[tuple[AlertSubscription, str]] = []
        for subscription, username in rows:
            result.append((subscription, str(username)))
        return result

    def get_alert_subscription(self, subscription_id: int) -> AlertSubscription | None:
        stmt = select(AlertSubscription).where(AlertSubscription.id == subscription_id)
        return self.session.scalar(stmt)

    def create_alert_subscription(
        self,
        *,
        user_id: int,
        symbol: str,
        asset_type: str,
        alert_scope: str,
        rule_key: str | None,
        metric: str,
        operator: str,
        threshold: float | None,
        frequency_seconds: int,
        timeframe: str,
        lookback_period: str,
        cooldown_minutes: int,
        notes: str | None,
        is_active: bool,
    ) -> AlertSubscription:
        row = AlertSubscription(
            user_id=user_id,
            symbol=symbol,
            asset_type=asset_type,
            alert_scope=alert_scope,
            rule_key=rule_key,
            metric=metric,
            operator=operator,
            threshold=threshold,
            frequency_seconds=frequency_seconds,
            timeframe=timeframe,
            lookback_period=lookback_period,
            cooldown_minutes=cooldown_minutes,
            notes=notes,
            is_active=is_active,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def update_alert_subscription(
        self,
        *,
        subscription: AlertSubscription,
        asset_type: str | None = None,
        alert_scope: str | None = None,
        rule_key: str | None = None,
        metric: str | None = None,
        operator: str | None = None,
        threshold: float | None = None,
        frequency_seconds: int | None = None,
        timeframe: str | None = None,
        lookback_period: str | None = None,
        cooldown_minutes: int | None = None,
        notes: str | None = None,
        is_active: bool | None = None,
        last_checked_at: datetime | None = None,
        last_triggered_at: datetime | None = None,
    ) -> AlertSubscription:
        if asset_type is not None:
            subscription.asset_type = asset_type
        if alert_scope is not None:
            subscription.alert_scope = alert_scope
        if rule_key is not None:
            subscription.rule_key = rule_key
        if metric is not None:
            subscription.metric = metric
        if operator is not None:
            subscription.operator = operator
        subscription.threshold = threshold
        if frequency_seconds is not None:
            subscription.frequency_seconds = frequency_seconds
        if timeframe is not None:
            subscription.timeframe = timeframe
        if lookback_period is not None:
            subscription.lookback_period = lookback_period
        if cooldown_minutes is not None:
            subscription.cooldown_minutes = cooldown_minutes
        subscription.notes = notes
        if is_active is not None:
            subscription.is_active = is_active
        if last_checked_at is not None:
            subscription.last_checked_at = last_checked_at
        if last_triggered_at is not None:
            subscription.last_triggered_at = last_triggered_at
        self.session.commit()
        self.session.refresh(subscription)
        return subscription

    def touch_alert_subscription(
        self,
        *,
        subscription: AlertSubscription,
        checked_at: datetime,
        triggered_at: datetime | None = None,
    ) -> AlertSubscription:
        subscription.last_checked_at = checked_at
        if triggered_at is not None:
            subscription.last_triggered_at = triggered_at
        self.session.commit()
        self.session.refresh(subscription)
        return subscription

    def delete_alert_subscription(self, subscription: AlertSubscription) -> None:
        self.session.delete(subscription)
        self.session.commit()

    def list_alert_rules(self, *, active_only: bool = True) -> list[AlertRule]:
        stmt = select(AlertRule).order_by(AlertRule.priority.asc(), AlertRule.id.asc())
        if active_only:
            stmt = stmt.where(AlertRule.is_active.is_(True))
        return list(self.session.scalars(stmt).all())

    def get_alert_rule_by_key(self, rule_key: str) -> AlertRule | None:
        stmt = select(AlertRule).where(AlertRule.rule_key == rule_key)
        return self.session.scalar(stmt)

    def upsert_alert_rule(self, payload: dict[str, Any]) -> AlertRule:
        rule_key = str(payload.get("rule_key", "")).strip()
        if not rule_key:
            raise ValueError("rule_key is required.")
        row = self.get_alert_rule_by_key(rule_key)
        if row is None:
            row = AlertRule(
                rule_key=rule_key,
                name=str(payload.get("name", rule_key)),
                description=str(payload.get("description", "")),
                category=str(payload.get("category", "technical")),
                asset_type=str(payload.get("asset_type", "any")),
                timeframe=str(payload.get("timeframe", "1h")),
                horizon=str(payload.get("horizon", "short_term")),
                action=str(payload.get("action", "watch")),
                severity=str(payload.get("severity", "info")),
                priority=int(payload.get("priority", 100)),
                expression_json=str(payload.get("expression_json", "{}")),
                data_requirements=payload.get("data_requirements"),
                is_active=bool(payload.get("is_active", True)),
            )
            self.session.add(row)
        else:
            row.name = str(payload.get("name", row.name))
            row.description = str(payload.get("description", row.description))
            row.category = str(payload.get("category", row.category))
            row.asset_type = str(payload.get("asset_type", row.asset_type))
            row.timeframe = str(payload.get("timeframe", row.timeframe))
            row.horizon = str(payload.get("horizon", row.horizon))
            row.action = str(payload.get("action", row.action))
            row.severity = str(payload.get("severity", row.severity))
            row.priority = int(payload.get("priority", row.priority))
            row.expression_json = str(payload.get("expression_json", row.expression_json))
            row.data_requirements = payload.get("data_requirements", row.data_requirements)
            row.is_active = bool(payload.get("is_active", row.is_active))
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_daemon_state(self) -> AlertDaemonState | None:
        stmt = select(AlertDaemonState).where(AlertDaemonState.id == 1)
        return self.session.scalar(stmt)

    def upsert_daemon_state(self, **values: Any) -> AlertDaemonState:
        row = self.get_daemon_state()
        if row is None:
            row = AlertDaemonState(id=1)
            self.session.add(row)
            self.session.flush()
        for key, value in values.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(row)
        return row

    def create_daemon_cycle(
        self,
        *,
        cycle_id: str,
        trigger_source: str,
        frequency_seconds: int,
        instance_id: str,
        started_at: datetime,
    ) -> AlertDaemonCycle:
        row = AlertDaemonCycle(
            cycle_id=cycle_id,
            trigger_source=trigger_source,
            status="running",
            frequency_seconds=frequency_seconds,
            instance_id=instance_id,
            started_at=started_at,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get_daemon_cycle(self, cycle_id: str) -> AlertDaemonCycle | None:
        stmt = select(AlertDaemonCycle).where(AlertDaemonCycle.cycle_id == cycle_id)
        return self.session.scalar(stmt)

    def update_daemon_cycle(self, cycle: AlertDaemonCycle, **values: Any) -> AlertDaemonCycle:
        for key, value in values.items():
            if hasattr(cycle, key):
                setattr(cycle, key, value)
        self.session.commit()
        self.session.refresh(cycle)
        return cycle

    def list_daemon_cycles(self, *, limit: int = 50) -> list[AlertDaemonCycle]:
        stmt = (
            select(AlertDaemonCycle)
            .order_by(desc(AlertDaemonCycle.id))
            .limit(max(1, min(limit, 1000)))
        )
        return list(self.session.scalars(stmt).all())

    def create_trigger_log(
        self,
        *,
        cycle_id: str,
        subscription_id: int | None,
        rule_key: str,
        rule_name: str,
        symbol: str,
        asset_type: str,
        timeframe: str,
        action: str,
        severity: str,
        title: str,
        message: str,
        metric_value: float | None,
        operator: str | None,
        threshold: float | None,
        payload: str | None,
        deliver_to_user_id: int | None,
    ) -> AlertTriggerLog:
        row = AlertTriggerLog(
            cycle_id=cycle_id,
            subscription_id=subscription_id,
            rule_key=rule_key,
            rule_name=rule_name,
            symbol=symbol,
            asset_type=asset_type,
            timeframe=timeframe,
            action=action,
            severity=severity,
            title=title,
            message=message,
            metric_value=metric_value,
            operator=operator,
            threshold=threshold,
            payload=payload,
            deliver_to_user_id=deliver_to_user_id,
            delivered=False,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_trigger_logs(
        self,
        *,
        cycle_id: str | None = None,
        symbol: str | None = None,
        deliver_to_user_id: int | None = None,
        limit: int = 200,
    ) -> list[AlertTriggerLog]:
        stmt = select(AlertTriggerLog).order_by(desc(AlertTriggerLog.id))
        if cycle_id:
            stmt = stmt.where(AlertTriggerLog.cycle_id == cycle_id)
        if symbol:
            stmt = stmt.where(AlertTriggerLog.symbol == symbol.upper())
        if deliver_to_user_id is not None:
            stmt = stmt.where(AlertTriggerLog.deliver_to_user_id == deliver_to_user_id)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list(self.session.scalars(stmt).all())

    def create_agent_event(
        self,
        *,
        cycle_id: str | None,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None,
        source: str = "alert_daemon",
    ) -> AlertAgentEvent:
        payload_text: str | None = None
        if payload is not None:
            payload_text = json.dumps(payload, default=str, ensure_ascii=True)
        row = AlertAgentEvent(
            cycle_id=cycle_id,
            source=source,
            event_type=event_type,
            message=message,
            payload=payload_text,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_agent_events(
        self,
        *,
        after_id: int = 0,
        limit: int = 20,
    ) -> list[AlertAgentEvent]:
        stmt = (
            select(AlertAgentEvent)
            .where(AlertAgentEvent.id > max(0, after_id))
            .order_by(AlertAgentEvent.id.asc())
            .limit(max(1, min(limit, 500)))
        )
        return list(self.session.scalars(stmt).all())
