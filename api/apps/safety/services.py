"""Trip safety (doc 11): trusted contacts, live share links, SOS, "¿Todo bien?" check-ins after
an anomaly, and the team's safety center.

Anomalies (``check_rides``, every 30 s from ``apps.safety.tasks``) never go straight to the team:
both people get "¿Todo bien?" first. "Necesito ayuda" from either, or no "Estoy bien" from the
passenger before the deadline, opens the alert for the team (and Telegram). An SOS opens at once.
"""

import hashlib
import logging
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import SafetySettings
from apps.config.services import get_app_config
from apps.control import services as control
from apps.control.flags import Audience
from apps.drivers.models import DriverProfile
from apps.notifications import tasks as notification_tasks
from apps.realtime.manager import publish
from apps.rides import presence
from apps.rides.models import ACTIVE_STATUSES, FINAL_STATUSES, Ride, RideStatus
from apps.rides.schemas import DriverLocation, VehicleBrief
from apps.rides.state import RideNotFoundError
from apps.safety import geo, track
from apps.safety.models import (
    ACTIVE_ALERT_STATUSES,
    AlertKind,
    AlertStatus,
    RideShareLink,
    RideTrack,
    SafetyAlert,
    TrustedContact,
)
from apps.safety.schemas import (
    AlertAdminRead,
    AlertParty,
    AlertRead,
    AlertResolve,
    AlertSummary,
    ContactWrite,
    Position,
    SharedPerson,
    SharedRide,
    ShareLink,
    SosRead,
    SosRequest,
)
from apps.users.models import User
from kuulis.core import storage
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError
from kuulis.core.pagination import PageParams, paginate
from kuulis.settings import settings

logger = logging.getLogger(__name__)

MAX_CONTACTS = 5
MAX_LINKS_PER_RIDE = 20  # per person; every share creates a new link (only hashes are stored)
SOS_GRACE = timedelta(minutes=30)  # an SOS can still be raised this long after the ride ended
STOP_RADIUS_M = 60  # GPS noise: points within this distance count as "not moving"
STOP_MIN_FROM_DROPOFF_M = 200
OVERTIME_MIN_EXTRA = timedelta(minutes=5)  # short rides: never "overtime" for a few minutes
WINDOW_SLACK_S = 30  # the track must cover the rule's window minus this


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Errors ------------------------------------------------------------------------------------


class ContactNotFoundError(NotFoundError):
    code = "contact_not_found"
    message = "Contact not found"


class TooManyContactsError(ConflictError):
    code = "too_many_contacts"
    message = "You reached the maximum number of trusted contacts"


class ShareClosedError(ConflictError):
    code = "share_closed"
    message = "Only an active ride can be shared"


class ShareNotFoundError(NotFoundError):
    code = "share_not_found"
    message = "This link does not exist"


class ShareExpiredError(AppError):
    status_code = 410
    code = "share_expired"
    message = "This ride has ended"


class SosClosedError(ConflictError):
    code = "sos_closed"
    message = "This ride ended too long ago"


class AlertNotFoundError(NotFoundError):
    code = "alert_not_found"
    message = "Alert not found"


class AlertClosedError(ConflictError):
    code = "alert_closed"
    message = "This alert is already closed"


class NoActiveSosError(NotFoundError):
    code = "no_active_sos"
    message = "There is no active SOS"


# --- Trusted contacts --------------------------------------------------------------------------


async def list_contacts(session: AsyncSession, user_id: uuid.UUID) -> list[TrustedContact]:
    rows = await session.scalars(
        select(TrustedContact)
        .where(TrustedContact.user_id == user_id)
        .order_by(TrustedContact.created_at, TrustedContact.id)
    )
    return list(rows)


async def add_contact(session: AsyncSession, user: User, data: ContactWrite) -> TrustedContact:
    # Serializes concurrent adds of the same user, so the limit holds.
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    count = await session.scalar(select(func.count()).where(TrustedContact.user_id == user.id))
    if (count or 0) >= MAX_CONTACTS:
        raise TooManyContactsError(details={"max": MAX_CONTACTS})
    contact = TrustedContact(user_id=user.id, **data.model_dump())
    session.add(contact)
    await session.flush()
    await session.refresh(contact)
    return contact


