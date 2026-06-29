from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db_session
from app.models.hermes_agent import HermesAgent
from app.models.user import User
from app.schemas.admin_agents import (
    AdminAgentItem,
    AdminAgentMapRequest,
    AdminAgentSearchResponse,
    AdminAgentUpdateRequest,
)
from app.services.admin_agents import (
    DEFAULT_AGENT_LIMIT,
    disable_admin_agent,
    map_admin_agent,
    search_admin_agents,
    update_admin_agent,
)

router = APIRouter(prefix="/admin/api/agents", tags=["admin"])

AGENT_NOT_FOUND_DETAIL = "Agent not found"


@router.get("", response_model=AdminAgentSearchResponse)
def search_agents(
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
    status: str | None = None,
    owner_email: str | None = None,
    source: str | None = None,
    keyword: str | None = None,
    limit: int = DEFAULT_AGENT_LIMIT,
    offset: int = 0,
) -> AdminAgentSearchResponse:
    result = search_admin_agents(
        session,
        status=status,
        owner_email=owner_email,
        source=source,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return AdminAgentSearchResponse(
        items=[admin_agent_to_item(agent) for agent in result.items],
        total=result.total,
    )


@router.patch("/{agent_uid}", response_model=AdminAgentItem)
def update_agent(
    agent_uid: str,
    request: AdminAgentUpdateRequest,
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AdminAgentItem:
    agent = update_admin_agent(
        session,
        agent_uid=agent_uid,
        display_name=request.display_name,
    )
    if agent is None:
        raise_agent_not_found()
    return admin_agent_to_item(agent)


@router.post("/{agent_uid}/map", response_model=AdminAgentItem)
def map_agent(
    agent_uid: str,
    request: AdminAgentMapRequest,
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AdminAgentItem:
    agent = map_admin_agent(session, agent_uid=agent_uid, owner_email=str(request.owner_email))
    if agent is None:
        raise_agent_not_found()
    return admin_agent_to_item(agent)


@router.post("/{agent_uid}/disable", response_model=AdminAgentItem)
def disable_agent(
    agent_uid: str,
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AdminAgentItem:
    agent = disable_admin_agent(session, agent_uid=agent_uid)
    if agent is None:
        raise_agent_not_found()
    return admin_agent_to_item(agent)


def admin_agent_to_item(agent: HermesAgent) -> AdminAgentItem:
    return AdminAgentItem(
        agent_uid=agent.agent_uid,
        profile_name=agent.profile_name,
        display_name=agent.display_name,
        owner_email=agent.owner_email,
        hostname=agent.hostname,
        ip_addr=agent.ip_addr,
        source=agent.source,
        status=agent.status,
        last_seen_at=agent.last_seen_at,
    )


def raise_agent_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=AGENT_NOT_FOUND_DETAIL,
    )
