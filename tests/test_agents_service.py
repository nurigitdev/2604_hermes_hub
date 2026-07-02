from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import API_TOKEN_PREFIX, hash_token
from app.models.agent_token import AgentToken
from app.models.hermes_agent import HermesAgent
from app.services.agent_tokens import (
    AGENT_ACTIVE_SCOPE,
    AGENT_UNMAPPED_SCOPE,
    API_TOKEN_TYPE,
    ENROLL_AGENT_SCOPE,
    ENROLLMENT_TOKEN_TYPE,
    issue_enrollment_token,
)
from app.services.agents import (
    AGENT_ACTIVE_STATUS,
    AGENT_DISABLED_STATUS,
    AGENT_UNMAPPED_STATUS,
    AgentAccessForbiddenError,
    InvalidAgentTokenError,
    InvalidEnrollmentTokenError,
    authenticate_agent_api_token,
    enroll_agent,
    get_usable_enrollment_token,
    is_expired,
    record_agent_heartbeat,
)


def test_enroll_agent_with_enrollment_token_creates_active_agent(
    db_session: Session,
) -> None:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )

    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=issued_token.token,
        profile_name="kim-teamlead",
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
    )

    db_session.refresh(issued_token.record)

    assert enrolled_agent.api_token.startswith(API_TOKEN_PREFIX)
    assert enrolled_agent.agent.agent_uid.startswith("agent_")
    assert enrolled_agent.agent.profile_name == "kim-teamlead"
    assert enrolled_agent.agent.owner_email == "agent.owner@example.com"
    assert enrolled_agent.agent.hostname == "KIM-PC"
    assert enrolled_agent.agent.ip_addr == "192.168.0.25"
    assert enrolled_agent.agent.source == "gateway"
    assert enrolled_agent.agent.status == AGENT_ACTIVE_STATUS
    assert enrolled_agent.agent.last_seen_at is not None
    assert enrolled_agent.api_token_record.token_hash == hash_token(enrolled_agent.api_token)
    assert enrolled_agent.api_token_record.token_hash != enrolled_agent.api_token
    assert enrolled_agent.api_token_record.token_type == API_TOKEN_TYPE
    assert enrolled_agent.api_token_record.scope == AGENT_ACTIVE_SCOPE
    assert enrolled_agent.api_token_record.owner_email == "agent.owner@example.com"
    assert enrolled_agent.api_token_record.agent_id == enrolled_agent.agent.id
    assert issued_token.record.used_at is not None
    assert issued_token.record.agent_id == enrolled_agent.agent.id


def test_enroll_agent_without_enrollment_token_creates_unmapped_agent(
    db_session: Session,
) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )

    assert enrolled_agent.api_token.startswith(API_TOKEN_PREFIX)
    assert enrolled_agent.agent.owner_email is None
    assert enrolled_agent.agent.status == AGENT_UNMAPPED_STATUS
    assert enrolled_agent.api_token_record.scope == AGENT_UNMAPPED_SCOPE
    assert enrolled_agent.api_token_record.owner_email is None
    assert enrolled_agent.api_token_record.agent_id == enrolled_agent.agent.id


def test_enroll_agent_rejects_unknown_enrollment_token(db_session: Session) -> None:
    with pytest.raises(InvalidEnrollmentTokenError):
        enroll_agent(
            db_session,
            enrollment_token="wps_enroll_missing",
            profile_name="kim-teamlead",
            hostname="KIM-PC",
            ip_addr="192.168.0.25",
            source="gateway",
        )

    assert db_session.scalars(select(HermesAgent)).all() == []


def test_get_usable_enrollment_token_accepts_future_token(db_session: Session) -> None:
    token = "wps_enroll_future"
    record = AgentToken(
        token_hash=hash_token(token),
        token_type=ENROLLMENT_TOKEN_TYPE,
        scope=ENROLL_AGENT_SCOPE,
        owner_email="agent.owner@example.com",
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        is_active=True,
    )
    db_session.add(record)
    db_session.flush()

    found = get_usable_enrollment_token(
        db_session,
        token=token,
        now=datetime(2026, 6, 29, tzinfo=UTC),
    )

    assert found is record


