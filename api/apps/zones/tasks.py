"""Rebuilds the demand map every minute, tells the connected drivers and pushes "busy zone"
alerts (doc 21)."""

import asyncio
import contextlib
import logging
import uuid
from typing import Any

import orjson
from sqlalchemy import select
from taskiq import TaskiqEvents, TaskiqState

from apps.config.schemas import AppConfig
from apps.config.services import get_app_config
from apps.realtime.manager import publish
from apps.rides import presence
from apps.safety.geo import distance_m
from apps.zones import demand
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

EVERY_SECONDS = 60
LOCK = f"{settings.APP_ENV}:demand:lock"
UPDATED_EVENT = "demand.updated"
# locale -> (title with a place, title without one, body)
TEXTS = {
    "es": (
        "Mucha demanda en {name}",
        "Mucha demanda cerca de ti",
        "Hay pasajeros esperando cerca de ti. Toca para ver el mapa.",
    ),
    "en": (
        "High demand in {name}",
        "High demand near you",
        "Riders are waiting near you. Tap to see the map.",
    ),
}
_task: asyncio.Task | None = None


def alert_key(user_id: str) -> str:
    return f"{demand.PREFIX}:alert:{user_id}"


def _signature(snapshot: dict[str, Any] | None) -> list[tuple[str, int, int, int]]:
    cells = (snapshot or {}).get("cells") or []
    return [(c["cell"], c["level"], c["requests"], c["unmatched"]) for c in cells]


async def run_once() -> dict[str, Any] | None:
    """One worker at a time. Returns the new map (None when another worker built it)."""
    if not await redis_client.set(LOCK, "1", nx=True, ex=EVERY_SECONDS - 5):
        return None
    async with SessionLocal() as session:
        config = await get_app_config(session)
    if not config.demand.enabled:
        return None
    raw = await redis_client.get(demand.SNAPSHOT_KEY)
    before = orjson.loads(raw) if raw else None
    after = await demand.compute(config)
    online = list(await presence.online_entries())
    if online and _signature(before) != _signature(after):
        await publish(UPDATED_EVENT, {"updated_at": after["updated_at"]}, online)
    if config.demand.notify:
        was_hot = {c["cell"] for c in (before or {}).get("cells", []) if c["level"] == 3}
        new_hot = [c for c in after["cells"] if c["level"] == 3 and c["cell"] not in was_hot]
        for cell in new_hot:
            await alert_drivers(config, cell)
    return after


async def alert_drivers(config: AppConfig, cell: dict[str, Any]) -> list[str]:
    """Pushes to free drivers within ``notify_radius_m`` who did not get one recently."""
    from apps.notifications.models import NotificationPreference
    from apps.notifications.tasks import send_push
    from apps.users.models import User

    lat, lng = cell["center"]
    entries = await presence.online_entries()
    locations = await presence.get_locations(list(entries))
    near = []
    for uid, loc in locations.items():
        if not loc.fresh or distance_m(lat, lng, loc.lat, loc.lng) > config.demand.notify_radius_m:
            continue
        if await redis_client.exists(presence.active_key(uid), presence.offer_key(uid)):
            continue  # on a ride or deciding an offer
        near.append(uid)
    if not near:
        return []
    ids = [uuid.UUID(u) for u in near]
    async with SessionLocal() as session:
        muted = set(
            (
                await session.scalars(
                    select(NotificationPreference.user_id).where(
                        NotificationPreference.user_id.in_(ids),
                        NotificationPreference.demand_alerts.is_(False),
                    )
                )
            ).all()
        )
        locales = dict(
            (await session.execute(select(User.id, User.locale).where(User.id.in_(ids)))).all()
        )
    ttl = config.demand.notify_every_minutes * 60
    by_locale: dict[str, list[str]] = {}
    for uid in ids:
        if uid in muted:
            continue
        if not await redis_client.set(alert_key(str(uid)), "1", nx=True, ex=ttl):
            continue
        locale = "en" if (locales.get(uid) or "es").startswith("en") else "es"
        by_locale.setdefault(locale, []).append(str(uid))
    name = cell.get("name") or ""
    data = {"type": "demand", "name": name, "lat": lat, "lng": lng}
    for locale, users in by_locale.items():
        named, unnamed, body = TEXTS[locale]
        await send_push.kiq(users, named.format(name=name) if name else unnamed, body, data)
    sent = [u for users in by_locale.values() for u in users]
    if sent:
        logger.info("Demand alert for %s sent to %s drivers", name or cell["cell"], len(sent))
    return sent


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            await run_once()
            await stats.beat("demand")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Demand loop failed")
        await asyncio.sleep(EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="demand-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
