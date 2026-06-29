import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent
from app.services.admin_seed import seed_admin_user
from app.services.agent_tokens import AGENT_ACTIVE_SCOPE, issue_enrollment_token


async def post_enroll(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/agents/enroll", json=payload)


async def post_heartbeat(
    app: FastAPI,
    payload: dict[str, str],
    api_token: str,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {api_token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/agents/heartbeat", json=payload, headers=headers)


async def post_message_ingest(
    app: FastAPI,
    payload: dict[str, object],
    api_token: str,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {api_token}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/messages/ingest", json=payload, headers=headers)


async def login_and_request_admin_agents(
    app: FastAPI,
    method: str = "GET",
    path: str = "/admin/api/agents",
    payload: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "change-me-admin-password"},
        )
        return await client.request(method, path, json=payload)


async def get_admin_agents_without_login(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/admin/api/agents")


def seed_admin(db_session: Session) -> None:
    seed_admin_user(
        db_session,
        Settings(
            admin_email="admin@example.com",
            admin_name="Admin User",
            admin_password="change-me-admin-password",
        ),
    )


def enrollment_payload(enrollment_token: str | None = None) -> dict[str, str]:
    payload = {
        "profile_name": "kim-teamlead",
        "hostname": "KIM-PC",
        "ip_addr": "192.168.0.25",
        "source": "gateway",
    }
    if enrollment_token is not None:
        payload["enrollment_token"] = enrollment_token
    return payload


def heartbeat_payload(agent_uid: str) -> dict[str, str]:
    return {
        "agent_uid": agent_uid,
        "profile_name": "kim-teamlead",
        "source": "gateway",
        "ip_addr": "192.168.0.25",
        "runtime_status": "running",
    }


def message_payload(agent_uid: str) -> dict[str, object]:
    return {
        "agent_uid": agent_uid,
        "idempotency_key": "admin-agent-map-message",
        "external_message_id": "message-after-map",
        "event_type": "message",
        "source": "telegram",
        "session_key": "agent:main:telegram:private:123456789",
        "direction": "INBOUND",
        "role": "user",
        "content": "mapped agent message",
        "request_id": "req-admin-agent-map",
        "occurred_at": "2026-06-25T09:30:00+09:00",
        "raw_payload": {},
    }


def enroll_active_agent(test_app: FastAPI, db_session: Session) -> dict[str, str]:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )
    response = anyio.run(post_enroll, test_app, enrollment_payload(issued_token.token))
    return response.json()


def enroll_unmapped_agent(test_app: FastAPI) -> dict[str, str]:
    response = anyio.run(post_enroll, test_app, enrollment_payload())
    return response.json()


def test_admin_can_search_agents(test_app: FastAPI, db_session: Session) -> None:
    seed_admin(db_session)
    active = enroll_active_agent(test_app, db_session)
    enroll_unmapped_agent(test_app)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "GET",
        "/admin/api/agents?status=ACTIVE&owner_email=agent.owner@example.com&keyword=kim",
    )

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["agent_uid"] == active["agent_uid"]
    assert body["items"][0]["profile_name"] == "kim-teamlead"
    assert body["items"][0]["owner_email"] == "agent.owner@example.com"
    assert body["items"][0]["status"] == "ACTIVE"
    assert body["items"][0]["last_seen_at"] is not None


def test_admin_agent_search_supports_pagination(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    first = enroll_unmapped_agent(test_app)
    second = enroll_unmapped_agent(test_app)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "GET",
        "/admin/api/agents?limit=1&offset=1",
    )

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["agent_uid"] in {first["agent_uid"], second["agent_uid"]}


def test_admin_can_update_agent_display_name(test_app: FastAPI, db_session: Session) -> None:
    seed_admin(db_session)
    active = enroll_active_agent(test_app, db_session)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "PATCH",
        f"/admin/api/agents/{active['agent_uid']}",
        {"display_name": "Kim Team Lead Agent"},
    )

    agent = db_session.scalar(
        select(HermesAgent).where(HermesAgent.agent_uid == active["agent_uid"])
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Kim Team Lead Agent"
    assert agent is not None
    assert agent.display_name == "Kim Team Lead Agent"


def test_admin_can_map_unmapped_agent_and_upgrade_token_scope(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    unmapped = enroll_unmapped_agent(test_app)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "POST",
        f"/admin/api/agents/{unmapped['agent_uid']}/map",
        {"owner_email": "agent.owner@example.com"},
    )
    token = db_session.scalar(select(AgentToken).where(AgentToken.agent_id.is_not(None)))
    ingest_response = anyio.run(
        post_message_ingest,
        test_app,
        message_payload(unmapped["agent_uid"]),
        unmapped["api_token"],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    assert response.json()["owner_email"] == "agent.owner@example.com"
    assert token is not None
    assert token.scope == AGENT_ACTIVE_SCOPE
    assert token.owner_email == "agent.owner@example.com"
    assert ingest_response.status_code == 200


def test_admin_can_disable_agent_and_block_agent_api(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    active = enroll_active_agent(test_app, db_session)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "POST",
        f"/admin/api/agents/{active['agent_uid']}/disable",
    )
    heartbeat_response = anyio.run(
        post_heartbeat,
        test_app,
        heartbeat_payload(active["agent_uid"]),
        active["api_token"],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"
    assert heartbeat_response.status_code == 403
    assert heartbeat_response.json() == {"detail": "Agent access forbidden"}


def test_admin_agent_management_requires_admin_session(test_app: FastAPI) -> None:
    response = anyio.run(get_admin_agents_without_login, test_app)

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_admin_agent_patch_returns_404_for_missing_agent(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "PATCH",
        "/admin/api/agents/agent_missing",
        {"display_name": "Missing"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Agent not found"}


def test_admin_agent_map_returns_404_for_missing_agent(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "POST",
        "/admin/api/agents/agent_missing/map",
        {"owner_email": "agent.owner@example.com"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Agent not found"}


def test_admin_agent_disable_returns_404_for_missing_agent(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "POST",
        "/admin/api/agents/agent_missing/disable",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Agent not found"}


def test_admin_agent_map_validates_owner_email(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    seed_admin(db_session)
    unmapped = enroll_unmapped_agent(test_app)

    response = anyio.run(
        login_and_request_admin_agents,
        test_app,
        "POST",
        f"/admin/api/agents/{unmapped['agent_uid']}/map",
        {"owner_email": "not-an-email"},
    )

    assert response.status_code == 422
