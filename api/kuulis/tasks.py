"""Background jobs (Taskiq on Redis Streams), the equivalent of Django's celery.py.

Each app declares its jobs in ``apps/<app>/tasks.py`` with ``@broker.task``.
Run a worker with:   taskiq worker kuulis.tasks:broker <TASK_MODULES...>  (see manage.py worker)
Run the scheduler:   taskiq scheduler kuulis.tasks:scheduler
"""

from taskiq import InMemoryBroker, TaskiqEvents, TaskiqScheduler, TaskiqState
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from kuulis.settings import settings

# Keep in sync with docker/entrypoint.sh (the container lists the modules explicitly).
TASK_MODULES = [
    "apps.users.tasks",
    "apps.notifications.tasks",
    "apps.rides.tasks",
    "apps.rates.tasks",
    "apps.wallet.tasks",
]

if settings.APP_ENV == "test":
    broker = InMemoryBroker(await_inplace=True)
else:
    broker = RedisStreamBroker(
        url=str(settings.REDIS_URL), queue_name=f"kuulis:{settings.APP_ENV}:tasks"
    ).with_result_backend(
        RedisAsyncResultBackend(redis_url=str(settings.REDIS_URL), result_ex_time=3600)
    )

scheduler = TaskiqScheduler(broker=broker, sources=[LabelScheduleSource(broker)])


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _worker_startup(_: TaskiqState) -> None:
    from kuulis.core.logging import configure_logging
    from kuulis.core.sentry import init_sentry

    configure_logging()
    init_sentry()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _worker_shutdown(_: TaskiqState) -> None:
    from kuulis.core.db import engine

    await engine.dispose()
