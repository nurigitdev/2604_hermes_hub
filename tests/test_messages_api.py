import json

import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.hermes_agent import HermesAgent
from app.services.agent_tokens import issue_enrollment_token


async def post_enroll(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/agents/enroll", json=payload)


async def post_message_ingest(
    app: FastAPI,
    payload: dict[str, object],
    api_token: str | None = None,
    idempotency_key_header: str | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    headers = {}
    if api_token is not None:
        headers["Authorization"] = f"Bearer {api_token}"
    if idempotency_key_header is not None:
        headers["Idempotency-Key"] = idempotency_key_header

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/messages/ingest", json=payload, headers=headers)


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


def message_payload(agent_uid: str) -> dict[str, object]:
    return {
        "agent_uid": agent_uid,
        "idempotency_key": "body-idempotency-key",
        "external_message_id": "telegram_123456789_100",
        "event_type": "message",
        "source": "telegram",
        "session_key": "agent:main:telegram:private:123456789",
        "direction": "INBOUND",
        "role": "user",
        "content": "오늘 작업 내용을 정리해줘",
        "request_id": "req_abc123",
        "occurred_at": "2026-06-25T09:30:00+09:00",
        "raw_payload": {"telegram_update_id": 100},
    }


def enroll_active_agent(test_app: FastAPI, db_session: Session) -> dict[str, str]:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )
    response = anyio.run(post_enroll, test_app, enrollment_payload(issued_token.token))
    return response.json()


def test_active_agent_can_ingest_message(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)

    response = anyio.run(
        post_message_ingest,
        test_app,
        message_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )

    body = response.json()
    message = db_session.scalar(select(AgentMessage))
    agent_session = db_session.scalar(select(AgentSession))

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["message_id"] == message.id
    assert body["duplicate"] is False
    assert agent_session is not None
    assert agent_session.hermes_session_id == "agent:main:telegram:private:123456789"
    assert message is not None
    assert message.session_id == agent_session.id
    assert message.source == "telegram"
    assert message.role == "user"
    assert message.event_type == "message"
    assert message.parent_message_id is None
    assert json.loads(message.raw_payload) == {"telegram_update_id": 100}


def test_message_ingest_accepts_parent_message_id(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)
    parent = anyio.run(
        post_message_ingest,
        test_app,
        message_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )
    child_payload = message_payload(enroll_body["agent_uid"])
    child_payload["idempotency_key"] = "child-idempotency-key"
    child_payload["external_message_id"] = "telegram_123456789_101"
    child_payload["parent_message_id"] = parent.json()["message_id"]

    response = anyio.run(
        post_message_ingest,
        test_app,
        child_payload,
        enroll_body["api_token"],
    )
    message = db_session.get(AgentMessage, response.json()["message_id"])

    assert response.status_code == 200
    assert message is not None
    assert message.parent_message_id == parent.json()["message_id"]


def test_message_ingest_header_idempotency_key_overrides_body(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)

    response = anyio.run(
        post_message_ingest,
        test_app,
        message_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
        "header-idempotency-key",
    )
    duplicate_payload = message_payload(enroll_body["agent_uid"])
    duplicate_payload["external_message_id"] = "telegram_123456789_101"
    duplicate = anyio.run(
        post_message_ingest,
        test_app,
        duplicate_payload,
        enroll_body["api_token"],
        "header-idempotency-key",
    )
    message = db_session.scalar(select(AgentMessage))

    assert response.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()["message_id"] == response.json()["message_id"]
    assert duplicate.json()["duplicate"] is True
    assert message is not None
    assert message.idempotency_key == "header-idempotency-key"


def test_message_ingest_returns_duplicate_by_external_message_id(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)
    first = anyio.run(
        post_message_ingest,
        test_app,
        message_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )
    duplicate_payload = message_payload(enroll_body["agent_uid"])
    duplicate_payload["idempotency_key"] = "different-idempotency-key"

    duplicate = anyio.run(
        post_message_ingest,
        test_app,
        duplicate_payload,
        enroll_body["api_token"],
    )

    assert duplicate.status_code == 200
    assert duplicate.json() == {
        "ok": True,
        "message_id": first.json()["message_id"],
        "duplicate": True,
    }


def test_message_ingest_requires_authorization_header(test_app: FastAPI) -> None:
    response = anyio.run(
        post_message_ingest,
        test_app,
        message_payload("agent_missing"),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Agent authentication required"}


def test_message_ingest_rejects_unmapped_agent(
    test_app: FastAPI,
) -> None:
    enroll_response = anyio.run(post_enroll, test_app, enrollment_payload())
    enroll_body = enroll_response.json()

    response = anyio.run(
        post_message_ingest,
        test_app,
        message_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Agent access forbidden"}


def test_message_ingest_rejects_agent_uid_mismatch(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)

    response = anyio.run(
        post_message_ingest,
        test_app,
        message_payload("agent_wrong"),
        enroll_body["api_token"],
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Agent access forbidden"}


def test_message_ingest_rejects_disabled_agent(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)
    agent = db_session.scalar(select(HermesAgent))
    assert agent is not None
    agent.status = "DISABLED"
    db_session.flush()

    response = anyio.run(
        post_message_ingest,
        test_app,
        message_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Agent access forbidden"}


def test_message_ingest_validates_required_session_key(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)
    payload = message_payload(enroll_body["agent_uid"])
    del payload["session_key"]

    response = anyio.run(
        post_message_ingest,
        test_app,
        payload,
        enroll_body["api_token"],
    )

    assert response.status_code == 422
