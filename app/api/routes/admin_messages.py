from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.admin_messages import (
    AdminMessageDetailResponse,
    AdminMessageListItem,
    AdminMessageSearchResponse,
)
from app.services.admin_messages import (
    AdminMessageDetail,
    AdminMessageRow,
    content_preview,
    get_admin_message_detail,
    parse_raw_payload,
    search_admin_messages,
)

router = APIRouter(prefix="/admin/api/messages", tags=["admin"])

MESSAGE_NOT_FOUND_DETAIL = "Message not found"


@router.get("", response_model=AdminMessageSearchResponse)
def search_messages(
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    agent_uid: str | None = None,
    owner_email: str | None = None,
    source: str | None = None,
    role: str | None = None,
    event_type: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AdminMessageSearchResponse:
    result = search_admin_messages(
        session,
        date_from=date_from,
        date_to=date_to,
        agent_uid=agent_uid,
        owner_email=owner_email,
        source=source,
        role=role,
        event_type=event_type,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return AdminMessageSearchResponse(
        items=[admin_message_row_to_item(row) for row in result.items],
        total=result.total,
    )


@router.get("/{message_id}", response_model=AdminMessageDetailResponse)
def get_message_detail(
    message_id: int,
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AdminMessageDetailResponse:
    detail = get_admin_message_detail(session, message_id=message_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=MESSAGE_NOT_FOUND_DETAIL,
        )
    return admin_message_detail_to_response(detail)


def admin_message_row_to_item(row: AdminMessageRow) -> AdminMessageListItem:
    return AdminMessageListItem(
        id=row.message.id,
        occurred_at=row.message.occurred_at,
        agent_uid=row.agent.agent_uid,
        profile_name=row.agent.profile_name,
        owner_email=row.agent.owner_email,
        source=row.message.source,
        role=row.message.role,
        event_type=row.message.event_type,
        content_preview=content_preview(row.message.content),
    )


def admin_message_detail_to_response(detail: AdminMessageDetail) -> AdminMessageDetailResponse:
    return AdminMessageDetailResponse(
        id=detail.message.id,
        agent_uid=detail.agent.agent_uid,
        session_key=(
            detail.agent_session.hermes_session_id if detail.agent_session is not None else None
        ),
        request_id=detail.message.request_id,
        parent_message_id=detail.message.parent_message_id,
        role=detail.message.role,
        direction=detail.message.direction,
        content=detail.message.content,
        tool_calls_json=detail.message.tool_calls_json,
        raw_payload=parse_raw_payload(detail.message.raw_payload),
    )
