import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.services.agent_tokens import ENROLL_AGENT_SCOPE, issue_enrollment_token
from app.services.agents import (
    AGENT_DISABLED_STATUS,
    AgentAccessForbiddenError,
    authenticate_agent_api_token,
    enroll_agent,
)
from app.services.events import ingest_event


def active_authenticated_agent(db_session: Session):
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=issued_token.token,
        profile_name="kim-teamlead",
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
    )
    return enrolled_agent, authenticate_agent_api_token(db_session, token=enrolled_agent.api_token)


def event_kwargs(agent_uid: str) -> dict[str, object]:
    return {
        "agent_uid": agent_uid,
        "event_type": "agent:end",
        "severity": "INFO",
        "summary": "Agent response completed",
        "occurred_at": datetime(2026, 6, 25, 9, 31, 15, tzinfo=UTC),
        "raw_payload": {"duration_ms": 1200},
    }


def test_ingest_event_creates_event_record(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)

    result = ingest_event(
        db_session,
        authenticated_agent=authenticated_agent,
        **event_kwargs(enrolled_agent.agent.agent_uid),
    )

    event = db_session.scalar(select(AgentEvent))

    assert event is not None
    assert result.event.id == event.id
    assert event.agent_id == enrolled_agent.agent.id
    assert event.event_type == "agent:end"
    assert event.severity == "INFO"
    assert event.summary == "Agent response completed"
    assert event.occurred_at == datetime(2026, 6, 25, 9, 31, 15)
    assert json.loads(event.raw_payload) == {"duration_ms": 1200}


def test_ingest_event_allows_missing_occurred_at(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    kwargs = event_kwargs(enrolled_agent.agent.agent_uid)
    kwargs["occurred_at"] = None

    result = ingest_event(db_session, authenticated_agent=authenticated_agent, **kwargs)

    assert result.event.occurred_at is None


def test_ingest_event_rejects_agent_uid_mismatch(db_session: Session) -> None:
    _enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)

    with pytest.raises(AgentAccessForbiddenError):
        ingest_event(
            db_session,
            authenticated_agent=authenticated_agent,
            **event_kwargs("agent_wrong"),
        )


def test_ingest_event_rejects_unmapped_agent(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )
    authenticated_agent = authenticate_agent_api_token(db_session, token=enrolled_agent.api_token)

    with pytest.raises(AgentAccessForbiddenError):
        ingest_event(
            db_session,
            authenticated_agent=authenticated_agent,
            **event_kwargs(enrolled_agent.agent.agent_uid),
        )


def test_ingest_event_rejects_disabled_agent(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    enrolled_agent.agent.status = AGENT_DISABLED_STATUS
    db_session.flush()

    with pytest.raises(AgentAccessForbiddenError):
        ingest_event(
            db_session,
            authenticated_agent=authenticated_agent,
            **event_kwargs(enrolled_agent.agent.agent_uid),
        )


def test_ingest_event_rejects_non_active_scope(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    enrolled_agent.api_token_record.scope = ENROLL_AGENT_SCOPE
    db_session.flush()

    with pytest.raises(AgentAccessForbiddenError):
        ingest_event(
            db_session,
            authenticated_agent=authenticated_agent,
            **event_kwargs(enrolled_agent.agent.agent_uid),
        )
