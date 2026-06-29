from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.models.agent_message import AgentMessage
from app.models.hermes_agent import HermesAgent
from app.models.user import utc_now
from app.services.agents import AGENT_ACTIVE_STATUS, AGENT_UNMAPPED_STATUS

ERROR_EVENT_SEVERITY = "ERROR"


@dataclass(frozen=True)
class AdminDashboardSummary:
    total_agent_count: int
    active_agent_count: int
    unmapped_agent_count: int
    messages_today_count: int
    events_last_24h_count: int
    error_events_last_24h_count: int


def get_admin_dashboard_summary(
    session: Session,
    *,
    now: datetime | None = None,
) -> AdminDashboardSummary:
    comparison_time = normalize_utc(now or utc_now())
    today_start = datetime.combine(comparison_time.date(), time.min, tzinfo=UTC)
    tomorrow_start = today_start + timedelta(days=1)
    recent_start = comparison_time - timedelta(hours=24)

    return AdminDashboardSummary(
        total_agent_count=count_rows(session, select(func.count()).select_from(HermesAgent)),
        active_agent_count=count_rows(
            session,
            select(func.count())
            .select_from(HermesAgent)
            .where(HermesAgent.status == AGENT_ACTIVE_STATUS),
        ),
        unmapped_agent_count=count_rows(
            session,
            select(func.count())
            .select_from(HermesAgent)
            .where(HermesAgent.status == AGENT_UNMAPPED_STATUS),
        ),
        messages_today_count=count_rows(
            session,
            select(func.count())
            .select_from(AgentMessage)
            .where(
                AgentMessage.occurred_at >= today_start,
                AgentMessage.occurred_at < tomorrow_start,
            ),
        ),
        events_last_24h_count=count_rows(
            session,
            select(func.count())
            .select_from(AgentEvent)
            .where(
                AgentEvent.occurred_at >= recent_start,
                AgentEvent.occurred_at <= comparison_time,
            ),
        ),
        error_events_last_24h_count=count_rows(
            session,
            select(func.count())
            .select_from(AgentEvent)
            .where(
                AgentEvent.occurred_at >= recent_start,
                AgentEvent.occurred_at <= comparison_time,
                AgentEvent.severity == ERROR_EVENT_SEVERITY,
            ),
        ),
    )


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def count_rows(session: Session, statement: Select) -> int:
    return session.scalar(statement) or 0
