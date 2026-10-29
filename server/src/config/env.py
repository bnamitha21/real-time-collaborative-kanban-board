from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    FLASK_ENV: Literal["development", "test", "production"] = "development"
    PORT: int = Field(default=4000)
    CLIENT_ORIGIN: str = Field(default="http://localhost:5173")
    DATABASE_URL: str = Field(default="postgresql://kanban_app:app_pw@localhost:5432/kanban")
    DATABASE_URL_OWNER: str | None = Field(
        default="postgresql://owner:owner_pw@localhost:5432/kanban"
    )
    JWT_ACCESS_SECRET: str = Field(
        min_length=32, default="change-me-at-least-32-characters-long-secret-key-12345"
    )
    JWT_ACCESS_TTL_SECONDS: int = Field(default=900)
    REFRESH_TTL_DAYS: int = Field(default=14)
    REDIS_URL: str | None = Field(default=None)
    LOG_LEVEL: str = Field(default="INFO")


env = Settings()
