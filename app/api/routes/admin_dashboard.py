from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.admin_dashboard import AdminDashboardSummaryResponse
from app.services.admin_dashboard import AdminDashboardSummary, get_admin_dashboard_summary

router = APIRouter(prefix="/admin/api/dashboard", tags=["admin"])


@router.get("/summary", response_model=AdminDashboardSummaryResponse)
def get_dashboard_summary(
    _current_admin: Annotated[User, Depends(get_current_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AdminDashboardSummaryResponse:
    return admin_dashboard_summary_to_response(get_admin_dashboard_summary(session))


def admin_dashboard_summary_to_response(
    summary: AdminDashboardSummary,
) -> AdminDashboardSummaryResponse:
    return AdminDashboardSummaryResponse(
        total_agent_count=summary.total_agent_count,
        active_agent_count=summary.active_agent_count,
        unmapped_agent_count=summary.unmapped_agent_count,
        messages_today_count=summary.messages_today_count,
        events_last_24h_count=summary.events_last_24h_count,
        error_events_last_24h_count=summary.error_events_last_24h_count,
    )
