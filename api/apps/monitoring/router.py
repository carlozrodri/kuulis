"""System status for staff (admin page) and Prometheus metrics for scrapers."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import PlainTextResponse

from apps.monitoring import checks
from apps.monitoring.schemas import SystemHealth
from apps.realtime.manager import manager
from apps.rides import presence
from apps.users.dependencies import Can, DBSession
from kuulis.core.exceptions import NotFoundError
from kuulis.settings import settings

router = APIRouter(prefix="/admin/system", tags=["monitoring"])
metrics_router = APIRouter(tags=["monitoring"])

STATUS_VALUE = {"ok": 1, "warning": 1, "down": 0}


@router.get("/health", response_model=SystemHealth)
async def system_health(_: Can("system.view"), session: DBSession) -> SystemHealth:
    return await checks.collect(session)


def _line(name: str, value: float | int | None, labels: dict[str, str] | None = None) -> str | None:
    if value is None:
        return None
    label = ",".join(f'{k}="{v}"' for k, v in (labels or {}).items())
    return f"kuulis_{name}{{{label}}} {value}" if label else f"kuulis_{name} {value}"


@metrics_router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics(
    session: DBSession, authorization: Annotated[str | None, Header()] = None
) -> PlainTextResponse:
    """Prometheus text format, behind ``Authorization: Bearer <METRICS_TOKEN>``."""
    expected = f"Bearer {settings.METRICS_TOKEN}"
    if not settings.METRICS_TOKEN or not secrets.compare_digest(authorization or "", expected):
        raise NotFoundError()
    health = await checks.collect(session)
    env = {"env": settings.APP_ENV}
    lines = [
        *(
            _line("service_up", STATUS_VALUE[s.status], {**env, "service": s.name})
            for s in health.services
            if s.status != "off"
        ),
        *(
            _line("service_latency_ms", s.latency_ms, {**env, "service": s.name})
            for s in health.services
        ),
        *(
            _line("loop_up", STATUS_VALUE[lp.status], {**env, "loop": lp.name})
            for lp in health.loops
        ),
        _line("http_requests_5m", health.traffic.requests_5m, env),
        _line("http_errors_5m", health.traffic.errors_5m, env),
        _line("http_avg_ms_5m", health.traffic.avg_ms_5m, env),
        _line("tasks_pending", health.queues.taskiq_pending, env),
        _line("dispatch_due", health.queues.dispatch_due, env),
        _line("dispatch_overdue", health.queues.dispatch_overdue, env),
        _line("rides_searching", health.rides.searching, env),
        _line("rides_requested_1h", health.rides.requested_last_hour, env),
        _line("rides_no_drivers_1h", health.rides.no_drivers_last_hour, env),
        _line("drivers_online", len(await presence.online_entries()), env),
        _line("websockets_process", manager.active_connections, env),
        _line("disk_used_percent", health.disk_used_percent, env),
        _line("alerts_open", len(health.alerts), env),
    ]
    return PlainTextResponse("\n".join(line for line in lines if line) + "\n")
