from datetime import datetime
from typing import Any, Literal

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
    message_type_code: int | None = Field(default=None, ge=1, le=4)
    message_type: Literal[
        "pre_llm_call",
        "post_llm_call",
        "pre_tool_call",
        "post_tool_call",
    ] | None = None
    content: str
    assistant_response: str | None = None
    request_id: str | None = None
    parent_message_id: int | None = None
    occurred_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class MessageIngestResponse(BaseModel):
    ok: bool
    message_id: int
    duplicate: bool
