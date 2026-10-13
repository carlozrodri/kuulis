"""Driver verification jobs (doc 12): the daily expiry run at 08:00 Caracas (notices at 30, 7 and 1
days and on the expiry day, plus taking expired drivers offline). A loop started with each
worker checks every 10 minutes; a Redis key makes it run once a day across workers."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from kuulis.core.calendar import local_now
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 600
DAILY_HOUR = 8  # Caracas: notices arrive in the morning, not at midnight

_task: asyncio.Task | None = None


def _done_key(day: str) -> str:
    return f"{settings.APP_ENV}:drivers:expirations:{day}"


async def run_expirations_once(force: bool = False) -> int | None:
    """Returns how many notices went out, or None when it is not time (or another worker ran)."""
    from apps.config.services import get_app_config
    from apps.drivers import services, verification
    from apps.rides import presence
    from apps.rides.services import _driver_active_ride_id
    from kuulis.core.db import SessionLocal
    from kuulis.core.redis import redis_client

    now = local_now()
    day = now.date().isoformat()
    if not force and now.hour < DAILY_HOUR:
        return None
    if not await redis_client.set(_done_key(day), "1", nx=True, ex=3 * 86400):
        return None
    try:
        async with SessionLocal() as session:
            config = await get_app_config(session)
            notices = await verification.expiry_notices(session, config, now.date())
            await session.commit()
            for notice in notices:
                profile, document = notice.profile, notice.document
                expired = notice.days_left < 0
                # Expired: offline unless mid-ride (the next "go online" refuses them anyway).
                if (
                    expired
                    and await presence.is_online(profile.user_id)
                    and not await _driver_active_ride_id(session, profile.user_id)
                ):
                    await presence.go_offline(profile.user_id)
                assert document.expires_on is not None
                await services.notify(
                    session,
                    profile,
                    "document_expired" if expired else "document_expiring",
                    document=document,
                    values={"date": document.expires_on.strftime("%d/%m/%Y")},
                    data={"event_kind": "expiry"},
                )
    except Exception:
        await redis_client.delete(_done_key(day))  # retried on the next check
        raise
    if notices:
        logger.info("Driver expirations: %s notices", len(notices))
    return len(notices)


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await run_expirations_once()
            await stats.beat("driver_expirations")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Driver expirations failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="driver-expirations-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
