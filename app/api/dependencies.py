from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_SESSION_COOKIE_NAME, Settings, get_settings
from app.core.session import verify_session_token
from app.db.session import get_db_session
from app.models.user import User
from app.services.agents import (
    AgentAccessForbiddenError,
    AuthenticatedAgent,
    InvalidAgentTokenError,
    authenticate_agent_api_token,
)
from app.services.auth import get_active_admin_by_id

UNAUTHENTICATED_DETAIL = "Authentication required"
AGENT_UNAUTHENTICATED_DETAIL = "Agent authentication required"
AGENT_FORBIDDEN_DETAIL = "Agent access forbidden"


def get_current_admin(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    session_token: Annotated[str | None, Cookie(alias=DEFAULT_SESSION_COOKIE_NAME)] = None,
) -> User:
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHENTICATED_DETAIL,
        )

    user_id = verify_session_token(session_token, secret_key=settings.secret_key)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHENTICATED_DETAIL,
        )

    user = get_active_admin_by_id(session, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=UNAUTHENTICATED_DETAIL,
        )

    return user


def get_current_agent(
    session: Annotated[Session, Depends(get_db_session)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthenticatedAgent:
    token = extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AGENT_UNAUTHENTICATED_DETAIL,
        )

    try:
        return authenticate_agent_api_token(session, token=token)
    except InvalidAgentTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AGENT_UNAUTHENTICATED_DETAIL,
        ) from exc
    except AgentAccessForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AGENT_FORBIDDEN_DETAIL,
        ) from exc


def extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    scheme, separator, token = authorization.partition(" ")
    if separator == "":
        return None
    if scheme.lower() != "bearer":
        return None

    stripped_token = token.strip()
    if stripped_token == "":
        return None
    return stripped_token
