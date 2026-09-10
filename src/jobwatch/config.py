"""Application settings, loaded from environment variables and an optional .env file."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://jobwatch:jobwatch@localhost:5432/jobwatch"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    poll_interval_seconds: int = 3600
    request_timeout_seconds: float = 30.0

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Managed platforms (Railway, Heroku) hand out postgres:// URLs;
        # SQLAlchemy 2.x needs an explicit dialect+driver scheme.
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)
