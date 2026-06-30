from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="DailyStoryBook API", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/dailystorybook",
        validation_alias="DATABASE_URL",
    )

    secret_key: str = Field(default="change-me", validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()