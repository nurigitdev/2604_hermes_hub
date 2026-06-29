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
