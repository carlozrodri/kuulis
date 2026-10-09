"""Rate polling. A small loop starts with each worker process and checks every minute which
source is due (see ``services.poll_due``); no scheduler process is needed."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from apps.rates import services
from kuulis.core.db import SessionLocal
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 60
_task: asyncio.Task | None = None


async def loop() -> None:
    while True:
        try:
            async with SessionLocal() as session:
                await services.poll_due(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Rate polling failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.RATES_ENABLED and settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="rates-poll-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
