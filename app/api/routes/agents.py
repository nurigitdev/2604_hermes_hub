from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import AGENT_FORBIDDEN_DETAIL, get_current_agent
from app.db.session import get_db_session
from app.schemas.agents import (
    AgentEnrollRequest,
    AgentEnrollResponse,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
)
from app.services.agents import (
    AgentAccessForbiddenError,
    AuthenticatedAgent,
    InvalidEnrollmentTokenError,
    enroll_agent,
    record_agent_heartbeat,
)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

INVALID_ENROLLMENT_TOKEN_DETAIL = "Invalid enrollment token"


@router.post("/enroll", response_model=AgentEnrollResponse)
def enroll(
    request: AgentEnrollRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentEnrollResponse:
    try:
        enrolled_agent = enroll_agent(
            session,
            enrollment_token=request.enrollment_token,
            profile_name=request.profile_name,
            hostname=request.hostname,
            ip_addr=request.ip_addr,
            source=request.source,
        )
    except InvalidEnrollmentTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_ENROLLMENT_TOKEN_DETAIL,
        ) from exc

    return AgentEnrollResponse(
        agent_uid=enrolled_agent.agent.agent_uid,
        api_token=enrolled_agent.api_token,
        status=enrolled_agent.agent.status,
        scope=enrolled_agent.api_token_record.scope,
    )


@router.post("/heartbeat", response_model=AgentHeartbeatResponse)
def heartbeat(
    request: AgentHeartbeatRequest,
    current_agent: Annotated[AuthenticatedAgent, Depends(get_current_agent)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentHeartbeatResponse:
    try:
        heartbeat_result = record_agent_heartbeat(
            session,
            authenticated_agent=current_agent,
            agent_uid=request.agent_uid,
            profile_name=request.profile_name,
            source=request.source,
            ip_addr=request.ip_addr,
            runtime_status=request.runtime_status,
        )
    except AgentAccessForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AGENT_FORBIDDEN_DETAIL,
        ) from exc

    return AgentHeartbeatResponse(
        ok=True,
        agent_uid=heartbeat_result.agent.agent_uid,
        last_seen_at=heartbeat_result.last_seen_at,
    )
