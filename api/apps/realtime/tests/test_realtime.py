import asyncio
import json
from datetime import timedelta

from apps.realtime.manager import ConnectionManager
from kuulis.asgi import app
from kuulis.core.security import create_token


async def _ws_session(messages: list[dict], idle: float = 1) -> list[dict]:
    """Drives the ASGI app with a raw websocket scope in the current event loop."""
    inbox: asyncio.Queue = asyncio.Queue()
    await inbox.put({"type": "websocket.connect"})
    for message in messages:
        await inbox.put(message)
    sent: list[dict] = []

    async def receive() -> dict:
        try:
            return await asyncio.wait_for(inbox.get(), idle)
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


def _auth(token: str) -> dict:
    return {"type": "websocket.receive", "text": f'{{"type": "auth", "token": "{token}"}}'}


def _events(sent: list[dict]) -> list[str]:
    return [json.loads(m["text"])["event"] for m in sent if m["type"] == "websocket.send"]


async def test_websocket_warns_and_closes_when_the_token_expires(user_headers):
    from jwt import decode

    sub = decode(user_headers["Authorization"].split()[1], options={"verify_signature": False})
    token, _, _ = create_token(sub["sub"], "access", timedelta(seconds=1.5))
    sent = await _ws_session([_auth(token)], idle=5)
    assert _events(sent) == ["ready", "auth.expiring"]
    assert sent[-1] == {"type": "websocket.close", "code": 4001, "reason": ""}


async def test_websocket_renews_with_a_new_token(user_headers):
    token = user_headers["Authorization"].split()[1]
    sent = await _ws_session([_auth(token), _auth(token)])
    assert _events(sent) == ["ready", "auth.renewed"]


async def test_websocket_closes_on_oversized_or_flooding_messages(user_headers):
    token = user_headers["Authorization"].split()[1]
    big = {"type": "websocket.receive", "text": '{"type": "ping", "x": "' + "a" * 5000 + '"}'}
    sent = await _ws_session([_auth(token), big])
    assert sent[-1] == {"type": "websocket.close", "code": 1009, "reason": ""}

    ping = {"type": "websocket.receive", "text": '{"type": "ping"}'}
    sent = await _ws_session([_auth(token)] + [ping] * 40)
    assert sent[-1] == {"type": "websocket.close", "code": 1008, "reason": ""}
    assert 15 <= _events(sent).count("pong") <= 25


def test_manager_tracks_connections():
    manager = ConnectionManager()
    ws1, ws2 = object(), object()
    manager.connect("u1", ws1)  # type: ignore[arg-type]
    manager.connect("u1", ws2)  # type: ignore[arg-type]
    assert manager.active_connections == 2
    manager.disconnect("u1", ws1)  # type: ignore[arg-type]
    manager.disconnect("u1", ws2)  # type: ignore[arg-type]
    assert manager.active_connections == 0
