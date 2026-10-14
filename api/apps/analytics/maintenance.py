"""Housekeeping of the product analytics tables (doc 19).

- Monthly partitions of ``analytics_events``: the current month and the next two always exist;
  partitions older than 13 months are dropped (that is the retention of the events).
- ``supply_hours`` and ``driver_online_sessions`` keep 13 months too.
- The supply sampler: every minute it compares the online drivers in Redis with the open online
  sessions (opening and closing them) and adds a minute of supply to each driver's cell.
"""

import logging
import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

import orjson
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.analytics.events import area_of, cell_of
from apps.analytics.models import DriverOnlineSession, SupplyHour
from apps.config.schemas import AppConfig
from apps.rides import presence
from kuulis.core.calendar import add_months
from kuulis.core.redis import redis_client

logger = logging.getLogger(__name__)

RETENTION_MONTHS = 13
MONTHS_AHEAD = 2
_PARTITION = re.compile(r"^analytics_events_y(\d{4})m(\d{2})$")


def partition_name(month: date) -> str:
    return f"analytics_events_y{month.year:04d}m{month.month:02d}"


def _utc_month(value: datetime) -> date:
    return value.astimezone(UTC).date().replace(day=1)


async def partitions(session: AsyncSession) -> list[str]:
    rows = await session.execute(
        text(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "WHERE p.relname = 'analytics_events' ORDER BY c.relname"
        )
    )
    return [r[0] for r in rows]


async def ensure_partitions(session: AsyncSession, now: datetime | None = None) -> list[str]:
    """Creates the missing monthly partitions (UTC months); returns the ones created."""
    now = now or datetime.now(UTC)
    existing = set(await partitions(session))
    created = []
    first = _utc_month(now)
    for offset in range(MONTHS_AHEAD + 1):
        month = add_months(first, offset)
        name = partition_name(month)
        if name in existing:
            continue
        upper = add_months(month, 1)
        try:
            async with session.begin_nested():
                await session.execute(
                    text(
                        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF analytics_events "
                        f"FOR VALUES FROM ('{month.isoformat()}') TO ('{upper.isoformat()}')"
                    )
                )
            created.append(name)
        except Exception:
            # Rows of that month already sit in the default partition (the job was down for
            # weeks): they stay there and the retention below still deletes them in time.
            logger.warning("Could not create partition %s", name, exc_info=True)
    await session.commit()
    return created


async def apply_retention(session: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    oldest = add_months(_utc_month(now), -RETENTION_MONTHS)
    cutoff = datetime.combine(oldest, datetime.min.time(), tzinfo=UTC)
    dropped = 0
    for name in await partitions(session):
        match = _PARTITION.match(name)
        if not match:
            continue
        month = date(int(match[1]), int(match[2]), 1)
        if add_months(month, 1) <= oldest:
            await session.execute(text(f"DROP TABLE IF EXISTS {name}"))
            dropped += 1
    default = await session.execute(
        text("DELETE FROM analytics_events_default WHERE occurred_at < :cutoff"),
        {"cutoff": cutoff},
    )
    supply = await session.execute(delete(SupplyHour).where(SupplyHour.hour < cutoff))
    sessions = await session.execute(
        delete(DriverOnlineSession).where(
            DriverOnlineSession.ended_at.is_not(None), DriverOnlineSession.ended_at < cutoff
        )
    )
    await session.commit()
    return {
        "partitions": dropped,
        "default_rows": default.rowcount or 0,
        "supply_hours": supply.rowcount or 0,
        "online_sessions": sessions.rowcount or 0,
    }


# --- Supply sampler ----------------------------------------------------------------------------


async def _online() -> dict[uuid.UUID, tuple[float, presence.Location | None]]:
    """Online drivers in Redis: user id -> (online since, last location)."""
    entries = await redis_client.hgetall(presence.ONLINE_KEY)
    if not entries:
        return {}
    ids = list(entries)
    locations = await redis_client.hmget(presence.LOC_KEY, ids)
    online: dict[uuid.UUID, tuple[float, Any]] = {}
    for uid, raw, loc in zip(ids, entries.values(), locations, strict=True):
        try:
            since = float(orjson.loads(raw).get("since") or 0)
            online[uuid.UUID(uid)] = (since, presence._location(loc))
        except (ValueError, TypeError, orjson.JSONDecodeError):
            continue
    return online


async def sample_supply(
    session: AsyncSession, config: AppConfig, now: datetime | None = None
) -> dict[str, int]:
    """One minute of the sampler (see the module docstring)."""
    now = now or datetime.now(UTC)
    online = await _online()
    open_ids = set(
        await session.scalars(
            select(DriverOnlineSession.driver_id).where(DriverOnlineSession.ended_at.is_(None))
        )
    )
    gone = open_ids - online.keys()
    if gone:
        await session.execute(
            update(DriverOnlineSession)
            .where(DriverOnlineSession.driver_id.in_(gone), DriverOnlineSession.ended_at.is_(None))
            .values(ended_at=now)
        )
    opened = 0
    minutes: dict[str, list[Any]] = {}
    hour = now.replace(minute=0, second=0, microsecond=0)
    for driver_id, (since, location) in online.items():
        area = area_of(config, location.lat, location.lng) if location else None
        if driver_id not in open_ids:
            started = datetime.fromtimestamp(since, UTC) if since else now
            session.add(
                DriverOnlineSession(driver_id=driver_id, started_at=min(started, now), area=area)
            )
            opened += 1
        if location is not None and location.fresh:
            cell = cell_of(location.lat, location.lng)
            minutes.setdefault(cell, [area, 0])[1] += 1
    if minutes:
        stmt = insert(SupplyHour).values(
            [
                {"id": uuid.uuid4(), "hour": hour, "cell": cell, "area": area, "driver_minutes": n}
                for cell, (area, n) in minutes.items()
            ]
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["hour", "cell"],
                set_={"driver_minutes": SupplyHour.driver_minutes + stmt.excluded.driver_minutes},
            )
        )
    await session.commit()
    return {"online": len(online), "opened": opened, "closed": len(gone), "cells": len(minutes)}
