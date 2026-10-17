"""Referral evaluation (doc 22): after an approval or a completed trip (queued), and an hourly
sweep that expires late invites and pays the ones waiting for a new month or more budget."""

import asyncio
import contextlib
import logging
import uuid

from taskiq import TaskiqEvents, TaskiqState

from apps.config.services import get_app_config
from apps.referrals import services
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

SWEEP_SECONDS = 3600
SWEEP_LOCK = f"{settings.APP_ENV}:referrals:sweep"
_task: asyncio.Task | None = None


@broker.task
async def evaluate_driver(driver_id: str) -> str | None:
    async with SessionLocal() as session:
        result = await services.evaluate_driver(session, uuid.UUID(driver_id))
    return result.value if result else None


async def run_once() -> None:
    """At most once an hour across workers and restarts."""
    if not await redis_client.set(SWEEP_LOCK, "1", nx=True, ex=SWEEP_SECONDS - 60):
        return
    async with SessionLocal() as session:
        result = await services.sweep(session, await get_app_config(session))
    if result:
        logger.info("Referrals sweep: %s", result)


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await run_once()
            await stats.beat("referrals")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Referrals loop failed")
        await asyncio.sleep(300)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="referrals-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
