from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import app.db.session as session_module
from app.db.session import (
    create_engine_for_url,
    create_session_factory,
    ensure_sqlite_parent_directory,
    get_db_session,
)


def test_test_database_engine_uses_tmp_sqlite_file(
    test_engine: Engine,
    tmp_db_path: Path,
) -> None:
    with test_engine.connect() as connection:
        assert connection.execute(text("select 1")).scalar_one() == 1

    assert tmp_db_path.exists()


def test_db_session_executes_sql(db_session: Session) -> None:
    assert db_session.execute(text("select 1")).scalar_one() == 1


def test_get_db_session_yields_configured_session(
    monkeypatch,
    test_engine: Engine,
) -> None:
    monkeypatch.setattr(session_module, "SessionLocal", create_session_factory(test_engine))
    session_generator = get_db_session()

    session = next(session_generator)

    try:
        assert session.execute(text("select 1")).scalar_one() == 1
    finally:
        session_generator.close()


def test_sqlite_parent_directory_is_created(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "hermes_hub.sqlite3"
    engine = create_engine_for_url(f"sqlite:///{db_path}")

    try:
        with engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar_one() == 1
        assert db_path.exists()
    finally:
        engine.dispose()


def test_ensure_sqlite_parent_directory_ignores_non_file_database() -> None:
    ensure_sqlite_parent_directory("sqlite:///:memory:")
