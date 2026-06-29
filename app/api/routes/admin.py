from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.admin import CurrentAdminResponse
from app.schemas.agent_token import AgentTokenCreateRequest, AgentTokenCreateResponse
from app.services.agent_tokens import issue_enrollment_token

router = APIRouter(prefix="/admin/api", tags=["admin"])


@router.get("/me", response_model=CurrentAdminResponse)
def get_me(current_admin: Annotated[User, Depends(get_current_admin)]) -> CurrentAdminResponse:
    return CurrentAdminResponse(
        id=current_admin.id,
        email=current_admin.email,
        name=current_admin.name,
        role=current_admin.role,
    )


@router.post("/agent-tokens", response_model=AgentTokenCreateResponse)
def create_agent_token(
    request: AgentTokenCreateRequest,
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AgentTokenCreateResponse:
    issued_token = issue_enrollment_token(
        session,
        owner_email=str(request.owner_email),
        expires_at=request.expires_at,
    )
    return AgentTokenCreateResponse(
        ok=True,
        token=issued_token.token,
        token_type=issued_token.record.token_type,
        owner_email=issued_token.record.owner_email,
        expires_at=request.expires_at,
    )
