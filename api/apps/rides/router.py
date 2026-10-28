import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response, status

from apps.audit.services import audit
from apps.legal.dependencies import LegalAccepted
from apps.releases.dependencies import AppUpToDate
from apps.rides import activity, events, presence, receipt, services, stats
from apps.rides.models import Ride, RideStatus
from apps.rides.schemas import (
    AdminCancelRequest,
    CancellationAdminRead,
    CancelRequest,
    DriverState,
    DriverStats,
    GoOnline,
    LocationUpdate,
    MessageCreate,
    MessageRead,
    OfferAdminRead,
    OnlineDriver,
    PassengerStats,
    PublicActivity,
    Quote,
    QuoteRequest,
    RatingAdminRead,
    RatingCreate,
    RideAdminDetail,
    RideAdminRead,
    RideCreate,
    RideRead,
    RideReceipt,
    RideSafetyAlert,
    StartRequest,
)
from apps.rides.state import RideNotFoundError
from apps.safety import services as safety
from apps.users.dependencies import Can, CurrentUser, DBSession
from apps.users.models import User
from kuulis.core.pagination import Page, PageParams, page_params
from kuulis.core.rate_limit import limiter

router = APIRouter(prefix="/rides", tags=["rides"])
driver_router = APIRouter(prefix="/drivers/me", tags=["rides"])
admin_router = APIRouter(prefix="/admin/rides", tags=["rides"])
admin_drivers_router = APIRouter(prefix="/admin/drivers", tags=["rides"])
public_router = APIRouter(prefix="/public/rides", tags=["rides"])


async def _read(session: DBSession, ride, user: User) -> RideRead:
    return await events.serialize_ride(session, ride, user.id)


# --- Passenger ---------------------------------------------------------------------------------


@router.post("/quote", response_model=Quote)
@limiter.limit("30/minute")
async def quote(
    request: Request, data: QuoteRequest, user: CurrentUser, session: DBSession
) -> Quote:
    return await services.create_quote(session, user, data)


@router.post(
    "",
    response_model=RideRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AppUpToDate, LegalAccepted],
)
@limiter.limit("6/minute")
async def create_ride(
    request: Request, data: RideCreate, user: CurrentUser, session: DBSession
) -> RideRead:
    ride = await services.create_ride(session, user, data)
    return await _read(session, ride, user)


@router.get("/me/stats", response_model=PassengerStats)
async def passenger_stats(user: CurrentUser, session: DBSession) -> PassengerStats:
    return await stats.passenger_stats(session, user.id)


@router.get("/active", response_model=RideRead | None)
async def active_ride(user: CurrentUser, session: DBSession) -> RideRead | None:
    ride = await services.get_active(session, user.id)
    return await _read(session, ride, user) if ride else None


@router.get("/pending-rating", response_model=RideRead | None)
async def pending_rating(user: CurrentUser, session: DBSession) -> RideRead | None:
    ride = await services.get_pending_rating(session, user.id)
    return await _read(session, ride, user) if ride else None


