from sqlalchemy.orm import Session

from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent
from app.services.admin_agents import (
    AdminAgentSearchResult,
    disable_admin_agent,
    get_agent_api_tokens,
    get_agent_by_uid,
    map_admin_agent,
    normalize_limit,
    search_admin_agents,
    update_admin_agent,
)
from app.services.agent_tokens import AGENT_ACTIVE_SCOPE, AGENT_UNMAPPED_SCOPE, API_TOKEN_TYPE


def make_agent(
    db_session: Session,
    *,
    agent_uid: str = "agent_20260629_0001",
    status: str = "UNMAPPED",
    owner_email: str | None = None,
    source: str = "gateway",
) -> HermesAgent:
    agent = HermesAgent(
        agent_uid=agent_uid,
        profile_name="kim-teamlead",
        display_name=None,
        owner_email=owner_email,
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source=source,
        status=status,
    )
    db_session.add(agent)
    db_session.flush()
    return agent


def make_api_token(
    db_session: Session,
    *,
    agent_id: int,
    scope: str = AGENT_UNMAPPED_SCOPE,
    owner_email: str | None = None,
) -> AgentToken:
    token = AgentToken(
        token_hash=f"hash-{agent_id}-{scope}",
        token_type=API_TOKEN_TYPE,
        scope=scope,
        owner_email=owner_email,
        agent_id=agent_id,
        is_active=True,
    )
    db_session.add(token)
    db_session.flush()
    return token


def test_search_admin_agents_returns_rows_and_total(db_session: Session) -> None:
    agent = make_agent(db_session)

    result = search_admin_agents(db_session, keyword="kim")

    assert result == AdminAgentSearchResult(items=[agent], total=1)


def test_search_admin_agents_filters_by_all_supported_values(db_session: Session) -> None:
    first = make_agent(
        db_session,
        status="ACTIVE",
        owner_email="agent.owner@example.com",
        source="gateway",
    )
    first.display_name = "Kim Team Lead Agent"
    make_agent(
        db_session,
        agent_uid="agent_20260629_0002",
        status="UNMAPPED",
        source="collector",
    )

    result = search_admin_agents(
        db_session,
        status="ACTIVE",
        owner_email="agent.owner@example.com",
        source="gateway",
        keyword="Team Lead",
    )

    assert result == AdminAgentSearchResult(items=[first], total=1)


def test_search_admin_agents_supports_offset(db_session: Session) -> None:
    first = make_agent(db_session, agent_uid="agent_20260629_0001")
    second = make_agent(db_session, agent_uid="agent_20260629_0002")

    result = search_admin_agents(db_session, limit=1, offset=1)

    assert result.total == 2
    assert result.items[0] in {first, second}


def test_get_agent_by_uid_returns_matching_agent(db_session: Session) -> None:
    agent = make_agent(db_session)

    assert get_agent_by_uid(db_session, agent_uid=agent.agent_uid) is agent


def test_get_agent_by_uid_returns_none_for_missing_agent(db_session: Session) -> None:
    assert get_agent_by_uid(db_session, agent_uid="agent_missing") is None


def test_update_admin_agent_updates_display_name(db_session: Session) -> None:
    agent = make_agent(db_session)

    updated = update_admin_agent(
        db_session,
        agent_uid=agent.agent_uid,
        display_name="Kim Team Lead Agent",
    )

    assert updated is agent
    assert agent.display_name == "Kim Team Lead Agent"


def test_update_admin_agent_allows_empty_patch(db_session: Session) -> None:
    agent = make_agent(db_session)

    updated = update_admin_agent(db_session, agent_uid=agent.agent_uid)

    assert updated is agent
    assert agent.display_name is None


def test_update_admin_agent_returns_none_for_missing_agent(db_session: Session) -> None:
    assert update_admin_agent(db_session, agent_uid="agent_missing") is None


def test_map_admin_agent_activates_agent_and_api_token(db_session: Session) -> None:
    agent = make_agent(db_session)
    token = make_api_token(db_session, agent_id=agent.id)

    mapped = map_admin_agent(
        db_session,
        agent_uid=agent.agent_uid,
        owner_email="agent.owner@example.com",
    )

    assert mapped is agent
    assert agent.status == "ACTIVE"
    assert agent.owner_email == "agent.owner@example.com"
    assert token.scope == AGENT_ACTIVE_SCOPE
    assert token.owner_email == "agent.owner@example.com"


def test_map_admin_agent_returns_none_for_missing_agent(db_session: Session) -> None:
    assert (
        map_admin_agent(
            db_session,
            agent_uid="agent_missing",
            owner_email="agent.owner@example.com",
        )
        is None
    )


def test_disable_admin_agent_sets_disabled_status(db_session: Session) -> None:
    agent = make_agent(db_session, status="ACTIVE", owner_email="agent.owner@example.com")

    disabled = disable_admin_agent(db_session, agent_uid=agent.agent_uid)

    assert disabled is agent
    assert agent.status == "DISABLED"


def test_disable_admin_agent_returns_none_for_missing_agent(db_session: Session) -> None:
    assert disable_admin_agent(db_session, agent_uid="agent_missing") is None


def test_get_agent_api_tokens_returns_only_api_tokens(db_session: Session) -> None:
    agent = make_agent(db_session)
    api_token = make_api_token(db_session, agent_id=agent.id)
    db_session.add(
        AgentToken(
            token_hash="enrollment-token",
            token_type="ENROLLMENT",
            scope="ENROLL_AGENT",
            owner_email="agent.owner@example.com",
            agent_id=agent.id,
            is_active=True,
        )
    )
    db_session.flush()

    assert get_agent_api_tokens(db_session, agent_id=agent.id) == [api_token]


def test_normalize_limit_uses_default_for_invalid_limit() -> None:
    assert normalize_limit(0) == 50


def test_normalize_limit_caps_large_limit() -> None:
    assert normalize_limit(999) == 200


def test_normalize_limit_keeps_valid_limit() -> None:
    assert normalize_limit(25) == 25
