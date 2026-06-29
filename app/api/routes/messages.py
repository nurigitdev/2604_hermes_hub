from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import AGENT_FORBIDDEN_DETAIL, get_current_agent
from app.db.session import get_db_session
from app.schemas.messages import MessageIngestRequest, MessageIngestResponse
from app.services.agents import AgentAccessForbiddenError, AuthenticatedAgent
from app.services.messages import ingest_message

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


@router.post("/ingest", response_model=MessageIngestResponse)
def ingest(
    request: MessageIngestRequest,
    current_agent: Annotated[AuthenticatedAgent, Depends(get_current_agent)],
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> MessageIngestResponse:
    try:
        result = ingest_message(
            session,
            authenticated_agent=current_agent,
            agent_uid=request.agent_uid,
            idempotency_key=idempotency_key_header or request.idempotency_key,
            external_message_id=request.external_message_id,
            event_type=request.event_type,
            source=request.source,
            session_key=request.session_key,
            direction=request.direction,
            role=request.role,
            content=request.content,
            request_id=request.request_id,
            occurred_at=request.occurred_at,
            raw_payload=request.raw_payload,
        )
    except AgentAccessForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AGENT_FORBIDDEN_DETAIL,
        ) from exc

    return MessageIngestResponse(
        ok=True,
        message_id=result.message.id,
        duplicate=result.duplicate,
    )
