from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_SESSION_COOKIE_NAME, Settings, get_settings
from app.core.session import verify_session_token
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth import get_active_admin_by_id

UNAUTHENTICATED_DETAIL = "Authentication required"


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
