"""Monthly subscription: fee tiers, earnings, the charge on the 1st, collection and blocking.

- Earnings of a month = sum of ``total`` of the driver's completed rides in that (Caracas) month,
  ignoring rides completed during the free period (first trip + ``subscription_free_months``).
- ``charge_month`` is idempotent (one charge per driver and month), so the worker can run it as
  often as it wants and an admin can re-run it.
- A charge the wallet cannot cover stays ``pending``; every credit retries it
  (``collect_pending``). Past ``due_at`` the driver is blocked until it is paid or waived.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig
from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile
from apps.rides.models import Ride, RideStatus
from apps.subscriptions.models import Charge, ChargeStatus, FeeSchedule
from apps.subscriptions.schemas import ChargeRead, Tier
from apps.users.models import User
from apps.wallet import notify
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind
from kuulis.core.calendar import (
    add_months,
    add_months_dt,
    format_month,
    local_now,
    month_bounds,
    month_start,
)
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from kuulis.core.pagination import PageParams

ZERO = Decimal("0.00")

# The table Carlos approved (docs/product/business-model.md). Used when no schedule is stored.
DEFAULT_TIERS = [
    Tier(above=Decimal(above), fee=Decimal(fee))
    for above, fee in (
        ("0", "0"),
        ("100", "5"),
        ("200", "10"),
        ("300", "15"),
        ("400", "20"),
        ("500", "25"),
        ("600", "30"),
    )
]
DEFAULT_EFFECTIVE = date(2026, 1, 1)


class SubscriptionOverdueError(PermissionDeniedError):
    code = "subscription_overdue"
    message = "Pay your pending fee to receive rides"


class ChargeNotFoundError(NotFoundError):
    code = "charge_not_found"
    message = "Charge not found"


class ChargeNotPendingError(ConflictError):
    code = "charge_not_pending"
    message = "Only pending charges can be waived"


class MonthNotClosedError(AppError):
    code = "month_not_closed"
    message = "Only months that already ended can be charged"


class ScheduleMonthInvalidError(AppError):
    code = "schedule_month_invalid"
    message = "A new schedule can only start next month or later"


class ScheduleExistsError(ConflictError):
    code = "schedule_exists"
    message = "There is already a schedule starting that month"


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Tiers -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Schedule:
    id: uuid.UUID | None
    effective_month: date
    tiers: list[Tier]


def fee_for(tiers: Sequence[Tier], earnings: Decimal) -> Decimal:
    if earnings <= 0:
        return ZERO
    fee = ZERO
    for tier in sorted(tiers, key=lambda t: t.above):
        if earnings > tier.above:
            fee = tier.fee
    return fee


def _schedule(row: FeeSchedule) -> Schedule:
    return Schedule(row.id, row.effective_month, [Tier.model_validate(t) for t in row.tiers])


async def schedule_for(session: AsyncSession, month: date) -> Schedule:
    row = await session.scalar(
        select(FeeSchedule)
        .where(FeeSchedule.effective_month <= month)
        .order_by(FeeSchedule.effective_month.desc())
        .limit(1)
    )
    return _schedule(row) if row else Schedule(None, DEFAULT_EFFECTIVE, DEFAULT_TIERS)


async def list_schedules(session: AsyncSession) -> list[tuple[Schedule, FeeSchedule | None]]:
    """Current schedule first, then future ones, then past ones."""
    rows = list(await session.scalars(select(FeeSchedule).order_by(FeeSchedule.effective_month)))
    current_month = month_start(local_now())
    current = await schedule_for(session, current_month)
    result: list[tuple[Schedule, FeeSchedule | None]] = []
    current_row = next((r for r in rows if r.id == current.id), None)
    result.append((current, current_row))
    result += [(_schedule(r), r) for r in rows if r.effective_month > current_month]
    result += [
        (_schedule(r), r)
        for r in reversed(rows)
        if r.effective_month <= current_month and r.id != current.id
    ]
    return result


async def create_schedule(
    session: AsyncSession, admin: User, effective_month: date, tiers: list[Tier]
) -> FeeSchedule:
    if effective_month <= month_start(local_now()):
        raise ScheduleMonthInvalidError()
    exists = await session.scalar(
        select(FeeSchedule.id).where(FeeSchedule.effective_month == effective_month)
    )
    if exists:
        raise ScheduleExistsError()
    row = FeeSchedule(
        effective_month=effective_month,
        tiers=[t.model_dump(mode="json") for t in tiers],
        created_by_id=admin.id,
    )
    session.add(row)
    await session.flush()
    return row


# --- Earnings ----------------------------------------------------------------------------------


def free_until(profile: DriverProfile | None, config: AppConfig) -> datetime | None:
    if profile is None or profile.first_trip_completed_at is None:
        return None
    return add_months_dt(profile.first_trip_completed_at, config.subscription_free_months)


async def earnings(
    session: AsyncSession, user_ids: Iterable[uuid.UUID], start: datetime, end: datetime
) -> dict[uuid.UUID, Decimal]:
    ids = list(user_ids)
    if not ids or end <= start:
        return {}
    rows = await session.execute(
        select(Ride.driver_id, func.sum(Ride.fare - Ride.discount))
        .where(
            Ride.driver_id.in_(ids),
            Ride.status == RideStatus.COMPLETED,
            Ride.completed_at >= start,
            Ride.completed_at < end,
        )
        .group_by(Ride.driver_id)
    )
    return {uid: Decimal(total or 0).quantize(Decimal("0.01")) for uid, total in rows}


async def month_earnings(
    session: AsyncSession, profile: DriverProfile, month: date, config: AppConfig
) -> tuple[Decimal, bool]:
    """(counted earnings, free period touched this month)."""
    start, end = month_bounds(month)
    until = free_until(profile, config)
    free = until is not None and until > start
    counted_from = max(start, until) if until else start
    totals = await earnings(session, [profile.user_id], counted_from, end)
    return totals.get(profile.user_id, ZERO), free


# --- Charging ----------------------------------------------------------------------------------


@dataclass
class RunResult:
    created: int = 0
    paid: int = 0
    pending: int = 0
    waived: int = 0


async def _pay(session: AsyncSession, charge: Charge) -> bool:
    """Debits the fee if the (locked) wallet covers it."""
    w = await wallet.lock_wallet(session, charge.user_id)
    if w.balance < charge.fee:
        return False
    entry = await wallet.post_entry(
        session,
        charge.user_id,
        EntryKind.SUBSCRIPTION_FEE,
        -charge.fee,
        details={"month": format_month(charge.month)},
    )
    charge.status = ChargeStatus.PAID
    charge.paid_at = utcnow()
    charge.entry_id = entry.id
    return True


async def charge_month(session: AsyncSession, month: date) -> RunResult:
    """Creates the charges of a closed month. Commits per driver (a failure stops the run but
    keeps what was done; re-running continues)."""
    month = month_start(month)
    if month >= month_start(local_now()):
        raise MonthNotClosedError()
    config = await get_app_config(session)
    schedule = await schedule_for(session, month)
    start, end = month_bounds(month)
    driver_ids = list(
        await session.scalars(
            select(Ride.driver_id)
            .where(
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= start,
                Ride.completed_at < end,
                Ride.driver_id.is_not(None),
            )
            .distinct()
        )
    )
    done = set(
        await session.scalars(
            select(Charge.user_id).where(Charge.month == month, Charge.user_id.in_(driver_ids))
        )
    )
    result = RunResult()
    for user_id in driver_ids:
        if user_id in done:
            continue
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == user_id)
        )
        if profile is None:
            continue
        total, free = await month_earnings(session, profile, month, config)
        fee = fee_for(schedule.tiers, total)
        now = utcnow()
        stmt = (
            insert(Charge)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                month=month,
                earnings=total,
                fee=fee,
                status=ChargeStatus.WAIVED if fee <= 0 else ChargeStatus.PENDING,
                free_period=free,
                schedule_id=schedule.id,
                due_at=now + timedelta(days=config.subscription_grace_days),
                waived_reason=("free_period" if free else "below_minimum") if fee <= 0 else None,
            )
            .on_conflict_do_nothing(index_elements=[Charge.user_id, Charge.month])
            .returning(Charge.id)
        )
        charge_id = await session.scalar(stmt)
        if charge_id is None:  # another worker got there first
            await session.rollback()
            continue
        result.created += 1
        charge = await session.get(Charge, charge_id)
        assert charge is not None
        if charge.status == ChargeStatus.WAIVED:
            result.waived += 1
        elif await _pay(session, charge):
            result.paid += 1
            await _notify(session, charge, "fee_paid")
        else:
            result.pending += 1
            await _notify(session, charge, "fee_pending")
        await session.commit()
    return result


async def _notify(session: AsyncSession, charge: Charge, event: str) -> None:
    await notify.send(
        session,
        charge.user_id,
        event,
        kind="subscription",
        localized=lambda locale: {
            "month": notify.month_label(charge.month, locale),
            "due": notify.date_label(charge.due_at, locale),
        },
        fee=f"{charge.fee:.2f}",
    )


async def collect_pending(session: AsyncSession, user_id: uuid.UUID) -> list[Charge]:
    """Pays pending charges, oldest first, while the balance covers them (caller commits)."""
    charges = list(
        await session.scalars(
            select(Charge)
            .where(Charge.user_id == user_id, Charge.status == ChargeStatus.PENDING)
            .order_by(Charge.month)
            .with_for_update()
        )
    )
    paid = []
    for charge in charges:
        if not await _pay(session, charge):
            break
        paid.append(charge)
        await _notify(session, charge, "fee_paid")
    return paid


async def waive(session: AsyncSession, admin: User, charge_id: uuid.UUID, reason: str) -> Charge:
    charge = await session.scalar(select(Charge).where(Charge.id == charge_id).with_for_update())
    if charge is None:
        raise ChargeNotFoundError()
    if charge.status != ChargeStatus.PENDING:
        raise ChargeNotPendingError(details={"status": charge.status.value})
    charge.status = ChargeStatus.WAIVED
    charge.waived_reason = reason
    charge.waived_by_id = admin.id
    await _notify(session, charge, "fee_waived")
    return charge


# --- Blocking ----------------------------------------------------------------------------------


async def overdue_user_ids(session: AsyncSession, user_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not user_ids:
        return set()
    rows = await session.scalars(
        select(Charge.user_id).where(
            Charge.user_id.in_(user_ids),
            Charge.status == ChargeStatus.PENDING,
            Charge.due_at <= utcnow(),
        )
    )
    return set(rows)


async def ensure_not_overdue(session: AsyncSession, user_id: uuid.UUID) -> None:
    if await overdue_user_ids(session, [user_id]):
        raise SubscriptionOverdueError()


async def send_reminders(session: AsyncSession) -> int:
    """Due-tomorrow and overdue notices, once per charge."""
    now = utcnow()
    sent = 0
    soon = await session.scalars(
        select(Charge).where(
            Charge.status == ChargeStatus.PENDING,
            Charge.notified_due_soon.is_(False),
            Charge.due_at > now,
            Charge.due_at <= now + timedelta(days=1),
        )
    )
    for charge in list(soon):
        charge.notified_due_soon = True
        await _notify(session, charge, "fee_due_soon")
        sent += 1
    overdue = await session.scalars(
        select(Charge).where(
            Charge.status == ChargeStatus.PENDING,
            Charge.notified_overdue.is_(False),
            Charge.due_at <= now,
        )
    )
    for charge in list(overdue):
        charge.notified_overdue = True
        await _notify(session, charge, "fee_overdue")
        sent += 1
    await session.commit()
    return sent


# --- Reads -------------------------------------------------------------------------------------


def charge_read(charge: Charge) -> ChargeRead:
    return ChargeRead(
        id=charge.id,
        month=charge.month,
        earnings=charge.earnings,
        fee=charge.fee,
        status=charge.status,
        free_period=charge.free_period,
        due_at=charge.due_at,
        paid_at=charge.paid_at,
        waived_reason=charge.waived_reason,
        overdue=charge.status == ChargeStatus.PENDING and charge.due_at <= utcnow(),
    )


@dataclass
class Summary:
    month: date
    earnings: Decimal
    estimated_fee: Decimal
    free_until: datetime | None
    in_free_period: bool
    tiers: list[Tier]
    next_charge_at: datetime
    pending: list[Charge]
    overdue: bool


async def summary(session: AsyncSession, user_id: uuid.UUID) -> Summary:
    config = await get_app_config(session)
    profile = await wallet.require_driver(session, user_id)
    month = month_start(local_now())
    schedule = await schedule_for(session, month)
    total, _ = await month_earnings(session, profile, month, config)
    until = free_until(profile, config)
    pending = list(
        await session.scalars(
            select(Charge)
            .where(Charge.user_id == user_id, Charge.status == ChargeStatus.PENDING)
            .order_by(Charge.month)
        )
    )
    next_start, _ = month_bounds(add_months(month, 1))
    return Summary(
        month=month,
        earnings=total,
        estimated_fee=fee_for(schedule.tiers, total),
        free_until=until,
        in_free_period=until is None or until > utcnow(),
        tiers=schedule.tiers,
        next_charge_at=next_start,
        pending=pending,
        overdue=any(c.due_at <= utcnow() for c in pending),
    )


async def list_charges(
    session: AsyncSession,
    params: PageParams,
    *,
    user_id: uuid.UUID | None = None,
    month: date | None = None,
    status: ChargeStatus | None = None,
    q: str | None = None,
) -> tuple[list[tuple[Charge, User]], int, dict[str, Decimal]]:
    stmt = select(Charge, User).join(User, User.id == Charge.user_id)
    if user_id is not None:
        stmt = stmt.where(Charge.user_id == user_id)
    if month is not None:
        stmt = stmt.where(Charge.month == month)
    if status is not None:
        stmt = stmt.where(Charge.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
    sub = stmt.order_by(None).subquery()
    total = await session.scalar(select(func.count()).select_from(sub))
    sums = {
        key: Decimal(value or 0)
        for key, value in (
            await session.execute(select(sub.c.status, func.sum(sub.c.fee)).group_by(sub.c.status))
        ).all()
    }
    rows = await session.execute(
        stmt.order_by(Charge.month.desc(), Charge.created_at.desc())
        .limit(params.limit)
        .offset(params.offset)
    )
    totals = {s.value: sums.get(s, ZERO) for s in ChargeStatus}
    return [(c, u) for c, u in rows.all()], int(total or 0), totals
