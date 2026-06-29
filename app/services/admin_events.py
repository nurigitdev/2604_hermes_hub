from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.models.hermes_agent import HermesAgent
from app.services.admin_messages import DEFAULT_MESSAGE_LIMIT, MAX_MESSAGE_LIMIT


@dataclass(frozen=True)
class AdminEventRow:
    event: AgentEvent
    agent: HermesAgent


@dataclass(frozen=True)
class AdminEventSearchResult:
    items: list[AdminEventRow]
    total: int


@dataclass(frozen=True)
class AdminEventDetail:
    event: AgentEvent
    agent: HermesAgent


def search_admin_events(
    session: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    agent_uid: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    keyword: str | None = None,
    limit: int = DEFAULT_MESSAGE_LIMIT,
    offset: int = 0,
) -> AdminEventSearchResult:
    normalized_limit = normalize_limit(limit)
    normalized_offset = max(offset, 0)
    base_statement = apply_event_filters(
        select(AgentEvent, HermesAgent).join(
            HermesAgent,
            AgentEvent.agent_id == HermesAgent.id,
        ),
        date_from=date_from,
        date_to=date_to,
        agent_uid=agent_uid,
        severity=severity,
        event_type=event_type,
        keyword=keyword,
    )
    count_statement = apply_event_filters(
        select(func.count()).select_from(AgentEvent).join(
            HermesAgent,
            AgentEvent.agent_id == HermesAgent.id,
        ),
        date_from=date_from,
        date_to=date_to,
        agent_uid=agent_uid,
        severity=severity,
        event_type=event_type,
        keyword=keyword,
    )

    rows = session.execute(
        base_statement.order_by(
            AgentEvent.occurred_at.desc().nullslast(),
            AgentEvent.id.desc(),
        )
        .limit(normalized_limit)
        .offset(normalized_offset)
    ).all()
    total = session.scalar(count_statement) or 0

    return AdminEventSearchResult(
        items=[AdminEventRow(event=row[0], agent=row[1]) for row in rows],
        total=total,
    )


def get_admin_event_detail(session: Session, *, event_id: int) -> AdminEventDetail | None:
    row = session.execute(
        select(AgentEvent, HermesAgent)
        .join(HermesAgent, AgentEvent.agent_id == HermesAgent.id)
        .where(AgentEvent.id == event_id)
    ).one_or_none()
    if row is None:
        return None

    return AdminEventDetail(event=row[0], agent=row[1])


def apply_event_filters(
    statement: Select,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    agent_uid: str | None,
    severity: str | None,
    event_type: str | None,
    keyword: str | None,
) -> Select:
    if date_from is not None:
        statement = statement.where(AgentEvent.occurred_at >= date_from)
    if date_to is not None:
        statement = statement.where(AgentEvent.occurred_at <= date_to)
    if agent_uid is not None:
        statement = statement.where(HermesAgent.agent_uid == agent_uid)
    if severity is not None:
        statement = statement.where(AgentEvent.severity == severity)
    if event_type is not None:
        statement = statement.where(AgentEvent.event_type == event_type)
    if keyword is not None:
        keyword_pattern = f"%{keyword}%"
        statement = statement.where(
            or_(
                AgentEvent.summary.like(keyword_pattern),
                AgentEvent.event_type.like(keyword_pattern),
            )
        )
    return statement


def normalize_limit(limit: int) -> int:
    if limit < 1:
        return DEFAULT_MESSAGE_LIMIT
    return min(limit, MAX_MESSAGE_LIMIT)
