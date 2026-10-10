"""Background loops started with each worker process: Binance Pay reconciliation (every minute,
only with API credentials) and the subscription job (charges on the 1st, reminders)."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from apps.subscriptions import tasks as subscription_tasks
from apps.wallet import binance
from kuulis.core.db import SessionLocal
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []


async def _binance_loop() -> None:
    logger.info("Binance Pay reconciliation enabled (every %ss)", binance.POLL_SECONDS)
    healthy: bool | None = None  # logs the first success and every change, not each poll
    while True:
        try:
            async with SessionLocal() as session:
                credited = await binance.reconcile(session)
            if credited is None:  # another worker's turn
                await asyncio.sleep(binance.POLL_SECONDS)
                continue
            if healthy is not True:
                logger.info("Binance Pay API reachable (%s new payments)", credited)
            healthy = True
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Binance Pay reconciliation failed")
            healthy = False
        await asyncio.sleep(binance.POLL_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    if settings.APP_ENV == "test" or _tasks:
        return
    _tasks.append(asyncio.create_task(subscription_tasks.loop(), name="subscriptions-loop"))
    if binance.enabled():
        _tasks.append(asyncio.create_task(_binance_loop(), name="binance-pay-loop"))


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    for task in _tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    _tasks.clear()
