from pydantic import BaseModel


class AdminDashboardSummaryResponse(BaseModel):
    total_agent_count: int
    active_agent_count: int
    unmapped_agent_count: int
    messages_today_count: int
    events_last_24h_count: int
    error_events_last_24h_count: int
