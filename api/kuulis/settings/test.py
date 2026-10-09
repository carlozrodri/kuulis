from pydantic import PostgresDsn, RedisDsn

from kuulis.settings.base import BaseAppSettings


class TestSettings(BaseAppSettings):
    APP_ENV: str = "test"  # type: ignore[assignment]
    SECRET_KEY: str = "test-secret-key-not-for-production"
    DATABASE_URL: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/kuulis_test"
    )
    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379/15")
    LOG_JSON: bool = False
    RATE_LIMIT_ENABLED: bool = False
    EMAIL_ENABLED: bool = False
    PUSH_ENABLED: bool = False
    STORAGE_PREFIX: str = "test"
    OSRM_URL: str = ""  # tests never call the network
    PHOTON_URL: str = ""
    RATES_ENABLED: bool = False  # tests never call the network
