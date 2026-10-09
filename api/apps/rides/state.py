"""Ride state machine helpers shared by the request handlers and the dispatcher.

Every status change happens on a row locked with ``SELECT ... FOR UPDATE``, so the dispatcher,
the driver accepting and the passenger cancelling are serialized per ride.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.rides.models import RIDE_TRANSITIONS, Ride, RideStatus
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError

# A driver may accept for this long after ``expires_at`` (network latency); the dispatcher only
# moves on once the grace period is over, so both sides agree on when an offer is dead.
OFFER_GRACE = timedelta(seconds=2)


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Errors (codes are part of the API contract) -----------------------------------------------


class RideNotFoundError(NotFoundError):
    code = "ride_not_found"
    message = "Ride not found"


class RideInvalidStatusError(ConflictError):
    code = "ride_invalid_transition"
    message = "The ride cannot do that in its current status"


class RideTakenError(ConflictError):
    code = "ride_taken"
    message = "Another driver already took this ride"


class OfferExpiredError(ConflictError):
    code = "offer_expired"
    message = "The offer is no longer available"


class RideAlreadyActiveError(ConflictError):
    code = "ride_already_active"
    message = "There is already an active ride"


class RideActiveError(ConflictError):
    code = "ride_active"
    message = "Not allowed during an active ride"


class RatingRequiredError(ConflictError):
    code = "rating_required"
    message = "Rate your last ride first"


class DriverNotApprovedError(PermissionDeniedError):
    code = "driver_not_approved"
    message = "Only approved drivers can do this"


class QuoteExpiredError(AppError):
    code = "quote_expired"
    message = "The quote expired, ask for a new one"


class OutsideServiceAreaError(AppError):
    code = "outside_service_area"
    message = "Kuulis does not operate there yet"


class PaymentMethodInvalidError(AppError):
    code = "payment_method_invalid"
    message = "Payment method not accepted"


class ChatClosedError(ConflictError):
    code = "chat_closed"
    message = "The chat is only open during the ride"


class RideNotCompletedError(ConflictError):
    code = "ride_not_completed"
    message = "Only completed rides can be rated"


class RatingAlreadySubmittedError(ConflictError):
    code = "rating_already_submitted"
    message = "You already rated this ride"


# --- Locking and transitions -------------------------------------------------------------------


async def lock_ride(session: AsyncSession, ride_id: uuid.UUID) -> Ride | None:
    return await session.scalar(
        select(Ride)
        .where(Ride.id == ride_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def lock_ride_or_404(session: AsyncSession, ride_id: uuid.UUID) -> Ride:
    ride = await lock_ride(session, ride_id)
    if ride is None:
        raise RideNotFoundError()
    return ride


def transition(ride: Ride, target: RideStatus) -> None:
    if target not in RIDE_TRANSITIONS.get(ride.status, frozenset()):
        raise RideInvalidStatusError(
            f"Cannot change ride status from {ride.status} to {target}",
            details={"status": ride.status.value, "to": target.value},
        )
    ride.status = target
