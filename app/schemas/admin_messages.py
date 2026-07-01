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
    message_type_code: int
    message_type: str
    content_preview: str


class AdminMessageSearchResponse(BaseModel):
    items: list[AdminMessageListItem]
    total: int


class AdminMessageRelatedItem(BaseModel):
    id: int
    occurred_at: datetime | None
    request_id: str | None
    parent_message_id: int | None
    role: str
    direction: str
    event_type: str
    message_type_code: int
    message_type: str
    content_preview: str


class AdminMessageDetailResponse(BaseModel):
    id: int
    agent_uid: str
    session_key: str | None
    request_id: str | None
    parent_message_id: int | None
    role: str
    direction: str
    message_type_code: int
    message_type: str
    content: str
    assistant_response: str | None
    tool_calls_json: str | None
    raw_payload: dict[str, Any]
    related_messages: list[AdminMessageRelatedItem]
