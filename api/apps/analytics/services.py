"""Read-only numbers for the admin: finance reconciliation, ride metrics and the overview."""

import csv
import io
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, distinct, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.analytics.schemas import (
    AdjustmentTotals,
    CountAmount,
    FeeTotals,
    FinanceDay,
    FinanceSummary,
    Metrics,
    MetricsDay,
    MetricsHour,
    MetricsTotals,
    Overview,
    TopDriver,
    TopUpTotals,
)
from apps.config.schemas import AppConfig, ServiceArea
from apps.drivers.models import DriverProfile, DriverStatus
from apps.moderation import services as moderation
from apps.rates import services as rates
from apps.rides import presence
from apps.rides.models import ACTIVE_STATUSES, Rating, RatingRole, Ride, RideStatus
from apps.subscriptions.models import Charge, ChargeStatus
from apps.users.models import User
from apps.wallet.models import EntryKind, TopUp, TopUpStatus, Wallet, WalletEntry
from kuulis.core.calendar import CARACAS_TZ, days_bounds, local_now
from kuulis.core.exceptions import AppError

ZERO = Decimal("0.00")
MAX_DAYS = 366
TZ = "America/Caracas"


class RangeInvalidError(AppError):
    status_code = 422
    code = "range_invalid"
    message = "The date range is invalid (from after to, or longer than 366 days)"


class AreaNotFoundError(AppError):
    code = "area_not_found"
    message = "Unknown city"


def check_range(first: date | None, last: date | None) -> tuple[date, date]:
    """Defaults to the current month so far."""
    today = local_now().date()
    last = last or today
    first = first or last.replace(day=1)
    if first > last or (last - first).days >= MAX_DAYS:
        raise RangeInvalidError(details={"from": str(first), "to": str(last)})
    return first, last


def _money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _local_day(column: Any) -> Any:
    return func.date(func.timezone(TZ, column))


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


# --- Finance -----------------------------------------------------------------------------------


async def finance_summary(session: AsyncSession, first: date, last: date) -> FinanceSummary:
    start, end = days_bounds(first, last)

    async def top_ups(*where: Any) -> CountAmount:
        row = (
            await session.execute(
                select(func.count(TopUp.id), func.sum(TopUp.amount)).where(*where)
            )
        ).one()
        return CountAmount(count=row[0], amount=_money(row[1]))

    completed = (
        TopUp.status == TopUpStatus.COMPLETED,
        TopUp.completed_at >= start,
        TopUp.completed_at < end,
    )
    created = (TopUp.created_at >= start, TopUp.created_at < end)
    totals = TopUpTotals(
        completed=await top_ups(*completed),
        # The reconciliation loop credits without a reviewer.
        completed_auto=await top_ups(*completed, TopUp.reviewed_by_id.is_(None)),
        completed_manual=await top_ups(*completed, TopUp.reviewed_by_id.is_not(None)),
        pending=await top_ups(TopUp.status == TopUpStatus.PENDING, *created),
        unmatched=await top_ups(TopUp.status == TopUpStatus.UNMATCHED, *created),
        rejected=await top_ups(TopUp.status == TopUpStatus.REJECTED, *created),
    )

    in_range = (WalletEntry.created_at >= start, WalletEntry.created_at < end)
    rows = await session.execute(
        select(
            WalletEntry.kind,
            func.count(WalletEntry.id),
            func.sum(func.greatest(WalletEntry.amount, 0)),
            func.sum(func.least(WalletEntry.amount, 0)),
        )
        .where(*in_range)
        .group_by(WalletEntry.kind)
    )
    by_kind = {kind: (count, _money(plus), _money(minus)) for kind, count, plus, minus in rows}
    empty = (0, ZERO, ZERO)

    pending_fees = await session.scalar(
        select(func.sum(Charge.fee)).where(Charge.status == ChargeStatus.PENDING)
    )
    waived = await session.scalar(
        select(func.count(Charge.id)).where(
            Charge.status == ChargeStatus.WAIVED,
            Charge.created_at >= start,
            Charge.created_at < end,
        )
    )
    balances = await session.scalar(select(func.sum(Wallet.balance)))

    day = _local_day(WalletEntry.created_at)
    daily = await session.execute(
        select(day, WalletEntry.kind, func.sum(WalletEntry.amount))
        .where(
            *in_range,
            WalletEntry.kind.in_(
                [EntryKind.TOP_UP, EntryKind.SUBSCRIPTION_FEE, EntryKind.PROMO_CREDIT]
            ),
        )
        .group_by(day, WalletEntry.kind)
    )
    per_day: dict[date, dict[EntryKind, Decimal]] = {}
    for d, kind, amount in daily:
        per_day.setdefault(d, {})[kind] = _money(amount)

    return FinanceSummary(
        from_=first,
        to=last,
        top_ups=totals,
        fees=FeeTotals(
            collected=-by_kind.get(EntryKind.SUBSCRIPTION_FEE, empty)[2],
            pending=_money(pending_fees),
            waived_count=waived or 0,
        ),
        promo_credits=by_kind.get(EntryKind.PROMO_CREDIT, empty)[1],
        adjustments=AdjustmentTotals(
            credit=by_kind.get(EntryKind.ADJUSTMENT, empty)[1],
            debit=-by_kind.get(EntryKind.ADJUSTMENT, empty)[2],
        ),
        transfers=CountAmount(
            count=by_kind.get(EntryKind.TRANSFER_OUT, empty)[0],
            amount=-by_kind.get(EntryKind.TRANSFER_OUT, empty)[2],
        ),
        wallet_balances=_money(balances),
        by_day=[
            FinanceDay(
                date=d,
                top_ups=per_day.get(d, {}).get(EntryKind.TOP_UP, ZERO),
                fees=-per_day.get(d, {}).get(EntryKind.SUBSCRIPTION_FEE, ZERO),
                promo_credits=per_day.get(d, {}).get(EntryKind.PROMO_CREDIT, ZERO),
            )
            for d in _days(first, last)
        ],
    )


