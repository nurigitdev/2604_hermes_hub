from datetime import datetime

from pydantic import BaseModel


class AgentEnrollRequest(BaseModel):
    enrollment_token: str | None = None
    profile_name: str
    hostname: str
    ip_addr: str
    source: str


class AgentEnrollResponse(BaseModel):
    agent_uid: str
    api_token: str
    status: str
    scope: str


class AgentHeartbeatRequest(BaseModel):
    agent_uid: str
    profile_name: str
    source: str
    ip_addr: str
    runtime_status: str


class AgentHeartbeatResponse(BaseModel):
    ok: bool
    agent_uid: str
    last_seen_at: datetime
