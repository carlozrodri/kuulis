"""Ongoing driver verification (doc 12): expiring documents, the random live selfie, re-checks
after reports, moto changes, document renewals and duplicate detection.

An approved driver keeps working while a check waits for a verifier. What keeps them offline:
an expired document (until its renewal is approved) and a selfie or re-verification they were
asked for and have not sent yet.
"""

import asyncio
import hashlib
import hmac
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.config.schemas import AppConfig
from apps.drivers import services
from apps.drivers.models import (
    BLOCKING_CHECKS,
    OPEN_CHECK_STATUSES,
    PHOTO_KINDS,
    CheckKind,
    CheckStatus,
    DocumentKind,
    DocumentStatus,
    DriverCheck,
    DriverDocument,
    DriverProfile,
    DriverStatus,
    IdentityMark,
    MarkKind,
    Vehicle,
    VehicleStatus,
)
from apps.drivers.schemas import (
    DOCUMENT_CONTENT_TYPES,
    CheckFile,
    CheckPresignRequest,
    DocumentAlert,
    Duplicate,
    VehicleChange,
    VerificationState,
)
from apps.files import metadata
from apps.files.schemas import UploadResponse
from apps.users.models import User
from kuulis.core import storage
from kuulis.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from kuulis.settings import settings

logger = logging.getLogger(__name__)

IMAGE_TYPES = frozenset(t for t in DOCUMENT_CONTENT_TYPES if t.startswith("image/"))
# What a check may carry, per kind of check.
CHECK_FILE_KINDS: dict[CheckKind, frozenset[DocumentKind]] = {
    CheckKind.SELFIE: frozenset({DocumentKind.SELFIE}),
    CheckKind.REVERIFICATION: frozenset({DocumentKind.SELFIE, DocumentKind.VEHICLE_PHOTO}),
    CheckKind.VEHICLE_CHANGE: frozenset(
        {DocumentKind.VEHICLE_REGISTRATION, DocumentKind.VEHICLE_PHOTO}
    ),
}


class DocumentExpiredError(PermissionDeniedError):
    code = "document_expired"
    message = "A document expired; upload the new one to go online"
    planned = True


class SelfieRequiredError(PermissionDeniedError):
    code = "selfie_required"
    message = "Send a live selfie to go online"
    planned = True


def _now() -> datetime:
    return services._now()


# --- Duplicates ----------------------------------------------------------------------------------


def _mark_key() -> bytes:
    return hashlib.sha256(b"kuulis:identity-marks:" + settings.SECRET_KEY.encode()).digest()


def mark_hash(kind: MarkKind | str, value: str) -> str:
    """Keyed hash: a cédula has few digits, so a plain hash could be reversed by brute force.
    ``kind`` may also be "email" (banned identifiers, doc 16)."""
    normalized = "".join(value.split()).upper()
    return hmac.new(_mark_key(), f"{kind}:{normalized}".encode(), hashlib.sha256).hexdigest()


async def record_marks(
    session: AsyncSession, user_id: uuid.UUID, values: dict[MarkKind, str | None]
) -> None:
    rows = [
        {"id": uuid.uuid4(), "user_id": user_id, "kind": kind, "value_hash": mark_hash(kind, v)}
        for kind, v in values.items()
        if v and v.strip()
    ]
    if rows:
        await session.execute(
            insert(IdentityMark)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_identity_marks_user_value")
        )


async def record_profile_marks(session: AsyncSession, profile: DriverProfile) -> None:
    await record_marks(
        session,
        profile.user_id,
        {
            MarkKind.NATIONAL_ID: profile.national_id,
            MarkKind.RIF: profile.rif,
            MarkKind.PHONE: profile.phone,
        },
    )


