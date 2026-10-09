"""Ride jobs. The dispatch loop starts with each worker process (see ``dispatch`` docstring)."""

import uuid

from taskiq import TaskiqEvents, TaskiqState

from apps.geo import clients as geo_clients
from apps.rides import dispatch
from kuulis.settings import settings
from kuulis.tasks import broker


@broker.task(task_name="rides.dispatch")
async def dispatch_ride(ride_id: str) -> None:
    await dispatch.advance(uuid.UUID(ride_id))


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start_dispatch_loop(_: TaskiqState) -> None:
    # Tests drive the dispatcher explicitly (the in-memory broker also fires this event).
    if settings.APP_ENV != "test":
        dispatch.start()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop_dispatch_loop(_: TaskiqState) -> None:
    await dispatch.stop()
    await geo_clients.aclose()
