from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models.user import User


def seed_admin_user(session: Session, settings: Settings) -> User:
    existing_user = session.scalar(select(User).where(User.email == str(settings.admin_email)))
    if existing_user is not None:
        return existing_user

    admin_user = User(
        email=str(settings.admin_email),
        name=settings.admin_name,
        role="ADMIN",
        password_hash=hash_password(settings.admin_password),
        is_active=True,
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)
    return admin_user
