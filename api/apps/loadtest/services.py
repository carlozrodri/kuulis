"""Synthetic users, drivers, admins and ride history for the load tests in ``loadtest/``.

Every synthetic account uses an email under ``LOADTEST_DOMAIN`` and is flagged as a test account
(left out of metrics), so ``clean`` can find and delete everything they produced. All share one
password (``LOADTEST_PASSWORD``); admins also share a TOTP secret derived from it, which the load
test runner derives the same way (``loadtest/runner/accounts.py``).

    python manage.py loadtest-seed     # 5000 riders, 600 drivers, 7 admins, 100 000 past rides
    python manage.py loadtest-report --since 2026-10-12T22:00:00Z
    python manage.py loadtest-clean
"""

import base64
import hashlib
import hmac
import logging
import random
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Table, delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.auth.models import UserTotp
from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile, DriverStatus, Vehicle, VehicleType
from apps.legal.models import LegalAcceptance
from apps.legal.services import FOR_DRIVERS, FOR_EVERYONE, required_versions
from apps.notifications.models import Device, Notification, Platform
from apps.rides import presence
from apps.rides.models import PaymentMethod, Ride, RideOffer, RideStatus
from apps.users.models import Role, User
from kuulis.core import crypto
from kuulis.core.models import Base
from kuulis.core.redis import redis_client
from kuulis.core.security import hash_password
from kuulis.settings import settings

logger = logging.getLogger(__name__)

LOADTEST_DOMAIN = "loadtest.example.com"
# Title of the push campaign the runner sends; ``clean`` removes these inbox rows from real
# accounts too (a broadcast reaches everyone).
CAMPAIGN_TITLE = "Prueba de carga Kuulis (ignorar)"
BATCH = 2000

# Requests per hour of day (0-23), shaped like the `by_hour` profile of the admin metrics: a
# morning peak, lunch and a stronger evening peak.
HOUR_WEIGHTS = [1, 1, 1, 1, 2, 4, 8, 12, 10, 7, 6, 7, 8, 7, 6, 7, 9, 12, 13, 11, 8, 5, 3, 2]


class LoadTestRefusedError(RuntimeError):
    pass


def email_for(kind: str, n: int) -> str:
    """``kind`` is p (passenger), d (driver) or a (admin)."""
    return f"lt-{kind}{n:05d}@{LOADTEST_DOMAIN}"


def admin_totp_secret(password: str, n: int) -> str:
    """Base32 TOTP secret of synthetic admin ``n``; the runner derives the same one."""
    digest = hmac.new(password.encode(), f"kuulis-loadtest-admin-{n}".encode(), hashlib.sha256)
    return base64.b32encode(digest.digest()[:20]).decode()


def _ensure_allowed(password: str) -> None:
    if settings.APP_ENV == "production":
        raise LoadTestRefusedError("Load test data is never created in production")
    if len(password) < 16:
        raise LoadTestRefusedError("LOADTEST_PASSWORD must have at least 16 characters")


def _synthetic_users():
    return select(User.id).where(User.email.like(f"%@{LOADTEST_DOMAIN}"))


async def _insert(session: AsyncSession, table: Table, rows: Sequence[dict[str, Any]]) -> None:
    for start in range(0, len(rows), BATCH):
        await session.execute(insert(table), list(rows[start : start + BATCH]))


def _area_points(config) -> tuple[float, float, float, float]:
    area = next((a for a in config.service_areas if a.name.lower() == "caracas"), None)
    area = area or config.service_areas[0]
    return area.min_lat, area.max_lat, area.min_lng, area.max_lng


