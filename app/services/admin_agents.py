from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent
from app.services.agent_tokens import AGENT_ACTIVE_SCOPE, API_TOKEN_TYPE
from app.services.agents import AGENT_ACTIVE_STATUS, AGENT_DISABLED_STATUS

DEFAULT_AGENT_LIMIT = 50
MAX_AGENT_LIMIT = 200


@dataclass(frozen=True)
class AdminAgentSearchResult:
    items: list[HermesAgent]
    total: int


def search_admin_agents(
    session: Session,
    *,
    status: str | None = None,
    owner_email: str | None = None,
    source: str | None = None,
    keyword: str | None = None,
    limit: int = DEFAULT_AGENT_LIMIT,
    offset: int = 0,
) -> AdminAgentSearchResult:
    normalized_limit = normalize_limit(limit)
    normalized_offset = max(offset, 0)
    base_statement = apply_agent_filters(
        select(HermesAgent),
        status=status,
        owner_email=owner_email,
        source=source,
        keyword=keyword,
    )
    count_statement = apply_agent_filters(
        select(func.count()).select_from(HermesAgent),
        status=status,
        owner_email=owner_email,
        source=source,
        keyword=keyword,
    )

    items = session.scalars(
        base_statement.order_by(
            HermesAgent.last_seen_at.desc().nullslast(),
            HermesAgent.id.desc(),
        )
        .limit(normalized_limit)
        .offset(normalized_offset)
    ).all()
    total = session.scalar(count_statement) or 0
    return AdminAgentSearchResult(items=list(items), total=total)


def update_admin_agent(
    session: Session,
    *,
    agent_uid: str,
    display_name: str | None = None,
) -> HermesAgent | None:
    agent = get_agent_by_uid(session, agent_uid=agent_uid)
    if agent is None:
        return None

    if display_name is not None:
        agent.display_name = display_name

    session.commit()
    session.refresh(agent)
    return agent


def map_admin_agent(session: Session, *, agent_uid: str, owner_email: str) -> HermesAgent | None:
    agent = get_agent_by_uid(session, agent_uid=agent_uid)
    if agent is None:
        return None

    agent.owner_email = owner_email
    agent.status = AGENT_ACTIVE_STATUS
    for token in get_agent_api_tokens(session, agent_id=agent.id):
        token.owner_email = owner_email
        token.scope = AGENT_ACTIVE_SCOPE

    session.commit()
    session.refresh(agent)
    return agent


def disable_admin_agent(session: Session, *, agent_uid: str) -> HermesAgent | None:
    agent = get_agent_by_uid(session, agent_uid=agent_uid)
    if agent is None:
        return None

    agent.status = AGENT_DISABLED_STATUS
    session.commit()
    session.refresh(agent)
    return agent


def get_agent_by_uid(session: Session, *, agent_uid: str) -> HermesAgent | None:
    return session.scalar(select(HermesAgent).where(HermesAgent.agent_uid == agent_uid))


def get_agent_api_tokens(session: Session, *, agent_id: int) -> list[AgentToken]:
    return list(
        session.scalars(
            select(AgentToken).where(
                AgentToken.agent_id == agent_id,
                AgentToken.token_type == API_TOKEN_TYPE,
            )
        ).all()
    )


def apply_agent_filters(
    statement: Select,
    *,
    status: str | None,
    owner_email: str | None,
    source: str | None,
    keyword: str | None,
) -> Select:
    if status is not None:
        statement = statement.where(HermesAgent.status == status)
    if owner_email is not None:
        statement = statement.where(HermesAgent.owner_email == owner_email)
    if source is not None:
        statement = statement.where(HermesAgent.source == source)
    if keyword is not None:
        keyword_pattern = f"%{keyword}%"
        statement = statement.where(
            or_(
                HermesAgent.agent_uid.like(keyword_pattern),
                HermesAgent.profile_name.like(keyword_pattern),
                HermesAgent.display_name.like(keyword_pattern),
                HermesAgent.hostname.like(keyword_pattern),
                HermesAgent.ip_addr.like(keyword_pattern),
            )
        )
    return statement


def normalize_limit(limit: int) -> int:
    if limit < 1:
        return DEFAULT_AGENT_LIMIT
    return min(limit, MAX_AGENT_LIMIT)
