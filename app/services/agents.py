from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import generate_agent_uid, generate_api_token, hash_token
from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent
from app.models.user import utc_now
from app.services.agent_tokens import (
    AGENT_ACTIVE_SCOPE,
    AGENT_UNMAPPED_SCOPE,
    API_TOKEN_TYPE,
    ENROLL_AGENT_SCOPE,
    ENROLLMENT_TOKEN_TYPE,
)

AGENT_ACTIVE_STATUS = "ACTIVE"
AGENT_UNMAPPED_STATUS = "UNMAPPED"


class InvalidEnrollmentTokenError(Exception):
    pass


@dataclass(frozen=True)
class EnrolledAgent:
    agent: HermesAgent
    api_token: str
    api_token_record: AgentToken


def enroll_agent(
    session: Session,
    *,
    enrollment_token: str | None,
    profile_name: str,
    hostname: str,
    ip_addr: str,
    source: str,
) -> EnrolledAgent:
    now = utc_now()
    enrollment_record: AgentToken | None = None
    owner_email: str | None = None
    status = AGENT_UNMAPPED_STATUS
    scope = AGENT_UNMAPPED_SCOPE

    if enrollment_token is not None:
        enrollment_record = get_usable_enrollment_token(
            session,
            token=enrollment_token,
            now=now,
        )
        owner_email = enrollment_record.owner_email
        status = AGENT_ACTIVE_STATUS
        scope = AGENT_ACTIVE_SCOPE

    agent = HermesAgent(
        agent_uid=generate_agent_uid(),
        profile_name=profile_name,
        owner_email=owner_email,
        hostname=hostname,
        ip_addr=ip_addr,
        source=source,
        status=status,
        last_seen_at=now,
    )
    session.add(agent)
    session.flush()

    api_token = generate_api_token()
    api_token_record = AgentToken(
        token_hash=hash_token(api_token),
        token_type=API_TOKEN_TYPE,
        scope=scope,
        owner_email=owner_email,
        agent_id=agent.id,
        is_active=True,
    )
    session.add(api_token_record)

    if enrollment_record is not None:
        enrollment_record.used_at = now
        enrollment_record.agent_id = agent.id

    session.commit()
    session.refresh(agent)
    session.refresh(api_token_record)
    return EnrolledAgent(agent=agent, api_token=api_token, api_token_record=api_token_record)


def get_usable_enrollment_token(
    session: Session,
    *,
    token: str,
    now: datetime | None = None,
) -> AgentToken:
    token_record = session.scalar(
        select(AgentToken).where(AgentToken.token_hash == hash_token(token))
    )
    if token_record is None:
        raise InvalidEnrollmentTokenError
    if token_record.token_type != ENROLLMENT_TOKEN_TYPE:
        raise InvalidEnrollmentTokenError
    if token_record.scope != ENROLL_AGENT_SCOPE:
        raise InvalidEnrollmentTokenError
    if token_record.owner_email is None:
        raise InvalidEnrollmentTokenError
    if not token_record.is_active:
        raise InvalidEnrollmentTokenError
    if token_record.used_at is not None:
        raise InvalidEnrollmentTokenError
    if is_expired(token_record.expires_at, now=now):
        raise InvalidEnrollmentTokenError
    return token_record


def is_expired(expires_at: datetime | None, *, now: datetime | None = None) -> bool:
    if expires_at is None:
        return False

    comparison_time = now or utc_now()
    normalized_expires_at = expires_at
    if normalized_expires_at.tzinfo is None:
        normalized_expires_at = normalized_expires_at.replace(tzinfo=UTC)

    return normalized_expires_at <= comparison_time