async def _own_contact(
    session: AsyncSession, user_id: uuid.UUID, contact_id: uuid.UUID
) -> TrustedContact:
    contact = await session.get(TrustedContact, contact_id)
    if contact is None or contact.user_id != user_id:
        raise ContactNotFoundError()
    return contact


async def update_contact(
    session: AsyncSession, user_id: uuid.UUID, contact_id: uuid.UUID, data: ContactWrite
) -> TrustedContact:
    contact = await _own_contact(session, user_id, contact_id)
    for field, value in data.model_dump().items():
        setattr(contact, field, value)
    await session.flush()
    await session.refresh(contact)
    return contact


async def delete_contact(session: AsyncSession, user_id: uuid.UUID, contact_id: uuid.UUID) -> None:
    await session.delete(await _own_contact(session, user_id, contact_id))


# --- Live share links --------------------------------------------------------------------------


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def share_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/v/{token}"


async def _participant_ride(session: AsyncSession, user: User, ride_id: uuid.UUID) -> Ride:
    ride = await session.get(Ride, ride_id)
    if ride is None or user.id not in (ride.passenger_id, ride.driver_id):
        raise RideNotFoundError()
    return ride


def _role(ride: Ride, user_id: uuid.UUID) -> str:
    return "driver" if user_id == ride.driver_id else "passenger"


async def _open_sos(session: AsyncSession, ride_id: uuid.UUID) -> SafetyAlert | None:
    return await session.scalar(
        select(SafetyAlert)
        .where(
            SafetyAlert.ride_id == ride_id,
            SafetyAlert.kind == AlertKind.SOS,
            SafetyAlert.status.in_(ACTIVE_ALERT_STATUSES),
        )
        .order_by(SafetyAlert.created_at.desc())
        .limit(1)
    )


async def _new_link(session: AsyncSession, ride: Ride, user: User) -> ShareLink:
    count = await session.scalar(
        select(func.count()).where(
            RideShareLink.ride_id == ride.id, RideShareLink.created_by_id == user.id
        )
    )
    if (count or 0) >= MAX_LINKS_PER_RIDE:
        # Revoke the oldest so a link only lives while it is needed.
        oldest = await session.scalar(
            select(RideShareLink)
            .where(RideShareLink.ride_id == ride.id, RideShareLink.created_by_id == user.id)
            .order_by(RideShareLink.created_at)
            .limit(1)
        )
        if oldest is not None:
            await session.delete(oldest)
    token = secrets.token_urlsafe(16)  # 128 bits
    session.add(RideShareLink(ride_id=ride.id, token_hash=_hash(token), created_by_id=user.id))
    return ShareLink(url=share_url(token), token=token)


async def share(session: AsyncSession, user: User, ride_id: uuid.UUID) -> ShareLink:
    ride = await _participant_ride(session, user, ride_id)
    await control.ensure_enabled(
        session, "share_live_link", Audience(ident=str(user.id), role=_role(ride, user.id))
    )
    if ride.status not in ACTIVE_STATUSES and await _open_sos(session, ride.id) is None:
        raise ShareClosedError(details={"status": ride.status.value})
    link = await _new_link(session, ride, user)
    await session.commit()
    return link


def _first_name(user: User | None) -> str:
    parts = (user.full_name or "").split() if user else []
    return parts[0] if parts else ""


async def shared_ride(session: AsyncSession, token: str) -> SharedRide:
    link = await session.scalar(
        select(RideShareLink).where(RideShareLink.token_hash == _hash(token))
    )
    if link is None:
        raise ShareNotFoundError()
    ride = await session.get(Ride, link.ride_id)
    if ride is None:
        raise ShareNotFoundError()
    sos = await _open_sos(session, ride.id)
    if link.revoked_at is not None or (ride.status in FINAL_STATUSES and sos is None):
        raise ShareExpiredError()

    passenger = await session.get(User, ride.passenger_id)
    driver = await session.get(User, ride.driver_id) if ride.driver_id else None
    driver_brief = None
    if driver is not None:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.id)
        )
        from apps.rides.events import _profiles

        selfie = (await _profiles(session, {driver.id})).get(driver.id, (None, None))[1]
        driver_brief = SharedPerson(
            first_name=_first_name(driver),
            photo_url=storage.download_url_or_none(selfie),
            rating=float(profile.rating_avg) if profile and profile.rating_avg else None,
        )
    location = None
    if ride.driver_id and ride.status not in FINAL_STATUSES:
        loc = await presence.get_location(ride.driver_id)
        if loc is not None:
            location = DriverLocation(lat=loc.lat, lng=loc.lng, heading=loc.heading)
    eta = None
    if ride.status == RideStatus.IN_PROGRESS and ride.started_at:
        eta = max(ride.started_at + timedelta(seconds=ride.duration_s), utcnow())
    sos_location = None
    if sos is not None and sos.lat is not None and sos.lng is not None:
        sos_location = DriverLocation(lat=sos.lat, lng=sos.lng, heading=None)
    return SharedRide(
        status=ride.status,
        pickup={"lat": ride.pickup_lat, "lng": ride.pickup_lng, "address": ride.pickup_address},
        dropoff={
            "lat": ride.dropoff_lat,
            "lng": ride.dropoff_lng,
            "address": ride.dropoff_address,
        },
        polyline=ride.polyline,
        passenger=SharedPerson(first_name=_first_name(passenger)),
        driver=driver_brief,
        vehicle=VehicleBrief.model_validate(ride.vehicle) if ride.vehicle else None,
        driver_location=location,
        started_at=ride.started_at,
        eta=eta,
        sos=sos is not None,
        sos_location=sos_location,
        updated_at=utcnow(),
    )


