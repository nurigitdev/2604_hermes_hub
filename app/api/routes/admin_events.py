from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.admin_events import AdminEventListItem, AdminEventSearchResponse
from app.services.admin_events import AdminEventRow, search_admin_events

router = APIRouter(prefix="/admin/api/events", tags=["admin"])


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


def admin_event_row_to_item(row: AdminEventRow) -> AdminEventListItem:
    return AdminEventListItem(
        id=row.event.id,
        occurred_at=row.event.occurred_at,
        agent_uid=row.agent.agent_uid,
        event_type=row.event.event_type,
        severity=row.event.severity,
        summary=row.event.summary,
    )
