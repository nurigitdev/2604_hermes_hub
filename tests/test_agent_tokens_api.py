import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.tokens import ENROLLMENT_TOKEN_PREFIX, hash_token
from app.models.agent_token import AgentToken
from app.services.admin_seed import seed_admin_user


async def login_and_issue_token(
    app: FastAPI,
    owner_email: str,
    expires_at: str | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    payload = {"owner_email": owner_email}
    if expires_at is not None:
        payload["expires_at"] = expires_at

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "change-me-admin-password"},
        )
        return await client.post("/admin/api/agent-tokens", json=payload)


async def issue_token_without_login(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/admin/api/agent-tokens",
            json={"owner_email": "agent.owner@example.com"},
        )


def seed_admin(db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    seed_admin_user(db_session, settings)


def test_admin_can_issue_enrollment_token(test_app: FastAPI, db_session: Session) -> None:
    seed_admin(db_session)

    response = anyio.run(
        login_and_issue_token,
        test_app,
        "agent.owner@example.com",
        "2026-07-25T23:59:59Z",
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["token"].startswith(ENROLLMENT_TOKEN_PREFIX)
    assert body["token_type"] == "ENROLLMENT"
    assert body["owner_email"] == "agent.owner@example.com"
    assert body["expires_at"] == "2026-07-25T23:59:59Z"


def test_issued_enrollment_token_stores_hash_only(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)

    response = anyio.run(
        login_and_issue_token,
        test_app,
        "agent.owner@example.com",
    )

    token = response.json()["token"]
    records = db_session.scalars(select(AgentToken)).all()

    assert len(records) == 1
    assert records[0].token_hash == hash_token(token)
    assert records[0].token_hash != token
    assert records[0].owner_email == "agent.owner@example.com"
    assert records[0].expires_at is None


def test_issue_enrollment_token_requires_admin_session(test_app: FastAPI) -> None:
    response = anyio.run(issue_token_without_login, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_issue_enrollment_token_validates_owner_email(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)

    response = anyio.run(
        login_and_issue_token,
        test_app,
        "not-an-email",
    )

    assert response.status_code == 422