async def duplicates(session: AsyncSession, user_id: uuid.UUID) -> list[Duplicate]:
    """Other accounts (erased or suspended ones included) that share a cédula, RIF, plate,
    phone, Binance Pay ID or device with this one."""
    mine = aliased(IdentityMark)
    other = aliased(IdentityMark)
    rows = (
        await session.execute(
            select(other.kind, User, DriverProfile.id, DriverProfile.status)
            .select_from(mine)
            .join(
                other,
                and_(
                    other.kind == mine.kind,
                    other.value_hash == mine.value_hash,
                    other.user_id != mine.user_id,
                ),
            )
            .join(User, User.id == other.user_id)
            .outerjoin(DriverProfile, DriverProfile.user_id == User.id)
            .where(mine.user_id == user_id)
            .order_by(other.kind, User.created_at)
            .limit(50)
        )
    ).all()
    return [
        Duplicate(
            kind=kind,
            user_id=user.id,
            name=user.full_name,
            email=None if user.deleted_at else user.email,
            driver_id=driver_id,
            driver_status=driver_status,
            deleted=user.deleted_at is not None,
            suspended=driver_status == DriverStatus.SUSPENDED,
        )
        for kind, user, driver_id, driver_status in rows
    ]


# --- State shown to the driver -------------------------------------------------------------------


def current_documents(profile: DriverProfile) -> list[DriverDocument]:
    return [d for d in profile.documents if d.superseded_by_id is None]


def in_force(profile: DriverProfile, kind: DocumentKind) -> DriverDocument | None:
    """The approved file of ``kind`` in use (a pending renewal does not replace it yet)."""
    approved = [
        d
        for d in current_documents(profile)
        if d.kind == kind and d.status == DocumentStatus.APPROVED
    ]
    return max(approved, key=lambda d: d.created_at, default=None)


def _pending_renewal(profile: DriverProfile, kind: DocumentKind) -> DriverDocument | None:
    in_use = in_force(profile, kind)
    return next(
        (
            d
            for d in current_documents(profile)
            if d.kind == kind and d.status == DocumentStatus.PENDING and d is not in_use
        ),
        None,
    )


def verification_state(
    profile: DriverProfile, checks: list[DriverCheck], config: AppConfig, today: date
) -> VerificationState:
    expired: list[DocumentKind] = []
    alerts: list[DocumentAlert] = []
    missing: list[DocumentKind] = []
    if profile.status in (DriverStatus.APPROVED, DriverStatus.SUSPENDED):
        horizon = max(config.verification.expiry_notice_days, default=30)
        for kind in config.verification.expiring_documents:
            document = in_force(profile, kind)
            if document is None:
                continue
            if document.expires_on is None:
                missing.append(kind)
                continue
            days = (document.expires_on - today).days
            if days < 0:
                expired.append(kind)
            if days <= horizon:
                alerts.append(
                    DocumentAlert(
                        kind=kind,
                        expires_on=document.expires_on,
                        days_left=days,
                        renewal_pending=_pending_renewal(profile, kind) is not None,
                    )
                )
    requested = next(
        (c for c in checks if c.status == CheckStatus.REQUESTED and c.kind in BLOCKING_CHECKS),
        None,
    )
    return VerificationState(
        expired=expired,
        expiring=alerts,
        missing_expiry=missing,
        required_check_id=requested.id if requested else None,
        required_check_kind=requested.kind if requested else None,
        can_go_online=not expired and requested is None,
    )


async def open_checks(session: AsyncSession, profile_id: uuid.UUID) -> list[DriverCheck]:
    return list(
        await session.scalars(
            select(DriverCheck)
            .where(DriverCheck.driver_id == profile_id, DriverCheck.status.in_(OPEN_CHECK_STATUSES))
            .order_by(DriverCheck.requested_at)
        )
    )


async def driver_checks(
    session: AsyncSession, profile_id: uuid.UUID, limit: int = 100
) -> list[DriverCheck]:
    return list(
        await session.scalars(
            select(DriverCheck)
            .where(DriverCheck.driver_id == profile_id)
            .order_by(DriverCheck.requested_at.desc())
            .limit(limit)
        )
    )


# --- Going online --------------------------------------------------------------------------------


def next_selfie_at(config: AppConfig, now: datetime) -> datetime | None:
    """A random moment around ``selfie_every_days`` from now, so nobody can predict it."""
    every = config.verification.selfie_every_days
    if every <= 0:
        return None
    return now + timedelta(days=every * random.uniform(0.5, 1.5))  # noqa: S311


async def request_check(
    session: AsyncSession, profile: DriverProfile, kind: CheckKind, reason: str
) -> DriverCheck:
    """Asks the driver for photos; an open request of the same kind is reused."""
    existing = await session.scalar(
        select(DriverCheck).where(
            DriverCheck.driver_id == profile.id,
            DriverCheck.kind == kind,
            DriverCheck.status == CheckStatus.REQUESTED,
        )
    )
    if existing is not None:
        return existing
    check = DriverCheck(
        driver_id=profile.id,
        kind=kind,
        status=CheckStatus.REQUESTED,
        reason=reason,
        requested_at=_now(),
        files=[],
    )
    session.add(check)
    await session.flush()
    return check


