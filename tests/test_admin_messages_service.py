from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.hermes_agent import HermesAgent
from app.services.admin_messages import (
    AdminMessageDetail,
    AdminMessageRow,
    content_preview,
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
) -> AgentMessage:
    message = AgentMessage(
        agent_id=agent_id,
        session_id=session_id,
        external_message_id="external-1",
        idempotency_key="idempotency-1",
        direction="INBOUND",
        role="user",
        event_type="message",
        content=content,
        content_hash="content-hash",
        source="telegram",
        request_id="req-1",
        raw_payload='{"ok":true}',
        occurred_at=datetime(2026, 6, 25, 9, 30, tzinfo=UTC),
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


def test_get_admin_message_detail_returns_message_agent_and_session(db_session: Session) -> None:
    agent = make_agent(db_session)
    agent_session = make_session(db_session, agent_id=agent.id)
    message = make_message(db_session, agent_id=agent.id, session_id=agent_session.id)

    detail = get_admin_message_detail(db_session, message_id=message.id)

    assert detail == AdminMessageDetail(message=message, agent=agent, agent_session=agent_session)


def test_get_admin_message_detail_returns_none_for_missing_message(db_session: Session) -> None:
    assert get_admin_message_detail(db_session, message_id=999) is None


def test_get_admin_message_detail_allows_missing_session(db_session: Session) -> None:
    agent = make_agent(db_session)
    message = make_message(db_session, agent_id=agent.id, session_id=None)

    detail = get_admin_message_detail(db_session, message_id=message.id)

    assert detail == AdminMessageDetail(message=message, agent=agent, agent_session=None)


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
