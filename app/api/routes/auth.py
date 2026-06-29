from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.session import create_session_token
from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import authenticate_admin

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_LOGIN_DETAIL = "Invalid email or password"


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    user = authenticate_admin(session, email=str(request.email), password=request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOGIN_DETAIL,
        )
    session_token = create_session_token(user_id=user.id, secret_key=settings.secret_key)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=settings.session_cookie_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.env == "production",
    )
    return LoginResponse(ok=True, role=user.role)
