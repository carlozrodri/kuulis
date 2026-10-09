import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from apps.realtime.manager import manager
from apps.users.dependencies import user_from_token
from kuulis.core.db import SessionLocal
from kuulis.core.exceptions import AuthenticationError

router = APIRouter(tags=["realtime"])

AUTH_TIMEOUT_SECONDS = 10


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Realtime channel.

    Protocol: connect, then send ``{"type": "auth", "token": "<access token>"}`` as the first
    message within 10s (tokens are kept out of URLs and proxy logs). After that the server pushes
    ``{"event": str, "data": any}`` messages; clients may send ``{"type": "ping"}``.
    """
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
        if first.get("type") != "auth" or not first.get("token"):
            raise AuthenticationError()
        async with SessionLocal() as session:
            user = await user_from_token(session, first["token"])
    except (TimeoutError, AuthenticationError, ValueError, WebSocketDisconnect):
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = str(user.id)
    manager.connect(user_id, websocket)
    await websocket.send_json({"event": "ready", "data": {"user_id": user_id}})
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"event": "pong", "data": None})
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        manager.disconnect(user_id, websocket)
