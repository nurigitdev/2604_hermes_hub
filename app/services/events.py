from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_event import AgentEvent
from app.services.agent_tokens import AGENT_ACTIVE_SCOPE
from app.services.agents import AGENT_ACTIVE_STATUS, AgentAccessForbiddenError, AuthenticatedAgent
from app.services.messages import dump_json


@dataclass(frozen=True)
class EventIngestResult:
    event: AgentEvent


def ingest_event(
    session: Session,
    *,
    authenticated_agent: AuthenticatedAgent,
    agent_uid: str,
    event_type: str,
    severity: str,
    summary: str,
    occurred_at: datetime | None,
    raw_payload: dict[str, Any],
) -> EventIngestResult:
    ensure_event_ingest_allowed(authenticated_agent, agent_uid=agent_uid)

    event = AgentEvent(
        agent_id=authenticated_agent.agent.id,
        event_type=event_type,
        severity=severity,
        summary=summary,
        raw_payload=dump_json(raw_payload),
        occurred_at=occurred_at,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return EventIngestResult(event=event)


def ensure_event_ingest_allowed(
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
