"""Ride serialization (batched, no N+1) and realtime / push emission."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig
from apps.config.services import get_app_config
from apps.drivers.models import DocumentKind, DocumentStatus, DriverDocument, DriverProfile
from apps.notifications import services as notifications
from apps.notifications import tasks as notification_tasks
from apps.promotions.models import Promotion
from apps.promotions.schemas import PromotionBrief
from apps.rates import services as rates
from apps.rates.schemas import FrozenRates
from apps.realtime.manager import publish
from apps.rides import notify, presence
from apps.rides.models import ASSIGNED_STATUSES, Rating, Ride, RideMessage, RideOffer, RideStatus
from apps.rides.schemas import (
    DriverAdminBrief,
    DriverBrief,
    DriverLocation,
    MessageRead,
    Offer,
    OfferPassenger,
    PersonBrief,
    RatingRead,
    RideAdminRead,
    RideRead,
    VehicleBrief,
)
from apps.users.models import User
from kuulis.core import storage
from kuulis.core.calendar import local_now

logger = logging.getLogger(__name__)
PIN_STATUSES = frozenset({RideStatus.DRIVER_ASSIGNED, RideStatus.DRIVER_ARRIVED})


def first_name(user: User | None) -> str:
    if user is None:
        return ""
    parts = (user.full_name or "").split()
    return parts[0] if parts else ""


def short_name(user: User | None) -> str:
    """ "Ana M." (first name and last initial)."""
    if user is None:
        return ""
    parts = (user.full_name or "").split()
    if not parts:
        return ""
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]


def _frozen(ride: Ride) -> FrozenRates:
    return FrozenRates(bcv=ride.rate_bcv, binance=ride.rate_binance)


async def _promotions(
    session: AsyncSession, ids: set[uuid.UUID]
) -> dict[uuid.UUID, PromotionBrief]:
    if not ids:
        return {}
    rows = await session.scalars(select(Promotion).where(Promotion.id.in_(ids)))
    return {p.id: PromotionBrief(id=p.id, name=p.name, code=p.code) for p in rows}


def _rating(value: Any) -> float | None:
    return float(value) if value is not None else None


def _place(lat: float, lng: float, address: str) -> dict[str, Any]:
    return {"lat": lat, "lng": lng, "address": address}


async def _users(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    rows = await session.scalars(select(User).where(User.id.in_(ids)))
    return {u.id: u for u in rows}


async def _profiles(
    session: AsyncSession, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[DriverProfile, str | None]]:
    """driver user id -> (profile, selfie key)."""
    if not user_ids:
        return {}
    profiles = {
        p.id: p
        for p in await session.scalars(
            select(DriverProfile).where(DriverProfile.user_id.in_(user_ids))
        )
    }
    selfies: dict[uuid.UUID, str] = {}
    if profiles:
        rows = await session.execute(
            select(DriverDocument.driver_id, DriverDocument.key)
            .where(
                DriverDocument.driver_id.in_(profiles),
                DriverDocument.kind == DocumentKind.SELFIE,
                DriverDocument.status != DocumentStatus.REJECTED,
            )
            .order_by(DriverDocument.created_at)
        )
        selfies = {driver_id: key for driver_id, key in rows}  # latest wins
    return {p.user_id: (p, selfies.get(p.id)) for p in profiles.values()}


def passenger_photo_allowed(config: AppConfig) -> bool:
    """Whether drivers see the passenger's photo now (doc 11: "night" by default)."""
    mode = config.safety.passenger_photo
    return mode == "always" or (mode == "night" and config.safety.is_night(local_now().time()))


async def _passenger_photos(
    session: AsyncSession, rides: Sequence[Ride], users: dict[uuid.UUID, User]
) -> dict[uuid.UUID, str | None]:
    """ride id -> passenger photo for the driver (only rides with a driver and a photo)."""
    candidates = [
        r
        for r in rides
        if r.driver_id
        and r.status in ASSIGNED_STATUSES
        and (p := users.get(r.passenger_id)) is not None
        and p.avatar_key
    ]
    if not candidates or not passenger_photo_allowed(await get_app_config(session)):
        return {}
    return {
        r.id: storage.download_url_or_none(users[r.passenger_id].avatar_key) for r in candidates
    }


