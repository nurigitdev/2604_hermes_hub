from pathlib import Path

from app.core.config import Settings, sqlite_file_path


def test_settings_defaults_are_development_safe() -> None:
    settings = Settings()

    assert settings.env == "development"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.test_database_url.startswith("sqlite:///")
    assert settings.session_cookie_name == "hermes_hub_session"
    assert settings.session_cookie_max_age_seconds == 86_400
    assert settings.admin_email == "admin@company.com"
    assert settings.admin_name == "Hub Admin"
    assert settings.admin_password == "change-me-admin-password"


def test_sqlite_file_path_returns_path_for_file_database() -> None:
    assert sqlite_file_path("sqlite:///./data/hermes_hub.sqlite3") == Path(
        "./data/hermes_hub.sqlite3"
    )


def test_sqlite_file_path_ignores_memory_database() -> None:
    assert sqlite_file_path("sqlite:///:memory:") is None


def test_sqlite_file_path_ignores_non_sqlite_database() -> None:
    assert sqlite_file_path("postgresql://user:password@localhost/hermes_hub") is None