async def seed(
    session: AsyncSession,
    password: str,
    passengers: int = 5000,
    drivers: int = 600,
    admins: int = 7,
    rides: int = 100_000,
    days: int = 180,
    seed_value: int = 18,
) -> dict[str, int]:
    """Creates the synthetic accounts and ride history. Refuses when they already exist (run
    ``clean`` first) so two runs never mix."""
    _ensure_allowed(password)
    existing = await session.scalar(select(func.count()).select_from(_synthetic_users().subquery()))
    if existing:
        raise LoadTestRefusedError(f"{existing} synthetic users already exist; run clean first")

    rng = random.Random(seed_value)  # noqa: S311  (repeatable fake data, not secrets)
    now = datetime.now(UTC)
    hashed = hash_password(password)  # one hash for everyone: Argon2 is slow on purpose
    versions = await required_versions(session)
    config = await get_app_config(session)
    min_lat, max_lat, min_lng, max_lng = _area_points(config)

    def user_row(kind: str, n: int, role: Role) -> dict[str, Any]:
        label = {"p": "Pasajero", "d": "Motorizado", "a": "Admin"}[kind]
        return {
            "id": uuid.uuid4(),
            "email": email_for(kind, n),
            "hashed_password": hashed,
            "full_name": f"{label} Carga {n}",
            "role": role,
            "locale": "es",
            "is_active": True,
            "is_verified": True,
            "is_test_account": True,
            "created_at": now - timedelta(days=days + 1),
            "updated_at": now,
        }

    passenger_rows = [user_row("p", n, Role.USER) for n in range(1, passengers + 1)]
    driver_rows = [user_row("d", n, Role.USER) for n in range(1, drivers + 1)]
    admin_rows = [user_row("a", n, Role.ADMIN) for n in range(1, admins + 1)]
    await _insert(session, User.__table__, passenger_rows + driver_rows + admin_rows)

    profiles, vehicles = [], []
    for n, row in enumerate(driver_rows, start=1):
        profile_id = uuid.uuid4()
        profiles.append(
            {
                "id": profile_id,
                "user_id": row["id"],
                "status": DriverStatus.APPROVED,
                "birth_date": date(1990, 1, 1),
                "national_id": f"LT{n:08d}",
                "rif": f"LT{n:08d}0",
                "phone": f"+5841200{n:05d}",
                "city": "caracas",
                "submitted_at": now - timedelta(days=days),
                "reviewed_at": now - timedelta(days=days),
                "approved_at": now - timedelta(days=days),
                "created_at": now - timedelta(days=days),
                "updated_at": now,
            }
        )
        vehicles.append(
            {
                "id": uuid.uuid4(),
                "driver_id": profile_id,
                "type": VehicleType.MOTO,
                "brand": "Carga",
                "model": "LT 150",
                "year": now.year - 2,
                "plate": f"LT{n:05d}",
                "color": "Negra",
                "created_at": now,
                "updated_at": now,
            }
        )
    await _insert(session, DriverProfile.__table__, profiles)
    await _insert(session, Vehicle.__table__, vehicles)

    acceptances = []
    for rows, kinds in ((passenger_rows, FOR_EVERYONE), (driver_rows, FOR_EVERYONE + FOR_DRIVERS)):
        for row in rows:
            for kind in kinds:
                if kind in versions:
                    acceptances.append(
                        {
                            "id": uuid.uuid4(),
                            "user_id": row["id"],
                            "kind": kind,
                            "version": versions[kind],
                            "platform": "loadtest",
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
    await _insert(session, LegalAcceptance.__table__, acceptances)

    devices = [
        {
            "id": uuid.uuid4(),
            "user_id": row["id"],
            "push_token": f"ExponentPushToken[loadtest-{row['id'].hex}]",
            "platform": Platform.ANDROID,
            "app_version": "loadtest",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        for row in passenger_rows + driver_rows
    ]
    await _insert(session, Device.__table__, devices)

    totps = [
        {
            "id": uuid.uuid4(),
            "user_id": row["id"],
            "secret": crypto.encrypt(admin_totp_secret(password, n)),
            "confirmed_at": now,
            "recovery_codes": [],
            "last_step": 0,
            "created_at": now,
            "updated_at": now,
        }
        for n, row in enumerate(admin_rows, start=1)
    ]
    await _insert(session, UserTotp.__table__, totps)

    history = _history(
        rng,
        [r["id"] for r in passenger_rows],
        [r["id"] for r in driver_rows],
        rides,
        days,
        now,
        (min_lat, max_lat, min_lng, max_lng),
    )
    await _insert(session, Ride.__table__, history)
    await session.commit()
    return {
        "passengers": len(passenger_rows),
        "drivers": len(driver_rows),
        "admins": len(admin_rows),
        "rides": len(history),
    }


def _history(
    rng: random.Random,
    passengers: list[uuid.UUID],
    drivers: list[uuid.UUID],
    count: int,
    days: int,
    now: datetime,
    box: tuple[float, float, float, float],
) -> list[dict[str, Any]]:
    """Finished rides spread over the last ``days`` days with the hourly profile above."""
    min_lat, max_lat, min_lng, max_lng = box
    hours = rng.choices(range(24), weights=HOUR_WEIGHTS, k=count)
    statuses = rng.choices(
        [
            RideStatus.COMPLETED,
            RideStatus.CANCELLED_BY_PASSENGER,
            RideStatus.CANCELLED_BY_DRIVER,
            RideStatus.NO_DRIVERS,
        ],
        weights=[82, 10, 3, 5],
        k=count,
    )
    methods = list(PaymentMethod)
    rows = []
    for hour, status in zip(hours, statuses, strict=True):
        day = now - timedelta(days=rng.randint(1, days))
        requested = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))
        distance = rng.randint(1200, 14000)
        duration = int(distance / rng.uniform(6, 10))
        fare = (Decimal("0.80") + Decimal(distance) / 1000 * Decimal("0.35")).quantize(
            Decimal("0.01")
        )
        assigned = status in (RideStatus.COMPLETED, RideStatus.CANCELLED_BY_DRIVER) or (
            status == RideStatus.CANCELLED_BY_PASSENGER and rng.random() < 0.5
        )
        row: dict[str, Any] = {
            "id": uuid.uuid4(),
            "passenger_id": rng.choice(passengers),
            "driver_id": rng.choice(drivers) if assigned else None,
            "status": status,
            "vehicle_type": VehicleType.MOTO,
            "pickup_lat": rng.uniform(min_lat, max_lat),
            "pickup_lng": rng.uniform(min_lng, max_lng),
            "pickup_address": "Carga (origen)",
            "dropoff_lat": rng.uniform(min_lat, max_lat),
            "dropoff_lng": rng.uniform(min_lng, max_lng),
            "dropoff_address": "Carga (destino)",
            "distance_m": distance,
            "duration_s": duration,
            "fare": fare,
            "surge_multiplier": Decimal("1.00"),
            "discount": Decimal("0"),
            "payment_method": rng.choice(methods),
            "requested_at": requested,
            "search_expires_at": requested + timedelta(minutes=3),
            "assigned_at": requested + timedelta(seconds=rng.randint(3, 60)) if assigned else None,
            "arrived_at": None,
            "started_at": None,
            "completed_at": None,
            "cancelled_at": None,
            "rated_by_passenger": False,
            "rated_by_driver": False,
            "created_at": requested,
            "updated_at": requested,
        }
        if status == RideStatus.COMPLETED:
            row["arrived_at"] = row["assigned_at"] + timedelta(seconds=rng.randint(120, 600))
            row["started_at"] = row["arrived_at"] + timedelta(seconds=rng.randint(30, 180))
            row["completed_at"] = row["started_at"] + timedelta(seconds=duration)
            # The apps ask to rate before the next ride: an unrated past ride would block both.
            row["rated_by_passenger"] = True
            row["rated_by_driver"] = True
            row["updated_at"] = row["completed_at"]
        elif status != RideStatus.NO_DRIVERS:
            row["cancelled_at"] = requested + timedelta(seconds=rng.randint(20, 400))
            row["updated_at"] = row["cancelled_at"]
        else:
            row["updated_at"] = row["search_expires_at"]
        rows.append(row)
    return rows


# --- Report ------------------------------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[index], 3)


async def report(session: AsyncSession, since: datetime) -> dict[str, Any]:
    """Dispatch numbers of the rides synthetic riders requested since ``since``: seconds from the
    request to the first offer, and how each ride ended. Read straight from the database, so it
    does not depend on what the load generator managed to observe."""
    synthetic = _synthetic_users()
    first_offer = (
        select(RideOffer.ride_id, func.min(RideOffer.created_at).label("first_offer_at"))
        .group_by(RideOffer.ride_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Ride.status, Ride.requested_at, Ride.assigned_at, first_offer.c.first_offer_at)
            .outerjoin(first_offer, first_offer.c.ride_id == Ride.id)
            .where(Ride.passenger_id.in_(synthetic), Ride.requested_at >= since)
        )
    ).all()
    to_offer = [
        (r.first_offer_at - r.requested_at).total_seconds() for r in rows if r.first_offer_at
    ]
    to_assign = [(r.assigned_at - r.requested_at).total_seconds() for r in rows if r.assigned_at]
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
    stuck = await session.scalar(
        select(func.count())
        .select_from(Ride)
        .where(
            Ride.passenger_id.in_(synthetic),
            Ride.status == RideStatus.SEARCHING,
            Ride.requested_at < datetime.now(UTC) - timedelta(seconds=30),
            ~Ride.id.in_(select(RideOffer.ride_id)),
        )
    )
    return {
        "since": since.isoformat(),
        "rides": len(rows),
        "by_status": by_status,
        "request_to_first_offer_s": {
            "p50": _percentile(to_offer, 50),
            "p95": _percentile(to_offer, 95),
            "p99": _percentile(to_offer, 99),
            "max": max(to_offer, default=None),
        },
        "request_to_assigned_s": {
            "p50": _percentile(to_assign, 50),
            "p95": _percentile(to_assign, 95),
            "max": max(to_assign, default=None),
        },
        "searching_without_offer_over_30s": stuck,
    }


