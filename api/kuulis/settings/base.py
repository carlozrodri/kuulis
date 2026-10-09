from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Comma separated env values ("a,b") instead of JSON. Subclasses must reuse this type.
CSVList = Annotated[list[str], NoDecode]


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Core -----------------------------------------------------------------
    APP_ENV: Literal["local", "test", "qa", "production"] = "local"
    APP_NAME: str = "Kuulis"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default="change-me-in-env", min_length=16)
    API_V1_PREFIX: str = "/api/v1"
    PUBLIC_URL: str = "http://localhost:8000"
    ALLOWED_HOSTS: CSVList = ["*"]
    CORS_ORIGINS: CSVList = []
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    DOCS_ENABLED: bool = True

    # --- Database -------------------------------------------------------------
    DATABASE_URL: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/kuulis"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # --- Redis ----------------------------------------------------------------
    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379/0")
    CACHE_DEFAULT_TTL: int = 60

    # --- Auth -----------------------------------------------------------------
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30
    PASSWORD_RESET_TTL_MINUTES: int = 30
    EMAIL_VERIFICATION_TTL_HOURS: int = 48

    # --- Rate limiting ----------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # --- Storage (S3 compatible) ------------------------------------------------
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_S3_ENDPOINT: str = ""
    AWS_S3_REGION: str = "us-east-1"
    STORAGE_PREFIX: str = "local"
    STORAGE_PRESIGN_TTL_SECONDS: int = 900
    STORAGE_MAX_UPLOAD_MB: int = 20

    # --- Email (Resend) ---------------------------------------------------------
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Kuulis <no-reply@email.top8.uk>"
    EMAIL_ENABLED: bool = False
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Push notifications (Expo) ---------------------------------------------
    EXPO_PUSH_URL: str = "https://exp.host/--/api/v2/push/send"
    EXPO_ACCESS_TOKEN: str = ""
    PUSH_ENABLED: bool = True

    # --- Observability ----------------------------------------------------------
    SENTRY_ENABLED: bool = False
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.05

    # --- Bootstrap --------------------------------------------------------------
    FIRST_SUPERUSER_EMAIL: str = ""
    FIRST_SUPERUSER_PASSWORD: str = ""

    @field_validator("ALLOWED_HOSTS", "CORS_ORIGINS", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _force_asyncpg(cls, value: object) -> object:
        # Coolify exposes postgres:// URLs; SQLAlchemy async needs the asyncpg driver.
        if isinstance(value, str):
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def storage_enabled(self) -> bool:
        return bool(self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY and self.AWS_S3_BUCKET)
