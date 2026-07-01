import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.message_types import message_type_name, normalize_message_type_code
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.hermes_agent import HermesAgent

DEFAULT_MESSAGE_LIMIT = 50
MAX_MESSAGE_LIMIT = 200
CONTENT_PREVIEW_LENGTH = 120


@dataclass(frozen=True)
class AdminMessageRow:
    message: AgentMessage
    agent: HermesAgent


@dataclass(frozen=True)
class AdminMessageSearchResult:
    items: list[AdminMessageRow]
    total: int


@dataclass(frozen=True)
class AdminMessageDetail:
    message: AgentMessage
    agent: HermesAgent
    agent_session: AgentSession | None
    related_messages: list[AgentMessage]


def search_admin_messages(
    session: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    agent_uid: str | None = None,
    owner_email: str | None = None,
    source: str | None = None,
    role: str | None = None,
    event_type: str | None = None,
    message_type: str | None = None,
    message_type_code: int | None = None,
    keyword: str | None = None,
    limit: int = DEFAULT_MESSAGE_LIMIT,
    offset: int = 0,
) -> AdminMessageSearchResult:
    normalized_limit = normalize_limit(limit)
    normalized_offset = max(offset, 0)
    base_statement = apply_message_filters(
        select(AgentMessage, HermesAgent).join(
            HermesAgent,
            AgentMessage.agent_id == HermesAgent.id,
        ),
        date_from=date_from,
        date_to=date_to,
        agent_uid=agent_uid,
        owner_email=owner_email,
        source=source,
        role=role,
        event_type=event_type,
        message_type=message_type,
        message_type_code=message_type_code,
        keyword=keyword,
    )
    count_statement = apply_message_filters(
        select(func.count()).select_from(AgentMessage).join(
            HermesAgent,
            AgentMessage.agent_id == HermesAgent.id,
        ),
        date_from=date_from,
        date_to=date_to,
        agent_uid=agent_uid,
        owner_email=owner_email,
        source=source,
        role=role,
        event_type=event_type,
        message_type=message_type,
        message_type_code=message_type_code,
        keyword=keyword,
    )

    rows = session.execute(
        base_statement.order_by(
            AgentMessage.occurred_at.desc().nullslast(),
            AgentMessage.id.desc(),
        )
        .limit(normalized_limit)
        .offset(normalized_offset)
    ).all()
    total = session.scalar(count_statement) or 0

    return AdminMessageSearchResult(
        items=[AdminMessageRow(message=row[0], agent=row[1]) for row in rows],
        total=total,
    )


def get_admin_message_detail(session: Session, *, message_id: int) -> AdminMessageDetail | None:
    row = session.execute(
        select(AgentMessage, HermesAgent, AgentSession)
        .join(HermesAgent, AgentMessage.agent_id == HermesAgent.id)
        .outerjoin(AgentSession, AgentMessage.session_id == AgentSession.id)
        .where(AgentMessage.id == message_id)
    ).one_or_none()
    if row is None:
        return None

    message = row[0]
    return AdminMessageDetail(
        message=message,
        agent=row[1],
        agent_session=row[2],
        related_messages=find_related_messages(session, message=message),
    )


def find_related_messages(session: Session, *, message: AgentMessage) -> list[AgentMessage]:
    conditions = []
    if message.request_id is not None:
        conditions.append(AgentMessage.request_id == message.request_id)
    if message.parent_message_id is not None:
        conditions.append(AgentMessage.id == message.parent_message_id)
    conditions.append(AgentMessage.parent_message_id == message.id)

    rows = session.scalars(
        select(AgentMessage)
        .where(
            AgentMessage.agent_id == message.agent_id,
            AgentMessage.id != message.id,
            or_(*conditions),
        )
        .order_by(
            AgentMessage.occurred_at.asc().nullslast(),
            AgentMessage.id.asc(),
        )
    ).all()
    return list(rows)


def apply_message_filters(
    statement: Select,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    agent_uid: str | None,
    owner_email: str | None,
    source: str | None,
    role: str | None,
    event_type: str | None,
    message_type: str | None,
    message_type_code: int | None,
    keyword: str | None,
) -> Select:
    if date_from is not None:
        statement = statement.where(AgentMessage.occurred_at >= date_from)
    if date_to is not None:
        statement = statement.where(AgentMessage.occurred_at <= date_to)
    if agent_uid is not None:
        statement = statement.where(HermesAgent.agent_uid == agent_uid)
    if owner_email is not None:
        statement = statement.where(HermesAgent.owner_email == owner_email)
    if source is not None:
        statement = statement.where(AgentMessage.source == source)
    if role is not None:
        statement = statement.where(AgentMessage.role == role)
    if event_type is not None:
        statement = statement.where(AgentMessage.event_type == event_type)
    if message_type is not None or message_type_code is not None:
        statement = statement.where(
            AgentMessage.message_type_code
            == normalize_message_type_code(
                message_type=message_type,
                message_type_code=message_type_code,
            )
        )
    if keyword is not None:
        keyword_pattern = f"%{keyword}%"
        statement = statement.where(
            or_(
                AgentMessage.content.like(keyword_pattern),
                AgentMessage.assistant_response.like(keyword_pattern),
                AgentMessage.event_type.like(keyword_pattern),
            )
        )
    return statement


def normalize_limit(limit: int) -> int:
    if limit < 1:
        return DEFAULT_MESSAGE_LIMIT
    return min(limit, MAX_MESSAGE_LIMIT)


def content_preview(content: str, *, max_length: int = CONTENT_PREVIEW_LENGTH) -> str:
    if len(content) <= max_length:
        return content
    return f"{content[: max_length - 3]}..."


def parse_raw_payload(raw_payload: str) -> dict[str, Any]:
    try:
        value = json.loads(raw_payload)
    except json.JSONDecodeError:
        return {"_raw": raw_payload}

    if isinstance(value, dict):
        return value
    return {"value": value}


def agent_message_type_name(message: AgentMessage) -> str:
    return message_type_name(message.message_type_code)
