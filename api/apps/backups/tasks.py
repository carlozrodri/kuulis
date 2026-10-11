"""Backup loop in the worker (only with the backup bucket configured). Each minute it checks what is
due; a Redis lock makes one worker process do each job:

- database dump every BACKUP_EVERY_MINUTES;
- after 03:00 Caracas, once a day: ledger CSV and file mirror;
- on Sundays after 04:00 Caracas: restore check.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from taskiq import TaskiqEvents, TaskiqState

from apps.backups import services
from apps.backups.store import AppFiles, backup_store
from apps.monitoring import stats
from kuulis.core.calendar import local_now
from kuulis.core.redis import redis_client
from kuulis.core.storage import get_s3_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 60
LOCK_KEY = f"{settings.APP_ENV}:backups:lock"
DONE_KEY = f"{settings.APP_ENV}:backups:done:"  # + job + date
LOCK_SECONDS = 30 * 60  # longest a job may hold the turn (a large restore check)
DAILY_HOUR = 3
RESTORE_WEEKDAY, RESTORE_HOUR = 6, 4  # Sunday 04:00

_task: asyncio.Task | None = None


async def _due_once(job: str, day: str) -> bool:
    return bool(await redis_client.set(f"{DONE_KEY}{job}:{day}", "1", nx=True, ex=8 * 86400))


async def run_due() -> list[str]:
    """Runs whatever is due. Returns the jobs it ran (empty when another process has the turn)."""
    if not await redis_client.set(LOCK_KEY, "1", nx=True, ex=LOCK_SECONDS):
        return []
    ran = []
    try:
        store = backup_store()
        state = await services.status()
        last = state.get("last_backup_at")
        age = (datetime.now(UTC) - datetime.fromisoformat(last)).total_seconds() if last else None
        if age is None or age >= settings.BACKUP_EVERY_MINUTES * 60 - 30:
            await _job("database", services.backup_database(store))
            ran.append("database")

        now = local_now()
        today = now.date().isoformat()
        if now.hour >= DAILY_HOUR and await _due_once("daily", today):
            await _job("ledger", services.export_ledger(store))
            if settings.BACKUP_MIRROR_FILES and settings.storage_enabled:
                await _job("files", services.mirror_files(store, AppFiles(get_s3_client())))
            ran.append("daily")
        if (
            now.weekday() == RESTORE_WEEKDAY
            and now.hour >= RESTORE_HOUR
            and await _due_once("restore", today)
        ):
            try:
                await services.restore_check(store)
            except Exception as error:
                logger.exception("Restore check failed")
                await services.record(
                    last_restore_check_at=datetime.now(UTC).isoformat(),
                    last_restore_ok=False,
                    last_restore={"error": str(error)[:500]},
                )
            ran.append("restore")
    finally:
        await redis_client.delete(LOCK_KEY)
    return ran


async def _job(name: str, work) -> None:
    """One failing job does not stop the others; the error is kept for the status page."""
    try:
        await work
        await services.record(**{f"last_{name}_error": None})
    except Exception as error:
        logger.exception("Backup job %s failed", name)
        await services.record(**{f"last_{name}_error": str(error)[:500]})


async def loop() -> None:
    while True:
        try:
            await run_due()
            await stats.beat("backups")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Backup loop failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and settings.backups_configured and _task is None:
        _task = asyncio.create_task(loop(), name="backups-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
