from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.agents import AgentEnrollRequest, AgentEnrollResponse
from app.services.agents import InvalidEnrollmentTokenError, enroll_agent

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
