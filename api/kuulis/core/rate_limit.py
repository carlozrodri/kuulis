"""Redis-backed rate limiting shared by every worker and container.

Signed-in requests are counted per user (the access token's subject), so the many riders behind
one carrier-grade NAT address do not share a limit. Anonymous requests (login, register, password
reset) are counted per IP; password logins are also locked per email (apps/auth/lockout.py).

The client IP is ``request.client``: uvicorn resolves it from X-Forwarded-For trusting only the
proxies' private networks (``--forwarded-allow-ips``, see docker/entrypoint.sh), taking the
right-most address that is not one of them. An address the client wrote into the header itself
stays to the left of the one our proxy appended, so it cannot change the key.
"""

from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

from kuulis.core.exceptions import AuthenticationError
from kuulis.core.security import decode_token
from kuulis.settings import settings


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def ip_key(request: Request) -> str:
    return f"ip:{client_ip(request)}"


def rate_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        try:
            return f"user:{decode_token(auth[7:], 'access')['sub']}"
        except AuthenticationError:
            pass
    return ip_key(request)


limiter = Limiter(
    key_func=rate_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=str(settings.REDIS_URL),
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=False,
    strategy="moving-window",
)


def rate_limited_handler(_: Request, exc: Exception) -> JSONResponse:
    limit = exc.limit.limit if isinstance(exc, RateLimitExceeded) else None
    retry_after = limit.get_expiry() if limit else 60
    return JSONResponse(
        {
            "error": {
                "code": "rate_limited",
                "message": "Too many requests, try again later",
                "details": {"retry_after": retry_after},
            }
        },
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )
