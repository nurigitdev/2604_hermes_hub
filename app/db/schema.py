from sqlalchemy.engine import Engine

from app import models as _models  # noqa: F401
from app.db.base import Base


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


def drop_schema(engine: Engine) -> None:
    Base.metadata.drop_all(bind=engine)
