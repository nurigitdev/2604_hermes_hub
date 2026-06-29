from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    env: str = "development"
    database_url: str = "sqlite:///./data/hermes_hub.sqlite3"
    test_database_url: str = "sqlite:///./tests/tmp/hermes_hub_test.sqlite3"
    secret_key: str = Field(default="change-me-in-local-env", min_length=8)
    admin_email: EmailStr = "admin@company.com"
    admin_name: str = "Hub Admin"
    admin_password: str = Field(default="change-me-admin-password", min_length=12)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HERMES_HUB_",
        extra="ignore",
    )


def sqlite_file_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None
    if not url.database or url.database == ":memory:":
        return None
    return Path(url.database)


@lru_cache
def get_settings() -> Settings:
    return Settings()
