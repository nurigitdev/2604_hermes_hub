import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_SESSION_COOKIE_NAME, Settings
from app.core.session import create_session_token
from app.services.admin_seed import seed_admin_user


async def login_and_get_me(
    app: FastAPI,
    payload: dict[str, str],
) -> tuple[httpx.Response, httpx.Response]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_response = await client.post("/auth/login", json=payload)
        me_response = await client.get("/admin/api/me")
        return login_response, me_response


async def get_me(app: FastAPI, session_cookie: str | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        if session_cookie is not None:
            client.cookies.set(DEFAULT_SESSION_COOKIE_NAME, session_cookie)
        return await client.get("/admin/api/me")


def test_get_me_returns_current_admin_after_login(test_app: FastAPI, db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    admin_user = seed_admin_user(db_session, settings)

    login_response, me_response = anyio.run(
        login_and_get_me,
        test_app,
        {"email": "admin@example.com", "password": "change-me-admin-password"},
    )

    assert login_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json() == {
        "id": admin_user.id,
        "email": "admin@example.com",
        "name": "Admin User",
        "role": "ADMIN",
    }


def test_get_me_rejects_missing_session_cookie(test_app: FastAPI) -> None:
    response = anyio.run(get_me, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_get_me_rejects_tampered_session_cookie(test_app: FastAPI) -> None:
    response = anyio.run(get_me, test_app, "tampered.cookie")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_get_me_rejects_session_for_missing_user(test_app: FastAPI) -> None:
    token = create_session_token(user_id=999, secret_key="change-me-in-local-env")

    response = anyio.run(get_me, test_app, token)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_get_me_rejects_session_for_inactive_admin(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    admin_user = seed_admin_user(db_session, settings)
    token = create_session_token(user_id=admin_user.id, secret_key="change-me-in-local-env")

    admin_user.is_active = False
    db_session.commit()

    response = anyio.run(get_me, test_app, token)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
