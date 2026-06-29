from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tokens import ENROLLMENT_TOKEN_PREFIX, hash_token
from app.models.agent_token import AgentToken
from app.services.agent_tokens import (
    ENROLL_AGENT_SCOPE,
    ENROLLMENT_TOKEN_TYPE,
    issue_enrollment_token,
)


def test_issue_enrollment_token_creates_hashed_token_record(db_session: Session) -> None:
    expires_at = datetime(2026, 7, 25, 23, 59, 59, tzinfo=UTC)

    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
        expires_at=expires_at,
    )

    assert issued_token.token.startswith(ENROLLMENT_TOKEN_PREFIX)
    assert issued_token.record.id is not None
    assert issued_token.record.token_hash == hash_token(issued_token.token)
    assert issued_token.token not in issued_token.record.token_hash
    assert issued_token.record.token_type == ENROLLMENT_TOKEN_TYPE
    assert issued_token.record.scope == ENROLL_AGENT_SCOPE
    assert issued_token.record.owner_email == "agent.owner@example.com"
    assert issued_token.record.expires_at == expires_at.replace(tzinfo=None)
    assert issued_token.record.used_at is None
    assert issued_token.record.agent_id is None
    assert issued_token.record.is_active is True


def test_issue_enrollment_token_persists_record(db_session: Session) -> None:
    issued_token = issue_enrollment_token(
        db_session,
        owner_email="agent.owner@example.com",
    )

    record = db_session.scalar(
        select(AgentToken).where(AgentToken.token_hash == hash_token(issued_token.token))
    )

    assert record is not None
    assert record.owner_email == "agent.owner@example.com"
