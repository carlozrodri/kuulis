"""Ride lifecycle: quote, request, driver actions, cancellation, chat, ratings and admin views.

Pattern for every change: lock the ride row, validate + mutate, commit, then emit events
(realtime and push only after the commit, so clients never see uncommitted state).
"""

import secrets
import uuid
from datetime import date, datetime, time, timedelta

import orjson
from sqlalchemy import Numeric, Select, cast, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from apps.config.schemas import AppConfig
from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile, DriverStatus
from apps.geo import clients as geo
from apps.moderation import services as moderation
from apps.promotions import services as promotions
from apps.promotions.schemas import PromotionBrief
from apps.rates import services as rates
from apps.rides import dispatch, events, presence, pricing
from apps.rides.models import (
    ACTIVE_STATUSES,
    ASSIGNED_STATUSES,
    OfferStatus,
    PaymentMethod,
    Rating,
    RatingRole,
    Ride,
    RideMessage,
    RideOffer,
    RideStatus,
)
from apps.rides.schemas import (
    DriverState,
    MessageCreate,
    OnlineDriver,
    Quote,
    QuoteRequest,
    RatingCreate,
    RideCreate,
)
from apps.rides.state import (
    OFFER_GRACE,
    ChatClosedError,
    DriverNotApprovedError,
    OfferExpiredError,
    OutsideServiceAreaError,
    PaymentMethodInvalidError,
    QuoteExpiredError,
    RatingAlreadySubmittedError,
    RatingRequiredError,
    RideActiveError,
    RideAlreadyActiveError,
    RideNotCompletedError,
    RideNotFoundError,
    RideTakenError,
    lock_ride_or_404,
    transition,
    utcnow,
)
from apps.subscriptions import services as subscriptions
from apps.users.models import User
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind
from kuulis.core.exceptions import AppError
from kuulis.core.pagination import PageParams, paginate
from kuulis.core.redis import redis_client
from kuulis.settings import settings

QUOTE_PREFIX = f"{settings.APP_ENV}:rides:quote:"


# --- Queries -----------------------------------------------------------------------------------


async def get_active(session: AsyncSession, user_id: uuid.UUID) -> Ride | None:
    """The user's ride in flight, as passenger or as driver."""
    return await session.scalar(
        select(Ride)
        .where(
            or_(
                (Ride.passenger_id == user_id) & Ride.status.in_(ACTIVE_STATUSES),
                (Ride.driver_id == user_id) & Ride.status.in_(ASSIGNED_STATUSES),
            )
        )
        .order_by(Ride.requested_at.desc())
        .limit(1)
    )


async def get_pending_rating(session: AsyncSession, user_id: uuid.UUID) -> Ride | None:
    return await session.scalar(
        select(Ride)
        .where(
            Ride.status == RideStatus.COMPLETED,
            or_(
                (Ride.passenger_id == user_id) & Ride.rated_by_passenger.is_(False),
                (Ride.driver_id == user_id) & Ride.rated_by_driver.is_(False),
            ),
        )
        .order_by(Ride.completed_at.desc())
        .limit(1)
    )


async def _passenger_pending_rating(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(
        select(Ride.id)
        .where(
            Ride.passenger_id == user_id,
            Ride.status == RideStatus.COMPLETED,
            Ride.rated_by_passenger.is_(False),
        )
        .limit(1)
    )


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, params: PageParams, role: str | None
) -> tuple[list[Ride], int]:
    if role == "passenger":
        condition = Ride.passenger_id == user_id
    elif role == "driver":
        condition = Ride.driver_id == user_id
    else:
        condition = or_(Ride.passenger_id == user_id, Ride.driver_id == user_id)
    stmt = select(Ride).where(condition).order_by(Ride.requested_at.desc())
    return await paginate(session, stmt, params)


async def get_for_participant(session: AsyncSession, user: User, ride_id: uuid.UUID) -> Ride:
    ride = await session.get(Ride, ride_id)
    if ride is None or user.id not in (ride.passenger_id, ride.driver_id):
        raise RideNotFoundError()
    return ride


def _ensure_participant(ride: Ride, user: User) -> None:
    if user.id not in (ride.passenger_id, ride.driver_id):
        raise RideNotFoundError()


# --- Quote and request -------------------------------------------------------------------------


