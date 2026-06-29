from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.schema import create_schema, drop_schema
from app.db.session import create_engine_for_url, create_session_factory, get_db_session
from app.main import create_app


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "hermes_hub_test.sqlite3"


@pytest.fixture()
def test_database_url(tmp_db_path: Path) -> str:
    return f"sqlite:///{tmp_db_path}"


@pytest.fixture()
def test_engine(test_database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine_for_url(test_database_url)
    create_schema(engine)
    try:
        yield engine
    finally:
        drop_schema(engine)
        engine.dispose()


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    session_factory = create_session_factory(test_engine)
    with session_factory() as session:
        yield session


@pytest.fixture()
def test_app(db_session: Session):
    app = create_app()

    def override_get_db_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return app