async def revoke_links(session: AsyncSession, ride_id: uuid.UUID) -> None:
    await session.execute(
        update(RideShareLink)
        .where(RideShareLink.ride_id == ride_id, RideShareLink.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


# --- SOS ---------------------------------------------------------------------------------------


def _ended_at(ride: Ride) -> datetime | None:
    return ride.completed_at or ride.cancelled_at


async def sos(session: AsyncSession, user: User, ride_id: uuid.UUID, data: SosRequest) -> SosRead:
    ride = await _participant_ride(session, user, ride_id)
    ended = _ended_at(ride)
    if ride.status in FINAL_STATUSES and (ended is None or utcnow() - ended > SOS_GRACE):
        raise SosClosedError()
    now = utcnow()
    alert = await session.scalar(
        select(SafetyAlert)
        .where(
            SafetyAlert.ride_id == ride.id,
            SafetyAlert.user_id == user.id,
            SafetyAlert.kind == AlertKind.SOS,
            SafetyAlert.status.in_(ACTIVE_ALERT_STATUSES),
        )
        .with_for_update()
    )
    created = alert is None
    if alert is None:
        alert = SafetyAlert(
            ride_id=ride.id,
            user_id=user.id,
            kind=AlertKind.SOS,
            status=AlertStatus.OPEN,
            escalated_at=now,
            details={"role": _role(ride, user.id)},
            answers={},
        )
        session.add(alert)
    if data.lat is not None and data.lng is not None:
        alert.lat, alert.lng, alert.location_at = data.lat, data.lng, now
    link = await _new_link(session, ride, user)
    await session.commit()
    await session.refresh(alert)
    if created:
        await _alert_team(alert)
    config = await get_app_config(session)
    return SosRead(
        **AlertRead.model_validate(alert).model_dump(),
        share_url=link.url,
        location_seconds=config.safety.sos_location_seconds,
    )


async def update_location(session: AsyncSession, user: User, data: Position) -> int:
    """Position of the user's open SOS (the app sends it every few seconds while it lasts)."""
    result = await session.execute(
        update(SafetyAlert)
        .where(
            SafetyAlert.user_id == user.id,
            SafetyAlert.kind == AlertKind.SOS,
            SafetyAlert.status.in_(ACTIVE_ALERT_STATUSES),
        )
        .values(lat=data.lat, lng=data.lng, location_at=utcnow())
    )
    await session.commit()
    if not result.rowcount:
        raise NoActiveSosError()
    return result.rowcount


async def cancel_sos(session: AsyncSession, user: User, alert_id: uuid.UUID) -> SafetyAlert:
    """The person who pressed SOS says it was a mistake; the team still sees it, closed."""
    alert = await session.get(SafetyAlert, alert_id, with_for_update=True)
    if alert is None or alert.user_id != user.id or alert.kind != AlertKind.SOS:
        raise AlertNotFoundError()
    if alert.status not in ACTIVE_ALERT_STATUSES:
        raise AlertClosedError()
    alert.status = AlertStatus.RESOLVED
    alert.outcome = "cancelled_by_user"
    alert.resolved_at = utcnow()
    await session.commit()
    await _send_team_text(f"SOS cancelado por quien lo activó ({_short(alert.id)}).")
    return alert


# --- My alerts and check-in answers ------------------------------------------------------------


async def my_active(session: AsyncSession, user: User) -> list[SafetyAlert]:
    """The user's open SOS and the "¿Todo bien?" questions still waiting for their answer."""
    rows = await session.scalars(
        select(SafetyAlert)
        .outerjoin(Ride, Ride.id == SafetyAlert.ride_id)
        .where(
            or_(
                (SafetyAlert.kind == AlertKind.SOS)
                & (SafetyAlert.user_id == user.id)
                & SafetyAlert.status.in_(ACTIVE_ALERT_STATUSES),
                (SafetyAlert.status == AlertStatus.CHECKING)
                & or_(Ride.passenger_id == user.id, Ride.driver_id == user.id),
            )
        )
        .order_by(SafetyAlert.created_at)
    )
    return [a for a in rows if str(user.id) not in (a.answers or {})]


async def answer(session: AsyncSession, user: User, alert_id: uuid.UUID, value: str) -> SafetyAlert:
    alert = await session.get(SafetyAlert, alert_id, with_for_update=True)
    ride = await session.get(Ride, alert.ride_id) if alert and alert.ride_id else None
    if (
        alert is None
        or ride is None
        or alert.kind == AlertKind.SOS
        or user.id not in (ride.passenger_id, ride.driver_id)
    ):
        raise AlertNotFoundError()
    if alert.status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
        raise AlertClosedError()
    alert.answers = {**(alert.answers or {}), str(user.id): value}
    escalate = False
    if value == "help" and alert.status == AlertStatus.CHECKING:
        alert.status, alert.escalated_at = AlertStatus.OPEN, utcnow()
        alert.details = {**alert.details, "reason": "help"}
        escalate = True
    elif value == "ok" and user.id == ride.passenger_id and alert.status == AlertStatus.CHECKING:
        alert.status, alert.resolved_at, alert.outcome = (
            AlertStatus.DISMISSED,
            utcnow(),
            "passenger_ok",
        )
    await session.commit()
    if escalate:
        await _alert_team(alert)
    return alert


# --- Anomaly rules -----------------------------------------------------------------------------


def detect(
    ride: Ride, points: list[track.Point], rules: SafetySettings, now: float
) -> dict[AlertKind, dict[str, Any]]:
    """Pure rules over the ride and its recent track (oldest first). Returns kind -> details."""
    found: dict[AlertKind, dict[str, Any]] = {}
    if ride.started_at is not None:
        elapsed = now - ride.started_at.timestamp()
        limit = max(ride.duration_s * rules.overtime_factor, ride.duration_s + 300)
        if elapsed > limit:
            found[AlertKind.OVERTIME] = {
                "minutes": round(elapsed / 60),
                "estimated_minutes": round(ride.duration_s / 60),
            }
    if not points:
        return found
    last = points[-1]

    window = rules.stop_minutes * 60
    stop_points = [p for p in points if p[2] >= now - window]
    if stop_points and stop_points[0][2] <= now - window + WINDOW_SLACK_S:
        still = all(
            geo.distance_m(p[0], p[1], last[0], last[1]) <= STOP_RADIUS_M for p in stop_points
        )
        from_dropoff = geo.distance_m(last[0], last[1], ride.dropoff_lat, ride.dropoff_lng)
        if still and from_dropoff > STOP_MIN_FROM_DROPOFF_M:
            found[AlertKind.STOP] = {
                "minutes": round((now - stop_points[0][2]) / 60),
                "lat": last[0],
                "lng": last[1],
            }

    if ride.polyline:
        window = rules.deviation_minutes * 60
        recent = [p for p in points if p[2] >= now - window]
        if recent and recent[0][2] <= now - window + WINDOW_SLACK_S:
            path = geo.decode_polyline(ride.polyline)
            distances = [geo.distance_to_path_m(p[0], p[1], path) for p in recent]
            if min(distances) > rules.deviation_m:
                found[AlertKind.DEVIATION] = {
                    "distance_m": round(distances[-1]),
                    "lat": last[0],
                    "lng": last[1],
                }
    return found


async def check_rides(session: AsyncSession) -> list[SafetyAlert]:
    """Evaluates the rides in progress and opens a "¿Todo bien?" for each new anomaly."""
    config = await get_app_config(session)
    rules = config.safety
    rides = list(await session.scalars(select(Ride).where(Ride.status == RideStatus.IN_PROGRESS)))
    if not rides:
        return []
    seen = set(
        (
            await session.execute(
                select(SafetyAlert.ride_id, SafetyAlert.kind).where(
                    SafetyAlert.ride_id.in_([r.id for r in rides]),
                    SafetyAlert.kind != AlertKind.SOS,
                )
            )
        ).all()
    )
    window = max(rules.stop_minutes, rules.deviation_minutes) * 60 + 60
    now = time.time()
    deadline = utcnow() + timedelta(seconds=rules.check_in_seconds)
    created: list[SafetyAlert] = []
    for ride in rides:
        points = await track.recent(ride.id, window)
        for kind, details in detect(ride, points, rules, now).items():
            if (ride.id, kind) in seen:
                continue
            alert = SafetyAlert(
                ride_id=ride.id,
                user_id=ride.passenger_id,
                kind=kind,
                status=AlertStatus.CHECKING,
                lat=details.get("lat", points[-1][0] if points else None),
                lng=details.get("lng", points[-1][1] if points else None),
                location_at=utcnow() if points else None,
                details=details,
                answers={},
                check_in_deadline=deadline,
            )
            session.add(alert)
            created.append(alert)
    if not created:
        return []
    await session.commit()
    rides_by_id = {r.id: r for r in rides}
    for alert in created:
        await _ask_participants(session, alert, rides_by_id[alert.ride_id])
    return created


async def escalate_due(session: AsyncSession) -> list[SafetyAlert]:
    """Check-ins nobody answered "Estoy bien" in time go to the team."""
    now = utcnow()
    due = list(
        await session.scalars(
            select(SafetyAlert)
            .where(
                SafetyAlert.status == AlertStatus.CHECKING,
                SafetyAlert.check_in_deadline <= now,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for alert in due:
        alert.status, alert.escalated_at = AlertStatus.OPEN, now
        alert.details = {**alert.details, "reason": "no_answer"}
    if due:
        await session.commit()
        for alert in due:
            await _alert_team(alert)
    return due


# --- Notifications -----------------------------------------------------------------------------

CHECK_IN_TEXT = {
    AlertKind.STOP: {
        "es": "El viaje lleva varios minutos detenido. ¿Todo bien?",
        "en": "Your ride has been stopped for a few minutes. Is everything OK?",
    },
    AlertKind.DEVIATION: {
        "es": "El viaje se apartó de la ruta prevista. ¿Todo bien?",
        "en": "Your ride left the planned route. Is everything OK?",
    },
    AlertKind.OVERTIME: {
        "es": "El viaje está tardando mucho más de lo estimado. ¿Todo bien?",
        "en": "Your ride is taking much longer than expected. Is everything OK?",
    },
}
CHECK_IN_TITLE = {"es": "¿Todo bien?", "en": "Is everything OK?"}


async def _ask_participants(session: AsyncSession, alert: SafetyAlert, ride: Ride) -> None:
    payload = AlertRead.model_validate(alert).model_dump(mode="json")
    for user_id in (ride.passenger_id, ride.driver_id):
        if user_id is None:
            continue
        user = await session.get(User, user_id)
        locale = user.locale if user and user.locale in ("es", "en") else "es"
        await publish("safety.check_in", payload, user_ids=[str(user_id)])
        await notification_tasks.send_push.kiq(
            [str(user_id)],
            CHECK_IN_TITLE[locale],
            CHECK_IN_TEXT[alert.kind][locale],
            {
                "type": "safety",
                "event": "check_in",
                "alert_id": str(alert.id),
                "ride_id": str(ride.id),
            },
            {"priority": "high", "categoryId": "safety_check"},
        )


def _short(alert_id: uuid.UUID) -> str:
    return str(alert_id)[:8]


async def _alert_team(alert: SafetyAlert) -> None:
    """Telegram (doc 03) for an alert that needs the team; the admin rings on its own poll."""
    from apps.safety import tasks

    await tasks.notify_team.kiq(str(alert.id))


async def _send_team_text(text: str) -> None:
    from apps.safety import tasks

    await tasks.send_team_text.kiq(text)


KIND_LABEL = {
    AlertKind.SOS: "🆘 SOS",
    AlertKind.STOP: "⚠️ Parada larga",
    AlertKind.DEVIATION: "⚠️ Desvío de la ruta",
    AlertKind.OVERTIME: "⚠️ Viaje demasiado largo",
}
REASON_LABEL = {"help": "pidió ayuda", "no_answer": "nadie respondió ¿Todo bien?"}


async def team_message(session: AsyncSession, alert: SafetyAlert) -> str:
    who = await session.get(User, alert.user_id)
    role = "motorizado" if alert.details.get("role") == "driver" else "pasajero"
    lines = [f"{KIND_LABEL[alert.kind]} · Kuulis {settings.APP_ENV}"]
    if alert.kind == AlertKind.SOS:
        lines.append(f"Activado por el {role} {who.full_name if who else ''}".rstrip())
    elif reason := alert.details.get("reason"):
        lines.append(f"Escalada: {REASON_LABEL.get(reason, reason)}")
    if alert.lat is not None and alert.lng is not None:
        lines.append(f"Ubicación: https://maps.google.com/?q={alert.lat:.5f},{alert.lng:.5f}")
    lines.append(f"Centro de seguridad: {settings.admin_url}/safety?alert={alert.id}")
    return "\n".join(lines)


# --- Admin -------------------------------------------------------------------------------------

ADMIN_FILTERS = {
    "active": (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED),
    "checking": (AlertStatus.CHECKING,),
    "closed": (AlertStatus.RESOLVED, AlertStatus.DISMISSED),
}


async def list_admin(
    session: AsyncSession, params: PageParams, status: str | None, ride_id: uuid.UUID | None
) -> tuple[list[SafetyAlert], int]:
    stmt = select(SafetyAlert).order_by(SafetyAlert.created_at.desc())
    if status in ADMIN_FILTERS:
        stmt = stmt.where(SafetyAlert.status.in_(ADMIN_FILTERS[status]))
    if ride_id is not None:
        stmt = stmt.where(SafetyAlert.ride_id == ride_id)
    return await paginate(session, stmt, params)


async def summary(session: AsyncSession) -> AlertSummary:
    rows = dict(
        (
            await session.execute(
                select(SafetyAlert.status, func.count())
                .where(SafetyAlert.status.in_(ACTIVE_ALERT_STATUSES))
                .group_by(SafetyAlert.status)
            )
        ).all()
    )
    latest = await session.scalar(
        select(SafetyAlert.id)
        .where(SafetyAlert.status == AlertStatus.OPEN)
        .order_by(SafetyAlert.escalated_at.desc().nulls_last(), SafetyAlert.created_at.desc())
        .limit(1)
    )
    return AlertSummary(
        open=rows.get(AlertStatus.OPEN, 0),
        acknowledged=rows.get(AlertStatus.ACKNOWLEDGED, 0),
        latest_id=latest,
    )


async def serialize_admin(session: AsyncSession, alerts: list[SafetyAlert]) -> list[AlertAdminRead]:
    if not alerts:
        return []
    ride_ids = {a.ride_id for a in alerts if a.ride_id}
    rides = (
        {r.id: r for r in await session.scalars(select(Ride).where(Ride.id.in_(ride_ids)))}
        if ride_ids
        else {}
    )
    user_ids = {a.user_id for a in alerts} | {a.handled_by_id for a in alerts if a.handled_by_id}
    for ride in rides.values():
        user_ids.add(ride.passenger_id)
        if ride.driver_id:
            user_ids.add(ride.driver_id)
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(user_ids)))}
    phones = dict(
        (
            await session.execute(
                select(DriverProfile.user_id, DriverProfile.phone).where(
                    DriverProfile.user_id.in_(user_ids)
                )
            )
        ).all()
    )
    live = [str(r.driver_id) for r in rides.values() if r.driver_id and r.status in ACTIVE_STATUSES]
    locations = await presence.get_locations(live)

    def party(user_id: uuid.UUID | None, role: str) -> AlertParty | None:
        user = users.get(user_id) if user_id else None
        if user is None:
            return None
        return AlertParty(
            id=user.id,
            name=user.full_name,
            email=user.email,
            phone=phones.get(user.id) if role == "driver" else None,
            role=role,  # type: ignore[arg-type]
        )

    result = []
    for alert in alerts:
        ride = rides.get(alert.ride_id) if alert.ride_id else None
        driver_id = ride.driver_id if ride else None
        loc = locations.get(str(driver_id)) if driver_id else None
        raised_role = "driver" if driver_id and alert.user_id == driver_id else "passenger"
        handler = users.get(alert.handled_by_id) if alert.handled_by_id else None
        result.append(
            AlertAdminRead(
                id=alert.id,
                ride_id=alert.ride_id,
                ride_status=ride.status if ride else None,
                kind=alert.kind,
                status=alert.status,
                raised_by=party(alert.user_id, raised_role),
                passenger=party(ride.passenger_id, "passenger") if ride else None,
                driver=party(driver_id, "driver"),
                vehicle=VehicleBrief.model_validate(ride.vehicle)
                if ride and ride.vehicle
                else None,
                lat=alert.lat,
                lng=alert.lng,
                location_at=alert.location_at,
                driver_location=DriverLocation(lat=loc.lat, lng=loc.lng, heading=loc.heading)
                if loc
                else None,
                pickup={
                    "lat": ride.pickup_lat,
                    "lng": ride.pickup_lng,
                    "address": ride.pickup_address,
                }
                if ride
                else None,
                dropoff={
                    "lat": ride.dropoff_lat,
                    "lng": ride.dropoff_lng,
                    "address": ride.dropoff_address,
                }
                if ride
                else None,
                polyline=ride.polyline if ride else None,
                details=alert.details or {},
                answers=alert.answers or {},
                check_in_deadline=alert.check_in_deadline,
                escalated_at=alert.escalated_at,
                acknowledged_at=alert.acknowledged_at,
                handled_by_id=alert.handled_by_id,
                handled_by_name=handler.full_name if handler else None,
                notes=alert.notes,
                outcome=alert.outcome,
                created_at=alert.created_at,
                resolved_at=alert.resolved_at,
            )
        )
    return result


async def _lock_alert(session: AsyncSession, alert_id: uuid.UUID) -> SafetyAlert:
    alert = await session.get(SafetyAlert, alert_id, with_for_update=True)
    if alert is None:
        raise AlertNotFoundError()
    return alert


async def acknowledge(session: AsyncSession, admin: User, alert_id: uuid.UUID) -> SafetyAlert:
    alert = await _lock_alert(session, alert_id)
    if alert.status not in (AlertStatus.OPEN, AlertStatus.CHECKING, AlertStatus.ACKNOWLEDGED):
        raise AlertClosedError()
    if alert.status != AlertStatus.ACKNOWLEDGED:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = utcnow()
        alert.escalated_at = alert.escalated_at or alert.acknowledged_at
    alert.handled_by_id = admin.id
    await session.commit()
    return alert


async def resolve(
    session: AsyncSession, admin: User, alert_id: uuid.UUID, data: AlertResolve
) -> SafetyAlert:
    alert = await _lock_alert(session, alert_id)
    if alert.status in (AlertStatus.RESOLVED, AlertStatus.DISMISSED):
        raise AlertClosedError()
    alert.status = AlertStatus.RESOLVED
    alert.outcome = data.outcome
    alert.resolved_at = utcnow()
    alert.handled_by_id = alert.handled_by_id or admin.id
    if data.notes.strip():
        alert.notes = data.notes.strip()
    await session.commit()
    return alert


async def set_notes(session: AsyncSession, alert_id: uuid.UUID, notes: str) -> SafetyAlert:
    alert = await _lock_alert(session, alert_id)
    alert.notes = notes.strip()
    await session.commit()
    return alert


# --- Ride track --------------------------------------------------------------------------------


async def ride_track(session: AsyncSession, ride: Ride) -> list[list[float]]:
    """Stored path of a finished ride, or the buffer of one still going."""
    stored = await session.scalar(select(RideTrack.points).where(RideTrack.ride_id == ride.id))
    if stored is not None:
        return stored
    return track.thin(await track.buffered(ride.id))


async def ride_alerts(session: AsyncSession, ride_id: uuid.UUID) -> list[SafetyAlert]:
    rows = await session.scalars(
        select(SafetyAlert).where(SafetyAlert.ride_id == ride_id).order_by(SafetyAlert.created_at)
    )
    return list(rows)


async def ride_ended(session: AsyncSession, ride_id: uuid.UUID) -> None:
    """After a ride completes or is cancelled: store its path and close its share links (an
    open SOS keeps them working until it is resolved)."""
    await track.flush(session, ride_id)
    if await _open_sos(session, ride_id) is None:
        await revoke_links(session, ride_id)
    await session.commit()
