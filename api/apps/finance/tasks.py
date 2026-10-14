"""Daily ledger invariants (doc 17): one worker a day checks that the books add up; the result is
kept in Redis, shown in System status and alerted by monitoring while it fails."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from apps.finance import services
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

EVERY_SECONDS = 60
INVARIANTS_SECONDS = 24 * 3600
LOCK_KEY = f"{settings.APP_ENV}:finance:invariants:lock"
_task: asyncio.Task | None = None


async def run_once() -> dict | None:
    if not await redis_client.set(LOCK_KEY, "1", nx=True, ex=INVARIANTS_SECONDS):
        return None
    async with SessionLocal() as session:
        result = await services.run_invariants(session)
    if result["ok"]:
        logger.info("Ledger invariants OK (%s wallets)", result["wallets"])
    else:
        logger.error("Ledger invariants failed: %s", result["issues"][:5])
    return result


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await run_once()
            await stats.beat("finance")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Finance loop failed")
        await asyncio.sleep(EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="finance-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