async def serialize_rides(
    session: AsyncSession,
    rides: Sequence[Ride],
    viewer_id: uuid.UUID | None = None,
    *,
    admin: bool = False,
) -> list[RideRead]:
    if not rides:
        return []
    driver_ids = {r.driver_id for r in rides if r.driver_id}
    users = await _users(session, {r.passenger_id for r in rides} | driver_ids)
    profiles = await _profiles(session, driver_ids)
    my_ratings: dict[uuid.UUID, Rating] = {}
    if viewer_id is not None:
        my_ratings = {
            r.ride_id: r
            for r in await session.scalars(
                select(Rating).where(
                    Rating.ride_id.in_([r.id for r in rides]), Rating.rater_id == viewer_id
                )
            )
        }
    live = [str(r.driver_id) for r in rides if r.driver_id and r.status in ASSIGNED_STATUSES]
    locations = await presence.get_locations(live)
    promos = await _promotions(session, {r.promotion_id for r in rides if r.promotion_id})
    photos = await _passenger_photos(session, rides, users)

    result: list[RideRead] = []
    for ride in rides:
        passenger = users.get(ride.passenger_id)
        driver_user = users.get(ride.driver_id) if ride.driver_id else None
        profile, selfie = (
            profiles.get(ride.driver_id, (None, None)) if ride.driver_id else (None, None)
        )
        driver = None
        if driver_user is not None:
            driver = DriverBrief(
                id=driver_user.id,
                first_name=first_name(driver_user),
                rating=_rating(profile.rating_avg) if profile else None,
                photo_url=storage.download_url_or_none(selfie),
                vehicle=VehicleBrief.model_validate(ride.vehicle) if ride.vehicle else None,
            )
        location = None
        if ride.driver_id and ride.status in ASSIGNED_STATUSES:
            loc = locations.get(str(ride.driver_id))
            if loc is not None:
                location = DriverLocation(lat=loc.lat, lng=loc.lng, heading=loc.heading)
        mine = my_ratings.get(ride.id)
        fields = {
            "id": ride.id,
            "status": ride.status,
            "vehicle_type": ride.vehicle_type,
            "pickup": _place(ride.pickup_lat, ride.pickup_lng, ride.pickup_address),
            "dropoff": _place(ride.dropoff_lat, ride.dropoff_lng, ride.dropoff_address),
            "distance_m": ride.distance_m,
            "duration_s": ride.duration_s,
            "fare": ride.fare,
            "surge_multiplier": ride.surge_multiplier,
            "discount": ride.discount,
            "total": ride.total,
            "promotion": promos.get(ride.promotion_id) if ride.promotion_id else None,
            "rates": _frozen(ride),
            "total_ves": rates.to_ves(ride.total, _frozen(ride)),
            "payment_method": ride.payment_method,
            "polyline": ride.polyline,
            "passenger": PersonBrief(
                id=ride.passenger_id,
                first_name=first_name(passenger),
                rating=_rating(passenger.rating_avg) if passenger else None,
                photo_url=photos.get(ride.id),
            ),
            "driver": driver,
            "driver_location": location,
            "requested_at": ride.requested_at,
            "assigned_at": ride.assigned_at,
            "arrived_at": ride.arrived_at,
            "started_at": ride.started_at,
            "completed_at": ride.completed_at,
            "cancelled_at": ride.cancelled_at,
            "cancel_reason": ride.cancel_reason,
            "my_rating": RatingRead.model_validate(mine) if mine else None,
            "pin_required": ride.start_pin is not None,
            "start_pin": _pin_for(ride, viewer_id),
        }
        if admin:
            if driver is not None:
                fields["driver"] = DriverAdminBrief(
                    **driver.model_dump(), profile_id=profile.id if profile else None
                )
            result.append(
                RideAdminRead(
                    **fields,
                    passenger_name=passenger.full_name if passenger else "",
                    passenger_email=passenger.email if passenger else "",
                    driver_name=driver_user.full_name if driver_user else None,
                    driver_email=driver_user.email if driver_user else None,
                    driver_profile_id=profile.id if profile else None,
                    cancelled_by_id=ride.cancelled_by_id,
                    pin_failures=ride.pin_failures or 0,
                )
            )
        else:
            result.append(RideRead(**fields))
    return result


def _pin_for(ride: Ride, viewer_id: uuid.UUID | None) -> str | None:
    """Only the passenger gets the code, and only until the ride starts."""
    if viewer_id != ride.passenger_id or ride.status not in PIN_STATUSES:
        return None
    return ride.start_pin


