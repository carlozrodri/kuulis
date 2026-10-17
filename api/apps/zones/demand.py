"""The drivers' demand map (doc 21): H3 cells (resolution 8, ~1 km across) counted in Redis.

Keys (prefixed with ``<APP_ENV>:demand``):

- ``req:<minute>``  hash  cell -> ride requests that minute
- ``unm:<minute>``  hash  cell -> searches that ended without a driver that minute
- ``snapshot``      str   the last computed map (JSON), rebuilt every minute by the worker
- ``alert:<user>``  str   set while a driver may not get another demand push

Only counts per cell leave the server: never a passenger's position.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

import h3
import orjson

from apps.config.schemas import AppConfig, DemandSettings
from apps.rides import presence
from apps.safety.geo import distance_m
from apps.zones import services
from apps.zones.schemas import DemandCell, DemandSnapshot, HotSpot
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

RESOLUTION = 8
DRIVER_RINGS = 5  # cells shown around a driver (~5 km)
PREFIX = f"{settings.APP_ENV}:demand"
SNAPSHOT_KEY = f"{PREFIX}:snapshot"
SNAPSHOT_TTL = 5 * 60
BUCKET_TTL = 65 * 60  # longer than the largest window
REQUESTS, UNMATCHED = "req", "unm"


def _minute(at: float | None = None) -> int:
    return int((at if at is not None else time.time()) // 60)


def cell_of(lat: float, lng: float) -> str:
    return h3.latlng_to_cell(lat, lng, RESOLUTION)


async def record(kind: str, lat: float, lng: float, count: int = 1) -> None:
    """Counts a request (``req``) or an unmatched search (``unm``). Never breaks the caller."""
    try:
        key = f"{PREFIX}:{kind}:{_minute()}"
        async with redis_client.pipeline(transaction=False) as pipe:
            pipe.hincrby(key, cell_of(lat, lng), count)
            pipe.expire(key, BUCKET_TTL)
            await pipe.execute()
    except Exception:
        logger.warning("Could not count demand", exc_info=True)


async def _window(kind: str, minutes: int) -> dict[str, int]:
    now = _minute()
    keys = [f"{PREFIX}:{kind}:{m}" for m in range(now - minutes + 1, now + 1)]
    async with redis_client.pipeline(transaction=False) as pipe:
        for key in keys:
            pipe.hgetall(key)
        buckets = await pipe.execute()
    totals: dict[str, int] = {}
    for bucket in buckets:
        for cell, value in bucket.items():
            totals[cell] = totals.get(cell, 0) + int(value)
    return totals


async def _drivers_per_cell() -> dict[str, int]:
    entries = await presence.online_entries()
    locations = await presence.get_locations(list(entries))
    per_cell: dict[str, int] = {}
    for loc in locations.values():
        if loc.fresh:
            cell = cell_of(loc.lat, loc.lng)
            per_cell[cell] = per_cell.get(cell, 0) + 1
    return per_cell


def level(requests: int, unmatched: int, drivers: int, hot: int) -> int:
    if requests >= hot and (unmatched > 0 or requests > 2 * drivers):
        return 3
    if requests >= hot:
        return 2
    return 1


async def _name(zones: list, lat: float, lng: float) -> str | None:
    """The zone containing the point, else the neighbourhood from Photon."""
    from apps.geo import clients as geo

    for kind in ("pickup", "surge", "restricted"):
        found = next((z for z in zones if z.kind == kind and z.contains(lat, lng)), None)
        if found:
            return found.name
    return await geo.area_name(lat, lng)


async def compute(config: AppConfig) -> dict[str, Any]:
    """Builds the whole map (every cell with a request) and stores it."""
    settings_: DemandSettings = config.demand
    requests = await _window(REQUESTS, settings_.window_minutes)
    unmatched = await _window(UNMATCHED, settings_.window_minutes)
    drivers = await _drivers_per_cell()
    async with SessionLocal() as session:
        zones = await services.live_zones(session)
    cells = []
    for cell in sorted(set(requests) | set(unmatched)):
        req, unm = requests.get(cell, 0), unmatched.get(cell, 0)
        if req + unm <= 0:
            continue
        lat, lng = h3.cell_to_latlng(cell)
        lvl = level(max(req, unm), unm, drivers.get(cell, 0), settings_.hot_requests)
        cells.append(
            {
                "cell": cell,
                "boundary": [[round(a, 6), round(b, 6)] for a, b in h3.cell_to_boundary(cell)],
                "center": [round(lat, 6), round(lng, 6)],
                "level": lvl,
                "requests": req,
                "unmatched": unm,
                "drivers": drivers.get(cell, 0),
                "name": await _name(zones, lat, lng) if lvl >= 2 else None,
            }
        )
    snapshot = {
        "enabled": settings_.enabled,
        "updated_at": datetime.now(UTC).isoformat(),
        "window_minutes": settings_.window_minutes,
        "cells": cells,
    }
    await redis_client.set(SNAPSHOT_KEY, orjson.dumps(snapshot), ex=SNAPSHOT_TTL)
    return snapshot


async def current(config: AppConfig) -> dict[str, Any]:
    """The stored map, or a fresh one when the worker has not built it yet."""
    raw = await redis_client.get(SNAPSHOT_KEY)
    if raw:
        return orjson.loads(raw)
    return await compute(config)


def _disabled(config: AppConfig) -> DemandSnapshot:
    return DemandSnapshot(enabled=False, window_minutes=config.demand.window_minutes)


async def for_admin(config: AppConfig) -> DemandSnapshot:
    if not config.demand.enabled:
        return _disabled(config)
    return DemandSnapshot.model_validate(await current(config))


async def for_driver(config: AppConfig, lat: float, lng: float) -> DemandSnapshot:
    """Cells around the driver without the driver counts, and the closest busy spot."""
    if not config.demand.enabled:
        return _disabled(config)
    snapshot = await current(config)
    near = set(h3.grid_disk(cell_of(lat, lng), DRIVER_RINGS))
    cells = [
        DemandCell.model_validate(c | {"drivers": None})
        for c in snapshot["cells"]
        if c["cell"] in near
    ]
    hot = hot_spot(cells, lat, lng)
    return DemandSnapshot(
        enabled=True,
        updated_at=snapshot["updated_at"],
        window_minutes=snapshot["window_minutes"],
        cells=cells,
        hot=hot,
    )


def hot_spot(cells: list[DemandCell], lat: float, lng: float) -> HotSpot | None:
    busy = [c for c in cells if c.level == 3 and c.name]
    if not busy:
        return None
    best = min(busy, key=lambda c: distance_m(lat, lng, *c.center))
    return HotSpot(
        name=best.name or "",
        level=best.level,
        distance_m=round(distance_m(lat, lng, *best.center)),
        center=best.center,
    )
