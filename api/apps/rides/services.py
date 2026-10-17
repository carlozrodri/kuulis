"""Ride lifecycle: quote, request, driver actions, cancellation, chat, ratings and admin views.

Pattern for every change: lock the ride row, validate + mutate, commit, then emit events
(realtime and push only after the commit, so clients never see uncommitted state).
"""

import logging
import secrets
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import orjson
from sqlalchemy import Numeric, Select, cast, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from apps.config.schemas import AppConfig
from apps.config.services import get_app_config
from apps.control import services as control
from apps.control.flags import Audience
from apps.drivers.models import DriverProfile, DriverStatus
from apps.geo import clients as geo
from apps.moderation import services as moderation
from apps.promotions import services as promotions
from apps.promotions.schemas import PromotionBrief
from apps.quality import services as quality
from apps.quality.models import QualityRole
from apps.rates import services as rates
from apps.referrals import services as referrals
from apps.rides import dispatch, events, presence, pricing
from apps.rides.models import (
    ACTIVE_STATUSES,
    ASSIGNED_STATUSES,
    DRIVER_REASONS,
    PASSENGER_REASONS,
    CancelReason,
    CancelSide,
    OfferStatus,
    PaymentMethod,
    Rating,
    RatingRole,
    Ride,
    RideCancellation,
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
    CancelReasonInvalidError,
    ChatClosedError,
    DriverNotApprovedError,
    NoShowTooEarlyError,
    OfferExpiredError,
    OutsideServiceAreaError,
    PaymentMethodInvalidError,
    PinAttemptsExceededError,
    PinInvalidError,
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
from apps.safety import tasks as safety_tasks
from apps.subscriptions import services as subscriptions
from apps.users.models import User
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind
from apps.zones import demand
from apps.zones import services as zones
from kuulis.core.exceptions import AppError
from kuulis.core.pagination import PageParams, paginate
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

QUOTE_PREFIX = f"{settings.APP_ENV}:rides:quote:"
PIN_MAX_ATTEMPTS = 3


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
    """Every point must fall inside a service area (its polygon when it has one, doc 21), the
    pickup's city or one paired with it in ``intercity_pairs``. Returns the pickup's city."""
    area = config.area_at(*points[0])
    for lat, lng in points:
        place = config.area_at(lat, lng)
        if area is None or place is None or not config.intercity_allowed(area.name, place.name):
            raise OutsideServiceAreaError(details={"lat": lat, "lng": lng})
    assert area is not None
    return area.name


async def create_quote(session: AsyncSession, user: User, data: QuoteRequest) -> Quote:
    await moderation.ensure_not_suspended(session, user.id)
    await quality.ensure_not_paused(session, user.id, QualityRole.PASSENGER)
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
    control.ensure_open(config, area)
    pickup, dropoff = (data.pickup.lat, data.pickup.lng), (data.dropoff.lat, data.dropoff.lng)
    live = await zones.ensure_allowed(session, pickup, dropoff)
    route = await geo.route(*pickup, *dropoff)
    surge, surge_reason, surge_zone = zones.surge_for(config, live, *pickup)
    fare = pricing.compute_fare(
        config.fares[data.vehicle_type],
        route.distance_m,
        route.duration_s,
        surge,
        config.fare_rounding,
    )
    promotion, discount = None, Decimal(0)
    who = Audience(ident=str(user.id), role="passenger", area=area)
    if await control.is_enabled(session, "promotions", who):
        promotion, discount = await promotions.for_quote(
            session, promotions.RideContext(user.id, area, data.vehicle_type, fare), data.promo_code
        )
    elif data.promo_code:
        raise control.FeatureDisabledError(details={"feature": "promotions"})
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
        surge_reason=surge_reason,
        surge_zone=surge_zone,
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
    await quality.ensure_not_paused(session, user.id, QualityRole.PASSENGER)
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
    control.ensure_open(config, area)
    # A zone may have changed since the quote (a restricted zone drawn meanwhile).
    await zones.ensure_allowed(
        session, (quote.pickup.lat, quote.pickup.lng), (quote.dropoff.lat, quote.dropoff.lng)
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
    await demand.record(demand.REQUESTS, ride.pickup_lat, ride.pickup_lng)
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


async def go_online(
    session: AsyncSession,
    user: User,
    lat: float,
    lng: float,
    device_id: str | None = None,
    mocked: bool = False,
) -> DriverState:
    from apps.drivers import services as drivers
    from apps.drivers import verification
    from apps.risk import services as risk

    profile = await _approved_profile(session, user)
    if mocked:  # Android says the position comes from a mock location app (doc 16)
        await risk.gps_signal(session, user.id, "mocked", {"lat": lat, "lng": lng, "online": True})
        await session.commit()
        raise risk.MockLocationError()
    await moderation.ensure_not_suspended(session, user.id)
    await quality.ensure_not_paused(session, user.id, QualityRole.DRIVER)
    await subscriptions.ensure_not_overdue(session, user.id)
    config = await get_app_config(session)
    # Needs the documents too: expired ones and the random selfie keep the driver offline.
    full = await drivers.get_or_404(session, profile.id)
    await verification.ensure_can_go_online(session, full, config, device_id)
    vehicle = profile.vehicle
    assert vehicle is not None
    if vehicle.type not in config.enabled_vehicle_types:
        raise AppError("This vehicle type is not available", code="vehicle_type_not_enabled")
    place = config.area_at(lat, lng)
    control.ensure_open(config, place.name if place else None)
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
    config = await get_app_config(session)
    area = config.area_at(ride.pickup_lat, ride.pickup_lng)
    # Load-test accounts (apps.loadtest) skip it: the simulated driver cannot hear the code.
    passenger = await session.get(User, ride.passenger_id)
    if (
        area is not None
        and area.name in config.safety.pin_areas
        and not (passenger and passenger.is_test_account)
    ):
        ride.start_pin = f"{secrets.randbelow(10_000):04d}"
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
    q = (await get_app_config(session)).quality
    await quality.after_offer_missed(session, user.id, q)


_DRIVER_STEPS: dict[RideStatus, tuple[str, str | None]] = {
    # target -> (timestamp field, push event for the passenger)
    RideStatus.DRIVER_ARRIVED: ("arrived_at", "arrived"),
    RideStatus.IN_PROGRESS: ("started_at", None),
    RideStatus.COMPLETED: ("completed_at", "completed"),
}


async def _check_pin(session: AsyncSession, ride: Ride, pin: str | None) -> None:
    """The passenger's code, when the city asks for it. Three wrong tries lock the start: the
    driver calls support or cancels."""
    if ride.start_pin is None:
        return
    if ride.pin_failures >= PIN_MAX_ATTEMPTS:
        raise PinAttemptsExceededError()
    if pin is not None and secrets.compare_digest(pin, ride.start_pin):
        return
    ride.pin_failures += 1
    left = PIN_MAX_ATTEMPTS - ride.pin_failures
    await session.commit()
    if left <= 0:
        raise PinAttemptsExceededError()
    raise PinInvalidError(details={"attempts_left": left})


async def driver_step(
    session: AsyncSession,
    user: User,
    ride_id: uuid.UUID,
    target: RideStatus,
    pin: str | None = None,
) -> Ride:
    """arrive / start / complete. Repeating the same step is a no-op (flaky networks)."""
    ride = await lock_ride_or_404(session, ride_id)
    if ride.driver_id != user.id:
        raise RideNotFoundError()
    if ride.status == target:
        await session.commit()  # release the lock; nothing changed
        return ride
    if target == RideStatus.IN_PROGRESS and ride.status == RideStatus.DRIVER_ARRIVED:
        await _check_pin(session, ride, pin)
    transition(ride, target)
    field, push_event = _DRIVER_STEPS[target]
    now = utcnow()
    setattr(ride, field, now)
    credited = False
    inviter = None
    if target == RideStatus.COMPLETED:
        first_trip = await session.scalar(
            update(DriverProfile)
            .where(
                DriverProfile.user_id == user.id,
                DriverProfile.first_trip_completed_at.is_(None),
            )
            .values(first_trip_completed_at=now)
            .returning(DriverProfile.id)
        )
        if first_trip is not None:
            inviter = await referrals.reward_first_trip(session, user.id)
        hold = await _check_ride(session, ride)
        credited = await _credit_promotion(session, ride, hold)
    await session.commit()
    if target == RideStatus.COMPLETED:
        await presence.clear_active_ride(user.id, ride.id)
        await safety_tasks.ride_ended.kiq(str(ride.id))
        if credited:
            await events.notify_promo_credit(session, ride)
        elif hold and ride.discount > 0:
            await _notify_promo_held(session, ride)
        if inviter is not None:
            await referrals.notify_rewarded(session, inviter, user)
    await events.emit_updated(session, ride)
    if push_event:
        await events.push_to(
            session, ride.passenger_id, push_event, ride, name=events.first_name(user)
        )
    return ride


async def _check_ride(session: AsyncSession, ride: Ride) -> list[str] | None:
    """Anti-fraud rules on a completed ride (doc 16). Returns the reasons when its promotion
    credit must wait for a review. A failing rule never blocks the completion."""
    from apps.risk import services as risk

    try:
        async with session.begin_nested():
            result = await risk.check_ride(session, ride, await get_app_config(session))
    except Exception:
        logger.exception("Risk check failed for ride %s", ride.id)
        return None
    if not result.hold:
        return None
    return result.reasons + (["frequent_pair"] if result.pair_rides else []) or ["risk_score"]


async def _notify_promo_held(session: AsyncSession, ride: Ride) -> None:
    from apps.risk import services as risk
    from apps.wallet import notify

    assert ride.driver_id is not None
    await notify.send(
        session,
        ride.driver_id,
        "promo_held",
        templates=risk.TEMPLATES,
        amount=f"{ride.discount:.2f}",
        data={"ride_id": str(ride.id)},
    )
    await session.commit()


async def _credit_promotion(
    session: AsyncSession, ride: Ride, hold: list[str] | None = None
) -> bool:
    """Kuulis pays the promotion discount into the driver's wallet (same transaction as the
    completion, so a completed promoted ride always has its credit), or holds it for a review
    when the ride looks fake (doc 16)."""
    if not ride.promotion_id or ride.discount <= 0 or ride.driver_id is None:
        return False
    if hold:
        from apps.risk import services as risk

        await risk.hold_promo_credit(session, ride, hold)
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
    session: AsyncSession,
    ride: Ride,
    by: User,
    reason: str | None,
    notify_ids: list[uuid.UUID],
    *,
    push_event: str | None = None,
    **push_values: object,
) -> Ride:
    """Commits a cancellation already applied to ``ride`` and cleans up offers and presence."""
    now = utcnow()
    ride.cancelled_at = now
    ride.cancel_reason = reason
    ride.cancelled_by_id = by.id
    open_offers = await _cancel_open_offers(session, ride, now)
    await session.commit()

    await _after_offers_cancelled(ride, open_offers)
    await presence.clear_active_ride(ride.driver_id, ride.id)
    if ride.driver_id is not None:
        await safety_tasks.ride_ended.kiq(str(ride.id))
    await events.emit_updated(session, ride)
    for user_id in notify_ids:
        await events.push_to(session, user_id, push_event or ride.status.value, ride, **push_values)
    return ride


async def _cancel_open_offers(session: AsyncSession, ride: Ride, now: datetime) -> list[RideOffer]:
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
    return open_offers


async def _after_offers_cancelled(ride: Ride, offers: list[RideOffer]) -> None:
    await dispatch.unschedule(ride.id)
    for offer in offers:
        await presence.release_offer(offer.driver_id, ride.id)
        await events.emit_offer_cancelled(offer.driver_id, ride.id)


def _log_cancel(
    session: AsyncSession,
    ride: Ride,
    user: User,
    side: CancelSide,
    code: CancelReason | None,
    reason: str | None,
    *,
    counted: bool,
    reassigned: bool = False,
) -> None:
    """Call before changing the status: the log keeps the stage it was cancelled from."""
    session.add(
        RideCancellation(
            ride_id=ride.id,
            user_id=user.id,
            passenger_id=ride.passenger_id,
            side=side,
            reason_code=code,
            reason=reason,
            stage=ride.status,
            counted=counted,
            reassigned=reassigned,
        )
    )


async def cancel(
    session: AsyncSession,
    user: User,
    ride_id: uuid.UUID,
    reason: str | None,
    code: CancelReason | None = None,
) -> Ride:
    """Doc 15. A passenger's cancellation counts unless it is within the grace period after a
    driver accepts (or the moto did not match, which also opens a report). A driver's
    cancellation sends the ride back to searching; only ``no_show`` after the wait ends it, and
    that one counts against the passenger instead."""
    ride = await lock_ride_or_404(session, ride_id)
    if user.id == ride.passenger_id:
        return await _cancel_as_passenger(session, ride, user, reason, code)
    if user.id == ride.driver_id:
        return await _cancel_as_driver(session, ride, user, reason, code)
    if user.id == ride.reassigned_from_driver_id:
        await session.commit()  # retried cancel: the ride already went to someone else
        return ride
    raise RideNotFoundError()


async def _cancel_as_passenger(
    session: AsyncSession, ride: Ride, user: User, reason: str | None, code: CancelReason | None
) -> Ride:
    if ride.status == RideStatus.CANCELLED_BY_PASSENGER:
        await session.commit()  # release the lock; nothing changed
        return ride
    if code is not None and code not in PASSENGER_REASONS:
        raise CancelReasonInvalidError(details={"allowed": sorted(PASSENGER_REASONS)})
    q = (await get_app_config(session)).quality
    driver_id = ride.driver_id
    counted = (
        ride.assigned_at is not None
        and (utcnow() - ride.assigned_at).total_seconds() > q.passenger_cancel_grace_s
        and code != CancelReason.VEHICLE_MISMATCH
    )
    _log_cancel(session, ride, user, CancelSide.PASSENGER, code, reason, counted=counted)
    transition(ride, RideStatus.CANCELLED_BY_PASSENGER)
    ride.cancel_reason_code = code
    await _close(session, ride, user, reason, [driver_id] if driver_id else [])
    if code == CancelReason.VEHICLE_MISMATCH and driver_id is not None:
        await _report_mismatch(session, user, ride, reason)
    return ride


async def _report_mismatch(
    session: AsyncSession, user: User, ride: Ride, reason: str | None
) -> None:
    """ "La moto no coincide" opens the same report as the support form (doc 12 counts them)."""
    from apps.drivers import checks as driver_checks
    from apps.moderation.models import ReportCategory

    try:
        report = await moderation.create_report(
            session,
            user,
            ReportCategory.VEHICLE_MISMATCH,
            reason or "Canceló el viaje: la moto no coincide.",
            ride.id,
        )
        await session.commit()
    except AppError:
        await session.rollback()  # one already open for this ride, or too many open ones
        return
    if report.reported_user_id is not None:
        await driver_checks.after_mismatch_report(session, report.reported_user_id)


async def _cancel_as_driver(
    session: AsyncSession, ride: Ride, user: User, reason: str | None, code: CancelReason | None
) -> Ride:
    if code is not None and code not in DRIVER_REASONS:
        raise CancelReasonInvalidError(details={"allowed": sorted(DRIVER_REASONS)})
    config = await get_app_config(session)
    if code == CancelReason.NO_SHOW:
        return await _no_show(session, ride, user, reason, config)
    _log_cancel(
        session,
        ride,
        user,
        CancelSide.DRIVER,
        code,
        reason,
        counted=code != CancelReason.SAFETY_CONCERN,
        reassigned=True,
    )
    # Fails with ride_invalid_transition once the ride started, like before.
    transition(ride, RideStatus.SEARCHING)
    now = utcnow()
    ride.reassigned_from_driver_id = user.id
    ride.reassign_count = (ride.reassign_count or 0) + 1
    ride.driver_id = None
    ride.assigned_at = None
    ride.arrived_at = None
    ride.vehicle = None
    ride.start_pin = None
    ride.pin_failures = 0
    ride.search_expires_at = now + timedelta(seconds=config.search_timeout_seconds)
    await session.commit()

    await presence.clear_active_ride(user.id, ride.id)
    await dispatch.kick(ride.id)
    await events.emit_updated(session, ride)
    await events.emit_left(session, ride, user.id)
    await events.push_to(session, ride.passenger_id, "reassigning", ride)
    await quality.after_driver_cancel(session, user.id, config.quality)
    return ride


async def _no_show(
    session: AsyncSession, ride: Ride, user: User, reason: str | None, config: AppConfig
) -> Ride:
    if ride.status == RideStatus.CANCELLED_BY_DRIVER:
        await session.commit()
        return ride
    available = (
        ride.arrived_at + timedelta(minutes=config.quality.pickup_wait_minutes)
        if ride.arrived_at is not None
        else None
    )
    if ride.status != RideStatus.DRIVER_ARRIVED or available is None or utcnow() < available:
        raise NoShowTooEarlyError(
            details={
                "status": ride.status.value,
                "available_at": available.isoformat() if available else None,
            }
        )
    _log_cancel(session, ride, user, CancelSide.DRIVER, CancelReason.NO_SHOW, reason, counted=False)
    transition(ride, RideStatus.CANCELLED_BY_DRIVER)
    ride.cancel_reason_code = CancelReason.NO_SHOW
    await _close(
        session,
        ride,
        user,
        reason,
        [ride.passenger_id],
        push_event="no_show",
        name=events.first_name(user),
    )
    await quality.after_no_show(session, ride.passenger_id, config.quality)
    return ride


async def admin_cancel(session: AsyncSession, admin: User, ride_id: uuid.UUID, reason: str) -> Ride:
    ride = await lock_ride_or_404(session, ride_id)
    transition(ride, RideStatus.CANCELLED_BY_ADMIN)
    participants = [ride.passenger_id] + ([ride.driver_id] if ride.driver_id else [])
    return await _close(session, ride, admin, reason, participants)


# --- Chat --------------------------------------------------------------------------------------


async def list_messages(
    session: AsyncSession, ride_id: uuid.UUID, since: datetime | None = None
) -> list[RideMessage]:
    stmt = select(RideMessage).where(RideMessage.ride_id == ride_id)
    if since is not None:
        stmt = stmt.where(RideMessage.created_at >= since)
    rows = await session.scalars(stmt.order_by(RideMessage.created_at, RideMessage.id))
    return list(rows)


async def post_message(
    session: AsyncSession, user: User, ride_id: uuid.UUID, data: MessageCreate
) -> RideMessage:
    ride = await get_for_participant(session, user, ride_id)
    role = "driver" if user.id == ride.driver_id else "passenger"
    await control.ensure_enabled(session, "chat", Audience(ident=str(user.id), role=role))
    if ride.status not in ASSIGNED_STATUSES:
        from apps.support.services import lost_item_chat_open

        # After the ride, only while a lost item is being handed over (doc 13).
        if ride.status != RideStatus.COMPLETED or not await lost_item_chat_open(session, ride.id):
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
    from apps.risk import services as risk

    ratee_id = ride.driver_id if as_passenger else ride.passenger_id
    # Between a pair that looks like fake rides the rating is kept but not counted (doc 16).
    ignored = await risk.rating_ignored(session, ride, await get_app_config(session))
    session.add(
        Rating(
            ride_id=ride.id,
            rater_id=user.id,
            ratee_id=ratee_id,
            rater_role=RatingRole.PASSENGER if as_passenger else RatingRole.DRIVER,
            stars=data.stars,
            tags=data.tags,
            comment=data.comment,
            ignored=ignored,
        )
    )
    if as_passenger:
        ride.rated_by_passenger = True
        table, condition = DriverProfile, DriverProfile.user_id == ratee_id
    else:
        ride.rated_by_driver = True
        table, condition = User, User.id == ratee_id
    if not ignored:
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


async def cancellations_for(
    session: AsyncSession, ride_id: uuid.UUID
) -> list[tuple[RideCancellation, str]]:
    rows = await session.execute(
        select(RideCancellation, User.full_name)
        .join(User, User.id == RideCancellation.user_id)
        .where(RideCancellation.ride_id == ride_id)
        .order_by(RideCancellation.created_at)
    )
    return [(c, name) for c, name in rows]


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
