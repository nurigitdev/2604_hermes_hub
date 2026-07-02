from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.tokens import generate_api_token, generate_enrollment_token, hash_token
from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent

ENROLLMENT_TOKEN_TYPE = "ENROLLMENT"
API_TOKEN_TYPE = "API"
ENROLL_AGENT_SCOPE = "ENROLL_AGENT"
AGENT_ACTIVE_SCOPE = "AGENT_ACTIVE"
AGENT_UNMAPPED_SCOPE = "AGENT_UNMAPPED"
ADMIN_ISSUED_AGENT_STATUS = "ACTIVE"
ADMIN_ISSUED_AGENT_HOSTNAME = "admin-issued"
ADMIN_ISSUED_AGENT_IP_ADDR = "0.0.0.0"
ADMIN_ISSUED_AGENT_SOURCE = "admin"


@dataclass(frozen=True)
class IssuedAgentToken:
    token: str
    record: AgentToken


@dataclass(frozen=True)
class AgentApiTokenRow:
    token: AgentToken
    agent_uid: str | None
    agent_status: str | None


@dataclass(frozen=True)
class AgentApiTokenList:
    items: list[AgentApiTokenRow]
    total: int


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


def issue_agent_api_token(
    session: Session,
    *,
    owner_email: str,
    expires_at: datetime | None = None,
) -> IssuedAgentToken:
    normalized_owner_email = owner_email.strip().lower()
    agent = get_or_create_email_agent(session, owner_email=normalized_owner_email)
    token = generate_api_token()
    record = AgentToken(
        token_hash=hash_token(token),
        token_type=API_TOKEN_TYPE,
        scope=AGENT_ACTIVE_SCOPE,
        owner_email=normalized_owner_email,
        agent_id=agent.id,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return IssuedAgentToken(token=token, record=record)


def get_or_create_email_agent(session: Session, *, owner_email: str) -> HermesAgent:
    agent = session.scalar(select(HermesAgent).where(HermesAgent.agent_uid == owner_email))
    if agent is None:
        agent = HermesAgent(
            agent_uid=owner_email,
            profile_name=owner_email,
            display_name=owner_email,
            owner_email=owner_email,
            hostname=ADMIN_ISSUED_AGENT_HOSTNAME,
            ip_addr=ADMIN_ISSUED_AGENT_IP_ADDR,
            source=ADMIN_ISSUED_AGENT_SOURCE,
            status=ADMIN_ISSUED_AGENT_STATUS,
        )
        session.add(agent)
        session.flush()
        return agent

    agent.owner_email = owner_email
    agent.status = ADMIN_ISSUED_AGENT_STATUS
    if not agent.display_name:
        agent.display_name = owner_email
    return agent


def list_agent_api_tokens(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> AgentApiTokenList:
    normalized_limit = min(max(limit, 1), 200)
    normalized_offset = max(offset, 0)

    statement = (
        select(AgentToken, HermesAgent.agent_uid, HermesAgent.status)
        .outerjoin(HermesAgent, AgentToken.agent_id == HermesAgent.id)
        .where(AgentToken.token_type == API_TOKEN_TYPE)
        .order_by(AgentToken.created_at.desc(), AgentToken.id.desc())
        .limit(normalized_limit)
        .offset(normalized_offset)
    )
    rows = [
        AgentApiTokenRow(token=token, agent_uid=agent_uid, agent_status=agent_status)
        for token, agent_uid, agent_status in session.execute(statement).all()
    ]
    total = (
        session.scalar(
            select(func.count())
            .select_from(AgentToken)
            .where(AgentToken.token_type == API_TOKEN_TYPE)
        )
        or 0
    )
    return AgentApiTokenList(items=rows, total=total)
