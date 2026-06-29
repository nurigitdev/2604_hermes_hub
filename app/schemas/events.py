from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventIngestRequest(BaseModel):
    agent_uid: str
    event_type: str
    severity: str
    summary: str
    occurred_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class EventIngestResponse(BaseModel):
    ok: bool
    event_id: int
