from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageIngestRequest(BaseModel):
    agent_uid: str
    idempotency_key: str | None = None
    external_message_id: str | None = None
    event_type: str
    source: str
    session_key: str
    direction: str
    role: str
    content: str
    request_id: str | None = None
    parent_message_id: int | None = None
    occurred_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MessageIngestResponse(BaseModel):
    ok: bool
    message_id: int
    duplicate: bool
