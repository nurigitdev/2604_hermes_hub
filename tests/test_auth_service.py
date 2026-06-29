from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models.user import User
from app.services.admin_seed import seed_admin_user
from app.services.auth import authenticate_admin, get_active_admin_by_id


def test_authenticate_admin_accepts_active_admin(db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    seed_admin_user(db_session, settings)

    user = authenticate_admin(
        db_session,
        email="admin@example.com",
        password="change-me-admin-password",
    )

    assert user is not None
    assert user.email == "admin@example.com"


def test_authenticate_admin_rejects_unknown_email(db_session: Session) -> None:
    assert authenticate_admin(db_session, email="missing@example.com", password="password") is None


def test_authenticate_admin_rejects_inactive_admin(db_session: Session) -> None:
    user = User(
        email="admin@example.com",
        role="ADMIN",
        password_hash=hash_password("change-me-admin-password"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    assert (
        authenticate_admin(
            db_session,
            email="admin@example.com",
            password="change-me-admin-password",
        )
        is None
    )


def test_authenticate_admin_rejects_non_admin_user(db_session: Session) -> None:
    user = User(
        email="viewer@example.com",
        role="VIEWER",
        password_hash=hash_password("change-me-admin-password"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    assert (
        authenticate_admin(
            db_session,
            email="viewer@example.com",
            password="change-me-admin-password",
        )
        is None
    )


def test_authenticate_admin_rejects_wrong_password(db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    seed_admin_user(db_session, settings)

    assert (
        authenticate_admin(db_session, email="admin@example.com", password="wrong-password")
        is None
    )


def test_get_active_admin_by_id_accepts_active_admin(db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    admin_user = seed_admin_user(db_session, settings)

    assert get_active_admin_by_id(db_session, user_id=admin_user.id) == admin_user


def test_get_active_admin_by_id_rejects_missing_user(db_session: Session) -> None:
    assert get_active_admin_by_id(db_session, user_id=999) is None


def test_get_active_admin_by_id_rejects_non_admin_user(db_session: Session) -> None:
    user = User(
        email="viewer@example.com",
        role="VIEWER",
        password_hash=hash_password("change-me-admin-password"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    assert get_active_admin_by_id(db_session, user_id=user.id) is None


def test_get_active_admin_by_id_rejects_inactive_admin(db_session: Session) -> None:
    user = User(
        email="admin@example.com",
        role="ADMIN",
        password_hash=hash_password("change-me-admin-password"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    assert get_active_admin_by_id(db_session, user_id=user.id) is None
