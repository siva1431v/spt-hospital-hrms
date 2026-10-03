"""
SPT Hospital HRMS — Application Configuration
Reads from environment variables with pydantic-settings.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "SPT Hospital HRMS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ENV: str = "development"
    ENVIRONMENT: str = "development"

    @property
    def is_production(self) -> bool:
        env = (self.ENVIRONMENT or self.ENV or "development").lower()
        return env in ("production", "prod")

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///spt_hrms.db"
    SYNC_DATABASE_URL: str = "sqlite:///spt_hrms.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str) -> str:
        if not v:
            return "sqlite+aiosqlite:///spt_hrms.db"
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("sqlite://") and not v.startswith("sqlite+"):
            return v.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return v

    @field_validator("SYNC_DATABASE_URL", mode="before")
    @classmethod
    def assemble_sync_db_url(cls, v: str) -> str:
        if not v:
            return "sqlite:///spt_hrms.db"
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        if v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql+asyncpg://", "postgresql://", 1)
        if v.startswith("sqlite+aiosqlite://"):
            return v.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return v

    # Auth
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app)(:\d+)?$"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # File Upload & Cloud Storage (AWS S3)
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # AWS Credentials & S3 Settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-south-1"
    AWS_S3_BUCKET_NAME: Optional[str] = None
    AWS_S3_PREFIX: str = "hrms"
    AWS_S3_ENDPOINT_URL: Optional[str] = None
    AWS_S3_SIGNATURE_VERSION: str = "s3v4"
    AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS: int = 3600

    @property
    def is_s3_enabled(self) -> bool:
        return self.STORAGE_BACKEND.lower() == "s3" and bool(self.AWS_S3_BUCKET_NAME)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Hospital Info
    HOSPITAL_NAME: str = "SPT Hospital"
    HOSPITAL_ADDRESS: str = ""
    HOSPITAL_PHONE: str = ""
    HOSPITAL_EMAIL: str = ""

    # Attendance & Lateness Defaults
    DEFAULT_GRACE_MINUTES: int = 5

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
