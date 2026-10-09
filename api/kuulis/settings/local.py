from kuulis.settings.base import BaseAppSettings


class LocalSettings(BaseAppSettings):
    APP_ENV: str = "local"  # type: ignore[assignment]
    DEBUG: bool = True
    LOG_JSON: bool = False
    LOG_LEVEL: str = "DEBUG"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8081"]
    STORAGE_PREFIX: str = "local"
