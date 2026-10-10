import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from apps.rides import events, presence, services
from apps.rides.models import Ride, RideStatus
from apps.rides.schemas import (
    AdminCancelRequest,
    CancelRequest,
    DriverState,
    GoOnline,
    LocationUpdate,
    MessageCreate,
    MessageRead,
    OfferAdminRead,
    OnlineDriver,
    Quote,
    QuoteRequest,
    RatingAdminRead,
    RatingCreate,
    RideAdminDetail,
    RideAdminRead,
    RideCreate,
    RideRead,
)
from apps.rides.state import RideNotFoundError
from apps.users.dependencies import CurrentUser, DBSession, StaffUser
from apps.users.models import User
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/rides", tags=["rides"])
driver_router = APIRouter(prefix="/drivers/me", tags=["rides"])
admin_router = APIRouter(prefix="/admin/rides", tags=["rides"])
admin_drivers_router = APIRouter(prefix="/admin/drivers", tags=["rides"])


async def _read(session: DBSession, ride, user: User) -> RideRead:
    return await events.serialize_ride(session, ride, user.id)


# --- Passenger ---------------------------------------------------------------------------------


@router.post("/quote", response_model=Quote)
async def quote(data: QuoteRequest, user: CurrentUser, session: DBSession) -> Quote:
    return await services.create_quote(session, user, data)


@router.post("", response_model=RideRead, status_code=status.HTTP_201_CREATED)
async def create_ride(data: RideCreate, user: CurrentUser, session: DBSession) -> RideRead:
    ride = await services.create_ride(session, user, data)
    return await _read(session, ride, user)


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
    ride = await services.get_for_participant(session, user, ride_id)
    return await _read(session, ride, user)


@router.post("/{ride_id}/cancel", response_model=RideRead)
async def cancel(
    ride_id: uuid.UUID, user: CurrentUser, session: DBSession, data: CancelRequest | None = None
) -> RideRead:
    ride = await services.cancel(session, user, ride_id, data.reason if data else None)
    return await _read(session, ride, user)


# --- Driver ------------------------------------------------------------------------------------


@router.post("/{ride_id}/accept", response_model=RideRead)
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
async def start(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> RideRead:
    ride = await services.driver_step(session, user, ride_id, RideStatus.IN_PROGRESS)
    return await _read(session, ride, user)


@router.post("/{ride_id}/complete", response_model=RideRead)
async def complete(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> RideRead:
    ride = await services.driver_step(session, user, ride_id, RideStatus.COMPLETED)
    return await _read(session, ride, user)


@driver_router.post("/online", response_model=DriverState)
async def go_online(data: GoOnline, user: CurrentUser, session: DBSession) -> DriverState:
    return await services.go_online(session, user, data.lat, data.lng)


@driver_router.post("/offline", response_model=DriverState)
async def go_offline(user: CurrentUser, session: DBSession) -> DriverState:
    return await services.go_offline(session, user)


@driver_router.post("/location", status_code=status.HTTP_204_NO_CONTENT)
async def update_location(data: LocationUpdate, user: CurrentUser) -> None:
    """Same as the socket's ``location`` message, for the background service (app minimized)."""
    await presence.handle_location(str(user.id), data.model_dump())


@driver_router.get("/state", response_model=DriverState)
async def driver_state(user: CurrentUser, session: DBSession) -> DriverState:
    return await services.driver_state(session, user)


# --- Chat and rating ---------------------------------------------------------------------------


@router.get("/{ride_id}/messages", response_model=list[MessageRead])
async def list_messages(
    ride_id: uuid.UUID, user: CurrentUser, session: DBSession
) -> list[MessageRead]:
    ride = await services.get_for_participant(session, user, ride_id)
    return [MessageRead.model_validate(m) for m in await services.list_messages(session, ride.id)]


@router.post("/{ride_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def post_message(
    ride_id: uuid.UUID, data: MessageCreate, user: CurrentUser, session: DBSession
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
    _: StaffUser,
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
async def admin_live(_: StaffUser, session: DBSession) -> list[RideAdminRead]:
    rides = await services.live_rides(session)
    return await events.serialize_rides(session, rides, admin=True)  # type: ignore[return-value]


@admin_router.get("/{ride_id}", response_model=RideAdminDetail)
async def admin_detail(ride_id: uuid.UUID, _: StaffUser, session: DBSession) -> RideAdminDetail:
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
    )


@admin_router.post("/{ride_id}/cancel", response_model=RideAdminRead)
async def admin_cancel(
    ride_id: uuid.UUID, data: AdminCancelRequest, admin: StaffUser, session: DBSession
) -> RideAdminRead:
    ride = await services.admin_cancel(session, admin, ride_id, data.reason)
    return (await events.serialize_rides(session, [ride], admin=True))[0]  # type: ignore[return-value]


@admin_drivers_router.get("/online", response_model=list[OnlineDriver])
async def online_drivers(_: StaffUser, session: DBSession) -> list[OnlineDriver]:
    return await services.online_drivers(session)
