import asyncio
from datetime import timedelta

from apps.realtime.manager import ConnectionManager
from kuulis.asgi import app
from kuulis.core.security import create_token


async def _ws_session(messages: list[dict]) -> list[dict]:
    """Drives the ASGI app with a raw websocket scope in the current event loop."""
    inbox: asyncio.Queue = asyncio.Queue()
    await inbox.put({"type": "websocket.connect"})
    for message in messages:
        await inbox.put(message)
    sent: list[dict] = []

    async def receive() -> dict:
        try:
            return await asyncio.wait_for(inbox.get(), 1)
        except TimeoutError:
            return {"type": "websocket.disconnect", "code": 1000}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "websocket",
        "path": "/api/v1/ws",
        "raw_path": b"/api/v1/ws",
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "subprotocols": [],
        "scheme": "ws",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
        "root_path": "",
        "asgi": {"version": "3.0"},
    }
    await app(scope, receive, send)
    return sent


async def test_websocket_rejects_missing_auth():
    sent = await _ws_session([{"type": "websocket.receive", "text": '{"type": "hello"}'}])
    assert sent[-1] == {"type": "websocket.close", "code": 1008, "reason": ""}


async def test_websocket_accepts_valid_token(client, user_headers):
    token = user_headers["Authorization"].split()[1]
    sent = await _ws_session(
        [
            {"type": "websocket.receive", "text": f'{{"type": "auth", "token": "{token}"}}'},
            {"type": "websocket.receive", "text": '{"type": "ping"}'},
        ]
    )
    texts = [m.get("text", "") for m in sent if m["type"] == "websocket.send"]
    assert '"ready"' in texts[0]
    assert '"pong"' in texts[1]


async def test_websocket_rejects_refresh_token():
    token, _, _ = create_token(
        "00000000-0000-0000-0000-000000000000", "refresh", timedelta(minutes=1)
    )
    sent = await _ws_session(
        [{"type": "websocket.receive", "text": f'{{"type": "auth", "token": "{token}"}}'}]
    )
    assert sent[-1]["type"] == "websocket.close"


def test_manager_tracks_connections():
    manager = ConnectionManager()
    ws1, ws2 = object(), object()
    manager.connect("u1", ws1)  # type: ignore[arg-type]
    manager.connect("u1", ws2)  # type: ignore[arg-type]
    assert manager.active_connections == 2
    manager.disconnect("u1", ws1)  # type: ignore[arg-type]
    manager.disconnect("u1", ws2)  # type: ignore[arg-type]
    assert manager.active_connections == 0
