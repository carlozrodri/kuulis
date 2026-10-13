"""The driver's path during a ride: buffered in Redis while the ride lasts, written to
``ride_tracks`` in one row when it ends (never one database write per location message).

Redis keys (prefixed with ``<APP_ENV>:safety``):

- ``track:<ride_id>``     list  "lat,lng,ts" every ``SAMPLE_SECONDS`` at most
- ``track_thr:<ride_id>`` str   sampling throttle
"""

import time
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.safety.geo import distance_m
from kuulis.core.redis import redis_client
from kuulis.settings import settings

PREFIX = f"{settings.APP_ENV}:safety"
SAMPLE_SECONDS = 5
TTL_SECONDS = 24 * 3600  # a ride whose end is never flushed does not leave keys behind
MIN_STEP_M = 15  # thinning: points closer than this to the previous kept one are dropped
MAX_POINTS = 5000  # ~7 h at one point every 5 s


def track_key(ride_id: uuid.UUID | str) -> str:
    return f"{PREFIX}:track:{ride_id}"


Point = tuple[float, float, float]  # lat, lng, unix seconds


async def record(ride_id: str, lat: float, lng: float) -> None:
    """Called for every driver location while a ride is assigned (throttled to one per 5 s)."""
    if not await redis_client.set(
        f"{PREFIX}:track_thr:{ride_id}", "1", nx=True, px=SAMPLE_SECONDS * 1000 - 200
    ):
        return
    key = track_key(ride_id)
    async with redis_client.pipeline(transaction=False) as pipe:
        pipe.rpush(key, f"{lat:.6f},{lng:.6f},{time.time():.0f}")
        pipe.ltrim(key, -MAX_POINTS, -1)
        pipe.expire(key, TTL_SECONDS)
        await pipe.execute()


def _parse(raw: list[str]) -> list[Point]:
    points = []
    for item in raw:
        lat, lng, ts = item.split(",")
        points.append((float(lat), float(lng), float(ts)))
    return points


async def recent(ride_id: uuid.UUID | str, seconds: int) -> list[Point]:
    """Points of the last ``seconds`` (oldest first)."""
    count = seconds // SAMPLE_SECONDS + 10
    points = _parse(await redis_client.lrange(track_key(ride_id), -count, -1))
    since = time.time() - seconds
    return [p for p in points if p[2] >= since]


async def buffered(ride_id: uuid.UUID | str) -> list[Point]:
    return _parse(await redis_client.lrange(track_key(ride_id), 0, -1))


def thin(points: list[Point]) -> list[list[float]]:
    """Keeps a point only when it moved ``MIN_STEP_M`` from the last kept one (plus the last)."""
    kept: list[Point] = []
    for point in points:
        if not kept or distance_m(kept[-1][0], kept[-1][1], point[0], point[1]) >= MIN_STEP_M:
            kept.append(point)
    if points and kept[-1] is not points[-1]:
        kept.append(points[-1])
    return [[round(lat, 6), round(lng, 6), int(ts)] for lat, lng, ts in kept]


async def flush(session: AsyncSession, ride_id: uuid.UUID) -> int:
    """Writes the buffered path of a finished ride (once) and drops the buffer. The caller
    commits."""
    from apps.safety.models import RideTrack

    points = thin(await buffered(ride_id))
    if points:
        await session.execute(
            insert(RideTrack)
            .values(id=uuid.uuid4(), ride_id=ride_id, points=points, point_count=len(points))
            .on_conflict_do_nothing(index_elements=[RideTrack.ride_id])
        )
    await redis_client.delete(track_key(ride_id))
    return len(points)
