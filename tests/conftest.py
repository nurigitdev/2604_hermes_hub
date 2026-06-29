from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.session import create_engine_for_url, create_session_factory


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "hermes_hub_test.sqlite3"


@pytest.fixture()
def test_database_url(tmp_db_path: Path) -> str:
    return f"sqlite:///{tmp_db_path}"


@pytest.fixture()
def test_engine(test_database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine_for_url(test_database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    session_factory = create_session_factory(test_engine)
    with session_factory() as session:
        yield session