@router.get("", response_model=Page[RideRead])
async def list_rides(
    user: CurrentUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    role: Literal["passenger", "driver"] | None = None,
) -> Page[RideRead]:
    items, total = await services.list_for_user(session, user.id, params, role)
    return Page[RideRead](
        items=await events.serialize_rides(session, items, user.id),
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/{ride_id}", response_model=RideRead)
async def get_ride(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> RideRead:
    ride = await session.get(Ride, ride_id)
    if ride is not None and _left(ride, user):
        return await events.left_read(session, ride)
    ride = await services.get_for_participant(session, user, ride_id)
    return await _read(session, ride, user)


@router.get("/{ride_id}/receipt", response_model=RideReceipt)
async def ride_receipt(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> RideReceipt:
    """Doc 23: receipt of a completed ride (409 receipt_unavailable before), with a signed image
    link in the user's language to share."""
    ride = await services.get_for_participant(session, user, ride_id)
    return await receipt.build(session, ride, user.locale)


@public_router.get("/activity", response_model=PublicActivity)
@limiter.limit("60/minute")
async def public_activity(
    request: Request, response: Response, session: DBSession
) -> PublicActivity:
    """No login: "Caracas en movimiento", real trips only, anonymous and approximate."""
    response.headers["Cache-Control"] = "public, max-age=30"
    return await activity.public_activity(session)


@public_router.get(
    "/receipts/{token}.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
@limiter.limit("60/minute")
async def receipt_image(
    request: Request, token: Annotated[str, Path(max_length=80)], session: DBSession
) -> Response:
    """No login: the receipt image behind the signed link (404 when forged or not completed)."""
    ride_id, lang = receipt.parse_token(token)
    ride = await session.get(Ride, ride_id)
    if ride is None or ride.status != RideStatus.COMPLETED:
        raise receipt.ReceiptNotFoundError()
    data = await receipt.build(session, ride, lang)
    return Response(
        receipt.render(data, lang),
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


def _left(ride: Ride, user: User) -> bool:
    """The driver cancelled and the ride went to someone else: for them it is cancelled."""
    return ride.reassigned_from_driver_id == user.id and user.id not in (
        ride.passenger_id,
        ride.driver_id,
    )


@router.post("/{ride_id}/cancel", response_model=RideRead)
async def cancel(
    ride_id: uuid.UUID, user: CurrentUser, session: DBSession, data: CancelRequest | None = None
) -> RideRead:
    """``reason_code`` (doc 15) is optional. A driver's cancellation sends the ride back to
    searching (the response shows it cancelled for them); ``no_show`` answers 409
    ``no_show_too_early`` (``available_at``) before the wait is over."""
    ride = await services.cancel(
        session,
        user,
        ride_id,
        data.reason if data else None,
        data.reason_code if data else None,
    )
    if _left(ride, user):
        return await events.left_read(session, ride)
    return await _read(session, ride, user)


# --- Driver ------------------------------------------------------------------------------------


@router.post(
    "/{ride_id}/accept", response_model=RideRead, dependencies=[AppUpToDate, LegalAccepted]
)
async def accept(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> RideRead:
    ride = await services.accept(session, user, ride_id)
    return await _read(session, ride, user)


@router.post("/{ride_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> None:
    await services.decline(session, user, ride_id)


@router.post("/{ride_id}/arrive", response_model=RideRead)
async def arrive(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> RideRead:
    ride = await services.driver_step(session, user, ride_id, RideStatus.DRIVER_ARRIVED)
    return await _read(session, ride, user)


@router.post("/{ride_id}/start", response_model=RideRead)
async def start(
    ride_id: uuid.UUID, user: CurrentUser, session: DBSession, data: StartRequest | None = None
) -> RideRead:
    """``{"pin": "1234"}`` when ``pin_required``: 400 ``pin_invalid`` (``attempts_left``), then
    429 ``pin_attempts_exceeded`` after three wrong codes."""
    ride = await services.driver_step(
        session, user, ride_id, RideStatus.IN_PROGRESS, data.pin if data else None
    )
    return await _read(session, ride, user)


@router.post("/{ride_id}/complete", response_model=RideRead)
async def complete(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> RideRead:
    ride = await services.driver_step(session, user, ride_id, RideStatus.COMPLETED)
    return await _read(session, ride, user)


@driver_router.post(
    "/online", response_model=DriverState, dependencies=[AppUpToDate, LegalAccepted]
)
async def go_online(
    data: GoOnline,
    user: CurrentUser,
    session: DBSession,
    device_id: Annotated[str | None, Header(alias="X-Device-Id", max_length=100)] = None,
) -> DriverState:
    """403 ``document_expired`` / ``selfie_required`` when the driver must update something
    first (doc 12); 409 ``mock_location`` with a simulated location (doc 16)."""
    return await services.go_online(
        session, user, data.lat, data.lng, device_id=device_id, mocked=data.mocked
    )


@driver_router.post("/offline", response_model=DriverState)
async def go_offline(user: CurrentUser, session: DBSession) -> DriverState:
    return await services.go_offline(session, user)


@driver_router.post("/location", status_code=status.HTTP_204_NO_CONTENT)
async def update_location(data: LocationUpdate, user: CurrentUser) -> None:
    """Same as the socket's ``location`` message, for the background service (app minimized)."""
    await presence.handle_location(str(user.id), data.model_dump())


@driver_router.get("/stats", response_model=DriverStats)
async def driver_stats(user: CurrentUser, session: DBSession) -> DriverStats:
    return await stats.driver_stats(session, user.id)


@driver_router.get("/state", response_model=DriverState)
async def driver_state(user: CurrentUser, session: DBSession) -> DriverState:
    return await services.driver_state(session, user)


# --- Chat and rating ---------------------------------------------------------------------------


@router.get("/{ride_id}/messages", response_model=list[MessageRead])
async def list_messages(
    ride_id: uuid.UUID, user: CurrentUser, session: DBSession
) -> list[MessageRead]:
    ride = await services.get_for_participant(session, user, ride_id)
    # After a reassignment the new driver only sees their own conversation.
    since = ride.assigned_at if ride.reassign_count else None
    return [
        MessageRead.model_validate(m)
        for m in await services.list_messages(session, ride.id, since=since)
    ]


@router.post("/{ride_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def post_message(
    request: Request, ride_id: uuid.UUID, data: MessageCreate, user: CurrentUser, session: DBSession
) -> MessageRead:
    return MessageRead.model_validate(await services.post_message(session, user, ride_id, data))


@router.post("/{ride_id}/rating", response_model=RideRead)
async def rate(
    ride_id: uuid.UUID, data: RatingCreate, user: CurrentUser, session: DBSession
) -> RideRead:
    ride = await services.rate(session, user, ride_id, data)
    return await _read(session, ride, user)


# --- Admin -------------------------------------------------------------------------------------


@admin_router.get("", response_model=Page[RideAdminRead])
async def admin_list(
    _: Can("rides.view"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status: RideStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[RideAdminRead]:
    """``date_from`` / ``date_to``: inclusive days in Caracas time, on ``requested_at``."""
    items, total = await services.list_admin(
        session, params, status=status, q=q, date_from=date_from, date_to=date_to
    )
    return Page[RideAdminRead](
        items=await events.serialize_rides(session, items, admin=True),  # type: ignore[arg-type]
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@admin_router.get("/live", response_model=list[RideAdminRead])
async def admin_live(_: Can("live.view"), session: DBSession) -> list[RideAdminRead]:
    rides = await services.live_rides(session)
    return await events.serialize_rides(session, rides, admin=True)  # type: ignore[return-value]


@admin_router.get("/{ride_id}", response_model=RideAdminDetail)
async def admin_detail(
    ride_id: uuid.UUID, _: Can("rides.view"), session: DBSession
) -> RideAdminDetail:
    ride = await session.get(Ride, ride_id)
    if ride is None:
        raise RideNotFoundError()
    base = (await events.serialize_rides(session, [ride], admin=True))[0]
    offers = [
        OfferAdminRead(
            id=offer.id,
            driver_id=offer.driver_id,
            driver_name=name,
            status=offer.status,
            pickup_distance_m=offer.pickup_distance_m,
            pickup_eta_s=offer.pickup_eta_s,
            sent_at=offer.created_at,
            expires_at=offer.expires_at,
            responded_at=offer.responded_at,
        )
        for offer, name in await services.offers_for(session, ride.id)
    ]
    return RideAdminDetail(
        **base.model_dump(),
        messages=[
            MessageRead.model_validate(m) for m in await services.list_messages(session, ride.id)
        ],
        ratings=[
            RatingAdminRead.model_validate(r) for r in await services.ratings_for(session, ride.id)
        ],
        offers=offers,
        track=await safety.ride_track(session, ride),
        safety_alerts=[
            RideSafetyAlert.model_validate(a) for a in await safety.ride_alerts(session, ride.id)
        ],
        cancellations=[
            CancellationAdminRead.model_validate(c).model_copy(update={"user_name": name})
            for c, name in await services.cancellations_for(session, ride.id)
        ],
    )


@admin_router.post(
    "/{ride_id}/cancel",
    dependencies=[audit("ride.cancel", "ride", "ride_id")],
    response_model=RideAdminRead,
)
async def admin_cancel(
    ride_id: uuid.UUID, data: AdminCancelRequest, admin: Can("rides.cancel"), session: DBSession
) -> RideAdminRead:
    ride = await services.admin_cancel(session, admin, ride_id, data.reason)
    return (await events.serialize_rides(session, [ride], admin=True))[0]  # type: ignore[return-value]


@admin_drivers_router.get("/online", response_model=list[OnlineDriver])
async def online_drivers(_: Can("live.view"), session: DBSession) -> list[OnlineDriver]:
    return await services.online_drivers(session)
