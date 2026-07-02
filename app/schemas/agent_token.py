from datetime import datetime

from pydantic import BaseModel, EmailStr


class AgentTokenCreateRequest(BaseModel):
    owner_email: EmailStr
    expires_at: datetime | None = None


class AgentTokenCreateResponse(BaseModel):
    ok: bool
    agent_uid: str
    token: str
    token_type: str
    owner_email: EmailStr
    expires_at: datetime | None


class AgentTokenListItem(BaseModel):
    id: int
    agent_uid: str | None
    owner_email: EmailStr | None
    token_type: str
    scope: str
    agent_status: str | None
    is_active: bool
    expires_at: datetime | None
    created_at: datetime


class AgentTokenListResponse(BaseModel):
    items: list[AgentTokenListItem]
    total: int