def _local(value: datetime | None) -> str:
    return value.astimezone(CARACAS_TZ).strftime("%Y-%m-%d %H:%M") if value else ""


def _detail(details: dict) -> str:
    return "; ".join(f"{k}: {v}" for k, v in (details or {}).items() if v not in (None, ""))


async def _csv(header: list[str], rows: AsyncIterator[list[Any]]) -> str:
    """Built in memory: at most a year of rows, and the DB session ends with the request."""
    buffer = io.StringIO()
    buffer.write("\ufeff")  # BOM: Excel opens UTF-8 correctly
    writer = csv.writer(buffer)
    writer.writerow(header)
    async for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


async def _stream(session: AsyncSession, stmt: Select) -> AsyncIterator[Any]:
    result = await session.stream(stmt.execution_options(yield_per=500))
    async for row in result:
        yield row


async def entries_csv(
    session: AsyncSession, first: date, last: date, kind: EntryKind | None
) -> str:
    start, end = days_bounds(first, last)
    stmt = (
        select(WalletEntry, User.full_name, User.email, TopUp.reference, TopUp.transaction_id)
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .join(User, User.id == Wallet.user_id)
        .outerjoin(TopUp, TopUp.entry_id == WalletEntry.id)
        .where(WalletEntry.created_at >= start, WalletEntry.created_at < end)
        .order_by(WalletEntry.created_at)
    )
    if kind:
        stmt = stmt.where(WalletEntry.kind == kind)

    async def rows() -> AsyncIterator[list[Any]]:
        async for entry, name, email, reference, transaction in _stream(session, stmt):
            yield [
                _local(entry.created_at),
                name or "",
                email,
                entry.kind.value,
                f"{entry.amount:.2f}",
                f"{entry.balance_after:.2f}",
                transaction or reference or "",
                _detail(entry.details),
            ]

    header = ["fecha", "usuario", "email", "tipo", "monto", "saldo_despues", "referencia"]
    return await _csv([*header, "detalle"], rows())


async def top_ups_csv(
    session: AsyncSession, first: date, last: date, status: TopUpStatus | None
) -> str:
    start, end = days_bounds(first, last)
    stmt = (
        select(TopUp, User.full_name, User.email)
        .outerjoin(User, User.id == TopUp.user_id)
        .where(TopUp.created_at >= start, TopUp.created_at < end)
        .order_by(TopUp.created_at)
    )
    if status:
        stmt = stmt.where(TopUp.status == status)

    async def rows() -> AsyncIterator[list[Any]]:
        async for top_up, name, email in _stream(session, stmt):
            completed = top_up.status == TopUpStatus.COMPLETED
            origin = ("manual" if top_up.reviewed_by_id else "auto") if completed else ""
            yield [
                _local(top_up.created_at),
                _local(top_up.completed_at),
                top_up.status.value,
                origin,
                f"{top_up.amount:.2f}",
                name or "",
                email or "",
                top_up.payer_binance_id or "",
                top_up.payer_name or "",
                top_up.transaction_id or "",
                top_up.reference or "",
                top_up.note or top_up.rejection_reason or "",
            ]

    header = [
        "creada",
        "acreditada",
        "estado",
        "origen",
        "monto",
        "motorizado",
        "email",
        "binance_pay_id_pagador",
        "nombre_pagador",
        "transaccion",
        "referencia",
        "nota",
    ]
    return await _csv(header, rows())


