"""Product analytics for the admin (doc 19): funnels, weekly retention, supply and demand by cell
and hour, promotions and drivers' economics.

Funnels and retention by cohort are precomputed once a day (``refresh_cohorts``) into
``analytics_cohorts`` for the last 26 weeks; the rest is computed when asked, over a date range.
Test accounts are left out everywhere, as in the operational metrics.
"""

import csv
import io
import statistics
import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Integer,
    String,
    cast,
    delete,
    distinct,
    exists,
    extract,
    func,
    insert,
    not_,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.analytics.events import ONBOARDING_STEPS, area_of, cell_center
from apps.analytics.models import (
    AnalyticsCohort,
    AnalyticsEvent,
    DriverOnlineSession,
    SupplyHour,
)
from apps.analytics.schemas import (
    DriverEconomics,
    Funnels,
    FunnelStep,
    PromotionRow,
    Retention,
    RetentionRow,
    RetentionTable,
    SupplyCell,
    SupplyDemand,
    SupplyHourRow,
    TierDrivers,
    ValueBucket,
)
from apps.config.schemas import AppConfig, ServiceArea
from apps.drivers.models import DriverDocument, DriverProfile, Vehicle
from apps.promotions.models import Promotion
from apps.rides.models import Ride, RideStatus
from apps.subscriptions import services as subscriptions
from apps.subscriptions.models import Charge
from apps.users.models import Role, User
from kuulis.core.calendar import CARACAS_TZ, days_bounds, local_now, month_bounds

TZ = "America/Caracas"
ZERO = Decimal("0.00")
WINDOW_DAYS = 26 * 7
PASSENGER_STEPS = ("signup", "first_request", "first_ride")
DRIVER_STEPS = (
    "application",
    "vehicle",
    "documents",
    "submitted",
    "approved",
    "first_ride",
    "first_fee",
)
RETENTION_WEEKS = (1, 2, 4, 8)
RETURN_DAYS = 30
EARNING_EDGES = (0, 10, 25, 50, 100, 200, 400)
UTILIZATION_EDGES = (0, 10, 25, 50, 75)
MIN_ONLINE_HOURS = 1.0  # drivers online for less are left out of the utilization spread
MAX_CELLS = 500


# --- Helpers -----------------------------------------------------------------------------------


