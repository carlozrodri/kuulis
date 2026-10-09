"""Matching: offers a searching ride to the nearest eligible driver, one at a time.

Design (no scheduler process needed):

- ``advance(ride_id)`` is one idempotent step run under the ride's row lock: it expires a dead
  offer, ends the search with ``no_drivers`` at the deadline, or offers the ride to the next
  driver. It always records when it wants to run again in a Redis sorted set
  (``rides:dispatch:due``, score = unix time).
- Events that need an immediate step (ride created, offer declined) enqueue the
  ``rides.dispatch`` Taskiq task. Timed steps (offer timeout, retry when nobody is around, the
  search deadline) are picked from the sorted set by a small loop that runs inside every worker
  process; a Lua script pops due entries atomically, so several workers never run the same
  step twice at the same moment, and the row lock serializes whatever is left.
- If a worker dies mid-step the entry is gone from the set, but ``reconcile`` (every 30 s, one
  worker at a time) re-schedules every ``searching`` ride found in Postgres. State lives in
  Postgres + Redis, never in worker memory.
"""

import asyncio
import contextlib
import logging
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig
from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile, DriverStatus, Vehicle, VehicleType
from apps.geo.clients import estimate_route
from apps.rides import events, presence
from apps.rides.models import (
    ACTIVE_STATUSES,
    ASSIGNED_STATUSES,
    OfferStatus,
    Ride,
    RideOffer,
    RideStatus,
)
from apps.rides.state import OFFER_GRACE, lock_ride, transition, utcnow
from apps.subscriptions import services as subscriptions
from apps.users.models import User
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

DUE_KEY = f"{settings.APP_ENV}:rides:dispatch:due"
MAINTENANCE_LOCK = f"{settings.APP_ENV}:rides:dispatch:maintenance"
RETRY_SECONDS = 4  # nobody available: look again this often until the deadline
CANDIDATES_PER_RADIUS = 30
LOOP_INTERVAL = 0.5
BATCH = 50
CONCURRENCY = 5
MAINTENANCE_EVERY = 30
OFFLINE_AFTER_SECONDS = 30 * 60  # online drivers silent this long are taken offline

_POP_DUE = """
local items = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2])
for _, member in ipairs(items) do redis.call('ZREM', KEYS[1], member) end
return items
"""


# --- Scheduling --------------------------------------------------------------------------------


async def schedule(ride_id: uuid.UUID, at: datetime) -> None:
    await redis_client.zadd(DUE_KEY, {str(ride_id): at.timestamp()})


async def unschedule(ride_id: uuid.UUID) -> None:
    await redis_client.zrem(DUE_KEY, str(ride_id))


async def kick(ride_id: uuid.UUID) -> None:
    """Run a step as soon as possible (task now; the due entry is the safety net)."""
    from apps.rides.tasks import dispatch_ride

    await schedule(ride_id, utcnow() + timedelta(seconds=10))
    await dispatch_ride.kiq(str(ride_id))


# --- One step ----------------------------------------------------------------------------------


async def _eligible(
    session: AsyncSession, user_ids: list[str], vehicle_type: VehicleType
) -> set[str]:
    """Approved, active, right vehicle type, not busy and nothing left to rate."""
    if not user_ids:
        return set()
    ids = [uuid.UUID(u) for u in user_ids]
    approved = set(
        await session.scalars(
            select(DriverProfile.user_id)
            .join(Vehicle, Vehicle.driver_id == DriverProfile.id)
            .join(User, User.id == DriverProfile.user_id)
            .where(
                DriverProfile.user_id.in_(ids),
                DriverProfile.status == DriverStatus.APPROVED,
                Vehicle.type == vehicle_type,
                User.is_active,
            )
        )
    )
    if not approved:
        return set()
    busy = set(
        await session.scalars(
            select(Ride.driver_id).where(
                Ride.driver_id.in_(approved),
                (Ride.status.in_(ASSIGNED_STATUSES))
                | ((Ride.status == RideStatus.COMPLETED) & Ride.rated_by_driver.is_(False)),
            )
        )
    )
    busy |= set(
        await session.scalars(
            select(Ride.passenger_id).where(
                Ride.passenger_id.in_(approved), Ride.status.in_(ACTIVE_STATUSES)
            )
        )
    )
    busy |= await subscriptions.overdue_user_ids(session, list(approved))  # unpaid fee
    return {str(u) for u in approved - busy}


async def _pick_driver(
    session: AsyncSession, ride: Ride, config: AppConfig
) -> tuple[str, presence.Location] | None:
    """Nearest eligible driver, searching the configured radii in order."""
    offered = await session.scalars(select(RideOffer.driver_id).where(RideOffer.ride_id == ride.id))
    seen = {str(u) for u in offered} | {str(ride.passenger_id)}
    ttl = int(config.offer_timeout_seconds + OFFER_GRACE.total_seconds()) + 5
    for radius in config.search_radius_m:
        found = await presence.nearby(
            ride.vehicle_type,
            ride.pickup_lat,
            ride.pickup_lng,
            radius,
            CANDIDATES_PER_RADIUS + len(seen),
        )
        candidates = [uid for uid, _ in found if uid not in seen]
        seen.update(candidates)
        if not candidates:
            continue
        locations = await presence.get_locations(candidates)
        candidates = [u for u in candidates if u in locations and locations[u].fresh]
        eligible = await _eligible(session, candidates, ride.vehicle_type)
        for uid in candidates:  # nearest first
            if uid in eligible and await presence.reserve_offer(uid, ride.id, ttl):
                return uid, locations[uid]
    return None


