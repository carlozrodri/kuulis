"""ASGI entrypoint: ``gunicorn kuulis.asgi:app`` (Django's asgi.py)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIASGIMiddleware

import kuulis.models  # noqa: F401  (register models)
from apps.realtime.manager import manager
from kuulis.core.db import engine
from kuulis.core.exceptions import register_exception_handlers
from kuulis.core.logging import configure_logging
from kuulis.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from kuulis.core.rate_limit import limiter
from kuulis.core.redis import redis_client
from kuulis.core.sentry import init_sentry
from kuulis.settings import settings
from kuulis.tasks import broker
from kuulis.urls import api_v1, root


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    if not broker.is_worker_process:
        await broker.startup()
    manager.start()
    yield
    await manager.stop()
    if not broker.is_worker_process:
        await broker.shutdown()
    await redis_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    init_sentry()
    docs = settings.DOCS_ENABLED
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version="1.0.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url=f"{settings.API_V1_PREFIX}/docs" if docs else None,
        redoc_url=None,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if docs else None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_exception_handlers(app)

    # Middleware order: last added runs first.
    app.add_middleware(SlowAPIASGIMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(root)
    app.include_router(root, prefix="/api")
    app.include_router(api_v1, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