def _monday(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _local_date(value: datetime) -> date:
    return value.astimezone(CARACAS_TZ).date()


def _test_users() -> Any:
    return select(User.id).where(User.is_test_account)


def _real_rides() -> list[Any]:
    test = _test_users()
    return [
        not_(Ride.passenger_id.in_(test)),
        or_(Ride.driver_id.is_(None), not_(Ride.driver_id.in_(test))),
    ]


def _in_area(area: ServiceArea | None) -> list[Any]:
    if area is None:
        return []
    return [
        Ride.pickup_lat.between(area.min_lat, area.max_lat),
        Ride.pickup_lng.between(area.min_lng, area.max_lng),
    ]


def _cell(lat: Any, lng: Any) -> Any:
    """Same cell as ``apps.analytics.events.cell_of`` (and the app), in SQL."""
    return func.concat(
        cast(func.floor(lat * 100), Integer), ":", cast(func.floor(lng * 100), Integer)
    )


def _local_hour(column: Any) -> Any:
    return cast(extract("hour", func.timezone(TZ, column)), Integer)


def _who() -> Any:
    """One person per event: the account, else the installation."""
    return func.coalesce(cast(AnalyticsEvent.user_id, String), AnalyticsEvent.anon_id)


def _bucket_label(edges: Sequence[float], index: int) -> tuple[float, float | None]:
    return edges[index], edges[index + 1] if index + 1 < len(edges) else None


def _buckets(values: Iterable[float], edges: Sequence[float]) -> list[ValueBucket]:
    counts = [0] * len(edges)
    for value in values:
        index = max(i for i, edge in enumerate(edges) if value >= edge or i == 0)
        counts[index] += 1
    return [
        ValueBucket(min=_bucket_label(edges, i)[0], max=_bucket_label(edges, i)[1], count=c)
        for i, c in enumerate(counts)
    ]


# --- Daily cohorts -----------------------------------------------------------------------------


async def _event_areas(session: AsyncSession, start: datetime) -> dict[uuid.UUID, str]:
    """City of each user's first event that had one."""
    rows = await session.execute(
        select(AnalyticsEvent.user_id, AnalyticsEvent.area)
        .where(
            AnalyticsEvent.user_id.is_not(None),
            AnalyticsEvent.area.is_not(None),
            AnalyticsEvent.occurred_at >= start - timedelta(days=30),
        )
        .distinct(AnalyticsEvent.user_id)
        .order_by(AnalyticsEvent.user_id, AnalyticsEvent.occurred_at)
    )
    return {uid: area for uid, area in rows}


async def _first_pickups(
    session: AsyncSession, column: Any, *, completed: bool
) -> dict[uuid.UUID, tuple[datetime, float, float]]:
    """Per person, the first ride (requested, or completed) as passenger or as driver: when and
    where it started."""
    when = Ride.completed_at if completed else Ride.requested_at
    stmt = (
        select(column, when, Ride.pickup_lat, Ride.pickup_lng)
        .where(column.is_not(None), *_real_rides())
        .distinct(column)
        .order_by(column, when)
    )
    if completed:
        stmt = stmt.where(Ride.status == RideStatus.COMPLETED)
    rows = await session.execute(stmt)
    return {uid: (at, lat, lng) for uid, at, lat, lng in rows}


def _reached(flags: Sequence[bool]) -> int:
    """How many steps of the funnel someone went through (a later step implies the earlier ones,
    e.g. rejected documents are deleted after 30 days but the driver did send them)."""
    last = -1
    for i, flag in enumerate(flags):
        if flag:
            last = i
    return last + 1


async def _passenger_funnel(
    session: AsyncSession,
    config: AppConfig,
    start: datetime,
    event_areas: dict[uuid.UUID, str],
    out: Counter,
) -> None:
    requests = await _first_pickups(session, Ride.passenger_id, completed=False)
    done = await _first_pickups(session, Ride.passenger_id, completed=True)
    users = await session.execute(
        select(User.id, User.created_at).where(
            User.role == Role.USER, not_(User.is_test_account), User.created_at >= start
        )
    )
    for uid, created in users:
        first = requests.get(uid)
        area = event_areas.get(uid) or (area_of(config, first[1], first[2]) if first else None)
        reached = _reached([True, first is not None, uid in done])
        day = _local_date(created)
        for step in PASSENGER_STEPS[:reached]:
            out[("passenger_funnel", day, area or "", step)] += 1


async def _driver_funnel(
    session: AsyncSession,
    config: AppConfig,
    start: datetime,
    event_areas: dict[uuid.UUID, str],
    out: Counter,
) -> None:
    by_city = {a.name.lower(): a.name for a in config.service_areas}
    rows = await session.execute(
        select(
            DriverProfile.user_id,
            DriverProfile.created_at,
            DriverProfile.city,
            exists().where(Vehicle.driver_id == DriverProfile.id),
            exists().where(DriverDocument.driver_id == DriverProfile.id),
            DriverProfile.submitted_at.is_not(None),
            DriverProfile.approved_at.is_not(None),
            DriverProfile.first_trip_completed_at.is_not(None),
            exists().where(Charge.user_id == DriverProfile.user_id, Charge.fee > 0),
        )
        .join(User, User.id == DriverProfile.user_id)
        .where(not_(User.is_test_account), DriverProfile.created_at >= start)
    )
    for uid, created, city, *flags in rows:
        area = by_city.get((city or "").lower()) or event_areas.get(uid) or ""
        day = _local_date(created)
        for step in DRIVER_STEPS[: _reached([True, *flags])]:
            out[("driver_funnel", day, area, step)] += 1


async def _retention(
    session: AsyncSession,
    config: AppConfig,
    role: str,
    start: datetime,
    today: date,
    out: Counter,
) -> None:
    column = Ride.passenger_id if role == "passenger" else Ride.driver_id
    firsts = {
        uid: value
        for uid, value in (await _first_pickups(session, column, completed=True)).items()
        if value[0] >= start
    }
    if not firsts:
        return
    weeks = dict(
        (
            await session.execute(
                select(column, func.array_agg(distinct(_local_date_sql(Ride.completed_at))))
                .where(
                    Ride.status == RideStatus.COMPLETED,
                    column.in_(list(firsts)),
                    Ride.completed_at >= start,
                )
                .group_by(column)
            )
        ).all()
    )
    kind = f"{role}_retention"
    for uid, (first_at, lat, lng) in firsts.items():
        first_day = _local_date(first_at)
        cohort = _monday(first_day)
        area = area_of(config, lat, lng) or ""
        out[(kind, cohort, area, "w0")] += 1
        offsets = {(day - first_day).days // 7 for day in weeks.get(uid) or []}
        for n in RETENTION_WEEKS:
            # Stored once week N is over for everyone in the cohort (first ride on its Sunday).
            if today < cohort + timedelta(days=7 * (n + 2)):
                continue
            out[(kind, cohort, area, f"w{n}")] += 1 if n in offsets else 0


def _local_date_sql(column: Any) -> Any:
    return func.date(func.timezone(TZ, column))


async def refresh_cohorts(
    session: AsyncSession, config: AppConfig, now: datetime | None = None
) -> dict[str, int]:
    """Recomputes the cohorts of the last 26 weeks (older ones stay as they were)."""
    now = now or datetime.now(UTC)
    today = _local_date(now)
    first_day = _monday(today - timedelta(days=WINDOW_DAYS))
    start = days_bounds(first_day, first_day)[0]
    out: Counter = Counter()
    event_areas = await _event_areas(session, start)
    await _passenger_funnel(session, config, start, event_areas, out)
    await _driver_funnel(session, config, start, event_areas, out)
    for role in ("passenger", "driver"):
        await _retention(session, config, role, start, today, out)
    await session.execute(delete(AnalyticsCohort).where(AnalyticsCohort.cohort >= first_day))
    if out:
        await session.execute(
            insert(AnalyticsCohort),
            [
                {
                    "id": uuid.uuid4(),
                    "kind": kind,
                    "cohort": cohort,
                    "area": area,
                    "step": step,
                    "users": users,
                }
                for (kind, cohort, area, step), users in out.items()
            ],
        )
    await session.commit()
    kinds = Counter(key[0] for key in out)
    return dict(kinds)


async def _computed_at(session: AsyncSession) -> datetime | None:
    return await session.scalar(select(func.max(AnalyticsCohort.updated_at)))


async def _cohort_steps(
    session: AsyncSession, kind: str, first: date, last: date, area: ServiceArea | None
) -> dict[str, int]:
    stmt = (
        select(AnalyticsCohort.step, func.sum(AnalyticsCohort.users))
        .where(
            AnalyticsCohort.kind == kind,
            AnalyticsCohort.cohort >= first,
            AnalyticsCohort.cohort <= last,
        )
        .group_by(AnalyticsCohort.step)
    )
    if area is not None:
        stmt = stmt.where(AnalyticsCohort.area == area.name)
    return {step: int(users or 0) for step, users in await session.execute(stmt)}


# --- Funnels -----------------------------------------------------------------------------------


def _steps(names: Sequence[str], counts: dict[str, int]) -> list[FunnelStep]:
    return [FunnelStep(step=name, users=counts.get(name, 0)) for name in names]


async def funnels(
    session: AsyncSession, first: date, last: date, area: ServiceArea | None
) -> Funnels:
    start, end = days_bounds(first, last)
    passenger = await _cohort_steps(session, "passenger_funnel", first, last, area)
    driver = await _cohort_steps(session, "driver_funnel", first, last, area)

    events = [AnalyticsEvent.occurred_at >= start, AnalyticsEvent.occurred_at < end]
    if area is not None:
        events.append(AnalyticsEvent.area == area.name)
    quotes = await session.scalar(
        select(func.count())
        .select_from(AnalyticsEvent)
        .where(*events, AnalyticsEvent.event == "quote_shown")
    )
    row = (
        await session.execute(
            select(
                func.count(Ride.id),
                func.count(Ride.id).filter(Ride.assigned_at.is_not(None)),
                func.count(Ride.id).filter(Ride.status == RideStatus.COMPLETED),
            ).where(
                Ride.requested_at >= start,
                Ride.requested_at < end,
                *_in_area(area),
                *_real_rides(),
            )
        )
    ).one()
    rides = [
        FunnelStep(step="quote", users=quotes or 0),
        FunnelStep(step="request", users=row[0]),
        FunnelStep(step="matched", users=row[1]),
        FunnelStep(step="completed", users=row[2]),
    ]

    step = AnalyticsEvent.props["step"].astext
    screens = dict(
        (
            await session.execute(
                select(step, func.count(distinct(_who())))
                .where(
                    AnalyticsEvent.occurred_at >= start,
                    AnalyticsEvent.occurred_at < end,
                    AnalyticsEvent.event == "driver_onboarding_step",
                )
                .group_by(step)
            )
        ).all()
    )
    return Funnels(
        passenger=_steps(PASSENGER_STEPS, passenger),
        driver=_steps(DRIVER_STEPS, driver),
        rides=rides,
        onboarding_screens=_steps(ONBOARDING_STEPS, screens),
        computed_at=await _computed_at(session),
    )


# --- Retention ---------------------------------------------------------------------------------


async def _retention_table(
    session: AsyncSession, role: str, first: date, last: date, area: ServiceArea | None
) -> RetentionTable:
    stmt = (
        select(AnalyticsCohort.cohort, AnalyticsCohort.step, func.sum(AnalyticsCohort.users))
        .where(
            AnalyticsCohort.kind == f"{role}_retention",
            AnalyticsCohort.cohort >= _monday(first),
            AnalyticsCohort.cohort <= last,
        )
        .group_by(AnalyticsCohort.cohort, AnalyticsCohort.step)
        .order_by(AnalyticsCohort.cohort.desc())
    )
    if area is not None:
        stmt = stmt.where(AnalyticsCohort.area == area.name)
    cohorts: dict[date, dict[str, int]] = {}
    for cohort, step, users in await session.execute(stmt):
        cohorts.setdefault(cohort, {})[step] = int(users or 0)
    rows = [
        RetentionRow(
            cohort=cohort,
            users=steps.get("w0", 0),
            weeks={str(n): steps.get(f"w{n}") for n in RETENTION_WEEKS},
        )
        for cohort, steps in cohorts.items()
    ]
    average: dict[str, float | None] = {}
    for n in RETENTION_WEEKS:
        measured = [r for r in rows if r.weeks[str(n)] is not None]
        base = sum(r.users for r in measured)
        returned = sum(r.weeks[str(n)] or 0 for r in measured)
        average[str(n)] = round(100 * returned / base, 1) if base else None
    return RetentionTable(rows=rows, average=average)


async def retention(
    session: AsyncSession, first: date, last: date, area: ServiceArea | None
) -> Retention:
    return Retention(
        passenger=await _retention_table(session, "passenger", first, last, area),
        driver=await _retention_table(session, "driver", first, last, area),
        computed_at=await _computed_at(session),
    )


# --- Supply and demand -------------------------------------------------------------------------


async def supply_demand(
    session: AsyncSession,
    first: date,
    last: date,
    area: ServiceArea | None,
    hour: int | None,
) -> SupplyDemand:
    start, end = days_bounds(first, last)
    cells: dict[str, dict[str, float]] = {}
    hours: dict[int, dict[str, float]] = {h: {} for h in range(24)}

    def add(cell: str, h: int, key: str, value: float) -> None:
        hours[h][key] = hours[h].get(key, 0) + value
        if hour is None or h == hour:
            bucket = cells.setdefault(cell, {})
            bucket[key] = bucket.get(key, 0) + value

    ride_cell = _cell(Ride.pickup_lat, Ride.pickup_lng)
    ride_hour = _local_hour(Ride.requested_at)
    for cell, h, requests, no_drivers in await session.execute(
        select(
            ride_cell,
            ride_hour,
            func.count(Ride.id),
            func.count(Ride.id).filter(Ride.status == RideStatus.NO_DRIVERS),
        )
        .where(
            Ride.requested_at >= start,
            Ride.requested_at < end,
            *_in_area(area),
            *_real_rides(),
        )
        .group_by(ride_cell, ride_hour)
    ):
        add(cell, h, "requests", requests)
        add(cell, h, "no_drivers", no_drivers)

    event_hour = _local_hour(AnalyticsEvent.occurred_at)
    events = [
        AnalyticsEvent.event == "quote_shown",
        AnalyticsEvent.cell.is_not(None),
        AnalyticsEvent.occurred_at >= start,
        AnalyticsEvent.occurred_at < end,
    ]
    if area is not None:
        events.append(AnalyticsEvent.area == area.name)
    for cell, h, quotes in await session.execute(
        select(AnalyticsEvent.cell, event_hour, func.count())
        .where(*events)
        .group_by(AnalyticsEvent.cell, event_hour)
    ):
        add(cell, h, "quotes", quotes)

    supply_hour = _local_hour(SupplyHour.hour)
    supply = [SupplyHour.hour >= start, SupplyHour.hour < end]
    if area is not None:
        supply.append(SupplyHour.area == area.name)
    for cell, h, minutes in await session.execute(
        select(SupplyHour.cell, supply_hour, func.sum(SupplyHour.driver_minutes))
        .where(*supply)
        .group_by(SupplyHour.cell, supply_hour)
    ):
        add(cell, h, "driver_minutes", minutes or 0)

    def cell_row(cell: str, values: dict[str, float]) -> SupplyCell:
        lat, lng = cell_center(cell)
        return SupplyCell(
            cell=cell,
            lat=lat,
            lng=lng,
            requests=int(values.get("requests", 0)),
            no_drivers=int(values.get("no_drivers", 0)),
            quotes=int(values.get("quotes", 0)),
            driver_hours=round(values.get("driver_minutes", 0) / 60, 1),
        )

    rows = sorted(
        (cell_row(c, v) for c, v in cells.items()),
        key=lambda r: (r.no_drivers, r.requests, r.quotes, r.driver_hours),
        reverse=True,
    )[:MAX_CELLS]
    return SupplyDemand(
        cells=rows,
        hours=[
            SupplyHourRow(
                hour=h,
                requests=int(v.get("requests", 0)),
                no_drivers=int(v.get("no_drivers", 0)),
                quotes=int(v.get("quotes", 0)),
                driver_hours=round(v.get("driver_minutes", 0) / 60, 1),
            )
            for h, v in hours.items()
        ],
    )


# --- Promotions --------------------------------------------------------------------------------


async def promotions(session: AsyncSession, first: date, last: date) -> list[PromotionRow]:
    start, end = days_bounds(first, last)
    done = [Ride.status == RideStatus.COMPLETED, *_real_rides()]
    used = {
        pid: (count, total or ZERO)
        for pid, count, total in await session.execute(
            select(Ride.promotion_id, func.count(Ride.id), func.sum(Ride.discount))
            .where(
                *done,
                Ride.promotion_id.is_not(None),
                Ride.completed_at >= start,
                Ride.completed_at < end,
            )
            .group_by(Ride.promotion_id)
        )
    }
    firsts = (
        select(
            Ride.passenger_id.label("uid"),
            Ride.promotion_id.label("pid"),
            Ride.completed_at.label("at"),
        )
        .where(*done)
        .distinct(Ride.passenger_id)
        .order_by(Ride.passenger_id, Ride.completed_at)
        .subquery()
    )
    later = aliased(Ride)
    returned = exists().where(
        later.passenger_id == firsts.c.uid,
        later.status == RideStatus.COMPLETED,
        later.completed_at > firsts.c.at,
        later.completed_at <= firsts.c.at + timedelta(days=RETURN_DAYS),
    )
    now = datetime.now(UTC)
    acquired = {
        pid: (new, back, eligible)
        for pid, new, back, eligible in await session.execute(
            select(
                firsts.c.pid,
                func.count(),
                func.count().filter(returned),
                func.count().filter(firsts.c.at <= now - timedelta(days=RETURN_DAYS)),
            )
            .where(firsts.c.pid.is_not(None), firsts.c.at >= start, firsts.c.at < end)
            .group_by(firsts.c.pid)
        )
    }
    ids = set(used) | set(acquired)
    if not ids:
        return []
    names = {p.id: p for p in await session.scalars(select(Promotion).where(Promotion.id.in_(ids)))}
    rows = []
    for pid in ids:
        promotion = names.get(pid)
        rides, cost = used.get(pid, (0, ZERO))
        new, back, eligible = acquired.get(pid, (0, 0, 0))
        cost = Decimal(cost).quantize(Decimal("0.01"))
        rows.append(
            PromotionRow(
                id=pid,
                name=promotion.name if promotion else "—",
                code=promotion.code if promotion else None,
                rides=rides,
                cost=cost,
                cost_per_ride=(cost / rides).quantize(Decimal("0.01")) if rides else None,
                new_passengers=new,
                cost_per_new_passenger=(cost / new).quantize(Decimal("0.01")) if new else None,
                returned_30d=back,
                eligible_30d=eligible,
                retention_30d=round(100 * back / new, 1) if new else None,
            )
        )
    return sorted(rows, key=lambda r: r.cost, reverse=True)


# --- Drivers' economics ------------------------------------------------------------------------


async def drivers(session: AsyncSession, month: date, area: ServiceArea | None) -> DriverEconomics:
    start, end = month_bounds(month)
    now = datetime.now(UTC)
    rows = await session.execute(
        select(Ride.driver_id, func.sum(Ride.fare - Ride.discount))
        .where(
            Ride.status == RideStatus.COMPLETED,
            Ride.completed_at >= start,
            Ride.completed_at < end,
            Ride.driver_id.is_not(None),
            *_in_area(area),
            *_real_rides(),
        )
        .group_by(Ride.driver_id)
    )
    earnings = {uid: Decimal(total or 0).quantize(Decimal("0.01")) for uid, total in rows}
    values = sorted(earnings.values())
    schedule = await subscriptions.schedule_for(session, month)
    tiers = subscriptions._breakdown(schedule.tiers, values)

    ride_seconds = dict(
        (
            await session.execute(
                select(
                    Ride.driver_id,
                    func.sum(extract("epoch", Ride.completed_at - Ride.assigned_at)),
                )
                .where(
                    Ride.status == RideStatus.COMPLETED,
                    Ride.completed_at >= start,
                    Ride.completed_at < end,
                    Ride.assigned_at.is_not(None),
                    *_in_area(area),
                    *_real_rides(),
                )
                .group_by(Ride.driver_id)
            )
        ).all()
    )
    ended = func.least(func.coalesce(DriverOnlineSession.ended_at, now), end)
    began = func.greatest(DriverOnlineSession.started_at, start)
    online = [
        DriverOnlineSession.started_at < end,
        or_(DriverOnlineSession.ended_at.is_(None), DriverOnlineSession.ended_at > start),
        not_(DriverOnlineSession.driver_id.in_(_test_users())),
    ]
    if area is not None:
        online.append(DriverOnlineSession.area == area.name)
    online_seconds = dict(
        (
            await session.execute(
                select(
                    DriverOnlineSession.driver_id,
                    func.sum(func.greatest(extract("epoch", ended - began), 0)),
                )
                .where(*online)
                .group_by(DriverOnlineSession.driver_id)
            )
        ).all()
    )
    total_online = sum(float(v or 0) for v in online_seconds.values()) / 3600
    total_ride = sum(float(v or 0) for v in ride_seconds.values()) / 3600
    shares = [
        min(100.0, 100 * float(ride_seconds.get(uid) or 0) / float(seconds))
        for uid, seconds in online_seconds.items()
        if seconds and float(seconds) / 3600 >= MIN_ONLINE_HOURS
    ]
    return DriverEconomics(
        month=month,
        drivers=len(values),
        total_earnings=sum(values, ZERO),
        median_earnings=Decimal(statistics.median(values)).quantize(Decimal("0.01"))
        if values
        else None,
        earnings=_buckets((float(v) for v in values), EARNING_EDGES),
        tiers=[TierDrivers(above=t.tier.above, fee=t.tier.fee, drivers=t.drivers) for t in tiers],
        online_drivers=len(online_seconds),
        online_hours=round(total_online, 1),
        ride_hours=round(total_ride, 1),
        utilization=round(100 * total_ride / total_online, 1) if total_online else None,
        utilization_spread=_buckets(shares, UTILIZATION_EDGES),
    )


def default_month() -> date:
    return local_now().date().replace(day=1)


# --- CSV ---------------------------------------------------------------------------------------


def _csv(header: list[str], rows: Iterable[Sequence[Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def funnels_csv(data: Funnels) -> str:
    groups = (
        ("pasajero", data.passenger),
        ("motorizado", data.driver),
        ("viajes", data.rides),
        ("pantallas_motorizado", data.onboarding_screens),
    )
    return _csv(
        ["embudo", "paso", "personas"],
        ([name, s.step, s.users] for name, steps in groups for s in steps),
    )


def retention_csv(data: Retention) -> str:
    header = ["rol", "cohorte", "personas", *(f"semana_{n}" for n in RETENTION_WEEKS)]
    rows = []
    for role, table in (("pasajero", data.passenger), ("motorizado", data.driver)):
        for r in table.rows:
            weeks = [r.weeks[str(n)] for n in RETENTION_WEEKS]
            rows.append([role, r.cohort, r.users, *("" if w is None else w for w in weeks)])
    return _csv(header, rows)


def supply_demand_csv(data: SupplyDemand) -> str:
    return _csv(
        ["celda", "lat", "lng", "pedidos", "sin_motorizado", "cotizaciones", "horas_motorizado"],
        (
            [c.cell, c.lat, c.lng, c.requests, c.no_drivers, c.quotes, c.driver_hours]
            for c in data.cells
        ),
    )


def promotions_csv(rows: list[PromotionRow]) -> str:
    return _csv(
        [
            "promocion",
            "codigo",
            "viajes",
            "costo",
            "costo_por_viaje",
            "pasajeros_nuevos",
            "costo_por_pasajero_nuevo",
            "volvieron_30d",
            "medibles_30d",
        ],
        (
            [
                r.name,
                r.code or "",
                r.rides,
                f"{r.cost:.2f}",
                "" if r.cost_per_ride is None else f"{r.cost_per_ride:.2f}",
                r.new_passengers,
                "" if r.cost_per_new_passenger is None else f"{r.cost_per_new_passenger:.2f}",
                r.returned_30d,
                r.eligible_30d,
            ]
            for r in rows
        ),
    )


def drivers_csv(data: DriverEconomics) -> str:
    rows: list[list[Any]] = [
        ["ganancias", f"{b.min:g}-{'' if b.max is None else f'{b.max:g}'}", b.count]
        for b in data.earnings
    ]
    rows += [["tramo", f"{t.above:.2f}", t.drivers] for t in data.tiers]
    rows += [
        ["utilizacion", f"{b.min:g}-{'' if b.max is None else f'{b.max:g}'}", b.count]
        for b in data.utilization_spread
    ]
    rows += [
        ["horas_conectado", "", data.online_hours],
        ["horas_en_viaje", "", data.ride_hours],
    ]
    return _csv(["serie", "rango", "valor"], rows)
