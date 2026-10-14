"""Releases first transfers whose 24 h ended (every minute) and runs the daily sweep (doc 16)."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from apps.config.services import get_app_config
from apps.risk import services
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

EVERY_SECONDS = 60
SWEEP_SECONDS = 24 * 3600
RELEASE_LOCK = f"{settings.APP_ENV}:risk:release"
SWEEP_LOCK = f"{settings.APP_ENV}:risk:sweep"
_task: asyncio.Task | None = None


async def run_once() -> None:
    """One worker at a time; the sweep at most once a day across workers and restarts."""
    if await redis_client.set(RELEASE_LOCK, "1", nx=True, ex=EVERY_SECONDS - 5):
        async with SessionLocal() as session:
            released = await services.release_due(session)
        if released:
            logger.info("Risk: %s held transfers released", released)
    if await redis_client.set(SWEEP_LOCK, "1", nx=True, ex=SWEEP_SECONDS):
        async with SessionLocal() as session:
            config = (await get_app_config(session)).risk
            logger.info("Risk sweep: %s", await services.sweep(session, config))


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await run_once()
            await stats.beat("risk")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Risk loop failed")
        await asyncio.sleep(EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="risk-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
