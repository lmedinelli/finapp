"""Unit tests for AdminAuthService.ensure_default_admin_user."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.admin import Base
from app.models import admin as _admin_models  # noqa: F401
from app.services.admin_auth import AdminAuthService


def _make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_ensure_creates_admin_with_configured_password(monkeypatch) -> None:
    """When BOOTSTRAP_ADMIN_PASSWORD is set, the admin user is created with that password."""
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "s3cr3t-configured")

    # Clear the lru_cache so settings picks up the monkeypatched env vars.
    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        session_factory = _make_session()
        service = AdminAuthService()
        with session_factory() as session:
            service.ensure_default_admin_user(session)
            from app.repositories.admin_auth_repo import AdminAuthRepository

            repo = AdminAuthRepository(session)
            user = repo.get_user_by_username("admin")
            assert user is not None
            assert user.role == "admin"
            assert service._verify_password("s3cr3t-configured", user.password_hash)
    finally:
        get_settings.cache_clear()


def test_ensure_creates_admin_with_generated_password_when_env_not_set(monkeypatch) -> None:
    """When BOOTSTRAP_ADMIN_PASSWORD is not set, a random password is generated."""
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        session_factory = _make_session()
        service = AdminAuthService()
        with session_factory() as session:
            service.ensure_default_admin_user(session)
            from app.repositories.admin_auth_repo import AdminAuthRepository

            repo = AdminAuthRepository(session)
            user = repo.get_user_by_username("admin")
            assert user is not None
            assert user.password_hash.startswith("pbkdf2_sha256$")
            # The generated password must NOT match a hard-coded value.
            assert not service._verify_password("passw0rd", user.password_hash)
            assert not service._verify_password("admin", user.password_hash)
    finally:
        get_settings.cache_clear()


def test_ensure_does_not_recreate_existing_admin(monkeypatch) -> None:
    """If the admin user already exists, ensure_default_admin_user must not duplicate it."""
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "initial-pass")

    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        session_factory = _make_session()
        service = AdminAuthService()
        with session_factory() as session:
            # First call creates the user.
            service.ensure_default_admin_user(session)
            # Second call must be idempotent.
            service.ensure_default_admin_user(session)

            from app.repositories.admin_auth_repo import AdminAuthRepository

            repo = AdminAuthRepository(session)
            users = repo.list_users()
            assert len(users) == 1
            assert users[0].username == "admin"
    finally:
        get_settings.cache_clear()


def test_ensure_patches_missing_role_on_existing_user(monkeypatch) -> None:
    """If an existing admin user has no role, ensure_default_admin_user must set it to 'admin'."""
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "any-pass")

    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        session_factory = _make_session()
        service = AdminAuthService()
        with session_factory() as session:
            # Create user directly with an empty role to simulate a legacy row.
            from app.models.admin import AdminUser

            user = AdminUser(
                username="admin",
                password_hash=service._hash_password("any-pass"),
                is_active=True,
                role="",
            )
            session.add(user)
            session.commit()

            service.ensure_default_admin_user(session)
            session.refresh(user)
            assert user.role == "admin"
    finally:
        get_settings.cache_clear()


def test_ensure_generated_password_warning_logged(monkeypatch, caplog) -> None:
    """A warning must be emitted when the password is auto-generated."""
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")

    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        session_factory = _make_session()
        service = AdminAuthService()
        with caplog.at_level(logging.WARNING, logger="app.services.admin_auth"):
            with session_factory() as session:
                service.ensure_default_admin_user(session)

        assert any("BOOTSTRAP_ADMIN_PASSWORD not set" in r.message for r in caplog.records)
    finally:
        get_settings.cache_clear()
