"""System health snapshot (admin page, metrics) and the alert rules evaluated on it."""

import asyncio
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.analytics.services import _real_rides
from apps.backups import services as backup_services
from apps.geo.clients import http
from apps.monitoring import alerts, stats
from apps.monitoring.schemas import (
    BackupsHealth,
    LoopHealth,
    Queues,
    RidesHealth,
    ServiceHealth,
    SystemHealth,
    Traffic,
)
from apps.rates import services as rates
from apps.rides import dispatch
from apps.rides.models import Ride, RideStatus
from apps.wallet import binance
from kuulis.core.redis import redis_client
from kuulis.settings import settings

TASK_QUEUE = f"kuulis:{settings.APP_ENV}:tasks"  # kuulis.tasks broker queue
OSRM_PROBE = "/route/v1/driving/-66.88,10.49;-66.85,10.50?overview=false"
PHOTON_PROBE = "/api?q=caracas&limit=1"
SLOW_SERVICE_MS = 1000

# Thresholds (Carlos' plan, docs/produccion/03).
ERROR_RATE_LIMIT = 0.02
ERROR_RATE_MIN_REQUESTS = 50
NO_DRIVERS_LIMIT = 0.30
NO_DRIVERS_MIN_RIDES = 10
DISPATCH_OVERDUE_SECONDS = 60
TASKS_PENDING_LIMIT = 500
DISK_LIMIT_PERCENT = 85


def expected_loops() -> dict[str, int]:
    """Background loops that must be beating, with the age (seconds) after which they are late."""
    loops = {
        "dispatch": 120,
        "subscriptions": 15 * 60,  # runs every 5 min
        "account_erasure": 3 * 3600,  # runs every hour
        "privacy_retention": 3 * 3600,  # checks every hour, works once a day
        "monitoring": 5 * 60,
        "safety": 5 * 60,  # anomaly checks every 30 s
        "driver_expirations": 3600,  # checks every 10 min, works once a day
        "support_sla": 5 * 60,  # every minute
        "notifications": 5 * 60,  # every 30 s (campaigns, receipts, daily cleanup)
        "quality": 5 * 60,  # beats every minute, recomputes every 10 min
    }
    if settings.RATES_ENABLED:
        loops["rates"] = 10 * 60  # checks every minute which source is due
    if binance.enabled():
        loops["binance"] = 10 * 60
    if settings.backups_configured:
        loops["backups"] = 10 * 60  # checks every minute what is due
    return loops


async def _timed(name: str, check) -> ServiceHealth:
    started = time.perf_counter()
    try:
        ok = await asyncio.wait_for(check(), 3)
    except Exception:
        ok = False
    latency = round((time.perf_counter() - started) * 1000, 1)
    if ok is None:
        return ServiceHealth(name=name, status="off")
    if not ok:
        return ServiceHealth(name=name, status="down", latency_ms=latency)
    return ServiceHealth(
        name=name, status="warning" if latency > SLOW_SERVICE_MS else "ok", latency_ms=latency
    )


async def services(session: AsyncSession) -> list[ServiceHealth]:
    async def database() -> bool:
        await session.execute(text("SELECT 1"))
        return True

    async def redis() -> bool:
        return bool(await redis_client.ping())

    def provider(base_url: str, path: str):
        async def check() -> bool | None:
            if not base_url:
                return None
            try:
                response = await http().get(f"{base_url.rstrip('/')}{path}", timeout=3)
            except httpx.HTTPError:
                return False
            return response.status_code == 200

        return check

    # The database probe shares the session, so it runs first and alone.
    results = [await _timed("database", database)]
    results += await asyncio.gather(
        _timed("redis", redis),
        _timed("osrm", provider(settings.OSRM_URL, OSRM_PROBE)),
        _timed("photon", provider(settings.PHOTON_URL, PHOTON_PROBE)),
    )
    return results


async def loops() -> list[LoopHealth]:
    try:
        beats = await stats.heartbeats()
    except Exception:
        beats = {}
    now = time.time()
    result = []
    for name, max_age in expected_loops().items():
        beat = beats.get(name)
        age = now - beat if beat else None
        if age is None or age > 2 * max_age:
            status = "down"
        elif age > max_age:
            status = "warning"
        else:
            status = "ok"
        result.append(
            LoopHealth(
                name=name,
                status=status,
                last_beat_at=datetime.fromtimestamp(beat, UTC) if beat else None,
                max_age_seconds=max_age,
            )
        )
    return result


async def queues() -> Queues:
    try:
        groups = await redis_client.xinfo_groups(TASK_QUEUE)
        pending = sum(int(g.get("pending") or 0) + int(g.get("lag") or 0) for g in groups)
    except Exception:
        pending = None  # the stream does not exist until the first task
    now = time.time()
    return Queues(
        taskiq_pending=pending,
        dispatch_due=await redis_client.zcard(dispatch.DUE_KEY),
        dispatch_overdue=await redis_client.zcount(
            dispatch.DUE_KEY, "-inf", now - DISPATCH_OVERDUE_SECONDS
        ),
    )


async def traffic() -> Traffic:
    totals = await stats.http_totals(5)
    requests = int(totals["requests"])
    errors = int(totals["errors"])
    return Traffic(
        requests_5m=requests,
        errors_5m=errors,
        error_rate_5m=round(errors / requests, 4) if requests else 0.0,
        avg_ms_5m=totals["avg_ms"],
    )