async def ensure_can_go_online(
    session: AsyncSession, profile: DriverProfile, config: AppConfig, device_id: str | None
) -> None:
    """Raises 403 ``document_expired`` or ``selfie_required``. Asking for the random selfie is
    committed before raising, so the request survives the error."""
    if device_id:
        await record_marks(session, profile.user_id, {MarkKind.DEVICE: device_id})
    checks = await open_checks(session, profile.id)
    state = verification_state(profile, checks, config, services.today_caracas())
    if state.expired:
        await session.commit()
        raise DocumentExpiredError(details={"kinds": [k.value for k in state.expired]})
    if state.required_check_id is not None:
        await session.commit()
        raise SelfieRequiredError(
            details={
                "check_id": str(state.required_check_id),
                "kind": state.required_check_kind.value if state.required_check_kind else None,
            }
        )
    now = _now()
    if profile.selfie_due_at is None:
        # Drivers approved before doc 12 start their cycle now.
        profile.selfie_due_at = next_selfie_at(config, now)
    elif (
        config.verification.selfie_every_days > 0
        and profile.selfie_due_at <= now
        and not any(c.kind in BLOCKING_CHECKS for c in checks)
    ):
        check = await request_check(session, profile, CheckKind.SELFIE, "random")
        await session.commit()
        raise SelfieRequiredError(details={"check_id": str(check.id), "kind": check.kind.value})


# --- Files ---------------------------------------------------------------------------------------


def check_folder(user_id: uuid.UUID, kind: DocumentKind) -> str:
    return f"drivers/{user_id}/checks/{kind.value}"


def presign_check_file(
    user: User, profile: DriverProfile, data: CheckPresignRequest
) -> UploadResponse:
    if profile.status != DriverStatus.APPROVED:
        raise ConflictError("Only approved drivers send checks", code="driver_not_approved")
    allowed = IMAGE_TYPES if data.kind in PHOTO_KINDS else DOCUMENT_CONTENT_TYPES
    if data.content_type not in allowed:
        raise AppError("File type not allowed", code="file_type_not_allowed")
    if data.size > settings.STORAGE_MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError("File too large", code="file_too_large")
    key = storage.build_key(check_folder(user.id, data.kind), data.filename)
    return UploadResponse(
        key=key,
        upload_url=storage.presigned_upload(key, data.content_type),
        headers={"Content-Type": data.content_type},
        expires_in=settings.STORAGE_PRESIGN_TTL_SECONDS,
    )


async def _verified_file(user_id: uuid.UUID, file: CheckFile) -> dict:
    if not storage.key_in_folder(file.key, check_folder(user_id, file.kind)):
        raise AppError("The file does not belong to this upload", code="document_key_invalid")
    try:
        head = await asyncio.to_thread(storage.head_object, file.key)
    except storage.StorageCheckUnavailable:
        head = {"ContentType": services._type_from_extension(file.key), "ContentLength": 0}
    if head is None:
        raise AppError("The file was not uploaded", code="document_not_uploaded")
    content_type = str(head.get("ContentType", "")).split(";")[0].strip().lower()
    allowed = IMAGE_TYPES if file.kind in PHOTO_KINDS else DOCUMENT_CONTENT_TYPES
    if content_type not in allowed:
        raise AppError("File type not allowed", code="file_type_not_allowed")
    if int(head.get("ContentLength", 0)) > settings.STORAGE_MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError("File too large", code="file_too_large")
    if content_type in metadata.FORMATS:
        await metadata.schedule(file.key)
    return {"kind": file.kind.value, "key": file.key, "content_type": content_type}