def _check_area(config: AppConfig, *points: tuple[float, float]) -> str:
    """Every point must fall inside one service area, the same one (no trips between cities).
    Returns the area name."""
    area = config.area_at(*points[0])
    for lat, lng in points:
        if area is None or not area.contains(lat, lng):
            raise OutsideServiceAreaError(details={"lat": lat, "lng": lng})
    assert area is not None
    return area.name


async def create_quote(session: AsyncSession, user: User, data: QuoteRequest) -> Quote:
    await moderation.ensure_not_suspended(session, user.id)
    config = await get_app_config(session)
    if data.vehicle_type not in config.enabled_vehicle_types:
        raise AppError(
            "This vehicle type is not available",
            code="vehicle_type_not_enabled",
            details={"enabled": [t.value for t in config.enabled_vehicle_types]},
        )
    area = _check_area(
        config, (data.pickup.lat, data.pickup.lng), (data.dropoff.lat, data.dropoff.lng)
    )
    route = await geo.route(data.pickup.lat, data.pickup.lng, data.dropoff.lat, data.dropoff.lng)
    fare, surge = pricing.quote_price(config, data.vehicle_type, route.distance_m, route.duration_s)
    promotion, discount = await promotions.for_quote(
        session, promotions.RideContext(user.id, area, data.vehicle_type, fare), data.promo_code
    )
    total = fare - discount
    quote = Quote(
        quote_id=secrets.token_urlsafe(18),
        vehicle_type=data.vehicle_type,
        pickup=data.pickup,
        dropoff=data.dropoff,
        distance_m=route.distance_m,
        duration_s=route.duration_s,
        fare=fare,
        surge_multiplier=surge,
        discount=discount,
        total=total,
        promotion=PromotionBrief(id=promotion.id, name=promotion.name, code=promotion.code)
        if promotion
        else None,
        total_ves=rates.to_ves(total, await rates.current_values(session)),
        polyline=route.polyline,
        expires_at=utcnow() + timedelta(seconds=config.quote_ttl_seconds),
    )
    stored = quote.model_dump(mode="json") | {"user_id": str(user.id)}
    await redis_client.set(
        QUOTE_PREFIX + quote.quote_id, orjson.dumps(stored).decode(), ex=config.quote_ttl_seconds
    )
    return quote


async def create_ride(session: AsyncSession, user: User, data: RideCreate) -> Ride:
    await moderation.ensure_not_suspended(session, user.id)
    config = await get_app_config(session)
    if data.payment_method not in {m.value for m in config.payment_methods}:
        raise PaymentMethodInvalidError(
            details={"allowed": [m.value for m in config.payment_methods]}
        )
    unrated = await _passenger_pending_rating(session, user.id)
    if unrated is not None:
        raise RatingRequiredError(details={"ride_id": str(unrated)})
    active = await get_active(session, user.id)
    if active is not None:
        raise RideAlreadyActiveError(details={"ride_id": str(active.id)})

    raw = await redis_client.get(QUOTE_PREFIX + data.quote_id)
    stored = orjson.loads(raw) if raw else None
    if stored is None or stored.get("user_id") != str(user.id):
        raise QuoteExpiredError()
    quote = Quote.model_validate(stored)
    area = _check_area(
        config, (quote.pickup.lat, quote.pickup.lng), (quote.dropoff.lat, quote.dropoff.lng)
    )
    if quote.promotion is not None:
        # Locks the promotion until the commit, so its budget cannot be overspent.
        await promotions.lock_for_ride(
            session,
            quote.promotion.id,
            promotions.RideContext(user.id, area, quote.vehicle_type, quote.fare),
            quote.discount,
        )
    frozen = await rates.current_values(session)

    now = utcnow()
    ride = Ride(
        passenger_id=user.id,
        status=RideStatus.SEARCHING,
        vehicle_type=quote.vehicle_type,
        pickup_lat=quote.pickup.lat,
        pickup_lng=quote.pickup.lng,
        pickup_address=quote.pickup.address,
        dropoff_lat=quote.dropoff.lat,
        dropoff_lng=quote.dropoff.lng,
        dropoff_address=quote.dropoff.address,
        distance_m=quote.distance_m,
        duration_s=quote.duration_s,
        fare=quote.fare,
        surge_multiplier=quote.surge_multiplier,
        promotion_id=quote.promotion.id if quote.promotion else None,
        discount=quote.discount,
        rate_bcv=frozen.bcv,
        rate_binance=frozen.binance,
        payment_method=PaymentMethod(data.payment_method),
        polyline=quote.polyline,
        requested_at=now,
        search_expires_at=now + timedelta(seconds=config.search_timeout_seconds),
    )
    session.add(ride)
    try:
        await session.commit()
    except IntegrityError as exc:  # concurrent double request: the partial unique index wins
        await session.rollback()
        raise RideAlreadyActiveError() from exc
    await redis_client.delete(QUOTE_PREFIX + data.quote_id)  # single use
    await dispatch.kick(ride.id)
    await session.refresh(ride)
    return ride


# --- Driver presence ---------------------------------------------------------------------------


async def _approved_profile(session: AsyncSession, user: User) -> DriverProfile:
    profile = await session.scalar(
        select(DriverProfile)
        .options(selectinload(DriverProfile.vehicle))
        .where(DriverProfile.user_id == user.id)
    )
    if profile is None or profile.status != DriverStatus.APPROVED or profile.vehicle is None:
        raise DriverNotApprovedError(details={"status": profile.status.value if profile else None})
    return profile


async def _driver_active_ride_id(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(
        select(Ride.id).where(Ride.driver_id == user_id, Ride.status.in_(ASSIGNED_STATUSES))
    )


async def _current_offer(session: AsyncSession, user_id: uuid.UUID) -> RideOffer | None:
    return await session.scalar(
        select(RideOffer)
        .where(
            RideOffer.driver_id == user_id,
            RideOffer.status == OfferStatus.PENDING,
            RideOffer.expires_at > utcnow() - OFFER_GRACE,
        )
        .order_by(RideOffer.created_at.desc())
        .limit(1)
    )


async def driver_state(session: AsyncSession, user: User) -> DriverState:
    offer = await _current_offer(session, user.id)
    current = None
    if offer is not None:
        ride = await session.get(Ride, offer.ride_id)
        if ride is not None and ride.status == RideStatus.SEARCHING:
            current = await events.build_offer(session, ride, offer)
    return DriverState(
        online=await presence.is_online(user.id),
        active_ride_id=await _driver_active_ride_id(session, user.id),
        current_offer=current,
    )


async def go_online(session: AsyncSession, user: User, lat: float, lng: float) -> DriverState:
    profile = await _approved_profile(session, user)
    await moderation.ensure_not_suspended(session, user.id)
    await subscriptions.ensure_not_overdue(session, user.id)
    config = await get_app_config(session)
    vehicle = profile.vehicle
    assert vehicle is not None
    if vehicle.type not in config.enabled_vehicle_types:
        raise AppError("This vehicle type is not available", code="vehicle_type_not_enabled")
    await presence.go_online(user.id, profile.id, vehicle.type, lat, lng)
    return await driver_state(session, user)


async def go_offline(session: AsyncSession, user: User) -> DriverState:
    active = await _driver_active_ride_id(session, user.id)
    if active is not None:
        raise RideActiveError(details={"ride_id": str(active)})
    await presence.go_offline(user.id)
    offer = await _current_offer(session, user.id)
    if offer is not None:
        await decline(session, user, offer.ride_id)
    return await driver_state(session, user)


# --- Driver actions ----------------------------------------------------------------------------


async def accept(session: AsyncSession, user: User, ride_id: uuid.UUID) -> Ride:
    ride = await lock_ride_or_404(session, ride_id)
    if ride.status != RideStatus.SEARCHING:
        if ride.driver_id == user.id:
            await session.commit()  # release the lock; nothing changed
            return ride  # retried accept: already ours
        raise RideTakenError(details={"status": ride.status.value})
    now = utcnow()
    offer = await session.scalar(
        select(RideOffer)
        .where(RideOffer.ride_id == ride.id, RideOffer.driver_id == user.id)
        .with_for_update()
    )
    if (
        offer is None
        or offer.status != OfferStatus.PENDING
        or offer.expires_at + OFFER_GRACE <= now
    ):
        raise OfferExpiredError()
    profile = await _approved_profile(session, user)
    vehicle = profile.vehicle
    assert vehicle is not None

    transition(ride, RideStatus.DRIVER_ASSIGNED)
    ride.driver_id = user.id
    ride.assigned_at = now
    ride.vehicle = {
        "type": vehicle.type.value,
        "brand": vehicle.brand,
        "model": vehicle.model,
        "color": vehicle.color,
        "plate": vehicle.plate,
    }
    offer.status = OfferStatus.ACCEPTED
    offer.responded_at = now
    try:
        await session.commit()
    except IntegrityError as exc:  # the driver is already on another ride
        await session.rollback()
        raise RideAlreadyActiveError() from exc

    await presence.release_offer(user.id, ride.id)
    await presence.set_active_ride(user.id, ride.id, ride.passenger_id)
    await dispatch.unschedule(ride.id)
    await events.emit_updated(session, ride)
    await events.push_to(session, ride.passenger_id, "assigned", ride, name=events.first_name(user))
    return ride


async def decline(session: AsyncSession, user: User, ride_id: uuid.UUID) -> None:
    ride = await lock_ride_or_404(session, ride_id)
    offer = await session.scalar(
        select(RideOffer).where(
            RideOffer.ride_id == ride.id,
            RideOffer.driver_id == user.id,
            RideOffer.status == OfferStatus.PENDING,
        )
    )
    if offer is None:
        await session.commit()
        return  # nothing to decline (already expired / declined): idempotent
    offer.status = OfferStatus.DECLINED
    offer.responded_at = utcnow()
    await session.commit()
    await presence.release_offer(user.id, ride.id)
    if ride.status == RideStatus.SEARCHING:
        await dispatch.kick(ride.id)


_DRIVER_STEPS: dict[RideStatus, tuple[str, str | None]] = {
    # target -> (timestamp field, push event for the passenger)
    RideStatus.DRIVER_ARRIVED: ("arrived_at", "arrived"),
    RideStatus.IN_PROGRESS: ("started_at", None),
    RideStatus.COMPLETED: ("completed_at", "completed"),
}


async def driver_step(
    session: AsyncSession, user: User, ride_id: uuid.UUID, target: RideStatus
) -> Ride:
    """arrive / start / complete. Repeating the same step is a no-op (flaky networks)."""
    ride = await lock_ride_or_404(session, ride_id)
    if ride.driver_id != user.id:
        raise RideNotFoundError()
    if ride.status == target:
        await session.commit()  # release the lock; nothing changed
        return ride
    transition(ride, target)
    field, push_event = _DRIVER_STEPS[target]
    now = utcnow()
    setattr(ride, field, now)
    credited = False
    if target == RideStatus.COMPLETED:
        await session.execute(
            update(DriverProfile)
            .where(
                DriverProfile.user_id == user.id,
                DriverProfile.first_trip_completed_at.is_(None),
            )
            .values(first_trip_completed_at=now)
        )
        credited = await _credit_promotion(session, ride)
    await session.commit()
    if target == RideStatus.COMPLETED:
        await presence.clear_active_ride(user.id, ride.id)
        if credited:
            await events.notify_promo_credit(session, ride)
    await events.emit_updated(session, ride)
    if push_event:
        await events.push_to(
            session, ride.passenger_id, push_event, ride, name=events.first_name(user)
        )
    return ride


async def _credit_promotion(session: AsyncSession, ride: Ride) -> bool:
    """Kuulis pays the promotion discount into the driver's wallet (same transaction as the
    completion, so a completed promoted ride always has its credit)."""
    if not ride.promotion_id or ride.discount <= 0 or ride.driver_id is None:
        return False
    promotion = await session.get(promotions.Promotion, ride.promotion_id)
    passenger = await session.get(User, ride.passenger_id)
    await wallet.credit(
        session,
        ride.driver_id,
        EntryKind.PROMO_CREDIT,
        ride.discount,
        ride_id=ride.id,
        promotion_id=ride.promotion_id,
        description=promotion.name if promotion else "",
        details={"passenger_name": events.short_name(passenger)},
    )
    return True


# --- Cancellation ------------------------------------------------------------------------------


async def _close(
    session: AsyncSession, ride: Ride, by: User, reason: str | None, notify_ids: list[uuid.UUID]
) -> Ride:
    """Commits a cancellation already applied to ``ride`` and cleans up offers and presence."""
    now = utcnow()
    ride.cancelled_at = now
    ride.cancel_reason = reason
    ride.cancelled_by_id = by.id
    open_offers = list(
        await session.scalars(
            select(RideOffer).where(
                RideOffer.ride_id == ride.id, RideOffer.status == OfferStatus.PENDING
            )
        )
    )
    for offer in open_offers:
        offer.status = OfferStatus.CANCELLED
        offer.responded_at = now
    await session.commit()

    await dispatch.unschedule(ride.id)
    for offer in open_offers:
        await presence.release_offer(offer.driver_id, ride.id)
        await events.emit_offer_cancelled(offer.driver_id, ride.id)
    await presence.clear_active_ride(ride.driver_id, ride.id)
    await events.emit_updated(session, ride)
    for user_id in notify_ids:
        await events.push_to(session, user_id, ride.status.value, ride)
    return ride


async def cancel(session: AsyncSession, user: User, ride_id: uuid.UUID, reason: str | None) -> Ride:
    ride = await lock_ride_or_404(session, ride_id)
    if user.id == ride.passenger_id:
        target = RideStatus.CANCELLED_BY_PASSENGER
        other = ride.driver_id
    elif user.id == ride.driver_id:
        target = RideStatus.CANCELLED_BY_DRIVER
        other = ride.passenger_id
    else:
        raise RideNotFoundError()
    if ride.status == target:
        await session.commit()  # release the lock; nothing changed
        return ride
    transition(ride, target)
    return await _close(session, ride, user, reason, [other] if other else [])


async def admin_cancel(session: AsyncSession, admin: User, ride_id: uuid.UUID, reason: str) -> Ride:
    ride = await lock_ride_or_404(session, ride_id)
    transition(ride, RideStatus.CANCELLED_BY_ADMIN)
    participants = [ride.passenger_id] + ([ride.driver_id] if ride.driver_id else [])
    return await _close(session, ride, admin, reason, participants)


# --- Chat --------------------------------------------------------------------------------------


async def list_messages(session: AsyncSession, ride_id: uuid.UUID) -> list[RideMessage]:
    rows = await session.scalars(
        select(RideMessage)
        .where(RideMessage.ride_id == ride_id)
        .order_by(RideMessage.created_at, RideMessage.id)
    )
    return list(rows)


async def post_message(
    session: AsyncSession, user: User, ride_id: uuid.UUID, data: MessageCreate
) -> RideMessage:
    ride = await get_for_participant(session, user, ride_id)
    if ride.status not in ASSIGNED_STATUSES:
        raise ChatClosedError(details={"status": ride.status.value})
    message = RideMessage(ride_id=ride.id, sender_id=user.id, text=data.text)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    await events.emit_message(ride, message)
    other = ride.driver_id if user.id == ride.passenger_id else ride.passenger_id
    if other is not None:
        await events.push_to(
            session,
            other,
            "message",
            ride,
            {"priority": "high"},
            name=events.first_name(user) or "Kuulis",
            text=data.text[:140],
        )
    return message


# --- Ratings -----------------------------------------------------------------------------------


async def rate(session: AsyncSession, user: User, ride_id: uuid.UUID, data: RatingCreate) -> Ride:
    ride = await lock_ride_or_404(session, ride_id)
    _ensure_participant(ride, user)
    if ride.status != RideStatus.COMPLETED:
        raise RideNotCompletedError(details={"status": ride.status.value})
    as_passenger = user.id == ride.passenger_id
    if ride.rated_by_passenger if as_passenger else ride.rated_by_driver:
        raise RatingAlreadySubmittedError()
    assert ride.driver_id is not None
    ratee_id = ride.driver_id if as_passenger else ride.passenger_id
    session.add(
        Rating(
            ride_id=ride.id,
            rater_id=user.id,
            ratee_id=ratee_id,
            rater_role=RatingRole.PASSENGER if as_passenger else RatingRole.DRIVER,
            stars=data.stars,
            tags=data.tags,
            comment=data.comment,
        )
    )
    if as_passenger:
        ride.rated_by_passenger = True
        table, condition = DriverProfile, DriverProfile.user_id == ratee_id
    else:
        ride.rated_by_driver = True
        table, condition = User, User.id == ratee_id
    # Old values on the right-hand side: one atomic UPDATE, exact average from sum / count.
    await session.execute(
        update(table)
        .where(condition)
        .values(
            rating_sum=table.rating_sum + data.stars,
            rating_count=table.rating_count + 1,
            rating_avg=func.round(
                cast(table.rating_sum + data.stars, Numeric) / (table.rating_count + 1), 2
            ),
        )
        .execution_options(synchronize_session=False)
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise RatingAlreadySubmittedError() from exc
    await events.emit_updated(session, ride)
    return ride


# --- Admin -------------------------------------------------------------------------------------


def _caracas_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=pricing.CARACAS_TZ)


def admin_query(
    status: RideStatus | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Select[tuple[Ride]]:
    stmt = select(Ride).order_by(Ride.requested_at.desc())
    if status is not None:
        stmt = stmt.where(Ride.status == status)
    if date_from is not None:
        stmt = stmt.where(Ride.requested_at >= _caracas_start(date_from))
    if date_to is not None:  # inclusive, Caracas days
        stmt = stmt.where(Ride.requested_at < _caracas_start(date_to + timedelta(days=1)))
    if q and q.strip():
        text = q.strip()
        try:
            return stmt.where(Ride.id == uuid.UUID(text))
        except ValueError:
            pass
        term = f"%{text.lower()}%"
        plate = f"%{text.upper().replace(' ', '').replace('-', '')}%"
        passenger, driver = aliased(User), aliased(User)
        stmt = (
            stmt.join(passenger, passenger.id == Ride.passenger_id)
            .outerjoin(driver, driver.id == Ride.driver_id)
            .where(
                or_(
                    func.lower(passenger.full_name).like(term),
                    func.lower(passenger.email).like(term),
                    func.lower(driver.full_name).like(term),
                    func.lower(driver.email).like(term),
                    Ride.vehicle["plate"].astext.like(plate),
                )
            )
        )
    return stmt


async def list_admin(
    session: AsyncSession, params: PageParams, **filters: object
) -> tuple[list[Ride], int]:
    return await paginate(session, admin_query(**filters), params)  # type: ignore[arg-type]


async def live_rides(session: AsyncSession) -> list[Ride]:
    rows = await session.scalars(
        select(Ride)
        .where(Ride.status.in_(ACTIVE_STATUSES))
        .order_by(Ride.requested_at.desc())
        .limit(500)
    )
    return list(rows)


async def offers_for(session: AsyncSession, ride_id: uuid.UUID) -> list[tuple[RideOffer, str]]:
    rows = await session.execute(
        select(RideOffer, User.full_name)
        .join(User, User.id == RideOffer.driver_id)
        .where(RideOffer.ride_id == ride_id)
        .order_by(RideOffer.created_at)
    )
    return [(offer, name) for offer, name in rows]


async def ratings_for(session: AsyncSession, ride_id: uuid.UUID) -> list[Rating]:
    rows = await session.scalars(
        select(Rating).where(Rating.ride_id == ride_id).order_by(Rating.created_at)
    )
    return list(rows)


async def online_drivers(session: AsyncSession) -> list[OnlineDriver]:
    entries = await presence.online_entries()
    if not entries:
        return []
    uids = list(entries)
    locations = await presence.get_locations(uids)
    ids = [uuid.UUID(u) for u in uids]
    names = dict(
        (await session.execute(select(User.id, User.full_name).where(User.id.in_(ids)))).all()
    )
    active = dict(
        (
            await session.execute(
                select(Ride.driver_id, Ride.id).where(
                    Ride.driver_id.in_(ids), Ride.status.in_(ASSIGNED_STATUSES)
                )
            )
        ).all()
    )
    result = []
    for uid in ids:
        entry, loc = entries[str(uid)], locations.get(str(uid))
        result.append(
            OnlineDriver(
                driver_id=uuid.UUID(entry["profile_id"]),
                driver_profile_id=uuid.UUID(entry["profile_id"]),
                user_id=uid,
                name=names.get(uid, ""),
                vehicle_type=entry["vehicle_type"],
                lat=loc.lat if loc else None,
                lng=loc.lng if loc else None,
                last_seen_at=datetime.fromtimestamp(loc.ts, pricing.CARACAS_TZ) if loc else None,
                active_ride_id=active.get(uid),
            )
        )
    result.sort(key=lambda d: d.name.lower())
    return result
