import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.message_types import normalize_message_type_code
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.user import utc_now
from app.services.agent_tokens import AGENT_ACTIVE_SCOPE
from app.services.agents import AGENT_ACTIVE_STATUS, AgentAccessForbiddenError, AuthenticatedAgent


@dataclass(frozen=True)
class MessageIngestResult:
    message: AgentMessage
    duplicate: bool


def ingest_message(
    session: Session,
    *,
    authenticated_agent: AuthenticatedAgent,
    agent_uid: str,
    idempotency_key: str | None,
    external_message_id: str | None,
    event_type: str,
    source: str,
    session_key: str,
    direction: str,
    role: str,
    content: str,
    request_id: str | None,
    occurred_at: datetime | None,
    raw_payload: dict[str, Any],
    message_type_code: int | None = None,
    message_type: str | None = None,
    assistant_response: str | None = None,
    parent_message_id: int | None = None,
) -> MessageIngestResult:
    ensure_message_ingest_allowed(authenticated_agent, agent_uid=agent_uid)

    duplicate_message = find_duplicate_message(
        session,
        agent_id=authenticated_agent.agent.id,
        source=source,
        idempotency_key=idempotency_key,
        external_message_id=external_message_id,
    )
    if duplicate_message is not None:
        return MessageIngestResult(message=duplicate_message, duplicate=True)

    agent_session = get_or_create_agent_session(
        session,
        agent_id=authenticated_agent.agent.id,
        source=source,
        session_key=session_key,
        occurred_at=occurred_at,
    )
    normalized_message_type_code = normalize_message_type_code(
        message_type_code=message_type_code,
        message_type=message_type,
        event_type=event_type,
        role=role,
        direction=direction,
    )
    message = AgentMessage(
        agent_id=authenticated_agent.agent.id,
        session_id=agent_session.id,
        external_message_id=external_message_id,
        idempotency_key=idempotency_key,
        direction=direction,
        role=role,
        event_type=event_type,
        message_type_code=normalized_message_type_code,
        content=content,
        assistant_response=assistant_response,
        content_hash=hash_content(content),
        source=source,
        request_id=request_id,
        parent_message_id=parent_message_id,
        raw_payload=dump_json(raw_payload),
        occurred_at=occurred_at,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    return MessageIngestResult(message=message, duplicate=False)


def ensure_message_ingest_allowed(
    authenticated_agent: AuthenticatedAgent,
    *,
    agent_uid: str,
) -> None:
    if authenticated_agent.agent.agent_uid != agent_uid:
        raise AgentAccessForbiddenError
    if authenticated_agent.agent.status != AGENT_ACTIVE_STATUS:
        raise AgentAccessForbiddenError
    if authenticated_agent.token_record.scope != AGENT_ACTIVE_SCOPE:
        raise AgentAccessForbiddenError


def find_duplicate_message(
    session: Session,
    *,
    agent_id: int,
    source: str,
    idempotency_key: str | None,
    external_message_id: str | None,
) -> AgentMessage | None:
    if idempotency_key is not None:
        message = session.scalar(
            select(AgentMessage).where(
                AgentMessage.agent_id == agent_id,
                AgentMessage.idempotency_key == idempotency_key,
            )
        )
        if message is not None:
            return message

    if external_message_id is not None:
        return session.scalar(
            select(AgentMessage).where(
                AgentMessage.agent_id == agent_id,
                AgentMessage.source == source,
                AgentMessage.external_message_id == external_message_id,
            )
        )

    return None


def get_or_create_agent_session(
    session: Session,
    *,
    agent_id: int,
    source: str,
    session_key: str,
    occurred_at: datetime | None,
) -> AgentSession:
    agent_session = session.scalar(
        select(AgentSession).where(
            AgentSession.agent_id == agent_id,
            AgentSession.source == source,
            AgentSession.hermes_session_id == session_key,
        )
    )
    if agent_session is not None:
        return agent_session

    agent_session = AgentSession(
        agent_id=agent_id,
        source=source,
        hermes_session_id=session_key,
        started_at=occurred_at or utc_now(),
        raw_payload="{}",
    )
    session.add(agent_session)
    session.flush()
    return agent_session


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def dump_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