# --- Metrics -----------------------------------------------------------------------------------


def find_area(config: AppConfig, name: str | None) -> ServiceArea | None:
    if not name:
        return None
    for area in config.service_areas:
        if area.name.lower() == name.strip().lower():
            return area
    raise AreaNotFoundError(details={"areas": [a.name for a in config.service_areas]})


def _in_area(area: ServiceArea | None) -> list[Any]:
    if area is None:
        return []
    return [
        Ride.pickup_lat.between(area.min_lat, area.max_lat),
        Ride.pickup_lng.between(area.min_lng, area.max_lng),
    ]


def _seconds(value: Any) -> int | None:
    return round(value) if value is not None else None


def _avg_secs(later: Any, earlier: Any) -> Any:
    return func.avg(extract("epoch", later - earlier))


async def metrics(
    session: AsyncSession, first: date, last: date, area: ServiceArea | None
) -> Metrics:
    start, end = days_bounds(first, last)
    where = [Ride.requested_at >= start, Ride.requested_at < end, *_in_area(area)]
    done = Ride.status == RideStatus.COMPLETED

    def count(condition: Any) -> Any:
        return func.count(Ride.id).filter(condition)

    row = (
        await session.execute(
            select(
                func.count(Ride.id),
                count(done),
                count(Ride.status == RideStatus.CANCELLED_BY_PASSENGER),
                count(Ride.status == RideStatus.CANCELLED_BY_DRIVER),
                count(Ride.status == RideStatus.CANCELLED_BY_ADMIN),
                count(Ride.status == RideStatus.NO_DRIVERS),
                func.sum(Ride.fare).filter(done),
                func.sum(Ride.discount).filter(done),
                func.avg(Ride.fare).filter(done),
                func.avg(Ride.distance_m).filter(done),
                _avg_secs(Ride.assigned_at, Ride.requested_at).filter(
                    Ride.assigned_at.is_not(None)
                ),
                _avg_secs(Ride.arrived_at, Ride.assigned_at).filter(
                    Ride.arrived_at.is_not(None), Ride.assigned_at.is_not(None)
                ),
                _avg_secs(Ride.completed_at, Ride.started_at).filter(
                    done, Ride.started_at.is_not(None)
                ),
                func.count(distinct(Ride.driver_id)).filter(done),
                func.count(distinct(Ride.passenger_id)).filter(done),
            ).where(*where)
        )
    ).one()
    requested, completed = row[0], row[1]
    # Rides still in flight are neither a success nor a failure yet.
    finished = requested - (
        await session.scalar(
            select(func.count(Ride.id)).where(*where, Ride.status.in_(ACTIVE_STATUSES))
        )
        or 0
    )

    new_passengers = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= start, User.created_at < end)
    )
    new_drivers = await session.scalar(
        select(func.count(DriverProfile.id)).where(
            DriverProfile.approved_at >= start,
            DriverProfile.approved_at < end,
            DriverProfile.status != DriverStatus.REJECTED,
        )
    )
    ratings = dict(
        (
            await session.execute(
                select(Rating.rater_role, func.avg(Rating.stars))
                .join(Ride, Ride.id == Rating.ride_id)
                .where(*where)
                .group_by(Rating.rater_role)
            )
        )
        .tuples()
        .all()
    )

    day = _local_day(Ride.requested_at)
    daily = await session.execute(
        select(
            day,
            func.count(Ride.id),
            count(done),
            count(
                Ride.status.in_(
                    [
                        RideStatus.CANCELLED_BY_PASSENGER,
                        RideStatus.CANCELLED_BY_DRIVER,
                        RideStatus.CANCELLED_BY_ADMIN,
                    ]
                )
            ),
            count(Ride.status == RideStatus.NO_DRIVERS),
            func.sum(Ride.fare).filter(done),
            func.count(distinct(Ride.driver_id)).filter(done),
        )
        .where(*where)
        .group_by(day)
    )
    per_day = {r[0]: r for r in daily}

    hour = extract("hour", func.timezone(TZ, Ride.requested_at))
    hourly = {
        int(h): (n, c)
        for h, n, c in await session.execute(
            select(hour, func.count(Ride.id), count(done)).where(*where).group_by(hour)
        )
    }

    top = await session.execute(
        select(
            Ride.driver_id,
            User.full_name,
            func.count(Ride.id),
            func.sum(Ride.fare),
            DriverProfile.rating_avg,
        )
        .join(User, User.id == Ride.driver_id)
        .outerjoin(DriverProfile, DriverProfile.user_id == Ride.driver_id)
        .where(*where, done)
        .group_by(Ride.driver_id, User.full_name, DriverProfile.rating_avg)
        .order_by(func.count(Ride.id).desc(), func.sum(Ride.fare).desc())
        .limit(10)
    )

    return Metrics(
        from_=first,
        to=last,
        area=area.name if area else None,
        totals=MetricsTotals(
            rides_requested=requested,
            rides_completed=completed,
            rides_cancelled_passenger=row[2],
            rides_cancelled_driver=row[3],
            rides_cancelled_admin=row[4],
            rides_no_drivers=row[5],
            completion_rate=round(completed / finished, 4) if finished else None,
            gmv=_money(row[6]),
            discounts=_money(row[7]),
            avg_fare=_money(row[8]) if row[8] is not None else None,
            avg_distance_m=_seconds(row[9]),
            avg_assign_s=_seconds(row[10]),
            avg_pickup_s=_seconds(row[11]),
            avg_trip_s=_seconds(row[12]),
            active_drivers=row[13],
            active_passengers=row[14],
            new_passengers=new_passengers or 0,
            new_drivers=new_drivers or 0,
            # Passengers rate drivers and the other way around.
            avg_rating_drivers=_rating(ratings.get(RatingRole.PASSENGER)),
            avg_rating_passengers=_rating(ratings.get(RatingRole.DRIVER)),
        ),
        by_day=[
            MetricsDay(
                date=d,
                requested=per_day[d][1] if d in per_day else 0,
                completed=per_day[d][2] if d in per_day else 0,
                cancelled=per_day[d][3] if d in per_day else 0,
                no_drivers=per_day[d][4] if d in per_day else 0,
                gmv=_money(per_day[d][5]) if d in per_day else ZERO,
                active_drivers=per_day[d][6] if d in per_day else 0,
            )
            for d in _days(first, last)
        ],
        by_hour=[
            MetricsHour(
                hour=h, requested=hourly.get(h, (0, 0))[0], completed=hourly.get(h, (0, 0))[1]
            )
            for h in range(24)
        ],
        top_drivers=[
            TopDriver(
                user_id=uid,
                name=_short(name),
                rides=n,
                earnings=_money(fare),
                rating_avg=float(avg) if avg is not None else None,
            )
            for uid, name, n, fare, avg in top
        ],
    )


