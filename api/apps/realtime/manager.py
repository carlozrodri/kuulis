"""WebSocket connection manager fanned out through Redis pub/sub.

Each API worker keeps its own sockets in memory. Events are published to one Redis channel and
every worker delivers them to its local sockets, so it works with N gunicorn workers and N
containers. Background jobs can call ``publish`` too.
"""

import asyncio
import contextlib
import logging
from collections import defaultdict
from typing import Any

import orjson
from fastapi import WebSocket

from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)
CHANNEL = f"{settings.APP_ENV}:realtime"


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._listener: asyncio.Task | None = None

    @property
    def active_connections(self) -> int:
        return sum(len(s) for s in self._connections.values())

    def connect(self, user_id: str, websocket: WebSocket) -> None:
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if sockets:
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)

    async def _deliver(self, message: dict[str, Any]) -> None:
        user_ids = message.get("user_ids")
        targets = (
            [ws for uid in user_ids for ws in self._connections.get(uid, ())]
            if user_ids
            else [ws for sockets in self._connections.values() for ws in sockets]
        )
        payload = {"event": message["event"], "data": message.get("data")}
        for ws in list(targets):
            try:
                await ws.send_json(payload)
            except Exception:  # Socket closed mid-send; cleanup happens on disconnect.
                logger.debug("Failed to deliver realtime message", exc_info=True)

    async def _listen(self) -> None:
        while True:
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(CHANNEL)
                async for raw in pubsub.listen():
                    if raw.get("type") == "message":
                        await self._deliver(orjson.loads(raw["data"]))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Realtime listener crashed, retrying in 2s")
                await asyncio.sleep(2)

    def start(self) -> None:
        if self._listener is None:
            self._listener = asyncio.create_task(self._listen(), name="realtime-listener")

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None


manager = ConnectionManager()


async def publish(event: str, data: Any = None, user_ids: list[str] | None = None) -> None:
    """Send an event to specific users (or everyone when user_ids is None)."""
    message = {"event": event, "data": data, "user_ids": user_ids}
    await redis_client.publish(CHANNEL, orjson.dumps(message, default=str).decode())
