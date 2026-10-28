"""Caracas en movimiento (docs/product/wow/01-mapa-vivo.md, part B): real trips, anonymous.

Only real rides count: never simulated ones, never test accounts, never drivers who opted out.
A moto in a trip is shown where its planned route says it was a few minutes ago, rounded to a
~200 m grid and never near the start or the end of the trip, so nobody can tell where it came from
or where it goes. There are no names, photos, plates or addresses: only the price, the distance and
an anonymous id that changes every hour.

Below the admin threshold (real trips started in the last hour) the layer is off and the app shows
an honest message with the real number of verified drivers instead.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile, DriverStatus
from apps.rides.models import Ride, RideStatus
from apps.rides.schemas import ActiveTrip, PublicActivity, RecentTrip
from apps.safety.geo import decode_polyline, distance_m
from apps.users.models import User
from kuulis.core.cache import cached

CACHE_KEY = "public_activity"
CACHE_TTL_SECONDS = 30
DELAY = timedelta(minutes=3)
# ~200 m: 0.0018° of latitude, and about the same of longitude at Caracas (10.5° N).
GRID_DEG = 0.0018
# Never show the first or last 15 % of a trip (where it starts and ends).
EDGE_FRACTION = 0.15
RECENT_WINDOW = timedelta(hours=2)
RECENT_MIN_AGE = timedelta(minutes=5)
RECENT_LIMIT = 8
ACTIVE_LIMIT = 40


def _round(value: float) -> float:
    return round(round(value / GRID_DEG) * GRID_DEG, 5)


def point_along(path: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    """The point `fraction` (0-1) of the way along `path`, by distance."""
    if len(path) == 1:
        return path[0]
    pairs = list(pairwise(path))
    legs = [distance_m(*a, *b) for a, b in pairs]
    goal = sum(legs) * min(1.0, max(0.0, fraction))
    for (a, b), leg in zip(pairs, legs, strict=True):
        if goal <= leg and leg > 0:
            t = goal / leg
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        goal -= leg
    return path[-1]


def public_point(ride: Ride, now: datetime) -> tuple[float, float] | None:
    """Where the trip is shown: delayed, kept away from both ends and snapped to the grid."""
    if not ride.polyline or ride.started_at is None or ride.duration_s <= 0:
        return None
    elapsed = (now - DELAY - ride.started_at).total_seconds()
    if elapsed <= 0:
        return None
    fraction = min(1 - EDGE_FRACTION, max(EDGE_FRACTION, elapsed / ride.duration_s))
    path = decode_polyline(ride.polyline)
    if not path:
        return None
    lat, lng = point_along(path, fraction)
    return _round(lat), _round(lng)


def anonymous_id(ride: Ride, now: datetime) -> str:
    """Stable within the hour (so the app can glide the marker), unlinkable to the ride."""
    salt = now.strftime("%Y%m%d%H")
    return hashlib.sha256(f"{salt}:{ride.id}".encode()).hexdigest()[:12]


def _real_rides():
    """Rides between real people: no test accounts on either side, driver did not opt out."""
    passenger = aliased(User)
    driver = aliased(User)
    return (
        select(Ride)
        .join(passenger, passenger.id == Ride.passenger_id)
        .join(driver, driver.id == Ride.driver_id)
        .join(DriverProfile, DriverProfile.user_id == Ride.driver_id)
        .where(
            passenger.is_test_account.is_(False),
            driver.is_test_account.is_(False),
            DriverProfile.hide_from_public_activity.is_(False),
        )
    )


async def _verified_drivers(session: AsyncSession) -> int:
    stmt = (
        select(func.count())
        .select_from(DriverProfile)
        .join(User, User.id == DriverProfile.user_id)
        .where(DriverProfile.status == DriverStatus.APPROVED, User.is_test_account.is_(False))
    )
    return int((await session.execute(stmt)).scalar_one())


async def build(session: AsyncSession, now: datetime | None = None) -> PublicActivity:
    now = now or datetime.now(UTC)
    config = await get_app_config(session)
    threshold = config.public_activity_min_trips_per_hour
    base = _real_rides().subquery()
    count_stmt = (
        select(func.count())
        .select_from(base)
        .where(
            base.c.started_at >= now - timedelta(hours=1),
            base.c.status.in_([RideStatus.IN_PROGRESS, RideStatus.COMPLETED]),
        )
    )
    trips_last_hour = int((await session.execute(count_stmt)).scalar_one())
    verified = await _verified_drivers(session)
    live = config.public_activity_enabled and trips_last_hour >= threshold
    activity = PublicActivity(
        live=live,
        threshold=threshold,
        trips_last_hour=trips_last_hour,
        verified_drivers=verified,
        updated_at=now,
    )
    if not live:
        return activity

    active = (
        await session.scalars(
            _real_rides()
            .where(Ride.status == RideStatus.IN_PROGRESS)
            .order_by(Ride.started_at.desc())
            .limit(ACTIVE_LIMIT)
        )
    ).all()
    for ride in active:
        point = public_point(ride, now)
        if point is None:
            continue
        activity.in_progress.append(
            ActiveTrip(
                id=anonymous_id(ride, now),
                lat=point[0],
                lng=point[1],
                distance_m=ride.distance_m,
                fare=ride.total.quantize(Decimal("0.01")),
            )
        )

    recent = (
        await session.scalars(
            _real_rides()
            .where(
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= now - RECENT_WINDOW,
                Ride.completed_at <= now - RECENT_MIN_AGE,
            )
            .order_by(Ride.completed_at.desc())
            .limit(RECENT_LIMIT)
        )
    ).all()
    for ride in recent:
        assert ride.completed_at is not None
        minutes = int((now - ride.completed_at).total_seconds() // 60)
        activity.recent.append(
            RecentTrip(
                # 5-minute steps: "hace 5 min", "hace 10 min"… never the exact time.
                minutes_ago=max(5, minutes - minutes % 5),
                distance_m=ride.distance_m,
                fare=ride.total.quantize(Decimal("0.01")),
            )
        )
    return activity


async def public_activity(session: AsyncSession) -> PublicActivity:
    """Cached for 30 s for everyone: the endpoint is public and cheap to call."""
    data = await cached(
        CACHE_KEY,
        lambda: _dump(session),
        ttl=CACHE_TTL_SECONDS,
    )
    return PublicActivity.model_validate(data)


async def _dump(session: AsyncSession) -> dict:
    return (await build(session)).model_dump(mode="json")
