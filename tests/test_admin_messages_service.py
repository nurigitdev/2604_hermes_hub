from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.hermes_agent import HermesAgent
from app.services.admin_messages import (
    AdminMessageDetail,
    AdminMessageRow,
    content_preview,
    find_related_messages,
    get_admin_message_detail,
    normalize_limit,
    parse_raw_payload,
    search_admin_messages,
)


def make_agent(
    db_session: Session,
    *,
    agent_uid: str = "agent_20260629_0001",
    owner_email: str | None = "agent.owner@example.com",
) -> HermesAgent:
    agent = HermesAgent(
        agent_uid=agent_uid,
        profile_name="kim-teamlead",
        owner_email=owner_email,
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
        status="ACTIVE",
    )
    db_session.add(agent)
    db_session.flush()
    return agent


def make_session(db_session: Session, *, agent_id: int) -> AgentSession:
    agent_session = AgentSession(
        agent_id=agent_id,
        hermes_session_id="agent:main:telegram:private:123456789",
        source="telegram",
        raw_payload="{}",
    )
    db_session.add(agent_session)
    db_session.flush()
    return agent_session


def make_message(
    db_session: Session,
    *,
    agent_id: int,
    session_id: int | None,
    content: str = "hello message",
    external_message_id: str = "external-1",
    idempotency_key: str = "idempotency-1",
    request_id: str | None = "req-1",
    parent_message_id: int | None = None,
    role: str = "user",
    direction: str = "INBOUND",
    message_type_code: int | None = None,
    assistant_response: str | None = None,
    occurred_at: datetime | None = datetime(2026, 6, 25, 9, 30, tzinfo=UTC),
) -> AgentMessage:
    message = AgentMessage(
        agent_id=agent_id,
        session_id=session_id,
        external_message_id=external_message_id,
        idempotency_key=idempotency_key,
        direction=direction,
        role=role,
        event_type="message",
        message_type_code=message_type_code or 1,
        content=content,
        assistant_response=assistant_response,
        content_hash="content-hash",
        source="telegram",
        request_id=request_id,
        parent_message_id=parent_message_id,
        raw_payload='{"ok":true}',
        occurred_at=occurred_at,
    )
    db_session.add(message)
    db_session.flush()
    return message


def test_search_admin_messages_returns_rows_and_total(db_session: Session) -> None:
    agent = make_agent(db_session)
    agent_session = make_session(db_session, agent_id=agent.id)
    message = make_message(db_session, agent_id=agent.id, session_id=agent_session.id)

    result = search_admin_messages(db_session, keyword="hello")

    assert result.total == 1
    assert result.items == [AdminMessageRow(message=message, agent=agent)]


def test_search_admin_messages_filters_by_message_type(db_session: Session) -> None:
    agent = make_agent(db_session)
    agent_session = make_session(db_session, agent_id=agent.id)
    make_message(
        db_session,
        agent_id=agent.id,
        session_id=agent_session.id,
        message_type_code=1,
    )
    post_llm_message = make_message(
        db_session,
        agent_id=agent.id,
        session_id=agent_session.id,
        external_message_id="external-2",
        idempotency_key="idempotency-2",
        message_type_code=2,
        role="assistant",
        direction="OUTBOUND",
    )

    result = search_admin_messages(db_session, message_type="post_llm_call")

    assert result.total == 1
    assert result.items == [AdminMessageRow(message=post_llm_message, agent=agent)]


def test_search_admin_messages_matches_assistant_response_keyword(db_session: Session) -> None:
    agent = make_agent(db_session)
    agent_session = make_session(db_session, agent_id=agent.id)
    message = make_message(
        db_session,
        agent_id=agent.id,
        session_id=agent_session.id,
        role="assistant",
        direction="OUTBOUND",
        message_type_code=2,
        assistant_response="alpha assistant answer",
    )

    result = search_admin_messages(db_session, keyword="assistant answer")

    assert result.total == 1
    assert result.items == [AdminMessageRow(message=message, agent=agent)]


