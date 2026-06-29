import json

import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.models.hermes_agent import HermesAgent
from app.services.agent_tokens import issue_enrollment_token


async def post_enroll(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/agents/enroll", json=payload)


async def post_event_ingest(
    app: FastAPI,
    payload: dict[str, object],
    api_token: str | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    headers = {}
    if api_token is not None:
        headers["Authorization"] = f"Bearer {api_token}"

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/events/ingest", json=payload, headers=headers)


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


def event_payload(agent_uid: str) -> dict[str, object]:
    return {
        "agent_uid": agent_uid,
        "event_type": "agent:end",
        "severity": "INFO",
        "summary": "Agent response completed",
        "occurred_at": "2026-06-25T09:31:15+09:00",
        "raw_payload": {"duration_ms": 1200},
    }


def enroll_active_agent(test_app: FastAPI, db_session: Session) -> dict[str, str]:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )
    response = anyio.run(post_enroll, test_app, enrollment_payload(issued_token.token))
    return response.json()


def test_active_agent_can_ingest_event(test_app: FastAPI, db_session: Session) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)

    response = anyio.run(
        post_event_ingest,
        test_app,
        event_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )

    body = response.json()
    event = db_session.scalar(select(AgentEvent))

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["event_id"] == event.id
    assert event is not None
    assert event.event_type == "agent:end"
    assert event.severity == "INFO"
    assert event.summary == "Agent response completed"
    assert json.loads(event.raw_payload) == {"duration_ms": 1200}


def test_event_ingest_requires_authorization_header(test_app: FastAPI) -> None:
    response = anyio.run(post_event_ingest, test_app, event_payload("agent_missing"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Agent authentication required"}


def test_event_ingest_rejects_unmapped_agent(test_app: FastAPI) -> None:
    enroll_response = anyio.run(post_enroll, test_app, enrollment_payload())
    enroll_body = enroll_response.json()

    response = anyio.run(
        post_event_ingest,
        test_app,
        event_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Agent access forbidden"}


def test_event_ingest_rejects_agent_uid_mismatch(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)

    response = anyio.run(
        post_event_ingest,
        test_app,
        event_payload("agent_wrong"),
        enroll_body["api_token"],
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Agent access forbidden"}


def test_event_ingest_rejects_disabled_agent(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)
    agent = db_session.scalar(select(HermesAgent))
    assert agent is not None
    agent.status = "DISABLED"
    db_session.flush()

    response = anyio.run(
        post_event_ingest,
        test_app,
        event_payload(enroll_body["agent_uid"]),
        enroll_body["api_token"],
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Agent access forbidden"}


def test_event_ingest_validates_required_summary(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    enroll_body = enroll_active_agent(test_app, db_session)
    payload = event_payload(enroll_body["agent_uid"])
    del payload["summary"]

    response = anyio.run(
        post_event_ingest,
        test_app,
        payload,
        enroll_body["api_token"],
    )

    assert response.status_code == 422
