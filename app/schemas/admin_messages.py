from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AdminMessageListItem(BaseModel):
    id: int
    occurred_at: datetime | None
    agent_uid: str
    profile_name: str
    owner_email: str | None
    source: str
    role: str
    event_type: str
    content_preview: str


class AdminMessageSearchResponse(BaseModel):
    items: list[AdminMessageListItem]
    total: int


class AdminMessageDetailResponse(BaseModel):
    id: int
    agent_uid: str
    session_key: str | None
    request_id: str | None
    parent_message_id: int | None
    role: str
    direction: str
    content: str
    tool_calls_json: str | None
    raw_payload: dict[str, Any]
