"""Safety jobs: the anomaly loop (every 30 s, one process at a time through a Redis lock, started
with each worker), the end-of-ride flush of the track, and Telegram messages to the team."""

import asyncio
import contextlib
import logging
import uuid

from taskiq import TaskiqEvents, TaskiqState

from kuulis.core.redis import redis_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 30
LOCK_KEY = f"{settings.APP_ENV}:safety:lock"

_task: asyncio.Task | None = None


async def run_once() -> bool:
    """Returns False when another process holds this round."""
    from apps.safety import services
    from kuulis.core.db import SessionLocal

    if not await redis_client.set(LOCK_KEY, "1", nx=True, ex=CHECK_EVERY_SECONDS - 5):
        return False
    async with SessionLocal() as session:
        await services.check_rides(session)
        await services.escalate_due(session)
    return True


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await run_once()
            await stats.beat("safety")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Safety check failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


@broker.task(task_name="safety.ride_ended")
async def ride_ended(ride_id: str) -> None:
    from apps.safety import services
    from kuulis.core.db import SessionLocal

    async with SessionLocal() as session:
        await services.ride_ended(session, uuid.UUID(ride_id))


@broker.task(task_name="safety.notify_team")
async def notify_team(alert_id: str) -> None:
    from apps.monitoring import alerts
    from apps.safety import services
    from apps.safety.models import SafetyAlert
    from kuulis.core.db import SessionLocal

    async with SessionLocal() as session:
        alert = await session.get(SafetyAlert, uuid.UUID(alert_id))
        if alert is None:
            return
        text = await services.team_message(session, alert)
    await alerts.notify(text)


@broker.task(task_name="safety.send_team_text")
async def send_team_text(text: str) -> None:
    from apps.monitoring import alerts

    await alerts.notify(f"[Kuulis {settings.APP_ENV}] {text}")


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="safety-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
