"""Small JSON cache helpers on top of Redis, plus short-lived per-process copies of hot entries."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

import orjson

from kuulis.core.redis import redis_client
from kuulis.settings import settings


def _key(key: str) -> str:
    return f"{settings.APP_ENV}:cache:{key}"


async def cache_get(key: str) -> Any | None:
    raw = await redis_client.get(_key(key))
    return orjson.loads(raw) if raw is not None else None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    await redis_client.set(
        _key(key), orjson.dumps(value).decode(), ex=ttl or settings.CACHE_DEFAULT_TTL
    )


async def cache_delete(*keys: str) -> None:
    if keys:
        await redis_client.delete(*(_key(k) for k in keys))


async def cached(key: str, loader: Callable[[], Awaitable[Any]], ttl: int | None = None) -> Any:
    value = await cache_get(key)
    if value is None:
        value = await loader()
        await cache_set(key, value, ttl)
    return value


# Per-process copies: a read that hits one skips the Redis round trip and the parsing, which every
# request paid for the app config. Dropped after LOCAL_CACHE_SECONDS or when any process publishes
# the key on INVALIDATE_CHANNEL (the realtime listener of each API process drops it at once).
INVALIDATE_CHANNEL = f"{settings.APP_ENV}:cache:invalidate"
_local: dict[str, tuple[float, Any]] = {}


def local_get(key: str) -> Any | None:
    hit = _local.get(key)
    if hit is None or time.monotonic() - hit[0] >= settings.LOCAL_CACHE_SECONDS:
        return None
    return hit[1]


def local_set(key: str, value: Any) -> None:
    if settings.LOCAL_CACHE_SECONDS > 0:
        _local[key] = (time.monotonic(), value)


def local_drop(key: str | None = None) -> None:
    """Drops one copy, or all of them."""
    if key is None:
        _local.clear()
    else:
        _local.pop(key, None)


async def local_invalidate(key: str) -> None:
    """Drops ``key`` in this process and tells the other processes to drop it too."""
    local_drop(key)
    await redis_client.publish(INVALIDATE_CHANNEL, key)