def test_get_usable_enrollment_token_rejects_api_token(db_session: Session) -> None:
    token = "hub_api_example"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=API_TOKEN_TYPE,
            scope=AGENT_ACTIVE_SCOPE,
            owner_email="agent.owner@example.com",
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidEnrollmentTokenError):
        get_usable_enrollment_token(db_session, token=token)


def test_get_usable_enrollment_token_rejects_wrong_scope(db_session: Session) -> None:
    token = "wps_enroll_wrong_scope"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=ENROLLMENT_TOKEN_TYPE,
            scope=AGENT_ACTIVE_SCOPE,
            owner_email="agent.owner@example.com",
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidEnrollmentTokenError):
        get_usable_enrollment_token(db_session, token=token)


def test_get_usable_enrollment_token_rejects_missing_owner_email(db_session: Session) -> None:
    token = "wps_enroll_missing_owner"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=ENROLLMENT_TOKEN_TYPE,
            scope=ENROLL_AGENT_SCOPE,
            owner_email=None,
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidEnrollmentTokenError):
        get_usable_enrollment_token(db_session, token=token)


def test_get_usable_enrollment_token_rejects_inactive_token(db_session: Session) -> None:
    token = "wps_enroll_inactive"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=ENROLLMENT_TOKEN_TYPE,
            scope=ENROLL_AGENT_SCOPE,
            owner_email="agent.owner@example.com",
            is_active=False,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidEnrollmentTokenError):
        get_usable_enrollment_token(db_session, token=token)


def test_get_usable_enrollment_token_rejects_used_token(db_session: Session) -> None:
    token = "wps_enroll_used"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=ENROLLMENT_TOKEN_TYPE,
            scope=ENROLL_AGENT_SCOPE,
            owner_email="agent.owner@example.com",
            used_at=datetime(2026, 6, 29, tzinfo=UTC),
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidEnrollmentTokenError):
        get_usable_enrollment_token(db_session, token=token)


def test_get_usable_enrollment_token_rejects_expired_token(db_session: Session) -> None:
    token = "wps_enroll_expired"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=ENROLLMENT_TOKEN_TYPE,
            scope=ENROLL_AGENT_SCOPE,
            owner_email="agent.owner@example.com",
            expires_at=datetime(2026, 6, 28),
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidEnrollmentTokenError):
        get_usable_enrollment_token(
            db_session,
            token=token,
            now=datetime(2026, 6, 29, tzinfo=UTC),
        )


def test_is_expired_handles_none_future_and_past_values() -> None:
    now = datetime(2026, 6, 29, tzinfo=UTC)

    assert is_expired(None, now=now) is False
    assert is_expired(datetime(2026, 6, 30, tzinfo=UTC), now=now) is False
    assert is_expired(datetime(2026, 6, 28), now=now) is True
    assert is_expired(datetime.now(UTC) - timedelta(days=1)) is True


def test_authenticate_agent_api_token_accepts_active_agent(db_session: Session) -> None:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=issued_token.token,
        profile_name="kim-teamlead",
        hostname="KIM-PC",
        ip_addr="192.168.0.25",
        source="gateway",
    )

    authenticated_agent = authenticate_agent_api_token(
        db_session,
        token=enrolled_agent.api_token,
    )

    assert authenticated_agent.agent.id == enrolled_agent.agent.id
    assert authenticated_agent.token_record.id == enrolled_agent.api_token_record.id


def test_authenticate_agent_api_token_accepts_unmapped_agent(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )

    authenticated_agent = authenticate_agent_api_token(
        db_session,
        token=enrolled_agent.api_token,
    )

    assert authenticated_agent.agent.status == AGENT_UNMAPPED_STATUS
    assert authenticated_agent.token_record.scope == AGENT_UNMAPPED_SCOPE


def test_authenticate_agent_api_token_rejects_unknown_token(db_session: Session) -> None:
    with pytest.raises(InvalidAgentTokenError):
        authenticate_agent_api_token(db_session, token="hub_api_missing")


