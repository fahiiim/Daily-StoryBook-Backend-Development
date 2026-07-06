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
    app_public_base_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias="APP_PUBLIC_BASE_URL",
    )
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")

    storage_backend: str = Field(default="local", validation_alias="STORAGE_BACKEND")
    local_storage_dir: str = Field(default="media", validation_alias="LOCAL_STORAGE_DIR")
    local_media_url_prefix: str = Field(
        default="/media",
        validation_alias="LOCAL_MEDIA_URL_PREFIX",
    )
    upload_max_image_size_bytes: int = Field(
        default=5_242_880,
        validation_alias="UPLOAD_MAX_IMAGE_SIZE_BYTES",
    )
    upload_allowed_image_types: str = Field(
        default="image/jpeg,image/png,image/webp,image/gif",
        validation_alias="UPLOAD_ALLOWED_IMAGE_TYPES",
    )

    aws_access_key_id: str | None = Field(default=None, validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(
        default=None,
        validation_alias="AWS_SECRET_ACCESS_KEY",
    )
    aws_region: str = Field(default="us-east-1", validation_alias="AWS_REGION")
    aws_s3_bucket: str | None = Field(default=None, validation_alias="AWS_S3_BUCKET")
    aws_s3_endpoint_url: str | None = Field(
        default=None,
        validation_alias="AWS_S3_ENDPOINT_URL",
    )
    aws_s3_public_base_url: str | None = Field(
        default=None,
        validation_alias="AWS_S3_PUBLIC_BASE_URL",
    )

    ai_backend_base_url: str = Field(
        default="http://localhost:8001/api/v1",
        validation_alias="AI_BACKEND_BASE_URL",
    )
    ai_backend_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="AI_BACKEND_TIMEOUT_SECONDS",
    )
    ai_backend_max_retries: int = Field(
        default=2,
        validation_alias="AI_BACKEND_MAX_RETRIES",
    )
    ai_backend_retry_backoff_seconds: float = Field(
        default=0.5,
        validation_alias="AI_BACKEND_RETRY_BACKOFF_SECONDS",
    )

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/dailystorybook",
        validation_alias="DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    admin_panel_path: str = Field(default="/admin-panel", validation_alias="ADMIN_PANEL_PATH")
    admin_username: str = Field(default="adminstorybook", validation_alias="ADMIN_USERNAME")
    admin_password: str = Field(default="iamadmin", validation_alias="ADMIN_PASSWORD")

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