from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.admin import AdminUser
from app.repositories.admin_auth_repo import AdminAuthRepository


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AdminAuthService:
    def ensure_default_admin_user(self, session: Session) -> None:
        repo = AdminAuthRepository(session)
        existing = repo.get_user_by_username("admin")
        if existing is not None:
            changed = False
            if existing.role != "admin":
                existing.role = "admin"
                changed = True
            if existing.email is None:
                existing.email = "admin@local.dev"
                changed = True
            if changed:
                session.commit()
            return
        password_hash = self._hash_password("passw0rd")
        repo.create_user_extended(
            username="admin",
            email="admin@local.dev",
            password_hash=password_hash,
            role="admin",
            subscription_ends_at=None,
            alerts_enabled=False,
            mobile_phone=None,
            is_active=True,
        )

    def login(
        self,
        session: Session,
        username: str,
        password: str,
        expires_hours: int = 8,
    ) -> tuple[AdminUser, str, datetime] | None:
        repo = AdminAuthRepository(session)
        repo.delete_expired_sessions(_utc_now_naive())
        user = repo.get_user_by_username(username.strip())
        if user is None or not user.is_active:
            return None
        if not self._verify_password(password, user.password_hash):
            return None

        token = uuid4().hex
        expires_at = _utc_now_naive() + timedelta(hours=max(1, min(expires_hours, 72)))
        repo.create_session(user_id=user.id, token=token, expires_at=expires_at)
        user.last_login_at = _utc_now_naive()
        session.commit()
        session.refresh(user)
        return user, token, expires_at

    def logout(self, session: Session, token: str) -> None:
        repo = AdminAuthRepository(session)
        repo.delete_session(token)

    def authenticate_token(self, session: Session, token: str) -> AdminUser | None:
        repo = AdminAuthRepository(session)
        row = repo.get_session(token)
        now = _utc_now_naive()
        if row is None:
            return None
        if row.expires_at < now:
            repo.delete_session(token)
            return None

        user = repo.get_user_by_id(row.user_id)
        if user is None or not user.is_active:
            repo.delete_session(token)
            return None
        return user

    def create_user(
        self,
        session: Session,
        username: str,
        email: str | None,
        password: str,
        role: str,
        subscription_ends_at: datetime | None,
        alerts_enabled: bool,
        mobile_phone: str | None,
        is_active: bool,
    ) -> AdminUser:
        repo = AdminAuthRepository(session)
        return repo.create_user_extended(
            username=username.strip(),
            email=(email or "").strip().lower() or None,
            password_hash=self._hash_password(password),
            role=role,
            subscription_ends_at=subscription_ends_at,
            alerts_enabled=alerts_enabled,
            mobile_phone=self._normalize_mobile_phone(mobile_phone),
            is_active=is_active,
        )

    def update_user(
        self,
        session: Session,
        user: AdminUser,
        email: str | None,
        password: str | None,
        role: str | None,
        subscription_ends_at: datetime | None,
        alerts_enabled: bool | None,
        mobile_phone: str | None,
        is_active: bool | None,
    ) -> AdminUser:
        repo = AdminAuthRepository(session)
        password_hash = self._hash_password(password) if password else None
        normalized_email = email
        if normalized_email is not None:
            normalized_email = normalized_email.strip().lower() or None
        return repo.update_user(
            user=user,
            email=normalized_email,
            password_hash=password_hash,
            role=role,
            subscription_ends_at=subscription_ends_at,
            alerts_enabled=alerts_enabled,
            mobile_phone=self._normalize_mobile_phone(mobile_phone),
            is_active=is_active,
        )

    @staticmethod
    def _normalize_mobile_phone(mobile_phone: str | None) -> str | None:
        if mobile_phone is None:
            return None
        cleaned = mobile_phone.strip()
        return cleaned or None

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = os.urandom(16)
        iterations = 120_000
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            method, iterations_text, salt_hex, digest_hex = encoded.split("$", 3)
            if method != "pbkdf2_sha256":
                return False
            iterations = int(iterations_text)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
        except (ValueError, TypeError):
            return False

        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(expected, computed)
