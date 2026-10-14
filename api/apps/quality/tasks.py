"""Refreshes quality rates and sends warnings every few minutes (doc 15)."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from apps.config.services import get_app_config
from apps.quality import services
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

EVERY_SECONDS = 10 * 60
LOCK_KEY = f"{settings.APP_ENV}:quality:refresh"
_task: asyncio.Task | None = None


async def run_once() -> int:
    """One worker at a time recomputes everyone's rates."""
    if not await redis_client.set(LOCK_KEY, "1", nx=True, ex=EVERY_SECONDS - 30):
        return 0
    async with SessionLocal() as session:
        config = await get_app_config(session)
        return await services.refresh(session, config)


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            written = await run_once()
            if written:
                logger.info("Quality: %s rows refreshed", written)
            await stats.beat("quality")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Quality loop failed")
        await asyncio.sleep(60)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="quality-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
