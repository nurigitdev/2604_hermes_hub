from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import authenticate_admin

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_LOGIN_DETAIL = "Invalid email or password"


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> LoginResponse:
    user = authenticate_admin(session, email=str(request.email), password=request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_LOGIN_DETAIL,
        )
    return LoginResponse(ok=True, role=user.role)
