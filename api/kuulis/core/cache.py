"""Small JSON cache helpers on top of Redis."""

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
