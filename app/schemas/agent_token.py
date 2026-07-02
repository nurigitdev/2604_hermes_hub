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
