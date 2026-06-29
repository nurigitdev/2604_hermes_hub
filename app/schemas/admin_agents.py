from datetime import datetime

from pydantic import BaseModel, EmailStr


class AdminAgentItem(BaseModel):
    agent_uid: str
    profile_name: str
    display_name: str | None
    owner_email: str | None
    hostname: str
    ip_addr: str
    source: str
    status: str
    last_seen_at: datetime | None


class AdminAgentSearchResponse(BaseModel):
    items: list[AdminAgentItem]
    total: int


class AdminAgentUpdateRequest(BaseModel):
    display_name: str | None = None


class AdminAgentMapRequest(BaseModel):
    owner_email: EmailStr
