from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import AGENT_FORBIDDEN_DETAIL, get_current_agent
from app.db.session import get_db_session
from app.schemas.events import EventIngestRequest, EventIngestResponse
from app.services.agents import AgentAccessForbiddenError, AuthenticatedAgent
from app.services.events import ingest_event

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("/ingest", response_model=EventIngestResponse)
def ingest(
    request: EventIngestRequest,
    current_agent: Annotated[AuthenticatedAgent, Depends(get_current_agent)],
    session: Annotated[Session, Depends(get_db_session)],
) -> EventIngestResponse:
    try:
        result = ingest_event(
            session,
            authenticated_agent=current_agent,
            agent_uid=request.agent_uid,
            event_type=request.event_type,
            severity=request.severity,
            summary=request.summary,
            occurred_at=request.occurred_at,
            raw_payload=request.raw_payload,
        )
    except AgentAccessForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AGENT_FORBIDDEN_DETAIL,
        ) from exc

    return EventIngestResponse(ok=True, event_id=result.event.id)
