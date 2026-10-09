"""Sentry is installed but only initialised when SENTRY_ENABLED=true and a DSN is set."""

from kuulis.settings import settings


def init_sentry() -> None:
    if not (settings.SENTRY_ENABLED and settings.SENTRY_DSN):
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )
