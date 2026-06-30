import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models.user import User
from app.services.admin_seed import seed_admin_user


async def post_login(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/auth/login", json=payload)


async def post_login_then_logout(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/auth/login", json=payload)
        return await client.post("/auth/logout")


def test_login_api_accepts_valid_admin(test_app: FastAPI, db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    seed_admin_user(db_session, settings)

    response = anyio.run(
        post_login,
        test_app,
        {"email": "admin@example.com", "password": "change-me-admin-password"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "role": "ADMIN"}
    assert "hermes_hub_session" in response.cookies
    assert "HttpOnly" in response.headers["set-cookie"]


def test_login_api_rejects_wrong_password(test_app: FastAPI, db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    seed_admin_user(db_session, settings)

    response = anyio.run(
        post_login,
        test_app,
        {"email": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_logout_api_clears_admin_session_cookie(test_app: FastAPI, db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    seed_admin_user(db_session, settings)

    response = anyio.run(
        post_login_then_logout,
        test_app,
        {"email": "admin@example.com", "password": "change-me-admin-password"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "hermes_hub_session" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_login_api_rejects_unknown_email(test_app: FastAPI) -> None:
    response = anyio.run(
        post_login,
        test_app,
        {"email": "missing@example.com", "password": "change-me-admin-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_login_api_rejects_inactive_admin(test_app: FastAPI, db_session: Session) -> None:
    user = User(
        email="admin@example.com",
        role="ADMIN",
        password_hash=hash_password("change-me-admin-password"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = anyio.run(
        post_login,
        test_app,
        {"email": "admin@example.com", "password": "change-me-admin-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_login_api_validates_malformed_email(test_app: FastAPI) -> None:
    response = anyio.run(
        post_login,
        test_app,
        {"email": "not-an-email", "password": "change-me-admin-password"},
    )

    assert response.status_code == 422


def test_login_api_validates_missing_password(test_app: FastAPI) -> None:
    response = anyio.run(post_login, test_app, {"email": "admin@example.com"})

    assert response.status_code == 422
