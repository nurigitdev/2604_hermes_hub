from datetime import datetime

from pydantic import BaseModel


class AdminEventListItem(BaseModel):
    id: int
    occurred_at: datetime | None
    agent_uid: str
    event_type: str
    severity: str
    summary: str


class AdminEventSearchResponse(BaseModel):
    items: list[AdminEventListItem]
    total: int
