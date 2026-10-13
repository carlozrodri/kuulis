"""Privacy (doc 07, part 2): "download my data", explicit consents, the extra scrubbing done when an
account is erased (``apps.users.services.erase_due``) and the retention rules.

Retention (``apply_retention``, run by ``apps.privacy.tasks`` once a day):
- chat messages: 180 days, unless the ride has a report;
- planned route of a ride: 180 days, unless the ride has a report;
- real path of a ride (doc 11): 180 days, unless the ride has a report or a safety alert;
- rejected driver documents: 30 days after the review (file included);
- inbox notifications: 90 days;
- exports: the file is deleted when its link expires (24 h).
"""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import (
    ColumnElement,
    Numeric,
    cast,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from apps.privacy.models import DataExport, ErasedEmail, UserConsent
from apps.users.models import User
from kuulis.core import storage
from kuulis.core.exceptions import ConflictError
from kuulis.core.pagination import PageParams, paginate
from kuulis.core.rate_limit import client_ip

logger = logging.getLogger(__name__)

CONSENT_KINDS = ("background_location",)
EXPORT_FOLDER = "exports"
EXPORT_LINK_SECONDS = 24 * 3600
EXPORT_EVERY = timedelta(days=1)
CHAT_DAYS = 180
ROUTE_DAYS = 180
REJECTED_DOCUMENT_DAYS = 30
NOTIFICATION_DAYS = 90


class ExportTooSoonError(ConflictError):
    code = "export_too_soon"
    message = "You can download your data once a day"


def email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


async def was_erased(session: AsyncSession, email: str, *, suspended_only: bool = True) -> bool:
    stmt = select(ErasedEmail.id).where(ErasedEmail.email_hash == email_hash(email))
    if suspended_only:
        stmt = stmt.where(ErasedEmail.was_suspended.is_(True))
    return await session.scalar(stmt.limit(1)) is not None


# --- Consents ----------------------------------------------------------------------------------


async def consents(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Kinds whose latest answer is "granted"."""
    rows = await session.execute(
        select(UserConsent.kind, UserConsent.granted)
        .where(UserConsent.user_id == user_id)
        .order_by(UserConsent.created_at)
    )
    latest = dict(rows.all())
    return [kind for kind in CONSENT_KINDS if latest.get(kind)]


async def record_consent(
    session: AsyncSession, user: User, kind: str, granted: bool, request: Request | None
) -> None:
    session.add(
        UserConsent(
            user_id=user.id,
            kind=kind,
            granted=granted,
            ip=client_ip(request)[:45] if request else None,
            platform=(request.headers.get("x-client-platform", "")[:20] or None)
            if request
            else None,
        )
    )
    await session.flush()


# --- Download my data --------------------------------------------------------------------------


async def latest_export(session: AsyncSession, user_id: uuid.UUID) -> DataExport | None:
    return await session.scalar(
        select(DataExport)
        .where(DataExport.user_id == user_id)
        .order_by(DataExport.created_at.desc())
        .limit(1)
    )


async def request_export(session: AsyncSession, user: User) -> DataExport:
    """One export a day; a failed one can be retried at once."""
    last = await latest_export(session, user.id)
    if last is not None and last.status != "failed":
        next_at = last.created_at + EXPORT_EVERY
        if next_at > datetime.now(UTC):
            raise ExportTooSoonError(details={"next_at": next_at.isoformat()})
    export = DataExport(user_id=user.id, status="pending")
    session.add(export)
    await session.flush()
    return export


def _money(value: Any) -> str | None:
    return None if value is None else f"{value:.2f}"


async def export_data(session: AsyncSession, user: User) -> dict[str, Any]:
    """Everything Kuulis keeps about ``user``, readable by a person. Ratings received go without
    their author, and reports only those the user filed."""
    from apps.drivers.models import DriverDocument, DriverProfile, Vehicle
    from apps.legal.models import LegalAcceptance
    from apps.moderation.models import Report
    from apps.places.models import SavedPlace
    from apps.referrals.models import Referral
    from apps.rides.models import Rating, Ride
    from apps.safety.models import TrustedContact
    from apps.subscriptions.models import Charge
    from apps.wallet.models import TopUp, Wallet, WalletEntry

    data: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "account": {
            "email": user.email,
            "full_name": user.full_name,
            "locale": user.locale,
            "created_at": user.created_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "email_verified": user.is_verified,
            "referral_code": user.referral_code,
        },
    }
    profile = await session.scalar(select(DriverProfile).where(DriverProfile.user_id == user.id))
    if profile is not None:
        vehicle = await session.scalar(select(Vehicle).where(Vehicle.driver_id == profile.id))
        documents = await session.scalars(
            select(DriverDocument).where(DriverDocument.driver_id == profile.id)
        )
        data["driver"] = {
            "status": profile.status.value,
            "national_id": profile.national_id,
            "rif": profile.rif,
            "phone": profile.phone,
            "birth_date": profile.birth_date.isoformat(),
            "city": profile.city,
            "vehicle": {
                "type": vehicle.type.value,
                "brand": vehicle.brand,
                "model": vehicle.model,
                "color": vehicle.color,
                "plate": vehicle.plate,
            }
            if vehicle
            else None,
            "documents": [
                {"kind": d.kind.value, "status": d.status.value, "uploaded_at": d.created_at}
                for d in documents
            ],
        }
    contacts = await session.scalars(
        select(TrustedContact)
        .where(TrustedContact.user_id == user.id)
        .order_by(TrustedContact.created_at)
    )
    data["trusted_contacts"] = [
        {"name": c.name, "phone": c.phone, "auto_share": c.auto_share} for c in contacts
    ]
    places = await session.scalars(select(SavedPlace).where(SavedPlace.user_id == user.id))
    data["saved_places"] = [
        {"kind": p.kind.value, "label": p.label, "address": p.address, "lat": p.lat, "lng": p.lng}
        for p in places
    ]
    rides = await session.scalars(
        select(Ride)
        .where(or_(Ride.passenger_id == user.id, Ride.driver_id == user.id))
        .order_by(Ride.requested_at)
    )
    data["rides"] = [
        {
            "id": r.id,
            "role": "passenger" if r.passenger_id == user.id else "driver",
            "status": r.status.value,
            "requested_at": r.requested_at,
            "completed_at": r.completed_at,
            "pickup": {"address": r.pickup_address, "lat": r.pickup_lat, "lng": r.pickup_lng},
            "dropoff": {"address": r.dropoff_address, "lat": r.dropoff_lat, "lng": r.dropoff_lng},
            "distance_m": r.distance_m,
            "fare_usd": _money(r.fare),
            "discount_usd": _money(r.discount),
            "payment_method": r.payment_method.value,
        }
        for r in rides
    ]
    received = await session.scalars(
        select(Rating).where(Rating.ratee_id == user.id).order_by(Rating.created_at)
    )
    data["ratings_received"] = [
        {"stars": r.stars, "tags": r.tags, "comment": r.comment, "date": r.created_at}
        for r in received
    ]
    given = await session.scalars(
        select(Rating).where(Rating.rater_id == user.id).order_by(Rating.created_at)
    )
    data["ratings_given"] = [
        {"ride_id": r.ride_id, "stars": r.stars, "tags": r.tags, "comment": r.comment}
        for r in given
    ]
    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == user.id))
    if wallet is not None:
        entries = await session.scalars(
            select(WalletEntry)
            .where(WalletEntry.wallet_id == wallet.id)
            .order_by(WalletEntry.created_at)
        )
        data["wallet"] = {
            "balance_usd": _money(wallet.balance),
            "binance_pay_id": wallet.binance_pay_id,
            "entries": [
                {
                    "date": e.created_at,
                    "kind": e.kind.value,
                    "amount_usd": _money(e.amount),
                    "balance_after_usd": _money(e.balance_after),
                    "description": e.description,
                    "details": e.details,
                }
                for e in entries
            ],
        }
    top_ups = await session.scalars(
        select(TopUp).where(TopUp.user_id == user.id).order_by(TopUp.created_at)
    )
    data["top_ups"] = [
        {
            "date": t.created_at,
            "method": t.method.value,
            "status": t.status.value,
            "amount_usd": _money(t.amount),
            "reference": t.reference or t.transaction_id,
            "payer_name": t.payer_name,
        }
        for t in top_ups
    ]
    charges = await session.scalars(
        select(Charge).where(Charge.user_id == user.id).order_by(Charge.month)
    )
    data["subscription_charges"] = [
        {
            "month": c.month.isoformat(),
            "earnings_usd": _money(c.earnings),
            "fee_usd": _money(c.fee),
            "status": c.status.value,
        }
        for c in charges
    ]
    reports = await session.scalars(
        select(Report).where(Report.reporter_id == user.id).order_by(Report.created_at)
    )
    data["reports_filed"] = [
        {
            "date": r.created_at,
            "category": r.category.value,
            "description": r.description,
            "status": r.status.value,
            "resolution": r.resolution,
        }
        for r in reports
    ]
    acceptances = await session.scalars(
        select(LegalAcceptance)
        .where(LegalAcceptance.user_id == user.id)
        .order_by(LegalAcceptance.created_at)
    )
    data["legal_acceptances"] = [
        {"kind": a.kind, "version": a.version, "date": a.created_at, "platform": a.platform}
        for a in acceptances
    ]
    data["consents"] = await consents(session, user.id)
    data["referrals"] = (
        await session.scalar(select(func.count(Referral.id)).where(Referral.referrer_id == user.id))
        or 0
    )
    return data


def export_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode()


# --- Account erasure ---------------------------------------------------------------------------


async def scrub(session: AsyncSession, user: User, was_suspended: bool) -> list[str]:
    """Personal data outside the user row, erased with the account. Rides, payments and reports
    stay for accounting and safety, without anything that identifies the person. Returns the
    storage keys to delete after the commit."""
    from apps.auth.models import UserTotp
    from apps.legal.models import LegalAcceptance
    from apps.rides.models import Rating, Ride, RideMessage
    from apps.wallet.models import TopUp, Wallet, WalletEntry

    session.add(
        ErasedEmail(
            email_hash=email_hash(user.email),
            was_suspended=was_suspended,
            erased_at=datetime.now(UTC),
        )
    )
    await session.execute(delete(RideMessage).where(RideMessage.sender_id == user.id))
    # Where the passenger went: no address, coordinates rounded to ~1 km, no route.
    await session.execute(
        update(Ride)
        .where(Ride.passenger_id == user.id)
        .values(
            pickup_address="",
            dropoff_address="",
            pickup_lat=_rounded(Ride.pickup_lat),
            pickup_lng=_rounded(Ride.pickup_lng),
            dropoff_lat=_rounded(Ride.dropoff_lat),
            dropoff_lng=_rounded(Ride.dropoff_lng),
            polyline=None,
        )
    )
    # The driver's plate in the rides they drove.
    await session.execute(
        update(Ride)
        .where(Ride.driver_id == user.id, Ride.vehicle.is_not(None))
        .values(vehicle=Ride.vehicle.op("-")("plate"))
    )
    await session.execute(update(Rating).where(Rating.rater_id == user.id).values(comment=None))
    await session.execute(
        update(TopUp)
        .where(TopUp.user_id == user.id)
        .values(payer_name=None, payer_binance_id=None, note=None)
    )
    await session.execute(
        update(Wallet)
        .where(Wallet.user_id == user.id)
        .values(binance_pay_id=None, binance_pay_id_verified_at=None)
    )
    # Their name in the other side's transfer entries.
    await session.execute(
        update(WalletEntry)
        .where(
            WalletEntry.counterpart_user_id == user.id,
            WalletEntry.details.has_key("counterpart_name"),
        )
        .values(details=WalletEntry.details.op("||")(_jsonb({"counterpart_name": ""})))
    )
    await session.execute(
        update(LegalAcceptance).where(LegalAcceptance.user_id == user.id).values(ip=None)
    )
    await session.execute(delete(UserConsent).where(UserConsent.user_id == user.id))
    await session.execute(delete(UserTotp).where(UserTotp.user_id == user.id))
    keys = list(
        await session.scalars(
            select(DataExport.file_key).where(
                DataExport.user_id == user.id, DataExport.file_key.is_not(None)
            )
        )
    )
    await session.execute(delete(DataExport).where(DataExport.user_id == user.id))
    return keys


def _rounded(column: ColumnElement) -> ColumnElement:
    return func.round(cast(column, Numeric(10, 6)), 2)


def _jsonb(value: dict) -> ColumnElement:
    return cast(literal(json.dumps(value)), JSONB)


# --- Retention ---------------------------------------------------------------------------------


async def apply_retention(session: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    """Deletes what Kuulis no longer needs (see the module docstring); returns what it removed."""
    from apps.drivers.models import DocumentStatus, DriverDocument
    from apps.moderation.models import Report
    from apps.notifications.models import Notification
    from apps.rides.models import Ride, RideMessage

    now = now or datetime.now(UTC)
    reported = exists().where(Report.ride_id == RideMessage.ride_id)
    chats = await session.execute(
        delete(RideMessage).where(
            RideMessage.created_at < now - timedelta(days=CHAT_DAYS), ~reported
        )
    )
    routes = await session.execute(
        update(Ride)
        .where(
            Ride.polyline.is_not(None),
            Ride.requested_at < now - timedelta(days=ROUTE_DAYS),
            ~exists().where(Report.ride_id == Ride.id),
        )
        .values(polyline=None)
    )
    from apps.safety.models import RideTrack, SafetyAlert

    tracks = await session.execute(
        delete(RideTrack).where(
            RideTrack.created_at < now - timedelta(days=ROUTE_DAYS),
            ~exists().where(Report.ride_id == RideTrack.ride_id),
            ~exists().where(SafetyAlert.ride_id == RideTrack.ride_id),
        )
    )
    old_documents = (
        DriverDocument.status == DocumentStatus.REJECTED,
        func.coalesce(DriverDocument.reviewed_at, DriverDocument.updated_at)
        < now - timedelta(days=REJECTED_DOCUMENT_DAYS),
    )
    keys = list(await session.scalars(select(DriverDocument.key).where(*old_documents)))
    documents = len(keys)
    await session.execute(delete(DriverDocument).where(*old_documents))
    notifications = await session.execute(
        delete(Notification).where(
            Notification.created_at < now - timedelta(days=NOTIFICATION_DAYS)
        )
    )
    expired = list(
        await session.scalars(
            select(DataExport).where(DataExport.status == "ready", DataExport.expires_at <= now)
        )
    )
    for export in expired:
        if export.file_key:
            keys.append(export.file_key)
        export.status = "expired"
        export.file_key = None
    await session.commit()
    storage.delete_objects(keys)
    return {
        "chat_messages": chats.rowcount or 0,
        "routes": routes.rowcount or 0,
        "tracks": tracks.rowcount or 0,
        "rejected_documents": documents,
        "notifications": notifications.rowcount or 0,
        "exports": len(expired),
    }


# --- Admin panel -------------------------------------------------------------------------------


async def deletion_requests(
    session: AsyncSession, params: PageParams, status: str | None
) -> tuple[list[User], int]:
    stmt = select(User).where(User.deletion_requested_at.is_not(None))
    if status == "scheduled":
        stmt = stmt.where(User.deleted_at.is_(None))
    elif status == "erased":
        stmt = stmt.where(User.deleted_at.is_not(None))
    return await paginate(session, stmt.order_by(User.deletion_requested_at.desc()), params)


async def exports(session: AsyncSession, params: PageParams) -> tuple[list[tuple], int]:
    stmt = (
        select(DataExport, User.email)
        .join(User, User.id == DataExport.user_id)
        .order_by(DataExport.created_at.desc())
    )
    total = await session.scalar(select(func.count(DataExport.id))) or 0
    rows = await session.execute(stmt.limit(params.limit).offset(params.offset))
    return list(rows.all()), int(total)
