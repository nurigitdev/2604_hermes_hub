from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.models.agent_message import AgentMessage
from app.models.hermes_agent import HermesAgent
from app.services.admin_dashboard import (
    AdminDashboardSummary,
    get_admin_dashboard_summary,
    normalize_utc,
)
from app.services.agents import AGENT_ACTIVE_STATUS, AGENT_DISABLED_STATUS, AGENT_UNMAPPED_STATUS
from app.services.messages import hash_content


def make_agent(
    db_session: Session,
    *,
    agent_uid: str = "agent_20260629_0001",
    status: str = AGENT_ACTIVE_STATUS,
) -> HermesAgent:
    agent = HermesAgent(
        agent_uid=agent_uid,
        profile_name="kim-teamlead",
        owner_email="agent.owner@example.com",
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
        status=status,
    )
    db_session.add(agent)
    db_session.flush()
    return agent


def make_message(
    db_session: Session,
    *,
    agent_id: int,
    occurred_at: datetime | None,
    content: str = "dashboard message",
) -> AgentMessage:
    message = AgentMessage(
        agent_id=agent_id,
        session_id=None,
        external_message_id=None,
        idempotency_key=None,
        direction="INBOUND",
        role="user",
        event_type="message",
        content=content,
        content_hash=hash_content(content),
        source="telegram",
        request_id=None,
        raw_payload="{}",
        occurred_at=occurred_at,
    )
    db_session.add(message)
    db_session.flush()
    return message


def make_event(
    db_session: Session,
    *,
    agent_id: int,
    occurred_at: datetime | None,
    severity: str = "INFO",
) -> AgentEvent:
    event = AgentEvent(
        agent_id=agent_id,
        event_type="agent:end",
        severity=severity,
        summary="Agent response completed",
        raw_payload="{}",
        occurred_at=occurred_at,
    )
    db_session.add(event)
    db_session.flush()
    return event


def test_get_admin_dashboard_summary_counts_statuses_and_time_windows(
    db_session: Session,
) -> None:
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
    active = make_agent(db_session)
    make_agent(db_session, agent_uid="agent_20260629_0002", status=AGENT_UNMAPPED_STATUS)
    make_agent(db_session, agent_uid="agent_20260629_0003", status=AGENT_DISABLED_STATUS)
    make_message(db_session, agent_id=active.id, occurred_at=now - timedelta(hours=1))
    make_message(db_session, agent_id=active.id, occurred_at=now - timedelta(days=1))
    make_message(db_session, agent_id=active.id, occurred_at=None)
    make_event(db_session, agent_id=active.id, occurred_at=now - timedelta(hours=1))
    make_event(
        db_session,
        agent_id=active.id,
        occurred_at=now - timedelta(hours=2),
        severity="ERROR",
    )
    make_event(
        db_session,
        agent_id=active.id,
        occurred_at=now - timedelta(hours=25),
        severity="ERROR",
    )
    make_event(db_session, agent_id=active.id, occurred_at=now + timedelta(minutes=1))
    make_event(db_session, agent_id=active.id, occurred_at=None)

    summary = get_admin_dashboard_summary(db_session, now=now)

    assert summary == AdminDashboardSummary(
        total_agent_count=3,
        active_agent_count=1,
        unmapped_agent_count=1,
        messages_today_count=1,
        events_last_24h_count=2,
        error_events_last_24h_count=1,
    )


def test_get_admin_dashboard_summary_returns_zero_counts_for_empty_db(
    db_session: Session,
) -> None:
    summary = get_admin_dashboard_summary(
        db_session,
        now=datetime(2026, 6, 29, 12, 0, tzinfo=UTC),
    )

    assert summary == AdminDashboardSummary(
        total_agent_count=0,
        active_agent_count=0,
        unmapped_agent_count=0,
        messages_today_count=0,
        events_last_24h_count=0,
        error_events_last_24h_count=0,
    )


def test_normalize_utc_accepts_naive_datetime() -> None:
    assert normalize_utc(datetime(2026, 6, 29, 12, 0)) == datetime(
        2026,
        6,
        29,
        12,
        0,
        tzinfo=UTC,
    )


def test_normalize_utc_converts_aware_datetime_to_utc() -> None:
    kst = timezone(timedelta(hours=9))

    assert normalize_utc(datetime(2026, 6, 29, 21, 0, tzinfo=kst)) == datetime(
        2026,
        6,
        29,
        12,
        0,
        tzinfo=UTC,
    )
