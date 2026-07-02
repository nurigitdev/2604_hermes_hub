from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.admin import CurrentAdminResponse
from app.schemas.agent_token import (
    AgentTokenCreateRequest,
    AgentTokenCreateResponse,
    AgentTokenListItem,
    AgentTokenListResponse,
)
from app.services.agent_tokens import AgentApiTokenRow, issue_agent_api_token, list_agent_api_tokens

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
    issued_token = issue_agent_api_token(
        session,
        owner_email=str(request.owner_email),
        expires_at=request.expires_at,
    )
    return AgentTokenCreateResponse(
        ok=True,
        agent_uid=issued_token.record.owner_email,
        token=issued_token.token,
        token_type=issued_token.record.token_type,
        owner_email=issued_token.record.owner_email,
        expires_at=request.expires_at,
    )


@router.get("/agent-tokens", response_model=AgentTokenListResponse)
def list_agent_tokens(
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = 50,
    offset: int = 0,
) -> AgentTokenListResponse:
    result = list_agent_api_tokens(session, limit=limit, offset=offset)
    return AgentTokenListResponse(
        items=[agent_token_row_to_item(row) for row in result.items],
        total=result.total,
    )


def agent_token_row_to_item(row: AgentApiTokenRow) -> AgentTokenListItem:
    token = row.token
    return AgentTokenListItem(
        id=token.id,
        agent_uid=row.agent_uid,
        owner_email=token.owner_email,
        token_type=token.token_type,
        scope=token.scope,
        agent_status=row.agent_status,
        is_active=token.is_active,
        expires_at=token.expires_at,
        created_at=token.created_at,
    )