async def _verified_files(
    user_id: uuid.UUID, kind: CheckKind, files: list[CheckFile], config: AppConfig
) -> list[dict]:
    allowed = CHECK_FILE_KINDS[kind]
    if any(f.kind not in allowed for f in files) or len({f.key for f in files}) != len(files):
        raise AppError("Unexpected files for this check", code="check_files_invalid")
    count = {k: sum(1 for f in files if f.kind == k) for k in allowed}
    photos_needed = max(config.vehicle_photo_min_count, 1)
    needed = {
        CheckKind.SELFIE: {DocumentKind.SELFIE: 1},
        CheckKind.REVERIFICATION: {
            DocumentKind.SELFIE: 1,
            DocumentKind.VEHICLE_PHOTO: photos_needed,
        },
        CheckKind.VEHICLE_CHANGE: {
            DocumentKind.VEHICLE_REGISTRATION: 1,
            DocumentKind.VEHICLE_PHOTO: photos_needed,
        },
    }[kind]
    single = {DocumentKind.SELFIE, DocumentKind.VEHICLE_REGISTRATION}
    if (
        any(count[k] < n for k, n in needed.items())
        or any(count.get(k, 0) > 1 for k in single)
        or count.get(DocumentKind.VEHICLE_PHOTO, 0) > services.MAX_VEHICLE_PHOTOS
    ):
        raise AppError(
            "Some photos are missing",
            code="check_files_missing",
            details={"needed": {k.value: n for k, n in needed.items()}},
        )
    return [await _verified_file(user_id, f) for f in files]


# --- Driver side ---------------------------------------------------------------------------------


async def submit_check(
    session: AsyncSession,
    user: User,
    profile: DriverProfile,
    check_id: uuid.UUID,
    files: list[CheckFile],
    config: AppConfig,
) -> DriverCheck:
    check = await session.scalar(
        select(DriverCheck)
        .where(DriverCheck.id == check_id, DriverCheck.driver_id == profile.id)
        .with_for_update()
    )
    if check is None:
        raise NotFoundError("Check not found", code="check_not_found")
    if check.status != CheckStatus.REQUESTED or check.kind not in BLOCKING_CHECKS:
        raise ConflictError(
            "This check does not wait for photos",
            code="check_not_requested",
            details={"status": check.status.value},
        )
    check.files = await _verified_files(user.id, check.kind, files, config)
    check.status = CheckStatus.PENDING
    check.submitted_at = _now()
    profile.selfie_due_at = next_selfie_at(config, check.submitted_at)
    await session.flush()
    return check


async def request_vehicle_change(
    session: AsyncSession,
    user: User,
    profile: DriverProfile,
    data: VehicleChange,
    config: AppConfig,
) -> DriverProfile:
    if profile.status != DriverStatus.APPROVED:
        raise ConflictError("Only approved drivers change their moto", code="driver_not_approved")
    if profile.pending_vehicle is not None:
        raise ConflictError("A moto change is already under review", code="vehicle_change_pending")
    services.validate_vehicle(data.vehicle, config)
    plate = services.normalize_plate(data.vehicle.plate)
    if profile.vehicle is not None and profile.vehicle.plate == plate:
        raise ConflictError("This is the moto you already use", code="vehicle_same_plate")
    await services.ensure_plate_free(session, plate, profile.id)
    files = [
        CheckFile(kind=DocumentKind.VEHICLE_REGISTRATION, key=data.registration_key),
        *(CheckFile(kind=DocumentKind.VEHICLE_PHOTO, key=k) for k in data.photo_keys),
    ]
    verified = await _verified_files(user.id, CheckKind.VEHICLE_CHANGE, files, config)
    verified[0]["expires_on"] = data.registration_expires_on.isoformat()
    vehicle = Vehicle(
        driver_id=profile.id,
        status=VehicleStatus.PENDING,
        **(data.vehicle.model_dump() | {"plate": plate}),
    )
    session.add(vehicle)
    await services.flush_unique(session, "Plate already registered", "plate_taken")
    now = _now()
    session.add(
        DriverCheck(
            driver_id=profile.id,
            kind=CheckKind.VEHICLE_CHANGE,
            status=CheckStatus.PENDING,
            reason="driver",
            files=verified,
            vehicle_id=vehicle.id,
            requested_at=now,
            submitted_at=now,
        )
    )
    await record_marks(session, user.id, {MarkKind.PLATE: plate})
    return await services.reload(session, profile)


