import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Request, status

from apps.audit.services import audit
from apps.safety import services
from apps.safety.schemas import (
    AlertAdminRead,
    AlertNotes,
    AlertRead,
    AlertResolve,
    AlertSummary,
    CheckInAnswer,
    ContactRead,
    ContactWrite,
    Position,
    SharedRide,
    ShareLink,
    ShareRequest,
    SosRead,
    SosRequest,
)
from apps.users.dependencies import Can, CurrentUser, DBSession
from kuulis.core.pagination import Page, PageParams, page_params
from kuulis.core.rate_limit import limiter

router = APIRouter(tags=["safety"])
admin_router = APIRouter(prefix="/admin/safety", tags=["safety"])


# --- Trusted contacts --------------------------------------------------------------------------


@router.get("/users/me/trusted-contacts", response_model=list[ContactRead])
async def list_contacts(user: CurrentUser, session: DBSession) -> list[ContactRead]:
    return [ContactRead.model_validate(c) for c in await services.list_contacts(session, user.id)]


@router.post(
    "/users/me/trusted-contacts", response_model=ContactRead, status_code=status.HTTP_201_CREATED
)
async def add_contact(data: ContactWrite, user: CurrentUser, session: DBSession) -> ContactRead:
    """Up to five (409 ``too_many_contacts``)."""
    return ContactRead.model_validate(await services.add_contact(session, user, data))


@router.put("/users/me/trusted-contacts/{contact_id}", response_model=ContactRead)
async def update_contact(
    contact_id: uuid.UUID, data: ContactWrite, user: CurrentUser, session: DBSession
) -> ContactRead:
    return ContactRead.model_validate(
        await services.update_contact(session, user.id, contact_id, data)
    )


@router.delete("/users/me/trusted-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: uuid.UUID, user: CurrentUser, session: DBSession) -> None:
    await services.delete_contact(session, user.id, contact_id)


# --- Sharing and SOS during a ride -------------------------------------------------------------


@router.post("/rides/{ride_id}/share", response_model=ShareLink)
@limiter.limit("20/minute")
async def share(
    request: Request,
    ride_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
    data: ShareRequest | None = None,
) -> ShareLink:
    """A new link to follow the ride live; it stops working when the ride ends (410).

    ``for_rider`` (doc 23, passenger of a ride requested for someone else): the link for the
    person riding, which also shows the start PIN.
    """
    return await services.share(session, user, ride_id, for_rider=data.for_rider if data else False)


@router.get("/public/rides/shared/{token}", response_model=SharedRide)
@limiter.limit("60/minute")
async def shared_ride(
    request: Request, token: Annotated[str, Path(max_length=64)], session: DBSession
) -> SharedRide:
    """No login: what ``/v/{token}`` on the website shows. 404 unknown, 410 ended."""
    return await services.shared_ride(session, token)


@router.post("/rides/{ride_id}/sos", response_model=SosRead)
@limiter.limit("10/minute")
async def sos(
    request: Request,
    ride_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
    data: SosRequest | None = None,
) -> SosRead:
    """Opens an SOS for the team (once; repeating it only updates the position). Works up to 30
    minutes after the ride ended. Returns a live link for the trusted contacts."""
    return await services.sos(session, user, ride_id, data or SosRequest())


@router.post("/safety/location", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def sos_location(
    request: Request, data: Position, user: CurrentUser, session: DBSession
) -> None:
    """Position while the user's SOS is open; 404 ``no_active_sos`` tells the app to stop."""
    await services.update_location(session, user, data)


@router.get("/safety/alerts/active", response_model=list[AlertRead])
async def my_alerts(user: CurrentUser, session: DBSession) -> list[AlertRead]:
    """The user's open SOS and the "¿Todo bien?" questions waiting for their answer."""
    return [AlertRead.model_validate(a) for a in await services.my_active(session, user)]


@router.post("/safety/alerts/{alert_id}/ok", response_model=AlertRead)
async def answer_ok(alert_id: uuid.UUID, user: CurrentUser, session: DBSession) -> AlertRead:
    return AlertRead.model_validate(await services.answer(session, user, alert_id, "ok"))


@router.post("/safety/alerts/{alert_id}/help", response_model=AlertRead)
async def answer_help(alert_id: uuid.UUID, user: CurrentUser, session: DBSession) -> AlertRead:
    return AlertRead.model_validate(await services.answer(session, user, alert_id, "help"))


@router.post("/safety/alerts/{alert_id}/answer", response_model=AlertRead)
async def answer(
    alert_id: uuid.UUID, data: CheckInAnswer, user: CurrentUser, session: DBSession
) -> AlertRead:
    return AlertRead.model_validate(await services.answer(session, user, alert_id, data.answer))


@router.post("/safety/alerts/{alert_id}/cancel", response_model=AlertRead)
async def cancel_sos(alert_id: uuid.UUID, user: CurrentUser, session: DBSession) -> AlertRead:
    """The person who pressed SOS closes it (false alarm)."""
    return AlertRead.model_validate(await services.cancel_sos(session, user, alert_id))


# --- Admin: safety center ----------------------------------------------------------------------


@admin_router.get("/summary", response_model=AlertSummary)
async def summary(_: Can("safety.view"), session: DBSession) -> AlertSummary:
    """Polled every few seconds by the admin for the badge and the alarm sound."""
    return await services.summary(session)


@admin_router.get("/alerts", response_model=Page[AlertAdminRead])
async def list_alerts(
    _: Can("safety.view"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status: Literal["active", "checking", "closed", "all"] = "active",
    ride_id: uuid.UUID | None = None,
) -> Page[AlertAdminRead]:
    items, total = await services.list_admin(session, params, status, ride_id)
    return Page[AlertAdminRead](
        items=await services.serialize_admin(session, items),
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@admin_router.get("/alerts/{alert_id}", response_model=AlertAdminRead)
async def get_alert(
    alert_id: uuid.UUID, _: Can("safety.view"), session: DBSession
) -> AlertAdminRead:
    alert = await session.get(services.SafetyAlert, alert_id)
    if alert is None:
        raise services.AlertNotFoundError()
    return (await services.serialize_admin(session, [alert]))[0]


@admin_router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertAdminRead,
    dependencies=[audit("safety.acknowledge", "safety_alert", "alert_id")],
)
async def acknowledge(
    alert_id: uuid.UUID, admin: Can("safety.manage"), session: DBSession
) -> AlertAdminRead:
    alert = await services.acknowledge(session, admin, alert_id)
    return (await services.serialize_admin(session, [alert]))[0]


@admin_router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertAdminRead,
    dependencies=[audit("safety.resolve", "safety_alert", "alert_id")],
)
async def resolve(
    alert_id: uuid.UUID, data: AlertResolve, admin: Can("safety.manage"), session: DBSession
) -> AlertAdminRead:
    alert = await services.resolve(session, admin, alert_id, data)
    return (await services.serialize_admin(session, [alert]))[0]


@admin_router.put(
    "/alerts/{alert_id}/notes",
    response_model=AlertAdminRead,
    dependencies=[audit("safety.notes", "safety_alert", "alert_id")],
)
async def set_notes(
    alert_id: uuid.UUID, data: AlertNotes, _: Can("safety.manage"), session: DBSession
) -> AlertAdminRead:
    alert = await services.set_notes(session, alert_id, data.notes)
    return (await services.serialize_admin(session, [alert]))[0]
