"""Promotions: which one applies to a quote, the locked re-check when the ride is requested,
usage stats, the admin CRUD and the abuse alerts.

Usage is never stored on the promotion: it is derived from the rides that carry it, so a
cancelled ride releases its reservation without any bookkeeping.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from pydantic import ValidationError
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.config.schemas import AppConfig
from apps.drivers.models import DriverProfile, VehicleType
from apps.promotions.models import DiscountType, Promotion
from apps.promotions.schemas import (
    AlertDriver,
    AlertPerson,
    PairAlert,
    PromotionCreate,
    PromotionFields,
    PromotionRead,
    PromotionRide,
    PromotionStats,
    PromotionStatus,
    PromotionUpdate,
    normalize_code,
)
from apps.rides.models import ACTIVE_STATUSES, Ride, RideStatus
from apps.users.models import User
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError
from kuulis.core.pagination import PageParams

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
# Rides that hold (in flight) or consumed (completed) a promotion.
_COUNTED = frozenset(ACTIVE_STATUSES | {RideStatus.COMPLETED})


class PromotionInvalidError(AppError):
    code = "promotion_invalid"
    message = "The promotion code cannot be used"


class PromotionUnavailableError(ConflictError):
    code = "promotion_unavailable"
    message = "The promotion is no longer available, quote again"


class PromotionNotFoundError(NotFoundError):
    code = "promotion_not_found"
    message = "Promotion not found"


class PromotionCodeTakenError(ConflictError):
    code = "promotion_code_taken"
    message = "Another promotion already uses this code"


class PromotionValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Invalid promotion"


class BudgetBelowCommittedError(ConflictError):
    code = "budget_below_committed"
    message = "The budget cannot be lower than what is already committed"


class _Ineligible(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


def now_utc() -> datetime:
    return datetime.now(UTC)


# --- Usage -------------------------------------------------------------------------------------


@dataclass
class Usage:
    uses: int = 0
    completed: int = 0
    credited: Decimal = ZERO
    reserved: Decimal = ZERO

    @property
    def committed(self) -> Decimal:
        return self.credited + self.reserved


async def usage(
    session: AsyncSession, promotion_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Usage]:
    if not promotion_ids:
        return {}
    completed = Ride.status == RideStatus.COMPLETED
    active = Ride.status.in_(ACTIVE_STATUSES)
    rows = await session.execute(
        select(
            Ride.promotion_id,
            func.count(Ride.id),
            func.count(Ride.id).filter(completed),
            func.coalesce(func.sum(case((completed, Ride.discount), else_=0)), 0),
            func.coalesce(func.sum(case((active, Ride.discount), else_=0)), 0),
        )
        .where(Ride.promotion_id.in_(promotion_ids), Ride.status.in_(_COUNTED))
        .group_by(Ride.promotion_id)
    )
    result = {pid: Usage() for pid in promotion_ids}
    for pid, uses, done, credited, reserved in rows:
        result[pid] = Usage(int(uses), int(done), Decimal(credited), Decimal(reserved))
    return result


async def _passenger_uses(
    session: AsyncSession, promotion_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    count = await session.scalar(
        select(func.count(Ride.id)).where(
            Ride.promotion_id == promotion_id,
            Ride.passenger_id == user_id,
            Ride.status.in_(_COUNTED),
        )
    )
    return int(count or 0)


async def _has_completed_ride(session: AsyncSession, user_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(Ride.id)
        .where(Ride.passenger_id == user_id, Ride.status == RideStatus.COMPLETED)
        .limit(1)
    )
    return found is not None


def status_of(promotion: Promotion, use: Usage, now: datetime) -> PromotionStatus:
    if not promotion.is_active:
        return PromotionStatus.INACTIVE
    if now < promotion.starts_at:
        return PromotionStatus.SCHEDULED
    if now >= promotion.ends_at:
        return PromotionStatus.ENDED
    if promotion.budget - use.committed < CENT or (
        promotion.max_total_uses is not None and use.uses >= promotion.max_total_uses
    ):
        return PromotionStatus.EXHAUSTED
    return PromotionStatus.ACTIVE


# --- Applying a promotion ----------------------------------------------------------------------


def discount_for(promotion: Promotion, fare: Decimal) -> Decimal:
    if promotion.discount_type == DiscountType.PERCENT:
        amount = (fare * promotion.discount_value / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        if promotion.max_discount is not None:
            amount = min(amount, promotion.max_discount)
    else:
        amount = promotion.discount_value
    return max(ZERO, min(amount, fare)).quantize(CENT)


@dataclass(frozen=True)
class RideContext:
    user_id: uuid.UUID
    area: str | None  # service area name of the pickup
    vehicle_type: VehicleType
    fare: Decimal


async def _check(
    session: AsyncSession, promotion: Promotion, ctx: RideContext, now: datetime
) -> Decimal:
    """The discount this ride would get, or ``_Ineligible`` with the reason (contract codes)."""
    if not promotion.is_active:
        raise _Ineligible("not_found")
    if now < promotion.starts_at:
        raise _Ineligible("not_started")
    if now >= promotion.ends_at:
        raise _Ineligible("ended")
    if promotion.service_areas and ctx.area not in promotion.service_areas:
        raise _Ineligible("not_eligible")
    if promotion.vehicle_types and ctx.vehicle_type.value not in promotion.vehicle_types:
        raise _Ineligible("not_eligible")
    if ctx.fare < promotion.min_fare:
        raise _Ineligible("not_eligible")
    if promotion.first_ride_only and await _has_completed_ride(session, ctx.user_id):
        raise _Ineligible("first_ride_only")
    if (
        await _passenger_uses(session, promotion.id, ctx.user_id)
        >= promotion.max_uses_per_passenger
    ):
        raise _Ineligible("max_uses")
    discount = discount_for(promotion, ctx.fare)
    use = (await usage(session, [promotion.id]))[promotion.id]
    if promotion.max_total_uses is not None and use.uses >= promotion.max_total_uses:
        raise _Ineligible("exhausted")
    if discount <= 0 or use.committed + discount > promotion.budget:
        raise _Ineligible("exhausted")
    return discount


async def for_quote(
    session: AsyncSession, ctx: RideContext, code: str | None
) -> tuple[Promotion | None, Decimal]:
    """With a code: that promotion or ``promotion_invalid``. Without: the best automatic one."""
    now = now_utc()
    code = normalize_code(code)
    if code is not None:
        promotion = await session.scalar(select(Promotion).where(Promotion.code == code))
        if promotion is None:
            raise PromotionInvalidError(details={"reason": "not_found"})
        try:
            return promotion, await _check(session, promotion, ctx, now)
        except _Ineligible as exc:
            raise PromotionInvalidError(details={"reason": exc.reason}) from exc

    candidates = await session.scalars(
        select(Promotion).where(
            Promotion.code.is_(None),
            Promotion.is_active,
            Promotion.starts_at <= now,
            Promotion.ends_at > now,
        )
    )
    best: tuple[Promotion | None, Decimal] = (None, ZERO)
    for promotion in candidates:
        try:
            discount = await _check(session, promotion, ctx, now)
        except _Ineligible:
            continue
        if discount > best[1]:
            best = (promotion, discount)
    return best


async def lock_for_ride(
    session: AsyncSession, promotion_id: uuid.UUID, ctx: RideContext, expected: Decimal
) -> Promotion:
    """Re-checks a quoted promotion under its row lock (serializes the budget)."""
    promotion = await session.scalar(
        select(Promotion).where(Promotion.id == promotion_id).with_for_update()
    )
    if promotion is None:
        raise PromotionUnavailableError()
    try:
        discount = await _check(session, promotion, ctx, now_utc())
    except _Ineligible as exc:
        raise PromotionUnavailableError(details={"reason": exc.reason}) from exc
    if discount != expected:
        raise PromotionUnavailableError(details={"reason": "changed"})
    return promotion


# --- Admin -------------------------------------------------------------------------------------


def to_read(promotion: Promotion, use: Usage, now: datetime) -> PromotionRead:
    remaining = max(ZERO, promotion.budget - use.committed)
    return PromotionRead(
        id=promotion.id,
        name=promotion.name,
        description=promotion.description,
        code=promotion.code,
        discount_type=promotion.discount_type,
        discount_value=promotion.discount_value,
        max_discount=promotion.max_discount,
        min_fare=promotion.min_fare,
        starts_at=promotion.starts_at,
        ends_at=promotion.ends_at,
        budget=promotion.budget,
        max_uses_per_passenger=promotion.max_uses_per_passenger,
        max_total_uses=promotion.max_total_uses,
        first_ride_only=promotion.first_ride_only,
        service_areas=list(promotion.service_areas or []),
        vehicle_types=[VehicleType(v) for v in promotion.vehicle_types or []],
        is_active=promotion.is_active,
        status=status_of(promotion, use, now),
        stats=PromotionStats(
            uses=use.uses,
            completed=use.completed,
            credited=use.credited,
            reserved=use.reserved,
            remaining=remaining,
        ),
        created_at=promotion.created_at,
        updated_at=promotion.updated_at,
    )


async def get_or_404(session: AsyncSession, promotion_id: uuid.UUID) -> Promotion:
    promotion = await session.get(Promotion, promotion_id)
    if promotion is None:
        raise PromotionNotFoundError()
    return promotion


async def read(session: AsyncSession, promotion: Promotion) -> PromotionRead:
    use = (await usage(session, [promotion.id]))[promotion.id]
    return to_read(promotion, use, now_utc())


async def list_promotions(
    session: AsyncSession, status: PromotionStatus | None, q: str | None, params: PageParams
) -> tuple[list[PromotionRead], int]:
    """Promotions are few (tens to hundreds), so status (which depends on usage) is filtered in
    Python over the text-filtered set."""
    stmt = select(Promotion).order_by(Promotion.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Promotion.name.ilike(like), Promotion.code.ilike(like)))
    promotions = list(await session.scalars(stmt))
    uses = await usage(session, [p.id for p in promotions])
    now = now_utc()
    items = [to_read(p, uses[p.id], now) for p in promotions]
    if status is not None:
        items = [i for i in items if i.status == status]
    return items[params.offset : params.offset + params.limit], len(items)


def _check_areas(data: PromotionFields, config: AppConfig) -> None:
    known = {a.name for a in config.service_areas}
    unknown = [a for a in data.service_areas if a not in known]
    if unknown:
        raise PromotionValidationError(
            details=[{"loc": ["body", "service_areas"], "msg": f"unknown: {', '.join(unknown)}"}],
        )


async def _flush(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise PromotionCodeTakenError() from exc


async def create(
    session: AsyncSession, user: User, data: PromotionCreate, config: AppConfig
) -> Promotion:
    _check_areas(data, config)
    if data.code and await session.scalar(select(Promotion.id).where(Promotion.code == data.code)):
        raise PromotionCodeTakenError()
    values = data.model_dump()
    values["vehicle_types"] = [v.value for v in data.vehicle_types]
    promotion = Promotion(**values, created_by_id=user.id)
    session.add(promotion)
    await _flush(session)
    return promotion


def _validation_error(exc: ValidationError) -> AppError:
    details = [
        {"loc": ["body", *err["loc"]], "msg": err["msg"], "type": err["type"]}
        for err in exc.errors(include_url=False, include_context=False, include_input=False)
    ]
    return PromotionValidationError(details=details)


async def update(
    session: AsyncSession, promotion: Promotion, data: PromotionUpdate, config: AppConfig
) -> Promotion:
    promotion = (
        await session.scalar(
            select(Promotion).where(Promotion.id == promotion.id).with_for_update()
        )
        or promotion
    )
    current = PromotionFields.model_construct(
        **{name: getattr(promotion, name) for name in PromotionFields.model_fields}
    ).model_dump()
    changes = data.model_dump(exclude_unset=True)
    try:
        merged = PromotionFields.model_validate(current | changes)
    except ValidationError as exc:
        raise _validation_error(exc) from exc
    _check_areas(merged, config)
    use = (await usage(session, [promotion.id]))[promotion.id]
    if merged.budget < use.committed:
        raise BudgetBelowCommittedError(details={"committed": f"{use.committed:.2f}"})
    if merged.code and merged.code != promotion.code:
        taken = await session.scalar(
            select(Promotion.id).where(Promotion.code == merged.code, Promotion.id != promotion.id)
        )
        if taken:
            raise PromotionCodeTakenError()
    for key, value in merged.model_dump().items():
        if key == "vehicle_types":
            value = [v.value if isinstance(v, VehicleType) else v for v in value]
        setattr(promotion, key, value)
    await _flush(session)
    return promotion


async def rides(
    session: AsyncSession, promotion_id: uuid.UUID, params: PageParams
) -> tuple[list[PromotionRide], int]:
    passenger = aliased(User)
    driver = aliased(User)
    stmt = (
        select(Ride, passenger.full_name, passenger.email, driver.full_name, driver.email)
        .join(passenger, passenger.id == Ride.passenger_id)
        .outerjoin(driver, driver.id == Ride.driver_id)
        .where(Ride.promotion_id == promotion_id)
        .order_by(Ride.requested_at.desc())
    )
    total = await session.scalar(
        select(func.count(Ride.id)).where(Ride.promotion_id == promotion_id)
    )
    rows = await session.execute(stmt.limit(params.limit).offset(params.offset))
    items = [
        PromotionRide(
            ride_id=ride.id,
            status=ride.status,
            passenger_name=p_name or p_email,
            driver_name=(d_name or d_email) if (d_name or d_email) else None,
            fare=ride.fare,
            discount=ride.discount,
            total=ride.total,
            requested_at=ride.requested_at,
            completed_at=ride.completed_at,
        )
        for ride, p_name, p_email, d_name, d_email in rows
    ]
    return items, int(total or 0)


async def pair_alerts(session: AsyncSession, config: AppConfig) -> list[PairAlert]:
    """Passenger-driver pairs with many promoted rides together (possible fake trips)."""
    since = now_utc() - timedelta(days=config.promo_pair_alert_days)
    rows = (
        await session.execute(
            select(
                Ride.passenger_id,
                Ride.driver_id,
                func.count(Ride.id),
                func.sum(Ride.discount),
                func.max(Ride.completed_at),
            )
            .where(
                Ride.promotion_id.is_not(None),
                Ride.status == RideStatus.COMPLETED,
                Ride.completed_at >= since,
            )
            .group_by(Ride.passenger_id, Ride.driver_id)
            .having(func.count(Ride.id) >= config.promo_pair_alert_threshold)
            .order_by(func.count(Ride.id).desc())
            .limit(200)
        )
    ).all()
    ids = {r[0] for r in rows} | {r[1] for r in rows if r[1]}
    users = (
        {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}
        if ids
        else {}
    )
    profiles = (
        dict(
            (
                await session.execute(
                    select(DriverProfile.user_id, DriverProfile.id).where(
                        DriverProfile.user_id.in_(ids)
                    )
                )
            ).all()
        )
        if ids
        else {}
    )
    alerts = []
    for passenger_id, driver_id, count, total, last in rows:
        p, d = users.get(passenger_id), users.get(driver_id)
        if p is None or d is None:
            continue
        alerts.append(
            PairAlert(
                passenger=AlertPerson(id=p.id, name=p.full_name or "", email=p.email),
                driver=AlertDriver(
                    id=d.id, name=d.full_name or "", email=d.email, profile_id=profiles.get(d.id)
                ),
                rides=int(count),
                discount_total=Decimal(total or 0),
                last_ride_at=last,
            )
        )
    return alerts