async def cancel_vehicle_change(session: AsyncSession, profile: DriverProfile) -> DriverProfile:
    vehicle = profile.pending_vehicle
    if vehicle is None:
        raise NotFoundError("No moto change under review", code="vehicle_change_not_found")
    check = await session.scalar(
        select(DriverCheck).where(
            DriverCheck.vehicle_id == vehicle.id, DriverCheck.status.in_(OPEN_CHECK_STATUSES)
        )
    )
    if check is not None:
        check.status = CheckStatus.CANCELLED
        check.vehicle_id = None
        check.reviewed_at = _now()
    await session.delete(vehicle)
    return await services.reload(session, profile)


async def register_renewal(
    session: AsyncSession, profile: DriverProfile, document: DriverDocument
) -> None:
    """A new file for an approved driver's document: it waits for a verifier while the old one
    stays in use. A second upload before the review replaces the first."""
    for old in current_documents(profile):
        if (
            old.kind == document.kind
            and old.status == DocumentStatus.PENDING
            and old is not document
        ):
            check = await session.scalar(
                select(DriverCheck).where(
                    DriverCheck.document_id == old.id, DriverCheck.status.in_(OPEN_CHECK_STATUSES)
                )
            )
            if check is not None:
                check.status = CheckStatus.CANCELLED
                check.reviewed_at = _now()
            await session.delete(old)
    now = _now()
    session.add(
        DriverCheck(
            driver_id=profile.id,
            kind=CheckKind.DOCUMENT_RENEWAL,
            status=CheckStatus.PENDING,
            reason="driver",
            files=[
                {
                    "kind": document.kind.value,
                    "key": document.key,
                    "content_type": document.content_type,
                }
            ],
            document_id=document.id,
            requested_at=now,
            submitted_at=now,
        )
    )


async def set_expiry(
    session: AsyncSession, profile: DriverProfile, document_id: uuid.UUID, expires_on: date
) -> DriverProfile:
    """The driver types the expiry of a document approved before doc 12 (a verifier confirms it
    later). A confirmed date changes only with a renewal."""
    document = next((d for d in current_documents(profile) if d.id == document_id), None)
    if document is None:
        raise NotFoundError("Document not found", code="document_not_found")
    if document.expiry_confirmed:
        raise ConflictError("The expiry date was already confirmed", code="expiry_confirmed")
    document.expires_on = expires_on
    document.expiry_notice_days = None
    return await services.reload(session, profile)


# --- Admin side ----------------------------------------------------------------------------------


async def get_check_or_404(session: AsyncSession, check_id: uuid.UUID) -> DriverCheck:
    check = await session.get(DriverCheck, check_id, populate_existing=True)
    if check is None:
        raise NotFoundError("Check not found", code="check_not_found")
    return check


async def list_checks(
    session: AsyncSession,
    *,
    status: CheckStatus | None,
    kind: CheckKind | None,
    assigned_to: uuid.UUID | None,
    unassigned: bool,
    limit: int,
    offset: int,
) -> tuple[list[DriverCheck], int]:
    stmt = select(DriverCheck)
    if status is not None:
        stmt = stmt.where(DriverCheck.status == status)
    if kind is not None:
        stmt = stmt.where(DriverCheck.kind == kind)
    if assigned_to is not None:
        stmt = stmt.where(DriverCheck.assigned_to_id == assigned_to)
    if unassigned:
        stmt = stmt.where(DriverCheck.assigned_to_id.is_(None))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    # Oldest first: the queue is worked in order.
    items = await session.scalars(
        stmt.order_by(func.coalesce(DriverCheck.submitted_at, DriverCheck.requested_at))
        .limit(limit)
        .offset(offset)
    )
    return list(items), total


async def _suspend_for(
    session: AsyncSession, profile: DriverProfile, admin: User, check: DriverCheck, reason: str
) -> None:
    """A rejected selfie or moto check: the profile is suspended and a report opened."""
    from apps.moderation.models import Report, ReportCategory, ReportPriority, ReportStatus
    from apps.rides import presence

    if profile.status == DriverStatus.APPROVED:
        services.transition(profile, DriverStatus.SUSPENDED)
        profile.suspended_at = _now()
        profile.rejection_reason = reason
        profile.reviewed_at = _now()
        profile.reviewed_by_id = admin.id
    label = {
        CheckKind.SELFIE: "Selfie de verificación rechazada",
        CheckKind.REVERIFICATION: "Reverificación rechazada",
    }[check.kind]
    session.add(
        Report(
            reporter_id=admin.id,
            reported_user_id=profile.user_id,
            category=(
                ReportCategory.VEHICLE_MISMATCH
                if check.kind == CheckKind.REVERIFICATION
                else ReportCategory.SAFETY
            ),
            description=f"{label}: {reason}",
            status=ReportStatus.OPEN,
            priority=ReportPriority.URGENT,
        )
    )
    await presence.go_offline(profile.user_id)


