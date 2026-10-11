"""Monitoring loop: every minute one process (Redis lock) checks the system and sends alerts, and at
08:00 Caracas it emails the daily summary.

It runs in the worker and in the API processes, so a stopped worker is still reported by the API.
"""

import asyncio
import contextlib
import logging
import time

from redis.exceptions import RedisError
from taskiq import TaskiqEvents, TaskiqState

from apps.monitoring import alerts, checks, stats
from kuulis.core.calendar import local_now
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 60
LOCK_KEY = f"{settings.APP_ENV}:monitoring:lock"
SUMMARY_KEY = f"{settings.APP_ENV}:monitoring:summary:"  # + date
SUMMARY_HOUR = 8
REDIS_DOWN_REPEAT_SECONDS = 30 * 60

_task: asyncio.Task | None = None
_redis_down_sent_at: float | None = None


async def run_once() -> bool:
    """Returns False when another process holds this minute's turn."""
    if not await redis_client.set(LOCK_KEY, "1", nx=True, ex=CHECK_EVERY_SECONDS - 5):
        return False
    async with SessionLocal() as session:
        health = await checks.collect(session)
    await alerts.process(checks.problems(health))
    await _daily_summary(health)
    return True


async def _daily_summary(health) -> None:
    now = local_now()
    if now.hour < SUMMARY_HOUR or not settings.ALERT_EMAILS:
        return
    if not await redis_client.set(f"{SUMMARY_KEY}{now.date()}", "1", nx=True, ex=2 * 86400):
        return
    events = await alerts.history(time.time() - 86400)
    fired = [e for e in events if e["kind"] == "alert"]
    lines = [f"Kuulis {settings.APP_ENV} · resumen del {now.date():%d/%m/%Y}", ""]
    lines.append(f"Alertas en las últimas 24 h: {len(fired)}")
    lines += [f"• {e['message']}" for e in reversed(fired)]
    lines.append("")
    lines.append(
        "Abiertas ahora: "
        + (", ".join(a.message for a in health.alerts) if health.alerts else "ninguna")
    )
    lines.append(f"Viajes pedidos en la última hora: {health.rides.requested_last_hour}")
    lines.append(f"Disco usado: {health.disk_used_percent} %")
    await alerts.send_email_to_team(f"Kuulis {settings.APP_ENV}: resumen diario", lines)


async def loop() -> None:
    global _redis_down_sent_at
    while True:
        try:
            await run_once()
            await stats.beat("monitoring")
        except asyncio.CancelledError:
            raise
        except RedisError:
            # No lock and no dedup without Redis: each process warns at most every 30 min.
            logger.exception("Monitoring: Redis unavailable")
            last = _redis_down_sent_at
            if last is None or time.monotonic() - last > REDIS_DOWN_REPEAT_SECONDS:
                _redis_down_sent_at = time.monotonic()
                with contextlib.suppress(Exception):
                    await alerts.notify(f"🔴 [Kuulis {settings.APP_ENV}] Redis no responde")
        except Exception:
            logger.exception("Monitoring check failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


def start() -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="monitoring-loop")


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    start()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    await stop()
