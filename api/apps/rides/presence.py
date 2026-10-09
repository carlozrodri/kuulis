"""Driver presence and live location in Redis.

Keys (all prefixed with ``<APP_ENV>:drivers``):

- ``online``            hash  user_id -> {profile_id, vehicle_type, since}
- ``loc``               hash  user_id -> {lat, lng, heading, speed, ts}   (last seen)
- ``geo:<vehicle_type>`` GEO   user_id                                     (nearest search)
- ``offer:<user_id>``   str   ride_id while the driver holds an open offer (one at a time)
- ``active:<user_id>``  str   "<ride_id>|<passenger_id>" while assigned to a ride

Drivers are identified by their *user* id everywhere (sockets, rides, offers).
"""

import time
import uuid
from dataclasses import dataclass
from typing import Any

import orjson

from apps.drivers.models import VehicleType
from apps.realtime.manager import publish
from kuulis.core.redis import redis_client
from kuulis.settings import settings

PREFIX = f"{settings.APP_ENV}:drivers"
ONLINE_KEY = f"{PREFIX}:online"
LOC_KEY = f"{PREFIX}:loc"
STALE_AFTER_SECONDS = 60  # no location for this long -> no offers
MIN_LOCATION_INTERVAL = 1.0  # ignore faster updates (abuse / buggy clients)
FORWARD_INTERVAL_MS = 2000  # ride.driver_location to the passenger at most every 2 s

# Compare-and-delete: release a key only if it still holds our value.
_RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""


def geo_key(vehicle_type: VehicleType | str) -> str:
    return f"{PREFIX}:geo:{VehicleType(vehicle_type).value}"


def offer_key(user_id: uuid.UUID | str) -> str:
    return f"{PREFIX}:offer:{user_id}"


def active_key(user_id: uuid.UUID | str) -> str:
    return f"{PREFIX}:active:{user_id}"


def _throttle_key(ride_id: str) -> str:
    return f"{settings.APP_ENV}:rides:locfwd:{ride_id}"


@dataclass(frozen=True)
class Location:
    lat: float
    lng: float
    heading: float | None
    speed: float | None
    ts: float

    @property
    def fresh(self) -> bool:
        return time.time() - self.ts <= STALE_AFTER_SECONDS


def _loads(raw: str | None) -> dict[str, Any] | None:
    return orjson.loads(raw) if raw else None


def _location(raw: str | None) -> Location | None:
    data = _loads(raw)
    if not data:
        return None
    return Location(
        lat=data["lat"],
        lng=data["lng"],
        heading=data.get("heading"),
        speed=data.get("speed"),
        ts=data["ts"],
    )


# --- Online / offline --------------------------------------------------------------------------


async def go_online(
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    vehicle_type: VehicleType,
    lat: float,
    lng: float,
) -> None:
    uid = str(user_id)
    previous = _loads(await redis_client.hget(ONLINE_KEY, uid))
    entry = {
        "profile_id": str(profile_id),
        "vehicle_type": vehicle_type.value,
        "since": (previous or {}).get("since") or time.time(),
    }
    async with redis_client.pipeline(transaction=True) as pipe:
        for other in VehicleType:
            if other != vehicle_type:
                pipe.zrem(geo_key(other), uid)
        pipe.hset(ONLINE_KEY, uid, orjson.dumps(entry).decode())
        pipe.hset(LOC_KEY, uid, _loc_json(lat, lng, None, None))
        pipe.geoadd(geo_key(vehicle_type), [lng, lat, uid])
        await pipe.execute()


async def go_offline(user_id: uuid.UUID | str) -> None:
    uid = str(user_id)
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.hdel(ONLINE_KEY, uid)
        pipe.hdel(LOC_KEY, uid)
        for vehicle_type in VehicleType:
            pipe.zrem(geo_key(vehicle_type), uid)
        await pipe.execute()


async def is_online(user_id: uuid.UUID | str) -> bool:
    return bool(await redis_client.hexists(ONLINE_KEY, str(user_id)))


async def online_entries() -> dict[str, dict[str, Any]]:
    raw = await redis_client.hgetall(ONLINE_KEY)
    return {uid: orjson.loads(value) for uid, value in raw.items()}


# --- Locations ---------------------------------------------------------------------------------


def _loc_json(lat: float, lng: float, heading: float | None, speed: float | None) -> str:
    return orjson.dumps(
        {"lat": lat, "lng": lng, "heading": heading, "speed": speed, "ts": time.time()}
    ).decode()


