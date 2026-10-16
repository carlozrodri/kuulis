"""``Idempotency-Key`` for ride and wallet writes (doc 20).

The app sends a random key with each action it may retry (a driver without signal pressing
"Terminar", a rating queued offline). The first request runs and its 2xx answer is kept in Redis for
24 h; a retry with the same key gets that answer back (``Idempotent-Replayed: true``) instead of
running again, so nothing is done twice. Keys are per user, so two people never share one.

- Same key while the first request is still running: 409 ``idempotency_in_progress`` (retry later).
- Same key with a different body: 422 ``idempotency_key_reused``.
- Errors (4xx/5xx) are not kept: the retry runs again and gets its own answer.
- Redis down: the request runs as if it had no key (better than refusing the action).
"""

import base64
import hashlib
import json
import logging
import re
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kuulis.core.exceptions import AppError
from kuulis.core.redis import redis_client
from kuulis.core.security import decode_token
from kuulis.settings import settings

logger = logging.getLogger("kuulis.idempotency")

HEADER = b"idempotency-key"
REPLAYED = (b"idempotent-replayed", b"true")
TTL_SECONDS = 24 * 3600
# A request still running after this long is considered lost; its key can be used again.
LOCK_SECONDS = 60
MAX_KEY_LENGTH = 200
MAX_STORED_BODY = 256 * 1024

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# Paths after the API prefix that honour the header.
IDEMPOTENT_PATHS = re.compile(
    "^(?:"
    + "|".join(
        [
            r"/rides",
            rf"/rides/{_UUID}/(?:accept|decline|arrive|start|complete|cancel|messages|rating)",
            r"/wallet/me/top-ups",
            rf"/wallet/me/top-ups/{_UUID}/dispute",
            r"/wallet/me/transfers",
        ]
    )
    + ")/?$"
)


def applies(method: str, path: str) -> bool:
    prefix = settings.API_V1_PREFIX
    if method != "POST" or not path.startswith(prefix):
        return False
    return bool(IDEMPOTENT_PATHS.match(path[len(prefix) :]))


def _subject(headers: dict[bytes, bytes]) -> str | None:
    auth = headers.get(b"authorization", b"").decode("latin1")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return str(decode_token(token, "access")["sub"])
    except AppError:
        return None


def _error(code: str, message: str, status: int) -> tuple[int, bytes]:
    body = {"error": {"code": code, "message": message, "details": None}}
    return status, json.dumps(body).encode()


async def _send_json(send: Send, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not applies(scope.get("method", ""), scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        raw_key = headers.get(HEADER)
        if raw_key is None:
            await self.app(scope, receive, send)
            return
        key = raw_key.decode("latin1").strip()
        if not key or len(key) > MAX_KEY_LENGTH:
            await _send_json(
                send, *_error("idempotency_key_invalid", "Invalid Idempotency-Key", 400)
            )
            return
        subject = _subject(headers)
        if subject is None:  # the endpoint answers 401 itself
            await self.app(scope, receive, send)
            return

        # Read the whole body to fingerprint it, then hand it to the app unchanged.
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunks.append(message.get("body", b""))
            if not message.get("more_body"):
                break
        body = b"".join(chunks)
        fingerprint = hashlib.sha256(body).hexdigest()
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        digest = hashlib.sha256(f"{subject}|{scope['path']}|{key}".encode()).hexdigest()
        redis_key = f"idem:{digest}"
        try:
            locked = await redis_client.set(
                redis_key,
                json.dumps({"state": "pending", "fp": fingerprint}),
                nx=True,
                ex=LOCK_SECONDS,
            )
            stored = None if locked else await redis_client.get(redis_key)
        except Exception:  # never block an action because Redis failed
            logger.warning("idempotency: redis unavailable, running without key", exc_info=True)
            await self.app(scope, replay_receive, send)
            return

        if not locked:
            if stored is None:  # expired between SET and GET: run it
                await self.app(scope, replay_receive, send)
                return
            await self._answer_existing(json.loads(stored), fingerprint, send)
            return

        await self._run(scope, replay_receive, send, redis_key, fingerprint)

    async def _answer_existing(self, stored: dict[str, Any], fingerprint: str, send: Send) -> None:
        if stored.get("fp") != fingerprint:
            await _send_json(
                send,
                *_error(
                    "idempotency_key_reused",
                    "This Idempotency-Key was used with a different request",
                    422,
                ),
            )
            return
        if stored.get("state") != "done":
            await _send_json(
                send,
                *_error("idempotency_in_progress", "The same request is still running", 409),
            )
            return
        headers = [(k.encode("latin1"), v.encode("latin1")) for k, v in stored["headers"]]
        await send(
            {
                "type": "http.response.start",
                "status": stored["status"],
                "headers": [*headers, REPLAYED],
            }
        )
        await send({"type": "http.response.body", "body": base64.b64decode(stored["body"])})

    async def _run(
        self, scope: Scope, receive: Receive, send: Send, redis_key: str, fingerprint: str
    ) -> None:
        status = 500
        response_headers: list[tuple[bytes, bytes]] = []
        body_parts: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal status, response_headers
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = list(message.get("headers") or [])
            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive, capture)
        except BaseException:
            await self._forget(redis_key)
            raise
        body = b"".join(body_parts)
        if not 200 <= status < 300 or len(body) > MAX_STORED_BODY:
            await self._forget(redis_key)
            return
        record = {
            "state": "done",
            "fp": fingerprint,
            "status": status,
            "headers": [(k.decode("latin1"), v.decode("latin1")) for k, v in response_headers],
            "body": base64.b64encode(body).decode(),
        }
        try:
            await redis_client.set(redis_key, json.dumps(record), ex=TTL_SECONDS)
        except Exception:
            logger.warning("idempotency: could not store the answer", exc_info=True)

    @staticmethod
    async def _forget(redis_key: str) -> None:
        try:
            await redis_client.delete(redis_key)
        except Exception:
            logger.warning("idempotency: could not release the key", exc_info=True)
