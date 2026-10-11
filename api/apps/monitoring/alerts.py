"""Alert delivery with deduplication: a problem is sent when it appears, repeated at most every
30 minutes while it lasts, and followed by a recovery message when it is gone.

Telegram gets the alerts; email (``ALERT_EMAILS``) gets the daily summary, and the alerts too when
Telegram is not configured. Open alerts and a short history live in Redis.
"""

import contextlib
import html
import logging
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Protocol

import httpx
import orjson
from redis.exceptions import RedisError

from apps.monitoring.schemas import OpenAlert
from kuulis.core.email import send_email
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

OPEN_KEY = f"{settings.APP_ENV}:monitoring:alerts"
HISTORY_KEY = f"{settings.APP_ENV}:monitoring:history"
CHAT_KEY = f"{settings.APP_ENV}:monitoring:telegram_chat"
HISTORY_SIZE = 500
REPEAT_SECONDS = 30 * 60
TELEGRAM_API = "https://api.telegram.org"


class Problem(Protocol):
    key: str
    message: str


def _prefix() -> str:
    return f"[Kuulis {settings.APP_ENV}]"


async def open_alerts() -> list[OpenAlert]:
    try:
        rows = await redis_client.hgetall(OPEN_KEY)
    except Exception:
        return []
    result = []
    for key, raw in rows.items():
        data = orjson.loads(raw)
        result.append(
            OpenAlert(
                key=key, message=data["message"], since=datetime.fromtimestamp(data["since"], UTC)
            )
        )
    return sorted(result, key=lambda alert: alert.since)


async def history(since: float) -> list[dict]:
    rows = [orjson.loads(raw) for raw in await redis_client.lrange(HISTORY_KEY, 0, HISTORY_SIZE)]
    return [row for row in rows if row["at"] >= since]


async def _remember(kind: str, key: str, message: str) -> None:
    entry = orjson.dumps({"kind": kind, "key": key, "message": message, "at": time.time()})
    async with redis_client.pipeline(transaction=False) as pipe:
        pipe.lpush(HISTORY_KEY, entry)
        pipe.ltrim(HISTORY_KEY, 0, HISTORY_SIZE - 1)
        await pipe.execute()


async def _telegram_chat(client: httpx.AsyncClient) -> str | None:
    """The configured chat, or the last private chat that wrote to the bot (remembered)."""
    if settings.ALERT_TELEGRAM_CHAT_ID:
        return settings.ALERT_TELEGRAM_CHAT_ID
    with contextlib.suppress(RedisError):
        if chat := await redis_client.get(CHAT_KEY):
            return chat
    response = await client.get(
        f"{TELEGRAM_API}/bot{settings.ALERT_TELEGRAM_BOT_TOKEN}/getUpdates", timeout=10
    )
    response.raise_for_status()
    chats = [
        update["message"]["chat"]
        for update in response.json().get("result", [])
        if update.get("message", {}).get("chat", {}).get("type") == "private"
    ]
    if not chats:
        logger.warning("Telegram alerts: nobody has written to the bot yet, so there is no chat")
        return None
    chat = str(chats[-1]["id"])
    with contextlib.suppress(RedisError):
        await redis_client.set(CHAT_KEY, chat)
    logger.info("Telegram alerts go to chat %s (set ALERT_TELEGRAM_CHAT_ID to pin it)", chat)
    return chat


async def send_telegram(text: str) -> bool:
    if not settings.ALERT_TELEGRAM_BOT_TOKEN:
        return False
    try:
        async with httpx.AsyncClient() as client:
            chat = await _telegram_chat(client)
            if chat is None:
                return False
            response = await client.post(
                f"{TELEGRAM_API}/bot{settings.ALERT_TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat, "text": text, "disable_web_page_preview": True},
                timeout=10,
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        # Never log the URL: it carries the bot token.
        logger.error("Telegram alert failed: %s", type(error).__name__)
        return False
    return True


async def send_email_to_team(subject: str, lines: Iterable[str]) -> bool:
    body = "<br>".join(html.escape(line) for line in lines)
    sent = False
    for to in settings.ALERT_EMAILS:
        try:
            sent = await send_email(to, subject, f"<p>{body}</p>") or sent
        except httpx.HTTPError:
            logger.error("Alert email to %s failed", to)
    return sent


async def notify(text: str) -> None:
    """One alert or recovery: Telegram, or email when Telegram is not configured or fails."""
    if await send_telegram(text):
        return
    if not await send_email_to_team(text[:120], [text]):
        logger.warning("Alert not delivered (no channel configured): %s", text)


async def process(problems: Iterable[Problem]) -> None:
    """Compares the current problems with the open alerts and sends what changed."""
    now = time.time()
    current = {problem.key: problem.message for problem in problems}
    open_rows = {
        key: orjson.loads(raw) for key, raw in (await redis_client.hgetall(OPEN_KEY)).items()
    }

    for key, message in current.items():
        row = open_rows.get(key)
        if row is None:
            await notify(f"🔴 {_prefix()} {message}")
            await _remember("alert", key, message)
            row = {"message": message, "since": now, "sent_at": now}
        elif now - row["sent_at"] >= REPEAT_SECONDS:
            minutes = int((now - row["since"]) // 60)
            await notify(f"🔴 {_prefix()} Sigue: {message} (desde hace {minutes} min)")
            row = {**row, "message": message, "sent_at": now}
        else:
            continue
        await redis_client.hset(OPEN_KEY, key, orjson.dumps(row))

    for key, row in open_rows.items():
        if key in current:
            continue
        minutes = int((now - row["since"]) // 60)
        await notify(f"✅ {_prefix()} Resuelto: {row['message']} (duró {minutes} min)")
        await _remember("recovered", key, row["message"])
        await redis_client.hdel(OPEN_KEY, key)
