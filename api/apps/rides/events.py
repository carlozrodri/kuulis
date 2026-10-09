"""Ride serialization (batched, no N+1) and realtime / push emission."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.drivers.models import DocumentKind, DocumentStatus, DriverDocument, DriverProfile
from apps.realtime.manager import publish
from apps.rides import notify, presence
from apps.rides.models import ASSIGNED_STATUSES, Rating, Ride, RideMessage, RideOffer
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
from kuulis.core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


def first_name(user: User | None) -> str:
    if user is None:
        return ""
    parts = (user.full_name or "").split()
    return parts[0] if parts else ""


def _rating(value: Any) -> float | None:
    return float(value) if value is not None else None


def _photo_url(key: str | None) -> str | None:
    if not key:
        return None
    try:
        return storage.presigned_download(key)
    except ServiceUnavailableError:
        return None  # storage not configured (local development)
    except Exception:
        logger.warning("Could not sign driver photo URL", exc_info=True)
        return None


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
                photo_url=_photo_url(selfie),
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
            "payment_method": ride.payment_method,
            "polyline": ride.polyline,
            "passenger": PersonBrief(
                id=ride.passenger_id,
                first_name=first_name(passenger),
                rating=_rating(passenger.rating_avg) if passenger else None,
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
                )
            )
        else:
            result.append(RideRead(**fields))
    return result


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
            update={"my_rating": RatingRead.model_validate(mine) if mine else None}
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
    return Offer(
        ride_id=ride.id,
        pickup=_place(ride.pickup_lat, ride.pickup_lng, ride.pickup_address),
        dropoff=_place(ride.dropoff_lat, ride.dropoff_lng, ride.dropoff_address),
        distance_m=ride.distance_m,
        duration_s=ride.duration_s,
        pickup_distance_m=offer.pickup_distance_m,
        pickup_eta_s=offer.pickup_eta_s,
        fare=ride.fare,
        payment_method=ride.payment_method,
        passenger=OfferPassenger(
            first_name=first_name(passenger),
            rating=_rating(passenger.rating_avg) if passenger else None,
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
        fare=f"{ride.fare:.2f}",
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
