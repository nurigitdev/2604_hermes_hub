import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.services.agent_tokens import ENROLL_AGENT_SCOPE, issue_enrollment_token
from app.services.agents import (
    AGENT_DISABLED_STATUS,
    AgentAccessForbiddenError,
    authenticate_agent_api_token,
    enroll_agent,
)
from app.services.messages import (
    dump_json,
    find_duplicate_message,
    get_or_create_agent_session,
    hash_content,
    ingest_message,
)


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


def message_kwargs(agent_uid: str) -> dict[str, object]:
    return {
        "agent_uid": agent_uid,
        "idempotency_key": "msg_agent_1_req_1",
        "external_message_id": "telegram_123456789_100",
        "event_type": "message",
        "source": "telegram",
        "session_key": "agent:main:telegram:private:123456789",
        "direction": "INBOUND",
        "role": "user",
        "content": "오늘 작업 내용을 정리해줘",
        "request_id": "req_abc123",
        "occurred_at": datetime(2026, 6, 25, 9, 30, tzinfo=UTC),
        "raw_payload": {"telegram_update_id": 100},
    }


def test_ingest_message_creates_session_and_message(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)

    result = ingest_message(
        db_session,
        authenticated_agent=authenticated_agent,
        **message_kwargs(enrolled_agent.agent.agent_uid),
    )

    agent_session = db_session.scalar(select(AgentSession))
    message = db_session.scalar(select(AgentMessage))

    assert result.duplicate is False
    assert result.message.id == message.id
    assert agent_session is not None
    assert agent_session.agent_id == enrolled_agent.agent.id
    assert agent_session.source == "telegram"
    assert agent_session.hermes_session_id == "agent:main:telegram:private:123456789"
    assert message is not None
    assert message.agent_id == enrolled_agent.agent.id
    assert message.session_id == agent_session.id
    assert message.idempotency_key == "msg_agent_1_req_1"
    assert message.external_message_id == "telegram_123456789_100"
    assert message.direction == "INBOUND"
    assert message.role == "user"
    assert message.event_type == "message"
    assert message.message_type_code == 1
    assert message.assistant_response is None
    assert message.parent_message_id is None
    assert message.content_hash == hash_content("오늘 작업 내용을 정리해줘")
    assert json.loads(message.raw_payload) == {"telegram_update_id": 100}


