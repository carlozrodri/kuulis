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
    # Git commit of the running build (Coolify: "Include source commit in build").
    SOURCE_COMMIT: str = ""
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
    # A "SELECT 1" before every checkout costs ~10 % of the CPU of a simple request. Without it a
    # Postgres restart fails the requests that were using a dropped connection, and the pool then
    # replaces all of them at once (SQLAlchemy invalidates the pool on a disconnect error).
    DB_POOL_PRE_PING: bool = False
    DB_ECHO: bool = False

    # --- Redis ----------------------------------------------------------------
    REDIS_URL: RedisDsn = RedisDsn("redis://localhost:6379/0")
    # Per process; a request waits up to REDIS_POOL_TIMEOUT seconds for a free connection.
    REDIS_MAX_CONNECTIONS: int = 100
    REDIS_POOL_TIMEOUT: int = 5
    CACHE_DEFAULT_TTL: int = 60

    # --- Auth -----------------------------------------------------------------
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30
    # A refresh retried this soon after its rotation (the answer was lost on a bad connection)
    # gets the same new tokens instead of tripping reuse detection.
    REFRESH_RETRY_GRACE_SECONDS: int = 30
    PASSWORD_RESET_TTL_MINUTES: int = 30
    EMAIL_VERIFICATION_TTL_HOURS: int = 48
    # Social login: accepted ``aud`` values. Empty disables the provider.
    GOOGLE_CLIENT_IDS: CSVList = []  # web, iOS and Android OAuth client ids
    APPLE_CLIENT_IDS: CSVList = []  # iOS bundle id (and Services ID if web sign-in is added)

    # --- Rate limiting ----------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "120/minute"
    RATE_LIMIT_AUTH: str = "20/minute"  # per IP; logins are also locked per email
    # Per IP too, and many riders share one carrier-grade NAT address: a refresh token cannot be
    # guessed, so this only guards against floods (30/minute logged real users out, doc 18).
    RATE_LIMIT_REFRESH: str = "3000/minute"

    # --- Storage (S3 compatible) ------------------------------------------------
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_S3_ENDPOINT: str = ""
    AWS_S3_REGION: str = "us-east-1"
    STORAGE_PREFIX: str = "local"
    STORAGE_PRESIGN_TTL_SECONDS: int = 900
    # Links the team opens to someone else's private files (driver documents): short lived.
    PRIVATE_FILE_URL_SECONDS: int = 300
    # Days between "delete my account" and erasing the personal data (signing in cancels it).
    ACCOUNT_DELETION_GRACE_DAYS: int = 30
    STORAGE_MAX_UPLOAD_MB: int = 20
    # Social media content (docs/marketing/09): its own bucket and, ideally, a key limited to it.
    # Endpoint and region are the ones above; empty credentials reuse AWS_ACCESS_KEY_ID/SECRET.
    MARKETING_S3_BUCKET: str = ""
    MARKETING_S3_ACCESS_KEY_ID: str = ""
    MARKETING_S3_SECRET_ACCESS_KEY: str = ""
    MARKETING_MAX_UPLOAD_MB: int = 500
    # Download links in the posting package: long enough to download a video on a slow connection.
    MARKETING_DOWNLOAD_URL_SECONDS: int = 3600

    # --- App updates (doc 09) ---------------------------------------------------
    # Private key (PEM, "\n" escapes allowed) that signs the OTA manifests. Its certificate ships
    # inside the app (mobile/certs/updates-<APP_ENV>.pem). Empty: apps that expect a signature get
    # 503 and keep the code they have.
    UPDATES_SIGNING_KEY: str = ""
    UPDATES_SIGNING_KEY_ID: str = "main"

    # --- Email (Resend) ---------------------------------------------------------
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Kuulis <no-reply@email.top8.uk>"
    EMAIL_ENABLED: bool = False
    # Public website (doc 08): the email links (verify email, reset password) open there.
    FRONTEND_URL: str = "http://localhost:3000"
    # Admin panel, when it lives on its own host (admin.<domain>); empty means FRONTEND_URL.
    ADMIN_URL: str = ""

    # --- Push notifications (Expo) ---------------------------------------------
    EXPO_PUSH_URL: str = "https://exp.host/--/api/v2/push/send"
    EXPO_ACCESS_TOKEN: str = ""
    PUSH_ENABLED: bool = True

    # --- Geo (routes and address search) --------------------------------------------------
    # Empty OSRM_URL: routes are estimated (straight line x 1.3 at 22 km/h, no polyline).
    # Empty PHOTON_URL: address search returns [] and reverse geocoding returns coordinates.
    OSRM_URL: str = ""  # e.g. https://router.project-osrm.org
    PHOTON_URL: str = ""  # e.g. https://photon.komoot.io
    GEO_TIMEOUT_SECONDS: float = 4.0

    # --- Exchange rates (bolívares per USD) -------------------------------------------------
    # The worker polls these sources; RATES_ENABLED=false turns polling off (manual rates only).
    RATES_ENABLED: bool = True
    RATES_BCV_URL: str = "https://ve.dolarapi.com/v1/dolares/oficial"
    RATES_BINANCE_URL: str = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
    RATES_BCV_INTERVAL_MINUTES: int = 60
    RATES_BINANCE_INTERVAL_MINUTES: int = 15
    RATES_TIMEOUT_SECONDS: float = 10.0

    # --- Binance Pay reconciliation (read-only API key of Kuulis' Binance account) ------------
    # Empty: top-ups are confirmed by hand in the admin.
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_API_URL: str = "https://api.binance.com"

    # --- Observability ----------------------------------------------------------
    SENTRY_ENABLED: bool = False
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.05
    # Alerts (apps/monitoring). Without a chat id the first private chat that wrote to the bot is
    # used. Email gets the daily summary, and the alerts too when Telegram is not configured.
    ALERT_TELEGRAM_BOT_TOKEN: str = ""
    ALERT_TELEGRAM_CHAT_ID: str = ""
    ALERT_EMAILS: CSVList = []
    # Bearer token for /api/metrics (Prometheus). Empty: the endpoint answers 404.
    METRICS_TOKEN: str = ""
    # Staff and admins need the second factor (apps/auth/totp.py) to use the admin endpoints.
    ADMIN_TOTP_REQUIRED: bool = True
    # Adds the raw X-Forwarded-For to each request log line, to check what the proxies send.
    LOG_FORWARDED_FOR: bool = False

    # --- Backups (apps/backups) ---------------------------------------------------
    # The worker dumps Postgres every BACKUP_EVERY_MINUTES, encrypted with BACKUP_PASSPHRASE
    # (openssl aes-256-cbc, pbkdf2), to an S3-compatible bucket outside the homelab (Cloudflare R2),
    # mirrors the uploaded files there and checks a restore every week.
    BACKUP_ENABLED: bool = False
    BACKUP_S3_ENDPOINT: str = ""
    BACKUP_S3_BUCKET: str = ""
    BACKUP_S3_ACCESS_KEY_ID: str = ""
    BACKUP_S3_SECRET_ACCESS_KEY: str = ""
    BACKUP_S3_REGION: str = "auto"
    BACKUP_PASSPHRASE: str = ""
    BACKUP_EVERY_MINUTES: int = 15
    BACKUP_MIRROR_FILES: bool = True

    # --- Bootstrap --------------------------------------------------------------
    FIRST_SUPERUSER_EMAIL: str = ""
    FIRST_SUPERUSER_PASSWORD: str = ""

    @field_validator(
        "ALLOWED_HOSTS",
        "CORS_ORIGINS",
        "GOOGLE_CLIENT_IDS",
        "APPLE_CLIENT_IDS",
        "ALERT_EMAILS",
        mode="before",
    )
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
    def backups_configured(self) -> bool:
        return bool(
            self.BACKUP_ENABLED
            and self.BACKUP_S3_BUCKET
            and self.BACKUP_S3_ACCESS_KEY_ID
            and self.BACKUP_S3_SECRET_ACCESS_KEY
            and self.BACKUP_PASSPHRASE
        )

    @property
    def storage_enabled(self) -> bool:
        return bool(self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY and self.AWS_S3_BUCKET)

    @property
    def marketing_storage_enabled(self) -> bool:
        key = self.MARKETING_S3_ACCESS_KEY_ID or self.AWS_ACCESS_KEY_ID
        secret = self.MARKETING_S3_SECRET_ACCESS_KEY or self.AWS_SECRET_ACCESS_KEY
        return bool(self.MARKETING_S3_BUCKET and key and secret)

    @property
    def admin_url(self) -> str:
        return (self.ADMIN_URL or self.FRONTEND_URL).rstrip("/")