# --- Database snapshot -------------------------------------------------------------------------


async def pg_stats(session: AsyncSession, samples: int = 1, every: float = 5.0) -> dict[str, Any]:
    """What Postgres is doing right now: connections by state and wait, the longest running
    statements, and (with pg_stat_statements) the statements that took the most time."""
    import asyncio

    snapshots = []
    for n in range(samples):
        if n:
            await asyncio.sleep(every)
        by_state = await session.execute(
            text(
                "SELECT state, wait_event_type, wait_event, count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() GROUP BY 1, 2, 3 ORDER BY 4 DESC"
            )
        )
        longest = await session.execute(
            text(
                "SELECT round(extract(epoch FROM now() - query_start)::numeric, 2), state, "
                "wait_event, left(regexp_replace(query, '\\s+', ' ', 'g'), 200) "
                "FROM pg_stat_activity WHERE datname = current_database() AND state <> 'idle' "
                "AND pid <> pg_backend_pid() ORDER BY 1 DESC NULLS LAST LIMIT 10"
            )
        )
        snapshots.append(
            {
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "connections": [list(r) for r in by_state],
                "longest": [[float(r[0] or 0), r[1], r[2], r[3]] for r in longest],
            }
        )
        await session.rollback()
    settings_rows = await session.execute(
        text(
            "SELECT name, setting FROM pg_settings WHERE name IN ('max_connections', "
            "'shared_buffers', 'work_mem', 'effective_cache_size', 'synchronous_commit')"
        )
    )
    result: dict[str, Any] = {"settings": dict(list(settings_rows)), "snapshots": snapshots}
    has_statements = await session.scalar(
        text(
            "SELECT count(*) FROM pg_extension WHERE extname = 'pg_stat_statements' "
            "AND current_setting('shared_preload_libraries') LIKE '%pg_stat_statements%'"
        )
    )
    if has_statements:
        top = await session.execute(
            text(
                "SELECT calls, round(total_exec_time::numeric, 0), "
                "round(mean_exec_time::numeric, 2), "
                "left(regexp_replace(query, '\\s+', ' ', 'g'), 200) "
                "FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 15"
            )
        )
        result["top_statements"] = [[r[0], float(r[1]), float(r[2]), r[3]] for r in top]
    return result


