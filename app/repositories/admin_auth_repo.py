from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.admin import AdminSession, AdminUser


class AdminAuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_username(self, username: str) -> AdminUser | None:
        stmt = select(AdminUser).where(AdminUser.username == username)
        return self.session.scalar(stmt)

    def get_user_by_email(self, email: str) -> AdminUser | None:
        stmt = select(AdminUser).where(AdminUser.email == email)
        return self.session.scalar(stmt)

    def get_user_by_id(self, user_id: int) -> AdminUser | None:
        stmt = select(AdminUser).where(AdminUser.id == user_id)
        return self.session.scalar(stmt)

    def list_users(self) -> list[AdminUser]:
        stmt = select(AdminUser).order_by(AdminUser.username.asc())
        return list(self.session.scalars(stmt).all())

    def create_user(self, username: str, password_hash: str, is_active: bool) -> AdminUser:
        user = AdminUser(
            username=username,
            password_hash=password_hash,
            is_active=is_active,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def create_user_extended(
        self,
        *,
        username: str,
        email: str | None,
        password_hash: str,
        role: str,
        subscription_ends_at: datetime | None,
        alerts_enabled: bool,
        mobile_phone: str | None,
        is_active: bool,
    ) -> AdminUser:
        user = AdminUser(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            subscription_ends_at=subscription_ends_at,
            alerts_enabled=alerts_enabled,
            mobile_phone=mobile_phone,
            is_active=is_active,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update_user(
        self,
        user: AdminUser,
        email: str | None = None,
        password_hash: str | None = None,
        role: str | None = None,
        subscription_ends_at: datetime | None = None,
        alerts_enabled: bool | None = None,
        mobile_phone: str | None = None,
        is_active: bool | None = None,
    ) -> AdminUser:
        user.email = email
        if password_hash is not None:
            user.password_hash = password_hash
        if role is not None:
            user.role = role
        user.subscription_ends_at = subscription_ends_at
        if alerts_enabled is not None:
            user.alerts_enabled = alerts_enabled
        user.mobile_phone = mobile_phone
        if is_active is not None:
            user.is_active = is_active
        self.session.commit()
        self.session.refresh(user)
        return user

    def delete_user(self, user: AdminUser) -> None:
        self.session.delete(user)
        self.session.commit()

    def count_active_users(self) -> int:
        stmt = (
            select(func.count())
            .select_from(AdminUser)
            .where(AdminUser.is_active.is_(True), AdminUser.role == "admin")
        )
        value = self.session.scalar(stmt)
        return int(value or 0)

    def create_session(self, user_id: int, token: str, expires_at: datetime) -> AdminSession:
        session = AdminSession(user_id=user_id, token=token, expires_at=expires_at)
        self.session.add(session)
        self.session.commit()
        self.session.refresh(session)
        return session

    def get_session(self, token: str) -> AdminSession | None:
        stmt = select(AdminSession).where(AdminSession.token == token)
        return self.session.scalar(stmt)

    def delete_session(self, token: str) -> None:
        stmt = delete(AdminSession).where(AdminSession.token == token)
        self.session.execute(stmt)
        self.session.commit()

    def delete_expired_sessions(self, now: datetime) -> None:
        stmt = delete(AdminSession).where(AdminSession.expires_at < now)
        self.session.execute(stmt)
        self.session.commit()
