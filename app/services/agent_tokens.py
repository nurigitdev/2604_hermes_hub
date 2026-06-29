from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.tokens import generate_enrollment_token, hash_token
from app.models.agent_token import AgentToken

ENROLLMENT_TOKEN_TYPE = "ENROLLMENT"
ENROLL_AGENT_SCOPE = "ENROLL_AGENT"


@dataclass(frozen=True)
class IssuedAgentToken:
    token: str
    record: AgentToken


def issue_enrollment_token(
    session: Session,
    *,
    owner_email: str,
    expires_at: datetime | None = None,
) -> IssuedAgentToken:
    token = generate_enrollment_token()
    record = AgentToken(
        token_hash=hash_token(token),
        token_type=ENROLLMENT_TOKEN_TYPE,
        scope=ENROLL_AGENT_SCOPE,
        owner_email=owner_email,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return IssuedAgentToken(token=token, record=record)