# --- Clean -------------------------------------------------------------------------------------


async def _referencing(session: AsyncSession, table: str) -> list[tuple[str, str, str]]:
    """(table, column, on_delete) of single-column foreign keys pointing at ``table.id``."""
    rows = await session.execute(
        text(
            """
            SELECT src.relname, att.attname, con.confdeltype
            FROM pg_constraint con
            JOIN pg_class src ON src.oid = con.conrelid
            JOIN pg_class dst ON dst.oid = con.confrelid
            JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
            WHERE con.contype = 'f' AND dst.relname = :table AND array_length(con.conkey, 1) = 1
            """
        ),
        {"table": table},
    )
    return [(r[0], r[1], r[2]) for r in rows]


async def _delete_rows(
    session: AsyncSession, table: str, ids: list[uuid.UUID], path: frozenset[str] = frozenset()
) -> int:
    """Deletes rows of ``table`` by id after deleting whatever would block it (RESTRICT / NO
    ACTION foreign keys), recursively. CASCADE and SET NULL are left to the database."""
    if not ids:
        return 0
    path = path | {table}
    for child, column, rule in await _referencing(session, table):
        if rule not in ("a", "r"):  # a = NO ACTION, r = RESTRICT
            continue
        child_table = Base.metadata.tables.get(child)
        if child_table is None:
            continue
        for start in range(0, len(ids), BATCH):
            chunk = ids[start : start + BATCH]
            where = child_table.c[column].in_(chunk)
            if child in path or "id" not in child_table.c:
                # Self reference or cycle: clear the link (or the row, without an id) instead.
                if child_table.c[column].nullable:
                    await session.execute(child_table.update().where(where).values({column: None}))
                else:
                    await session.execute(delete(child_table).where(where))
                continue
            child_ids = list(await session.scalars(select(child_table.c.id).where(where)))
            await _delete_rows(session, child, child_ids, path)
    target = Base.metadata.tables[table]
    deleted = 0
    for start in range(0, len(ids), BATCH):
        chunk = ids[start : start + BATCH]
        result = await session.execute(delete(target).where(target.c.id.in_(chunk)))
        deleted += result.rowcount or 0
    return deleted