def test_authenticate_agent_api_token_rejects_enrollment_token(db_session: Session) -> None:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )

    with pytest.raises(InvalidAgentTokenError):
        authenticate_agent_api_token(db_session, token=issued_token.token)


def test_authenticate_agent_api_token_rejects_inactive_api_token(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )
    enrolled_agent.api_token_record.is_active = False
    db_session.flush()

    with pytest.raises(InvalidAgentTokenError):
        authenticate_agent_api_token(db_session, token=enrolled_agent.api_token)


def test_authenticate_agent_api_token_rejects_expired_api_token(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )
    enrolled_agent.api_token_record.expires_at = datetime(2026, 6, 28)
    db_session.flush()

    with pytest.raises(InvalidAgentTokenError):
        authenticate_agent_api_token(db_session, token=enrolled_agent.api_token)


def test_authenticate_agent_api_token_rejects_missing_agent_id(db_session: Session) -> None:
    token = "hub_api_without_agent"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=API_TOKEN_TYPE,
            scope=AGENT_ACTIVE_SCOPE,
            owner_email="agent.owner@example.com",
            agent_id=None,
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidAgentTokenError):
        authenticate_agent_api_token(db_session, token=token)


def test_authenticate_agent_api_token_rejects_missing_agent(db_session: Session) -> None:
    token = "hub_api_missing_agent"
    db_session.add(
        AgentToken(
            token_hash=hash_token(token),
            token_type=API_TOKEN_TYPE,
            scope=AGENT_ACTIVE_SCOPE,
            owner_email="agent.owner@example.com",
            agent_id=999,
            is_active=True,
        )
    )
    db_session.flush()

    with pytest.raises(InvalidAgentTokenError):
        authenticate_agent_api_token(db_session, token=token)


def test_authenticate_agent_api_token_rejects_forbidden_scope(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )
    enrolled_agent.api_token_record.scope = ENROLL_AGENT_SCOPE
    db_session.flush()

    with pytest.raises(AgentAccessForbiddenError):
        authenticate_agent_api_token(db_session, token=enrolled_agent.api_token)


def test_authenticate_agent_api_token_rejects_disabled_agent(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )
    enrolled_agent.agent.status = AGENT_DISABLED_STATUS
    db_session.flush()

    with pytest.raises(AgentAccessForbiddenError):
        authenticate_agent_api_token(db_session, token=enrolled_agent.api_token)


def test_record_agent_heartbeat_updates_agent_snapshot(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )
    authenticated_agent = authenticate_agent_api_token(
        db_session,
        token=enrolled_agent.api_token,
    )

    heartbeat = record_agent_heartbeat(
        db_session,
        authenticated_agent=authenticated_agent,
        agent_uid=enrolled_agent.agent.agent_uid,
        profile_name="kim-teamlead",
        source="gateway",
        ip_addr="192.168.0.25",
        runtime_status="running",
    )

    assert heartbeat.agent.profile_name == "kim-teamlead"
    assert heartbeat.agent.source == "gateway"
    assert heartbeat.agent.ip_addr == "192.168.0.25"
    assert heartbeat.agent.last_heartbeat_status == "running"
    assert heartbeat.agent.last_seen_at is not None
    assert heartbeat.last_seen_at.tzinfo is not None


def test_record_agent_heartbeat_rejects_agent_uid_mismatch(db_session: Session) -> None:
    enrolled_agent = enroll_agent(
        db_session,
        enrollment_token=None,
        profile_name="unknown-profile",
        hostname="UNKNOWN-PC",
        ip_addr="192.168.0.26",
        source="collector",
    )
    authenticated_agent = authenticate_agent_api_token(
        db_session,
        token=enrolled_agent.api_token,
    )

    with pytest.raises(AgentAccessForbiddenError):
        record_agent_heartbeat(
            db_session,
            authenticated_agent=authenticated_agent,
            agent_uid="agent_wrong",
            profile_name="kim-teamlead",
            source="gateway",
            ip_addr="192.168.0.25",
            runtime_status="running",
        )