def test_ingest_message_stores_parent_message_id(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    parent = ingest_message(
        db_session,
        authenticated_agent=authenticated_agent,
        **message_kwargs(enrolled_agent.agent.agent_uid),
    )
    child_kwargs = message_kwargs(enrolled_agent.agent.agent_uid)
    child_kwargs["idempotency_key"] = "msg_agent_1_resp_1"
    child_kwargs["external_message_id"] = "telegram_123456789_101"
    child_kwargs["parent_message_id"] = parent.message.id

    child = ingest_message(db_session, authenticated_agent=authenticated_agent, **child_kwargs)

    assert child.message.parent_message_id == parent.message.id


def test_ingest_message_stores_post_llm_type_and_assistant_response(
    db_session: Session,
) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    kwargs = message_kwargs(enrolled_agent.agent.agent_uid)
    kwargs["idempotency_key"] = "msg_agent_1_resp_1"
    kwargs["external_message_id"] = "telegram_123456789_101"
    kwargs["event_type"] = "post_llm_call"
    kwargs["direction"] = "OUTBOUND"
    kwargs["role"] = "assistant"
    kwargs["content"] = "정리 결과입니다"
    kwargs["assistant_response"] = "정리 결과입니다"

    result = ingest_message(db_session, authenticated_agent=authenticated_agent, **kwargs)

    assert result.message.message_type_code == 2
    assert result.message.assistant_response == "정리 결과입니다"


def test_ingest_message_reuses_existing_session(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)

    first = ingest_message(
        db_session,
        authenticated_agent=authenticated_agent,
        **message_kwargs(enrolled_agent.agent.agent_uid),
    )
    second_kwargs = message_kwargs(enrolled_agent.agent.agent_uid)
    second_kwargs["idempotency_key"] = "msg_agent_1_req_2"
    second_kwargs["external_message_id"] = "telegram_123456789_101"
    second = ingest_message(db_session, authenticated_agent=authenticated_agent, **second_kwargs)

    sessions = db_session.scalars(select(AgentSession)).all()

    assert len(sessions) == 1
    assert first.message.session_id == second.message.session_id


def test_ingest_message_returns_duplicate_by_idempotency_key(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    first = ingest_message(
        db_session,
        authenticated_agent=authenticated_agent,
        **message_kwargs(enrolled_agent.agent.agent_uid),
    )
    duplicate_kwargs = message_kwargs(enrolled_agent.agent.agent_uid)
    duplicate_kwargs["external_message_id"] = "telegram_123456789_101"

    duplicate = ingest_message(
        db_session,
        authenticated_agent=authenticated_agent,
        **duplicate_kwargs,
    )
    messages = db_session.scalars(select(AgentMessage)).all()

    assert duplicate.duplicate is True
    assert duplicate.message.id == first.message.id
    assert len(messages) == 1


def test_ingest_message_returns_duplicate_by_external_message_id(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    first = ingest_message(
        db_session,
        authenticated_agent=authenticated_agent,
        **message_kwargs(enrolled_agent.agent.agent_uid),
    )
    duplicate_kwargs = message_kwargs(enrolled_agent.agent.agent_uid)
    duplicate_kwargs["idempotency_key"] = "msg_agent_1_req_2"

    duplicate = ingest_message(
        db_session,
        authenticated_agent=authenticated_agent,
        **duplicate_kwargs,
    )
    messages = db_session.scalars(select(AgentMessage)).all()

    assert duplicate.duplicate is True
    assert duplicate.message.id == first.message.id
    assert len(messages) == 1


def test_ingest_message_allows_missing_optional_duplicate_keys(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    kwargs = message_kwargs(enrolled_agent.agent.agent_uid)
    kwargs["idempotency_key"] = None
    kwargs["external_message_id"] = None

    result = ingest_message(db_session, authenticated_agent=authenticated_agent, **kwargs)

    assert result.duplicate is False
    assert find_duplicate_message(
        db_session,
        agent_id=enrolled_agent.agent.id,
        source="telegram",
        idempotency_key=None,
        external_message_id=None,
    ) is None


def test_ingest_message_rejects_agent_uid_mismatch(db_session: Session) -> None:
    _enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)

    with pytest.raises(AgentAccessForbiddenError):
        ingest_message(
            db_session,
            authenticated_agent=authenticated_agent,
            **message_kwargs("agent_wrong"),
        )


def test_ingest_message_rejects_unmapped_agent(db_session: Session) -> None:
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
        ingest_message(
            db_session,
            authenticated_agent=authenticated_agent,
            **message_kwargs(enrolled_agent.agent.agent_uid),
        )


def test_ingest_message_rejects_disabled_agent(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    enrolled_agent.agent.status = AGENT_DISABLED_STATUS
    db_session.flush()

    with pytest.raises(AgentAccessForbiddenError):
        ingest_message(
            db_session,
            authenticated_agent=authenticated_agent,
            **message_kwargs(enrolled_agent.agent.agent_uid),
        )


def test_ingest_message_rejects_non_active_scope(db_session: Session) -> None:
    enrolled_agent, authenticated_agent = active_authenticated_agent(db_session)
    enrolled_agent.api_token_record.scope = ENROLL_AGENT_SCOPE
    db_session.flush()

    with pytest.raises(AgentAccessForbiddenError):
        ingest_message(
            db_session,
            authenticated_agent=authenticated_agent,
            **message_kwargs(enrolled_agent.agent.agent_uid),
        )


def test_get_or_create_agent_session_uses_current_time_without_occurred_at(
    db_session: Session,
) -> None:
    enrolled_agent, _authenticated_agent = active_authenticated_agent(db_session)

    agent_session = get_or_create_agent_session(
        db_session,
        agent_id=enrolled_agent.agent.id,
        source="telegram",
        session_key="session-without-occurred-at",
        occurred_at=None,
    )

    assert agent_session.started_at is not None


def test_hash_content_is_deterministic() -> None:
    assert hash_content("hello") == hash_content("hello")
    assert hash_content("hello") != hash_content("world")


def test_dump_json_is_stable_and_preserves_unicode() -> None:
    assert dump_json({"b": 2, "a": "한글"}) == '{"a":"한글","b":2}'
