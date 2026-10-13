"""Privacy jobs: building a "download my data" file, and the daily retention run (a loop started
with each worker process; a Redis key makes one process do each day)."""

import asyncio
import contextlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from taskiq import TaskiqEvents, TaskiqState

from kuulis.core.email import send_email
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 3600
_task: asyncio.Task | None = None


@broker.task(task_name="privacy.build_export")
async def build_export(export_id: str) -> str:
    """Builds the file, uploads it to private storage and emails a link valid for 24 h."""
    from apps.privacy import services
    from apps.privacy.models import DataExport
    from apps.users.models import User
    from kuulis.core import storage
    from kuulis.core.db import SessionLocal

    async with SessionLocal() as session:
        export = await session.get(DataExport, uuid.UUID(export_id))
        if export is None or export.status != "pending":
            return "skipped"
        user = await session.get(User, export.user_id)
        if user is None or user.deleted_at is not None:
            export.status = "failed"
            export.error = "account_erased"
            await session.commit()
            return export.status
        try:
            data = await services.export_data(session, user)
            key = storage.build_key(f"{services.EXPORT_FOLDER}/{user.id.hex}", "kuulis-data.json")
            await asyncio.to_thread(
                storage.put_object, key, services.export_json(data), "application/json"
            )
            link = storage.presigned_download(key, services.EXPORT_LINK_SECONDS)
        except Exception as exc:
            logger.warning("Data export %s failed", export_id, exc_info=True)
            export.status = "failed"
            export.error = getattr(exc, "code", None) or type(exc).__name__[:64]
            await session.commit()
            return export.status
        now = datetime.now(UTC)
        export.status = "ready"
        export.file_key = key
        export.completed_at = now
        export.expires_at = now + timedelta(seconds=services.EXPORT_LINK_SECONDS)
        await session.commit()
        from apps.notifications import emails
        from apps.notifications.tasks import first_name

        subject, body, text = emails.render(
            "data_export", user.locale, {"name": first_name(user), "link": link}
        )
        try:
            await send_email(user.email, subject, body, text)
        except Exception:
            logger.warning("Could not email data export %s", export_id, exc_info=True)
        return export.status


def _done_key(day: str) -> str:
    return f"{settings.APP_ENV}:privacy:retention:{day}"


async def run_retention_once() -> dict[str, int] | None:
    from apps.privacy import services
    from kuulis.core.db import SessionLocal
    from kuulis.core.redis import redis_client

    day = datetime.now(UTC).date().isoformat()
    if not await redis_client.set(_done_key(day), "1", nx=True, ex=3 * 86400):
        return None  # another worker (or an earlier run today) did it
    try:
        async with SessionLocal() as session:
            result = await services.apply_retention(session)
    except Exception:
        await redis_client.delete(_done_key(day))  # retried on the next check
        raise
    logger.info("Privacy retention: %s", result)
    return result


async def retention_loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await run_retention_once()
            await stats.beat("privacy_retention")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Privacy retention failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(retention_loop(), name="privacy-retention-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