def test_get_admin_message_detail_returns_message_agent_and_session(db_session: Session) -> None:
    agent = make_agent(db_session)
    agent_session = make_session(db_session, agent_id=agent.id)
    message = make_message(db_session, agent_id=agent.id, session_id=agent_session.id)

    detail = get_admin_message_detail(db_session, message_id=message.id)

    assert detail == AdminMessageDetail(
        message=message,
        agent=agent,
        agent_session=agent_session,
        related_messages=[],
    )


def test_get_admin_message_detail_returns_none_for_missing_message(db_session: Session) -> None:
    assert get_admin_message_detail(db_session, message_id=999) is None


def test_get_admin_message_detail_allows_missing_session(db_session: Session) -> None:
    agent = make_agent(db_session)
    message = make_message(db_session, agent_id=agent.id, session_id=None)

    detail = get_admin_message_detail(db_session, message_id=message.id)

    assert detail == AdminMessageDetail(
        message=message,
        agent=agent,
        agent_session=None,
        related_messages=[],
    )


def test_get_admin_message_detail_includes_related_messages(db_session: Session) -> None:
    agent = make_agent(db_session)
    other_agent = make_agent(db_session, agent_uid="agent_20260629_0002")
    agent_session = make_session(db_session, agent_id=agent.id)
    message = make_message(db_session, agent_id=agent.id, session_id=agent_session.id)
    by_request_id = make_message(
        db_session,
        agent_id=agent.id,
        session_id=agent_session.id,
        content="assistant response",
        external_message_id="external-2",
        idempotency_key="idempotency-2",
        role="assistant",
        direction="OUTBOUND",
        occurred_at=datetime(2026, 6, 25, 9, 31, tzinfo=UTC),
    )
    by_parent_id = make_message(
        db_session,
        agent_id=agent.id,
        session_id=agent_session.id,
        content="child response",
        external_message_id="external-3",
        idempotency_key="idempotency-3",
        request_id=None,
        parent_message_id=message.id,
        role="assistant",
        direction="OUTBOUND",
        occurred_at=datetime(2026, 6, 25, 9, 32, tzinfo=UTC),
    )
    make_message(
        db_session,
        agent_id=other_agent.id,
        session_id=None,
        external_message_id="external-4",
        idempotency_key="idempotency-4",
    )

    detail = get_admin_message_detail(db_session, message_id=message.id)

    assert detail == AdminMessageDetail(
        message=message,
        agent=agent,
        agent_session=agent_session,
        related_messages=[by_request_id, by_parent_id],
    )


def test_find_related_messages_can_resolve_parent_message(db_session: Session) -> None:
    agent = make_agent(db_session)
    parent = make_message(
        db_session,
        agent_id=agent.id,
        session_id=None,
        external_message_id="external-parent",
        idempotency_key="idempotency-parent",
        request_id=None,
    )
    child = make_message(
        db_session,
        agent_id=agent.id,
        session_id=None,
        external_message_id="external-child",
        idempotency_key="idempotency-child",
        request_id=None,
        parent_message_id=parent.id,
    )

    assert find_related_messages(db_session, message=child) == [parent]


def test_normalize_limit_uses_default_for_invalid_limit() -> None:
    assert normalize_limit(0) == 50


def test_normalize_limit_caps_large_limit() -> None:
    assert normalize_limit(999) == 200


def test_normalize_limit_keeps_valid_limit() -> None:
    assert normalize_limit(25) == 25


def test_content_preview_keeps_short_content() -> None:
    assert content_preview("short", max_length=10) == "short"


def test_content_preview_truncates_long_content() -> None:
    assert content_preview("abcdefghijklmnop", max_length=10) == "abcdefg..."


def test_parse_raw_payload_returns_object() -> None:
    assert parse_raw_payload('{"ok": true}') == {"ok": True}


def test_parse_raw_payload_wraps_non_object_json() -> None:
    assert parse_raw_payload("[1, 2]") == {"value": [1, 2]}


def test_parse_raw_payload_wraps_invalid_json() -> None:
    assert parse_raw_payload("not-json") == {"_raw": "not-json"}
