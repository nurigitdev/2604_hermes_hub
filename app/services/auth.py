from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User


def authenticate_admin(session: Session, *, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        return None
    if not user.is_active:
        return None
    if user.role != "ADMIN":
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
