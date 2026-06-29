from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.models.hermes_agent import HermesAgent
from app.services.admin_events import (
    AdminEventRow,
    normalize_limit,
    search_admin_events,
)


def make_agent(db_session: Session, *, agent_uid: str = "agent_20260629_0001") -> HermesAgent:
    agent = HermesAgent(
        agent_uid=agent_uid,
        profile_name="kim-teamlead",
        owner_email="agent.owner@example.com",
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
        status="ACTIVE",
    )
    db_session.add(agent)
    db_session.flush()
    return agent


def make_event(
    db_session: Session,
    *,
    agent_id: int,
    event_type: str = "agent:end",
    severity: str = "INFO",
    summary: str = "Agent response completed",
) -> AgentEvent:
    event = AgentEvent(
        agent_id=agent_id,
        event_type=event_type,
        severity=severity,
        summary=summary,
        raw_payload='{"ok":true}',
        occurred_at=datetime(2026, 6, 25, 9, 31, 15, tzinfo=UTC),
    )
    db_session.add(event)
    db_session.flush()
    return event


def test_search_admin_events_returns_rows_and_total(db_session: Session) -> None:
    agent = make_agent(db_session)
    event = make_event(db_session, agent_id=agent.id)

    result = search_admin_events(db_session, keyword="response")

    assert result.total == 1
    assert result.items == [AdminEventRow(event=event, agent=agent)]


def test_search_admin_events_filters_by_all_supported_values(db_session: Session) -> None:
    agent = make_agent(db_session)
    first = make_event(db_session, agent_id=agent.id, summary="alpha event")
    make_event(
        db_session,
        agent_id=agent.id,
        event_type="agent:error",
        severity="ERROR",
        summary="beta event",
    )

    result = search_admin_events(
        db_session,
        date_from=datetime(2026, 6, 25, tzinfo=UTC),
        date_to=datetime(2026, 6, 26, tzinfo=UTC),
        agent_uid=agent.agent_uid,
        severity="INFO",
        event_type="agent:end",
        keyword="alpha",
    )

    assert result.total == 1
    assert result.items == [AdminEventRow(event=first, agent=agent)]


def test_search_admin_events_supports_offset(db_session: Session) -> None:
    agent = make_agent(db_session)
    first = make_event(db_session, agent_id=agent.id, summary="first event")
    second = make_event(db_session, agent_id=agent.id, summary="second event")

    result = search_admin_events(db_session, limit=1, offset=1)

    assert result.total == 2
    assert result.items[0] in {
        AdminEventRow(event=first, agent=agent),
        AdminEventRow(event=second, agent=agent),
    }


def test_search_admin_events_matches_keyword_against_event_type(db_session: Session) -> None:
    agent = make_agent(db_session)
    event = make_event(db_session, agent_id=agent.id, event_type="agent:step", summary="plain")

    result = search_admin_events(db_session, keyword="step")

    assert result.total == 1
    assert result.items == [AdminEventRow(event=event, agent=agent)]


def test_normalize_limit_uses_default_for_invalid_limit() -> None:
    assert normalize_limit(0) == 50


def test_normalize_limit_caps_large_limit() -> None:
    assert normalize_limit(999) == 200


def test_normalize_limit_keeps_valid_limit() -> None:
    assert normalize_limit(25) == 25
