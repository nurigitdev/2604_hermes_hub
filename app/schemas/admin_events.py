from datetime import datetime
from typing import Any

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


class AdminEventDetailResponse(BaseModel):
    id: int
    occurred_at: datetime | None
    agent_uid: str
    profile_name: str
    owner_email: str | None
    event_type: str
    severity: str
    summary: str
    raw_payload: dict[str, Any]