def _supersede(profile: DriverProfile, kind: DocumentKind, new: DriverDocument) -> None:
    for old in current_documents(profile):
        if old.kind == kind and old.id != new.id and old.status != DocumentStatus.PENDING:
            old.superseded_by_id = new.id


async def review_check(
    session: AsyncSession,
    check: DriverCheck,
    admin: User,
    approved: bool,
    reason: str | None,
    expires_on: date | None,
) -> tuple[DriverProfile, str | None]:
    """Returns the profile and the driver notification event to send after the commit."""
    if check.status != CheckStatus.PENDING:
        raise ConflictError(
            "This check is not waiting for a review",
            code="check_not_pending",
            details={"status": check.status.value},
        )
    profile = await services.get_or_404(session, check.driver_id)
    now = _now()
    check.status = CheckStatus.APPROVED if approved else CheckStatus.REJECTED
    check.result_reason = None if approved else reason
    check.reviewed_by_id = admin.id
    check.reviewed_at = now
    event: str | None = None

    if check.kind in BLOCKING_CHECKS:
        if approved:
            if check.kind == CheckKind.REVERIFICATION:
                for file in check.files:
                    if file["kind"] == DocumentKind.VEHICLE_PHOTO.value:
                        _add_document(session, profile, file, admin, now, None)
                await session.flush()
                profile = await services.reload(session, profile)
                new_photos = [
                    d
                    for d in current_documents(profile)
                    if d.kind == DocumentKind.VEHICLE_PHOTO
                    and d.key in {f["key"] for f in check.files}
                ]
                for old in current_documents(profile):
                    if old.kind == DocumentKind.VEHICLE_PHOTO and old not in new_photos:
                        old.superseded_by_id = new_photos[0].id
        else:
            await _suspend_for(session, profile, admin, check, reason or "")
            event = "suspended"

    elif check.kind == CheckKind.DOCUMENT_RENEWAL:
        document = next((d for d in profile.documents if d.id == check.document_id), None)
        if document is None:
            raise ConflictError("The document is gone", code="document_not_found")
        expiring = document.kind in (await _config(session)).verification.expiring_documents
        if approved and expiring and not (expires_on or document.expires_on):
            raise AppError("Type the expiry date", code="expiry_required")
        document.reviewed_by_id = admin.id
        document.reviewed_at = now
        if approved:
            document.status = DocumentStatus.APPROVED
            document.rejection_reason = None
            if expires_on:
                document.expires_on = expires_on
            document.expiry_confirmed = document.expires_on is not None
            _supersede(profile, document.kind, document)
            event = "document_renewed"
        else:
            document.status = DocumentStatus.REJECTED
            document.rejection_reason = reason
            event = "document_rejected"

    elif check.kind == CheckKind.VEHICLE_CHANGE:
        vehicle = await session.get(Vehicle, check.vehicle_id) if check.vehicle_id else None
        if vehicle is None or vehicle.status != VehicleStatus.PENDING:
            raise ConflictError("The moto change is gone", code="vehicle_change_not_found")
        if approved:
            registration = next(
                f for f in check.files if f["kind"] == DocumentKind.VEHICLE_REGISTRATION.value
            )
            day = expires_on or (
                date.fromisoformat(registration["expires_on"])
                if registration.get("expires_on")
                else None
            )
            if day is None:
                raise AppError("Type the expiry date", code="expiry_required")
            if profile.vehicle is not None:
                profile.vehicle.status = VehicleStatus.RETIRED
                await session.flush()  # free the "one active moto" slot first
            vehicle.status = VehicleStatus.ACTIVE
            for file in check.files:
                _add_document(session, profile, file, admin, now, day)
            await session.flush()
            profile = await services.reload(session, profile)
            keys = {f["key"] for f in check.files}
            for kind in (DocumentKind.VEHICLE_REGISTRATION, DocumentKind.VEHICLE_PHOTO):
                newest = next(
                    d for d in current_documents(profile) if d.kind == kind and d.key in keys
                )
                for old in current_documents(profile):
                    if old.kind == kind and old.key not in keys:
                        old.superseded_by_id = newest.id
            event = "vehicle_approved"
        else:
            vehicle.status = VehicleStatus.RETIRED
            event = "vehicle_rejected"
    return await services.reload(session, profile), event