async def get_location(user_id: uuid.UUID | str) -> Location | None:
    return _location(await redis_client.hget(LOC_KEY, str(user_id)))


async def get_locations(user_ids: list[str]) -> dict[str, Location]:
    if not user_ids:
        return {}
    values = await redis_client.hmget(LOC_KEY, user_ids)
    return {
        uid: loc
        for uid, raw in zip(user_ids, values, strict=True)
        if (loc := _location(raw)) is not None
    }


async def nearby(
    vehicle_type: VehicleType, lat: float, lng: float, radius_m: int, count: int
) -> list[tuple[str, float]]:
    """Online drivers of a type around a point, nearest first: [(user_id, distance_m)]."""
    rows = await redis_client.geosearch(
        geo_key(vehicle_type),
        longitude=lng,
        latitude=lat,
        radius=radius_m,
        unit="m",
        sort="ASC",
        count=count,
        withdist=True,
    )
    return [(member, float(dist)) for member, dist in rows]


def _number(value: Any, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    value = float(value)
    return value if low <= value <= high else None


async def handle_location(user_id: str, message: dict[str, Any]) -> None:
    """``{"type": "location", lat, lng, heading?, speed?}`` from a driver's socket.

    Stored only for drivers that are online or assigned to a ride; forwarded to the passenger
    (throttled) while a ride is assigned / in progress.
    """
    lat = _number(message.get("lat"), -90, 90)
    lng = _number(message.get("lng"), -180, 180)
    if lat is None or lng is None:
        return
    heading = _number(message.get("heading"), 0, 360)
    speed = _number(message.get("speed"), 0, 100)

    async with redis_client.pipeline(transaction=False) as pipe:
        pipe.hget(ONLINE_KEY, user_id)
        pipe.get(active_key(user_id))
        pipe.hget(LOC_KEY, user_id)
        online_raw, active, last_raw = await pipe.execute()
    if not online_raw and not active:
        return
    last = _location(last_raw)
    if last and time.time() - last.ts < MIN_LOCATION_INTERVAL:
        return

    online = _loads(online_raw)
    async with redis_client.pipeline(transaction=False) as pipe:
        pipe.hset(LOC_KEY, user_id, _loc_json(lat, lng, heading, speed))
        if online:
            pipe.geoadd(geo_key(online["vehicle_type"]), [lng, lat, user_id])
        await pipe.execute()

    if active:
        ride_id, passenger_id = active.split("|", 1)
        if await redis_client.set(_throttle_key(ride_id), "1", nx=True, px=FORWARD_INTERVAL_MS):
            await publish(
                "ride.driver_location",
                {"ride_id": ride_id, "lat": lat, "lng": lng, "heading": heading},
                user_ids=[passenger_id],
            )


# --- Offer reservation and active ride ---------------------------------------------------------


async def reserve_offer(user_id: uuid.UUID | str, ride_id: uuid.UUID, ttl_seconds: int) -> bool:
    """Atomically claims the driver for one offer; False if another ride holds them."""
    return bool(
        await redis_client.set(offer_key(user_id), str(ride_id), nx=True, ex=max(ttl_seconds, 1))
    )


async def release_offer(user_id: uuid.UUID | str, ride_id: uuid.UUID) -> None:
    await redis_client.eval(_RELEASE, 1, offer_key(user_id), str(ride_id))


async def set_active_ride(
    driver_id: uuid.UUID, ride_id: uuid.UUID, passenger_id: uuid.UUID
) -> None:
    # Expires on its own in case a cleanup is missed; rides do not last a day.
    await redis_client.set(active_key(driver_id), f"{ride_id}|{passenger_id}", ex=24 * 3600)


async def clear_active_ride(driver_id: uuid.UUID | None, ride_id: uuid.UUID) -> None:
    if driver_id is None:
        return
    key = active_key(driver_id)
    raw = await redis_client.get(key)
    if raw and raw.split("|", 1)[0] == str(ride_id):
        await redis_client.delete(key)


async def cleanup_stale(max_age_seconds: int) -> list[str]:
    """Takes offline drivers that sent no location for ``max_age_seconds`` (app killed)."""
    entries = await online_entries()
    if not entries:
        return []
    uids = list(entries)
    locations = await get_locations(uids)
    now = time.time()
    removed: list[str] = []
    for uid in uids:
        loc = locations.get(uid)
        if (loc is None or now - loc.ts > max_age_seconds) and not await redis_client.exists(
            active_key(uid)
        ):
            await go_offline(uid)
            removed.append(uid)
    return removed