async def advance(ride_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        ride = await lock_ride(session, ride_id)
        if ride is None or ride.status != RideStatus.SEARCHING:
            await session.rollback()
            await unschedule(ride_id)
            return
        config = await get_app_config(session)
        now = utcnow()
        pending = await session.scalar(
            select(RideOffer).where(
                RideOffer.ride_id == ride.id, RideOffer.status == OfferStatus.PENDING
            )
        )
        if pending is not None and pending.expires_at + OFFER_GRACE > now:
            await session.rollback()
            await schedule(ride.id, pending.expires_at + OFFER_GRACE)
            return

        expired: RideOffer | None = None
        if pending is not None:
            pending.status = OfferStatus.EXPIRED
            pending.responded_at = now
            expired = pending

        if now >= ride.search_expires_at:
            transition(ride, RideStatus.NO_DRIVERS)
            await session.commit()
            await unschedule(ride.id)
            if expired is not None:
                await _after_expired(expired)
            await events.emit_updated(session, ride)
            await events.push_to(session, ride.passenger_id, "no_drivers", ride)
            logger.info("Ride %s: no drivers", ride.id)
            return

        offer: RideOffer | None = None
        picked = await _pick_driver(session, ride, config)
        if picked is not None:
            driver_id, location = picked
            pickup = estimate_route(location.lat, location.lng, ride.pickup_lat, ride.pickup_lng)
            offer = RideOffer(
                ride_id=ride.id,
                driver_id=uuid.UUID(driver_id),
                status=OfferStatus.PENDING,
                pickup_distance_m=pickup.distance_m,
                pickup_eta_s=pickup.duration_s,
                expires_at=now + timedelta(seconds=config.offer_timeout_seconds),
            )
            session.add(offer)
        try:
            await session.commit()
        except IntegrityError:
            # Should not happen (offered drivers are skipped); retry the step shortly.
            logger.exception("Ride %s: could not store the offer", ride.id)
            await session.rollback()
            if picked is not None:
                await presence.release_offer(picked[0], ride.id)
            await schedule(ride.id, now + timedelta(seconds=1))
            return

        if expired is not None:
            await _after_expired(expired)
        if offer is not None:
            await schedule(ride.id, offer.expires_at + OFFER_GRACE)
            await events.emit_offer(session, ride, offer)
            logger.info("Ride %s offered to driver %s", ride.id, offer.driver_id)
        else:
            retry = min(now + timedelta(seconds=RETRY_SECONDS), ride.search_expires_at)
            await schedule(ride.id, retry)


async def _after_expired(offer: RideOffer) -> None:
    await presence.release_offer(offer.driver_id, offer.ride_id)
    await events.emit_offer_cancelled(offer.driver_id, offer.ride_id)


# --- Background loop (inside each worker process) ----------------------------------------------


async def run_due(now: float | None = None, limit: int = BATCH) -> int:
    due = await redis_client.eval(_POP_DUE, 1, DUE_KEY, now or time.time(), limit)
    if not due:
        return 0
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def _one(member: str) -> None:
        async with semaphore:
            try:
                await advance(uuid.UUID(member))
            except Exception:
                logger.exception("Dispatch step failed for ride %s", member)
                # Try again soon; reconcile also covers a crash of the whole process.
                await redis_client.zadd(DUE_KEY, {member: time.time() + 2})

    await asyncio.gather(*(_one(m) for m in due))
    return len(due)


async def reconcile() -> int:
    """Re-schedules searching rides missing from the due set (lost after a crash)."""
    async with SessionLocal() as session:
        ids = [
            str(i)
            for i in await session.scalars(
                select(Ride.id).where(Ride.status == RideStatus.SEARCHING)
            )
        ]
    if not ids:
        return 0
    scores = await redis_client.zmscore(DUE_KEY, ids)
    missing = {rid: time.time() for rid, score in zip(ids, scores, strict=True) if score is None}
    if missing:
        await redis_client.zadd(DUE_KEY, missing)
        logger.warning("Re-scheduled %s searching rides", len(missing))
    return len(missing)


async def maintenance() -> None:
    if not await redis_client.set(MAINTENANCE_LOCK, "1", nx=True, ex=MAINTENANCE_EVERY - 5):
        return
    await reconcile()
    removed = await presence.cleanup_stale(OFFLINE_AFTER_SECONDS)
    if removed:
        logger.info("Took %s silent drivers offline", len(removed))


async def loop() -> None:
    last_maintenance = 0.0
    while True:
        processed = 0
        try:
            processed = await run_due()
            if time.monotonic() - last_maintenance >= MAINTENANCE_EVERY:
                last_maintenance = time.monotonic()
                await maintenance()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dispatch loop error")
        if processed < BATCH:
            await asyncio.sleep(LOOP_INTERVAL)


_task: asyncio.Task | None = None


def start() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(loop(), name="rides-dispatch-loop")


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