def _add_document(
    session: AsyncSession,
    profile: DriverProfile,
    file: dict,
    admin: User,
    now: datetime,
    expires_on: date | None,
) -> None:
    kind = DocumentKind(file["kind"])
    session.add(
        DriverDocument(
            driver_id=profile.id,
            kind=kind,
            key=file["key"],
            content_type=file["content_type"],
            status=DocumentStatus.APPROVED,
            reviewed_by_id=admin.id,
            reviewed_at=now,
            expires_on=expires_on if kind == DocumentKind.VEHICLE_REGISTRATION else None,
            expiry_confirmed=kind == DocumentKind.VEHICLE_REGISTRATION and expires_on is not None,
        )
    )


async def _config(session: AsyncSession) -> AppConfig:
    from apps.config.services import get_app_config

    return await get_app_config(session)


async def on_mismatch_report(session: AsyncSession, driver_user_id: uuid.UUID) -> bool:
    """After a passenger reports another moto: enough reports in the window ask for a selfie and
    new moto photos. Returns True when a re-verification was asked."""
    from apps.moderation.models import Report, ReportCategory

    config = await _config(session)
    rules = config.verification
    since = _now() - timedelta(days=rules.report_window_days)
    count = await session.scalar(
        select(func.count(Report.id)).where(
            Report.reported_user_id == driver_user_id,
            Report.category == ReportCategory.VEHICLE_MISMATCH,
            Report.created_at >= since,
        )
    )
    if (count or 0) < rules.mismatch_reports:
        return False
    profile = await services.get_by_user(session, driver_user_id)
    if profile is None or profile.status != DriverStatus.APPROVED:
        return False
    recent = await session.scalar(
        select(DriverCheck.id).where(
            DriverCheck.driver_id == profile.id,
            DriverCheck.kind == CheckKind.REVERIFICATION,
            or_(
                DriverCheck.status.in_(OPEN_CHECK_STATUSES),
                DriverCheck.requested_at >= since,
            ),
        )
    )
    if recent is not None:
        return False
    await request_check(session, profile, CheckKind.REVERIFICATION, "reports")
    return True


# --- Daily expiry run ----------------------------------------------------------------------------


@dataclass
class ExpiryNotice:
    profile: DriverProfile
    document: DriverDocument
    days_left: int


async def expiry_notices(
    session: AsyncSession, config: AppConfig, today: date
) -> list[ExpiryNotice]:
    """Documents that reached a new notice step (30, 7, 1 days, expired). Marks them as sent;
    the caller notifies after the commit."""
    rules = config.verification
    if not rules.expiring_documents:
        return []
    horizon = max(rules.expiry_notice_days, default=30)
    rows = (
        await session.execute(
            select(DriverDocument.driver_id)
            .join(DriverProfile, DriverProfile.id == DriverDocument.driver_id)
            .where(
                DriverProfile.status == DriverStatus.APPROVED,
                DriverDocument.kind.in_(rules.expiring_documents),
                DriverDocument.status == DocumentStatus.APPROVED,
                DriverDocument.superseded_by_id.is_(None),
                DriverDocument.expires_on.is_not(None),
                DriverDocument.expires_on <= today + timedelta(days=horizon),
            )
            .distinct()
        )
    ).scalars()
    notices: list[ExpiryNotice] = []
    for driver_id in list(rows):
        profile = await services.get_or_404(session, driver_id)
        for kind in rules.expiring_documents:
            document = in_force(profile, kind)
            if document is None or document.expires_on is None:
                continue
            if _pending_renewal(profile, kind) is not None:
                continue  # already sent the new one
            days = (document.expires_on - today).days
            step = (
                0
                if days < 0
                else min((d for d in rules.expiry_notice_days if days <= d), default=None)
            )
            if step is None:
                continue
            if document.expiry_notice_days is not None and document.expiry_notice_days <= step:
                continue
            document.expiry_notice_days = step
            notices.append(ExpiryNotice(profile, document, days))
        # The next get_or_404 reloads from the database (populate_existing): keep these marks.
        await session.flush()
    return notices
