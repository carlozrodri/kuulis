"""Subscription job, run by the loop in ``apps.wallet.tasks``: on the 1st (Caracas time) it
charges the month that just ended, and it sends due-soon / overdue reminders."""

import asyncio
import logging

from apps.subscriptions import services
from kuulis.core.calendar import add_months, format_month, local_now, month_start
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 300
LOCK_KEY = f"{settings.APP_ENV}:subscriptions:lock"


def _done_key(month: str) -> str:
    return f"{settings.APP_ENV}:subscriptions:charged:{month}"


async def run_once() -> None:
    if not await redis_client.set(LOCK_KEY, "1", nx=True, ex=CHECK_EVERY_SECONDS - 10):
        return
    previous = add_months(month_start(local_now()), -1)
    label = format_month(previous)
    if not await redis_client.exists(_done_key(label)):
        async with SessionLocal() as session:
            result = await services.charge_month(session, previous)
        await redis_client.set(_done_key(label), "1", ex=90 * 24 * 3600)
        logger.info("Subscription charges for %s: %s", label, result)
    async with SessionLocal() as session:
        await services.send_reminders(session)


async def loop() -> None:
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Subscription job failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)
