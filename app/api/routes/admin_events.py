from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.admin_events import (
    AdminEventDetailResponse,
    AdminEventListItem,
    AdminEventSearchResponse,
)
from app.services.admin_events import (
    AdminEventDetail,
    AdminEventRow,
    get_admin_event_detail,
    search_admin_events,
)
from app.services.admin_messages import parse_raw_payload

router = APIRouter(prefix="/admin/api/events", tags=["admin"])

EVENT_NOT_FOUND_DETAIL = "Event not found"


@router.get("", response_model=AdminEventSearchResponse)
def search_events(
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    agent_uid: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AdminEventSearchResponse:
    result = search_admin_events(
        session,
        date_from=date_from,
        date_to=date_to,
        agent_uid=agent_uid,
        severity=severity,
        event_type=event_type,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return AdminEventSearchResponse(
        items=[admin_event_row_to_item(row) for row in result.items],
        total=result.total,
    )


@router.get("/{event_id}", response_model=AdminEventDetailResponse)
def get_event_detail(
    event_id: int,
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AdminEventDetailResponse:
    detail = get_admin_event_detail(session, event_id=event_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=EVENT_NOT_FOUND_DETAIL,
        )
    return admin_event_detail_to_response(detail)


def admin_event_row_to_item(row: AdminEventRow) -> AdminEventListItem:
    return AdminEventListItem(
        id=row.event.id,
        occurred_at=row.event.occurred_at,
        agent_uid=row.agent.agent_uid,
        event_type=row.event.event_type,
        severity=row.event.severity,
        summary=row.event.summary,
    )


def admin_event_detail_to_response(detail: AdminEventDetail) -> AdminEventDetailResponse:
    return AdminEventDetailResponse(
        id=detail.event.id,
        occurred_at=detail.event.occurred_at,
        agent_uid=detail.agent.agent_uid,
        profile_name=detail.agent.profile_name,
        owner_email=detail.agent.owner_email,
        event_type=detail.event.event_type,
        severity=detail.event.severity,
        summary=detail.event.summary,
        raw_payload=parse_raw_payload(detail.event.raw_payload),
    )
