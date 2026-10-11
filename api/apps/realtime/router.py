import asyncio
import contextlib
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from apps.realtime.manager import manager
from apps.rides import presence
from apps.users.dependencies import user_from_token
from apps.users.models import User
from kuulis.core.db import SessionLocal
from kuulis.core.exceptions import AuthenticationError
from kuulis.core.security import decode_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realtime"])

AUTH_TIMEOUT_SECONDS = 10
MAX_MESSAGE_BYTES = 4096
RATE_PER_SECOND, RATE_BURST = 10, 20  # token bucket per connection
EXPIRING_NOTICE_SECONDS = 60
CLOSE_TOKEN_EXPIRED = 4001


async def _authenticate(token: object) -> tuple[User, float]:
    if not isinstance(token, str) or not token:
        raise AuthenticationError()
    expires_at = float(decode_token(token, "access")["exp"])
    async with SessionLocal() as session:
        return await user_from_token(session, token), expires_at


async def _close(websocket: WebSocket, code: int) -> None:
    with contextlib.suppress(RuntimeError):
        await websocket.close(code=code)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Realtime channel.

    Protocol: connect, then send ``{"type": "auth", "token": "<access token>"}`` as the first
    message within 10s (tokens are kept out of URLs and proxy logs). After that the server pushes
    ``{"event": str, "data": any}`` messages; clients may send ``{"type": "ping"}``.
    Drivers send ``{"type": "location", "lat", "lng", "heading"?, "speed"?}`` every 3-5 s.

    The connection lives as long as its access token: a minute before it expires the server sends
    ``auth.expiring``; the client refreshes and sends ``{"type": "auth", "token"}`` again
    (answered with ``auth.renewed``), otherwise the socket closes with code 4001. Messages over
    4 KB (1009) or more than 10 per second sustained (1008) close it too.
    """
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
        if not isinstance(first, dict) or first.get("type") != "auth":
            raise AuthenticationError()
        user, expires_at = await _authenticate(first.get("token"))
    except (TimeoutError, AuthenticationError, ValueError, WebSocketDisconnect):
        await _close(websocket, status.WS_1008_POLICY_VIOLATION)
        return

    user_id = str(user.id)
    manager.connect(user_id, websocket)
    await websocket.send_json({"event": "ready", "data": {"user_id": user_id}})
    warned = False
    allowance, last = float(RATE_BURST), time.monotonic()
    try:
        while True:
            now = time.time()
            if now >= expires_at:
                await _close(websocket, CLOSE_TOKEN_EXPIRED)
                return
            notice_at = expires_at - EXPIRING_NOTICE_SECONDS
            if not warned and now >= notice_at:
                warned = True
                await websocket.send_json({"event": "auth.expiring", "data": None})
            wake_at = expires_at if warned else notice_at
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=wake_at - now)
            except TimeoutError:
                continue

            if len(raw) > MAX_MESSAGE_BYTES:
                await _close(websocket, status.WS_1009_MESSAGE_TOO_BIG)
                return
            tick = time.monotonic()
            allowance = min(RATE_BURST, allowance + (tick - last) * RATE_PER_SECOND)
            last = tick
            if allowance < 1:
                await _close(websocket, status.WS_1008_POLICY_VIOLATION)
                return
            allowance -= 1

            try:
                message = json.loads(raw)
            except ValueError:
                continue
            kind = message.get("type") if isinstance(message, dict) else None
            if kind == "ping":
                await websocket.send_json({"event": "pong", "data": None})
            elif kind == "auth":
                try:
                    renewed, renewed_expiry = await _authenticate(message.get("token"))
                except AuthenticationError:
                    continue
                if renewed.id == user.id:
                    expires_at, warned = renewed_expiry, False
                    await websocket.send_json({"event": "auth.renewed", "data": None})
            elif kind == "location":
                try:
                    await presence.handle_location(user_id, message)
                except Exception:  # never drop the socket because of one bad update
                    logger.warning("Location update failed", exc_info=True)
    except (WebSocketDisconnect, KeyError):  # KeyError: a binary frame (we only speak text)
        pass
    finally:
        manager.disconnect(user_id, websocket)