async def rides(session: AsyncSession) -> RidesHealth:
    since = datetime.now(UTC) - timedelta(hours=1)
    searching = await session.scalar(
        select(func.count(Ride.id)).where(Ride.status == RideStatus.SEARCHING)
    )
    total, no_drivers = (
        await session.execute(
            select(
                func.count(Ride.id),
                func.count(Ride.id).filter(Ride.status == RideStatus.NO_DRIVERS),
            ).where(Ride.requested_at >= since, *_real_rides())
        )
    ).one()
    return RidesHealth(
        searching=searching or 0, requested_last_hour=total, no_drivers_last_hour=no_drivers
    )


async def backups() -> BackupsHealth:
    if not settings.backups_configured:
        return BackupsHealth(configured=False)
    try:
        state = await backup_services.status()
    except Exception:
        state = {}
    errors = {
        key.removeprefix("last_").removesuffix("_error"): value
        for key, value in state.items()
        if key.endswith("_error") and value
    }
    fields = {
        k: state.get(k) for k in BackupsHealth.model_fields if k not in ("configured", "errors")
    }
    return BackupsHealth(configured=True, errors=errors, **fields)


def disk_used_percent() -> float | None:
    try:
        usage = shutil.disk_usage("/")
    except OSError:
        return None
    return round(usage.used / usage.total * 100, 1)


async def collect(session: AsyncSession) -> SystemHealth:
    current = await rates.current_rates(session)
    return SystemHealth(
        env=settings.APP_ENV,
        commit=settings.SOURCE_COMMIT[:12] or None,
        checked_at=datetime.now(UTC),
        services=await services(session),
        loops=await loops(),
        queues=await queues(),
        traffic=await traffic(),
        rides=await rides(session),
        stale_rates=[n for n, v in current.model_dump().items() if v and v["stale"]],
        disk_used_percent=disk_used_percent(),
        backups=await backups(),
        alerts=await alerts.open_alerts(),
    )


@dataclass(frozen=True)
class Problem:
    key: str  # stable id: the same problem keeps the same key until it is solved
    message: str


SERVICE_NAMES = {
    "database": "Postgres",
    "redis": "Redis",
    "osrm": "OSRM (rutas)",
    "photon": "Photon (direcciones)",
}


def problems(health: SystemHealth) -> list[Problem]:
    """The alert rules. Messages are in Spanish: they go to Carlos' Telegram as they are."""
    found = []
    for service in health.services:
        if service.status == "down":
            found.append(
                Problem(f"service:{service.name}", f"{SERVICE_NAMES[service.name]} no responde")
            )

    late = [loop for loop in health.loops if loop.status == "down" and loop.name != "monitoring"]
    worker_loops = [loop for loop in health.loops if loop.name != "monitoring"]
    if late and len(late) == len(worker_loops):
        found.append(
            Problem("worker", "El worker no está corriendo (ningún proceso de fondo late)")
        )
    else:
        for loop in late:
            found.append(Problem(f"loop:{loop.name}", f"El proceso de fondo '{loop.name}' no late"))

    traffic = health.traffic
    if traffic.requests_5m >= ERROR_RATE_MIN_REQUESTS and traffic.error_rate_5m > ERROR_RATE_LIMIT:
        found.append(
            Problem(
                "http:5xx",
                f"Errores 500: {traffic.error_rate_5m:.1%} de {traffic.requests_5m} peticiones "
                "en 5 min",
            )
        )
    for name in health.stale_rates:
        found.append(Problem(f"rate:{name}", f"La tasa {name} está vencida"))

    queues = health.queues
    if queues.dispatch_overdue:
        found.append(
            Problem(
                "queue:dispatch", f"Despacho atascado: {queues.dispatch_overdue} viajes sin atender"
            )
        )
    if queues.taskiq_pending is not None and queues.taskiq_pending > TASKS_PENDING_LIMIT:
        found.append(
            Problem("queue:tasks", f"Cola de tareas atascada: {queues.taskiq_pending} pendientes")
        )
    if health.disk_used_percent is not None and health.disk_used_percent > DISK_LIMIT_PERCENT:
        found.append(Problem("disk", f"Disco al {health.disk_used_percent:.0f} %"))

    backup = health.backups
    if backup.configured:
        late_after = timedelta(minutes=2 * settings.BACKUP_EVERY_MINUTES + 5)
        if backup.last_backup_at is None or health.checked_at - backup.last_backup_at > late_after:
            found.append(Problem("backup:stale", "No hay backup reciente de la base de datos"))
        if backup.last_restore_ok is False:
            found.append(Problem("backup:restore", "Falló la prueba de restauración del backup"))
        for job, error in backup.errors.items():
            found.append(Problem(f"backup:{job}", f"Falla el backup '{job}': {error[:120]}"))

    rides = health.rides
    if (
        rides.requested_last_hour >= NO_DRIVERS_MIN_RIDES
        and rides.no_drivers_last_hour / rides.requested_last_hour > NO_DRIVERS_LIMIT
    ):
        found.append(
            Problem(
                "rides:no_drivers",
                f"{rides.no_drivers_last_hour} de {rides.requested_last_hour} viajes de la última "
                "hora quedaron sin motorizado",
            )
        )
    return found
