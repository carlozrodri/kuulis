"""Redis-backed rate limiting shared by every worker and container."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from kuulis.settings import settings


def client_key(request: Request) -> str:
    # Behind Coolify/Traefik + Nginx Proxy Manager the real IP comes in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=str(settings.REDIS_URL),
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=False,
    strategy="moving-window",
)