async def clean(session: AsyncSession) -> dict[str, int]:
    """Deletes every synthetic account and what it produced (rides, offers, chat, wallet rows,
    notifications…), the campaign's inbox rows on real accounts, and their live presence."""
    if settings.APP_ENV == "production":
        raise LoadTestRefusedError("Refusing to touch production")
    user_ids = list(await session.scalars(_synthetic_users()))
    synthetic = _synthetic_users()
    ride_ids = list(
        await session.scalars(
            select(Ride.id).where(Ride.passenger_id.in_(synthetic) | Ride.driver_id.in_(synthetic))
        )
    )
    rides = await _delete_rows(session, "rides", ride_ids)
    users = await _delete_rows(session, "users", user_ids)
    campaign = await session.execute(
        delete(Notification).where(Notification.title == CAMPAIGN_TITLE)
    )
    await session.commit()
    await _clear_presence([str(u) for u in user_ids])
    return {"users": users, "rides": rides, "campaign_notifications": campaign.rowcount or 0}


async def _clear_presence(user_ids: Iterable[str]) -> None:
    ids = list(user_ids)
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        async with redis_client.pipeline(transaction=False) as pipe:
            pipe.hdel(presence.ONLINE_KEY, *chunk)
            pipe.hdel(presence.LOC_KEY, *chunk)
            for vehicle_type in VehicleType:
                pipe.zrem(presence.geo_key(vehicle_type), *chunk)
            for uid in chunk:
                pipe.delete(presence.offer_key(uid), presence.active_key(uid))
            await pipe.execute()
