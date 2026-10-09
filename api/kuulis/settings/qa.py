from kuulis.settings.base import BaseAppSettings


class QASettings(BaseAppSettings):
    APP_ENV: str = "qa"  # type: ignore[assignment]
    DEBUG: bool = False
    DOCS_ENABLED: bool = True
    STORAGE_PREFIX: str = "qa"
    PUBLIC_URL: str = "https://kuulis-qa.top8.uk"
    FRONTEND_URL: str = "https://kuulis-qa.top8.uk"
    CORS_ORIGINS: list[str] = ["https://kuulis-qa.top8.uk"]
    EMAIL_ENABLED: bool = True
