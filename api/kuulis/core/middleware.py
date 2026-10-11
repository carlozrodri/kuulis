"""Pure ASGI middlewares (no BaseHTTPMiddleware, so they are cheap and stream-safe)."""

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.monitoring import stats
from kuulis.core.request_context import log_fields_ctx, request_id_ctx
from kuulis.settings import settings

logger = logging.getLogger("kuulis.request")
RIDE_PATH = re.compile(r"/rides/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")


class RequestContextMiddleware:
    """Assigns an X-Request-ID, logs method/path/status/duration (with user and ride ids when known)
    and counts requests and 5xx for the monitoring checks."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        request_id = headers.get(b"x-request-id", b"").decode() or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        path = scope.get("path", "")
        fields: dict[str, str] = {}
        if client := scope.get("client"):
            fields["ip"] = client[0]  # resolved by uvicorn from the trusted proxies
        if settings.LOG_FORWARDED_FOR:  # diagnosing the proxy chain (docs/deployment.md)
            fields["forwarded_for"] = headers.get(b"x-forwarded-for", b"").decode("latin1")
        if ride := RIDE_PATH.search(path):
            fields["ride_id"] = ride.group(1)
        fields_token = log_fields_ctx.set(fields)
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            if not path.startswith(("/health", "/api/health", "/api/metrics")):
                logger.info("%s %s %s %sms", scope.get("method"), path, status_code, duration_ms)
                await stats.record_request(status_code, duration_ms)
            log_fields_ctx.reset(fields_token)
            request_id_ctx.reset(token)


# JSON only: nothing to load, embed or frame. The Swagger page (local/QA) loads its own assets.
API_CSP = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"strict-transport-security", b"max-age=31536000"),
    (b"cross-origin-opener-policy", b"same-origin"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        docs = scope.get("path", "").endswith(("/docs", "/docs/oauth2-redirect"))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].extend(SECURITY_HEADERS)
                if not docs:
                    message["headers"].append((b"content-security-policy", API_CSP))
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RestoreApiPrefixMiddleware:
    """Coolify's Traefik strips the ``/api`` path prefix when a domain has a path
    (``https://host/api``). Put it back so routes are identical with or without the proxy."""

    def __init__(self, app: ASGIApp, prefix: str = "/api") -> None:
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            path: str = scope.get("path", "")
            if not path.startswith((self.prefix + "/", "/health")) and path != self.prefix:
                scope = dict(scope)
                scope["path"] = self.prefix + path
                scope["raw_path"] = self.prefix.encode() + scope.get("raw_path", path.encode())
        await self.app(scope, receive, send)
