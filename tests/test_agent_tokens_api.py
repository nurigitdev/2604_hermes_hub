import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.tokens import API_TOKEN_PREFIX, hash_token
from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent
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


async def list_tokens_after_login(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "change-me-admin-password"},
        )
        return await client.get("/admin/api/agent-tokens")


async def list_tokens_without_login(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/admin/api/agent-tokens")


async def post_heartbeat(
    app: FastAPI,
    agent_uid: str,
    api_token: str,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/api/v1/agents/heartbeat",
            json={
                "agent_uid": agent_uid,
                "profile_name": "hermes-cli",
                "source": "cli",
                "ip_addr": "127.0.0.1",
                "runtime_status": "running",
            },
            headers={"Authorization": f"Bearer {api_token}"},
        )


def seed_admin(db_session: Session) -> None:
    settings = Settings(
        admin_email="admin@example.com",
        admin_name="Admin User",
        admin_password="change-me-admin-password",
    )
    seed_admin_user(db_session, settings)


def test_admin_can_issue_agent_api_token(test_app: FastAPI, db_session: Session) -> None:
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
    assert body["agent_uid"] == "agent.owner@example.com"
    assert body["token"].startswith(API_TOKEN_PREFIX)
    assert body["token_type"] == "API"
    assert body["owner_email"] == "agent.owner@example.com"
    assert body["expires_at"] == "2026-07-25T23:59:59Z"


def test_issued_agent_api_token_stores_hash_only_and_creates_email_agent(
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
    agent = db_session.scalar(select(HermesAgent))

    assert len(records) == 1
    assert records[0].token_hash == hash_token(token)
    assert records[0].token_hash != token
    assert records[0].token_type == "API"
    assert records[0].scope == "AGENT_ACTIVE"
    assert records[0].owner_email == "agent.owner@example.com"
    assert records[0].agent_id is not None
    assert records[0].expires_at is None
    assert agent is not None
    assert agent.id == records[0].agent_id
    assert agent.agent_uid == "agent.owner@example.com"
    assert agent.owner_email == "agent.owner@example.com"
    assert agent.status == "ACTIVE"


def test_issued_agent_api_token_can_authenticate_agent_heartbeat(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    issue_response = anyio.run(login_and_issue_token, test_app, "agent.owner@example.com")
    issue_body = issue_response.json()

    response = anyio.run(
        post_heartbeat,
        test_app,
        issue_body["agent_uid"],
        issue_body["token"],
    )

    agent = db_session.scalar(select(HermesAgent))
    assert response.status_code == 200
    assert response.json()["agent_uid"] == "agent.owner@example.com"
    assert agent is not None
    assert agent.profile_name == "hermes-cli"
    assert agent.source == "cli"
    assert agent.last_heartbeat_status == "running"


def test_admin_can_list_issued_agent_api_tokens_without_secret_values(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    first_response = anyio.run(login_and_issue_token, test_app, "first.owner@example.com")
    second_response = anyio.run(login_and_issue_token, test_app, "second.owner@example.com")

    response = anyio.run(list_tokens_after_login, test_app)

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 2
    assert [item["agent_uid"] for item in body["items"]] == [
        "second.owner@example.com",
        "first.owner@example.com",
    ]
    assert body["items"][0]["owner_email"] == "second.owner@example.com"
    assert body["items"][0]["token_type"] == "API"
    assert body["items"][0]["scope"] == "AGENT_ACTIVE"
    assert body["items"][0]["agent_status"] == "ACTIVE"
    assert body["items"][0]["is_active"] is True
    assert body["items"][0]["created_at"] is not None
    assert "token" not in body["items"][0]
    assert "token_hash" not in body["items"][0]
    assert first_response.json()["token"] not in response.text
    assert second_response.json()["token"] not in response.text


def test_issue_agent_api_token_requires_admin_session(test_app: FastAPI) -> None:
    response = anyio.run(issue_token_without_login, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_list_agent_api_tokens_requires_admin_session(test_app: FastAPI) -> None:
    response = anyio.run(list_tokens_without_login, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_issue_agent_api_token_validates_owner_email(
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