async def serialize_ride(
    session: AsyncSession, ride: Ride, viewer_id: uuid.UUID | None = None
) -> RideRead:
    return (await serialize_rides(session, [ride], viewer_id))[0]


# --- Emission ----------------------------------------------------------------------------------


async def emit_updated(session: AsyncSession, ride: Ride) -> None:
    """``ride.updated`` to every participant, each with their own ``my_rating``."""
    base = await serialize_ride(session, ride)
    participants = [ride.passenger_id] + ([ride.driver_id] if ride.driver_id else [])
    ratings = {
        r.rater_id: r
        for r in await session.scalars(select(Rating).where(Rating.ride_id == ride.id))
    }
    for user_id in participants:
        mine = ratings.get(user_id)
        payload = base.model_copy(
            update={
                "my_rating": RatingRead.model_validate(mine) if mine else None,
                "start_pin": _pin_for(ride, user_id),
            }
        )
        await publish("ride.updated", payload.model_dump(mode="json"), user_ids=[str(user_id)])


async def push_to(
    session: AsyncSession,
    user_id: uuid.UUID,
    event: str,
    ride: Ride,
    options: dict[str, Any] | None = None,
    **values: Any,
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        return
    await notify.push(user.id, user.locale, event, ride.id, options, **values)


async def driver_name(session: AsyncSession, ride: Ride) -> str:
    if ride.driver_id is None:
        return ""
    return first_name(await session.get(User, ride.driver_id))


async def build_offer(session: AsyncSession, ride: Ride, offer: RideOffer) -> Offer:
    passenger = await session.get(User, ride.passenger_id)
    photo = None
    if (
        passenger is not None
        and passenger.avatar_key
        and passenger_photo_allowed(await get_app_config(session))
    ):
        photo = storage.download_url_or_none(passenger.avatar_key)
    return Offer(
        ride_id=ride.id,
        pickup=_place(ride.pickup_lat, ride.pickup_lng, ride.pickup_address),
        dropoff=_place(ride.dropoff_lat, ride.dropoff_lng, ride.dropoff_address),
        distance_m=ride.distance_m,
        duration_s=ride.duration_s,
        pickup_distance_m=offer.pickup_distance_m,
        pickup_eta_s=offer.pickup_eta_s,
        fare=ride.fare,
        discount=ride.discount,
        total=ride.total,
        total_ves=rates.to_ves(ride.total, _frozen(ride)),
        payment_method=ride.payment_method,
        passenger=OfferPassenger(
            first_name=first_name(passenger),
            rating=_rating(passenger.rating_avg) if passenger else None,
            photo_url=photo,
        ),
        expires_at=offer.expires_at,
    )


async def emit_offer(session: AsyncSession, ride: Ride, offer: RideOffer) -> None:
    payload = await build_offer(session, ride, offer)
    await publish("ride.offer", payload.model_dump(mode="json"), user_ids=[str(offer.driver_id)])
    ttl = max(int((offer.expires_at - datetime.now(UTC)).total_seconds()), 1)
    await push_to(
        session,
        offer.driver_id,
        "offer",
        ride,
        {"priority": "high", "ttl": ttl},
        pickup=ride.pickup_address or f"{ride.pickup_lat:.4f}, {ride.pickup_lng:.4f}",
        fare=f"{ride.total:.2f}",
    )


async def emit_offer_cancelled(driver_id: uuid.UUID, ride_id: uuid.UUID) -> None:
    await publish("ride.offer_cancelled", {"ride_id": str(ride_id)}, user_ids=[str(driver_id)])


async def emit_message(ride: Ride, message: RideMessage) -> None:
    participants = [str(ride.passenger_id)] + ([str(ride.driver_id)] if ride.driver_id else [])
    await publish(
        "ride.message",
        MessageRead.model_validate(message).model_dump(mode="json"),
        user_ids=participants,
    )


async def notify_promo_credit(session: AsyncSession, ride: Ride) -> None:
    """Inbox row + push to the driver: Kuulis credited the promotion discount."""
    if ride.driver_id is None:
        return
    driver = await session.get(User, ride.driver_id)
    if driver is None:
        return
    title, body = notify.render("promo_credit", driver.locale, amount=f"{ride.discount:.2f}")
    data = {"type": "wallet", "event": "promo_credit", "ride_id": str(ride.id)}
    await notifications.create_notifications(session, [driver.id], title, body, data)
    await session.commit()
    await notification_tasks.send_push.kiq([str(driver.id)], title, body, data)
