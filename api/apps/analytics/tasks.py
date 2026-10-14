"""Product analytics jobs (doc 19), as loops started with each worker process; Redis keys make one
process do each run:

- every minute, the supply sampler (online sessions and driver minutes per cell);
- once a day, the monthly partitions, the 13-month retention and the cohort tables.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from taskiq import TaskiqEvents, TaskiqState

from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

SAMPLE_EVERY_SECONDS = 60
_task: asyncio.Task | None = None


def _key(name: str, stamp: str) -> str:
    return f"{settings.APP_ENV}:analytics:{name}:{stamp}"


async def sample_once() -> dict[str, int] | None:
    from apps.analytics import maintenance
    from apps.config.services import get_app_config
    from kuulis.core.db import SessionLocal
    from kuulis.core.redis import redis_client

    minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
    if not await redis_client.set(_key("sample", minute), "1", nx=True, ex=120):
        return None
    async with SessionLocal() as session:
        config = await get_app_config(session)
        return await maintenance.sample_supply(session, config)


async def daily_once(force: bool = False) -> dict[str, object] | None:
    """Partitions, retention and cohorts; ``force`` runs it again today (admin "Recalcular")."""
    from apps.analytics import maintenance, product
    from apps.config.services import get_app_config
    from kuulis.core.db import SessionLocal
    from kuulis.core.redis import redis_client

    day = datetime.now(UTC).date().isoformat()
    key = _key("daily", day)
    if not await redis_client.set(key, "1", nx=True, ex=3 * 86400) and not force:
        return None
    try:
        async with SessionLocal() as session:
            created = await maintenance.ensure_partitions(session)
            removed = await maintenance.apply_retention(session)
            config = await get_app_config(session)
            cohorts = await product.refresh_cohorts(session, config)
    except Exception:
        await redis_client.delete(key)  # retried on the next pass
        raise
    result = {"partitions": created, "retention": removed, "cohorts": cohorts}
    logger.info("Product analytics daily run: %s", result)
    return result


@broker.task(task_name="analytics.refresh")
async def refresh() -> str:
    await daily_once(force=True)
    return "ok"


async def analytics_loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await sample_once()
            await daily_once()
            await stats.beat("product_analytics")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Product analytics loop failed")
        await asyncio.sleep(SAMPLE_EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(analytics_loop(), name="product-analytics-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
