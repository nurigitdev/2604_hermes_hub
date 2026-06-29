from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import verify_password
from app.models.user import User
from app.services.admin_seed import seed_admin_user


def test_seed_admin_user_creates_active_admin(db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )

    admin_user = seed_admin_user(db_session, settings)

    assert admin_user.id is not None
    assert admin_user.email == "admin@example.com"
    assert admin_user.name == "Admin User"
    assert admin_user.role == "ADMIN"
    assert admin_user.is_active is True
    assert admin_user.password_hash != "change-me-admin-password"
    assert verify_password("change-me-admin-password", admin_user.password_hash)


def test_seed_admin_user_is_idempotent(db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )

    first_user = seed_admin_user(db_session, settings)
    second_user = seed_admin_user(db_session, settings)
    users = db_session.scalars(select(User)).all()

    assert first_user.id == second_user.id
    assert len(users) == 1


def test_seed_admin_user_does_not_rotate_existing_password(db_session: Session) -> None:
    initial_settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    changed_settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="changed-admin-password",
    )

    first_user = seed_admin_user(db_session, initial_settings)
    first_password_hash = first_user.password_hash
    second_user = seed_admin_user(db_session, changed_settings)

    assert second_user.password_hash == first_password_hash
    assert verify_password("change-me-admin-password", second_user.password_hash)
