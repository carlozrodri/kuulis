from pydantic import model_validator

from kuulis.settings.base import BaseAppSettings


class ProductionSettings(BaseAppSettings):
    APP_ENV: str = "production"  # type: ignore[assignment]
    DEBUG: bool = False
    DOCS_ENABLED: bool = False
    STORAGE_PREFIX: str = "production"
    PUBLIC_URL: str = "https://kuulis-prod.top8.uk"
    FRONTEND_URL: str = "https://kuulis-prod.top8.uk"
    CORS_ORIGINS: list[str] = ["https://kuulis-prod.top8.uk"]
    EMAIL_ENABLED: bool = True
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5

    @model_validator(mode="after")
    def _require_real_secret(self) -> "ProductionSettings":
        if self.SECRET_KEY == "change-me-in-env" or len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be set to a strong value (>= 32 chars) in production")
        return self
