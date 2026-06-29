import anyio
import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import API_TOKEN_PREFIX, hash_token
from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent
from app.services.agent_tokens import issue_enrollment_token
from app.services.agents import AGENT_ACTIVE_STATUS, AGENT_UNMAPPED_STATUS


async def post_enroll(app: FastAPI, payload: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/agents/enroll", json=payload)


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


def test_agent_can_enroll_with_valid_enrollment_token(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )

    response = anyio.run(post_enroll, test_app, enrollment_payload(issued_token.token))

    body = response.json()
    agent = db_session.scalar(select(HermesAgent))
    token_records = db_session.scalars(select(AgentToken).order_by(AgentToken.id)).all()

    assert response.status_code == 200
    assert body["agent_uid"].startswith("agent_")
    assert body["api_token"].startswith(API_TOKEN_PREFIX)
    assert body["status"] == "ACTIVE"
    assert body["scope"] == "AGENT_ACTIVE"
    assert agent is not None
    assert agent.agent_uid == body["agent_uid"]
    assert agent.status == AGENT_ACTIVE_STATUS
    assert agent.owner_email == "agent.owner@example.com"
    assert agent.source == "gateway"
    assert token_records[0].used_at is not None
    assert token_records[0].agent_id == agent.id
    assert token_records[1].token_hash == hash_token(body["api_token"])
    assert token_records[1].token_hash != body["api_token"]
    assert token_records[1].agent_id == agent.id


def test_agent_can_enroll_without_token_as_unmapped(
    test_app: FastAPI,
    db_session: Session,
) -> None:
    response = anyio.run(post_enroll, test_app, enrollment_payload())

    body = response.json()
    agent = db_session.scalar(select(HermesAgent))
    token_record = db_session.scalar(select(AgentToken))

    assert response.status_code == 200
    assert body["api_token"].startswith(API_TOKEN_PREFIX)
    assert body["status"] == "UNMAPPED"
    assert body["scope"] == "AGENT_UNMAPPED"
    assert agent is not None
    assert agent.status == AGENT_UNMAPPED_STATUS
    assert agent.owner_email is None
    assert token_record is not None
    assert token_record.owner_email is None
    assert token_record.agent_id == agent.id


def test_agent_enroll_rejects_invalid_enrollment_token(test_app: FastAPI) -> None:
    response = anyio.run(post_enroll, test_app, enrollment_payload("wps_enroll_wrong"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid enrollment token"}


def test_agent_enroll_validates_required_profile_name(test_app: FastAPI) -> None:
    payload = enrollment_payload()
    del payload["profile_name"]

    response = anyio.run(post_enroll, test_app, payload)

    assert response.status_code == 422
