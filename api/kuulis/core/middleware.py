"""Pure ASGI middlewares (no BaseHTTPMiddleware, so they are cheap and stream-safe)."""

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kuulis.core.request_context import request_id_ctx

logger = logging.getLogger("kuulis.request")


class RequestContextMiddleware:
    """Assigns an X-Request-ID, logs method/path/status/duration."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        request_id = headers.get(b"x-request-id", b"").decode() or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
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
            path = scope.get("path", "")
            if not path.startswith("/health"):
                logger.info("%s %s %s %sms", scope.get("method"), path, status_code, duration_ms)
            request_id_ctx.reset(token)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    ]
                )
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
