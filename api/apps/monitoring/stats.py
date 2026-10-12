"""Cheap counters in Redis for the monitoring checks: loop heartbeats and per-minute HTTP totals.

Shared by every API and worker process, so the checks see the whole deployment. Writing them must
never break a request or a loop: Redis errors are swallowed (the checks report Redis itself).
"""

import logging
import time

from redis.exceptions import RedisError

from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

HEARTBEATS_KEY = f"{settings.APP_ENV}:monitoring:heartbeats"
HTTP_KEY = f"{settings.APP_ENV}:monitoring:http:"  # + minute (epoch // 60)
HTTP_KEEP_SECONDS = 3600
BEAT_EVERY_SECONDS = 10  # fast loops (dispatch runs twice a second) write at most this often

_last_beat: dict[str, float] = {}


async def beat(loop: str) -> None:
    """A background loop finished a round without errors."""
    now = time.time()
    if now - _last_beat.get(loop, 0) < BEAT_EVERY_SECONDS:
        return
    try:
        await redis_client.hset(HEARTBEATS_KEY, loop, now)
        _last_beat[loop] = now
    except RedisError:
        logger.warning("Could not record the %s heartbeat", loop)


async def heartbeats() -> dict[str, float]:
    return {
        name: float(value) for name, value in (await redis_client.hgetall(HEARTBEATS_KEY)).items()
    }


# Per-process totals not yet written: minute -> [requests, 5xx, total ms]. One Redis write a
# second instead of one per request (that write was ~5 % of the CPU of a simple request).
_pending: dict[int, list[float]] = {}
_last_flush = 0.0
FLUSH_EVERY_SECONDS = 1.0


async def record_request(status_code: int, duration_ms: float) -> None:
    totals = _pending.setdefault(int(time.time() // 60), [0, 0, 0.0])
    totals[0] += 1
    totals[1] += status_code >= 500
    totals[2] += duration_ms
    if time.monotonic() - _last_flush >= FLUSH_EVERY_SECONDS:
        await flush_requests()


async def flush_requests() -> None:
    global _last_flush
    _last_flush = time.monotonic()
    if not _pending:
        return
    pending = dict(_pending)
    _pending.clear()
    try:
        async with redis_client.pipeline(transaction=False) as pipe:
            for minute, (total, errors, ms) in pending.items():
                key = f"{HTTP_KEY}{minute}"
                pipe.hincrby(key, "total", int(total))
                if errors:
                    pipe.hincrby(key, "errors", int(errors))
                pipe.hincrbyfloat(key, "ms", ms)
                pipe.expire(key, HTTP_KEEP_SECONDS)
            await pipe.execute()
    except RedisError:
        pass


async def http_totals(minutes: int) -> dict[str, float]:
    """Requests, 5xx and average latency over the last ``minutes`` complete or current minutes."""
    await flush_requests()  # this process's latest ones too
    current = int(time.time() // 60)
    async with redis_client.pipeline(transaction=False) as pipe:
        for minute in range(current - minutes + 1, current + 1):
            pipe.hgetall(f"{HTTP_KEY}{minute}")
        rows = await pipe.execute()
    total = sum(int(row.get("total", 0)) for row in rows)
    errors = sum(int(row.get("errors", 0)) for row in rows)
    ms = sum(float(row.get("ms", 0)) for row in rows)
    return {"requests": total, "errors": errors, "avg_ms": round(ms / total, 1) if total else 0.0}
