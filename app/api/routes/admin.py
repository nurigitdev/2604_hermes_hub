from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_admin
from app.models.user import User
from app.schemas.admin import CurrentAdminResponse

router = APIRouter(prefix="/admin/api", tags=["admin"])


@router.get("/me", response_model=CurrentAdminResponse)
def get_me(current_admin: Annotated[User, Depends(get_current_admin)]) -> CurrentAdminResponse:
    return CurrentAdminResponse(
        id=current_admin.id,
        email=current_admin.email,
        name=current_admin.name,
        role=current_admin.role,
    )