def _rating(value: Any) -> float | None:
    return round(float(value), 2) if value is not None else None


def _short(name: str | None) -> str:
    parts = (name or "").split()
    if not parts:
        return ""
    return parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")


# --- Overview ----------------------------------------------------------------------------------


async def overview(session: AsyncSession) -> Overview:
    today = local_now().date()
    start, end = days_bounds(today, today)
    today_row = (
        await session.execute(
            select(
                func.count(Ride.id),
                func.count(Ride.id).filter(Ride.status == RideStatus.COMPLETED),
                func.sum(Ride.fare).filter(Ride.status == RideStatus.COMPLETED),
            ).where(Ride.requested_at >= start, Ride.requested_at < end)
        )
    ).one()
    in_progress = await session.scalar(
        select(func.count(Ride.id)).where(Ride.status.in_(ACTIVE_STATUSES))
    )
    applications = await session.scalar(
        select(func.count(DriverProfile.id)).where(
            DriverProfile.status == DriverStatus.PENDING_REVIEW
        )
    )
    top_ups = dict(
        (
            await session.execute(
                select(TopUp.status, func.count(TopUp.id))
                .where(TopUp.status.in_([TopUpStatus.PENDING, TopUpStatus.UNMATCHED]))
                .group_by(TopUp.status)
            )
        )
        .tuples()
        .all()
    )
    reports = await moderation.counts(session)
    overdue = await session.scalar(
        select(func.count(distinct(Charge.user_id))).where(
            and_(Charge.status == ChargeStatus.PENDING, Charge.due_at <= func.now())
        )
    )
    current = await rates.current_rates(session)
    stale = [name for name, value in current.model_dump().items() if value and value["stale"]]
    return Overview(
        online_drivers=len(await presence.online_entries()),
        rides_in_progress=in_progress or 0,
        rides_today=today_row[0],
        completed_today=today_row[1],
        gmv_today=_money(today_row[2]),
        pending_driver_applications=applications or 0,
        pending_top_ups=top_ups.get(TopUpStatus.PENDING, 0),
        unmatched_top_ups=top_ups.get(TopUpStatus.UNMATCHED, 0),
        open_reports=reports["open"] + reports["in_review"],
        urgent_reports=reports["urgent_open"],
        overdue_drivers=overdue or 0,
        stale_rates=stale,
    )
