"""Fake GPS (doc 16), called from the driver location messages. The hot path only does a little
math; Redis and the database are touched when something looks wrong."""

import contextlib
import logging
import uuid

from apps.realtime.manager import publish
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

PREFIX = f"{settings.APP_ENV}:risk"
MOCK_EVENT = "driver.mock_location"
MOCK_COOLDOWN_S = 600  # one alert and one notice per driver in this time
JUMP_WINDOW_S = 600


async def on_mocked(user_id: str, lat: float, lng: float, *, active: bool) -> None:
    """A position from a mock location app. Off a ride the driver goes offline at once (no more
    offers); on a ride they finish it. Raises one alert and one notice per cooldown."""
    from apps.rides import presence

    if not active:
        await presence.go_offline(user_id)
    if not await redis_client.set(f"{PREFIX}:mock:{user_id}", "1", nx=True, ex=MOCK_COOLDOWN_S):
        return
    from apps.risk import services as risk
    from apps.wallet import notify

    uid = uuid.UUID(user_id)
    try:
        async with SessionLocal() as session:
            await risk.gps_signal(
                session, uid, "mocked", {"lat": round(lat, 5), "lng": round(lng, 5), "ride": active}
            )
            await notify.send(session, uid, "mock_location", kind="risk", templates=risk.TEMPLATES)
            await session.commit()
    except Exception:
        logger.exception("Could not record the mock location of %s", user_id)
    await publish(MOCK_EVENT, {"online": False if not active else None}, user_ids=[user_id])


async def on_jump(user_id: str, distance: float, seconds: float) -> None:
    """An impossible jump between two positions. GPS glitches happen, so only several in
    ``JUMP_WINDOW_S`` raise an alert; the driver stays online."""
    key = f"{PREFIX}:jumps:{user_id}"
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, JUMP_WINDOW_S, nx=True)
        count, _ = await pipe.execute()
    from apps.config.services import get_app_config
    from apps.risk import services as risk

    with contextlib.suppress(Exception):
        async with SessionLocal() as session:
            if int(count) != (await get_app_config(session)).risk.jump_alerts:
                return
            await risk.gps_signal(
                session,
                uuid.UUID(user_id),
                "jumps",
                {"jumps": int(count), "last_m": round(distance), "last_s": round(seconds, 1)},
            )
            await session.commit()
