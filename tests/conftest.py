import os

from app.db.admin import Base, SessionLocal, engine, run_admin_migrations
from app.models import admin as _admin_models  # noqa: F401
from app.repositories.admin_auth_repo import AdminAuthRepository
from app.services.admin_auth import AdminAuthService

# Keep auth-related integration tests deterministic while avoiding hard-coded
# bootstrap credentials in application code.
BOOTSTRAP_ADMIN_USERNAME = os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
BOOTSTRAP_ADMIN_PASSWORD = os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-test-password")


def _ensure_test_bootstrap_admin() -> None:
    Base.metadata.create_all(bind=engine)
    run_admin_migrations()
    service = AdminAuthService()
    with SessionLocal() as session:
        service.ensure_default_admin_user(session)
        repo = AdminAuthRepository(session)
        user = repo.get_user_by_username(BOOTSTRAP_ADMIN_USERNAME)
        if user is None:
            return
        if not service._verify_password(BOOTSTRAP_ADMIN_PASSWORD, user.password_hash):
            user.password_hash = service._hash_password(BOOTSTRAP_ADMIN_PASSWORD)
            session.commit()


_ensure_test_bootstrap_admin()
