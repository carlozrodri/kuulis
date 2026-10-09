"""Driver onboarding: profile, vehicle, documents, review workflow and notifications."""

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.config.schemas import AppConfig
from apps.drivers.models import (
    DRIVER_TRANSITIONS,
    EDITABLE_STATUSES,
    MULTI_FILE_KINDS,
    DocumentKind,
    DocumentStatus,
    DriverDocument,
    DriverProfile,
    DriverStatus,
    Vehicle,
)
from apps.drivers.schemas import (
    DOCUMENT_CONTENT_TYPES,
    DocumentAdminRead,
    DocumentPresignRequest,
    DocumentRead,
    DocumentRegister,
    DocumentReview,
    DriverAdminRead,
    DriverProfileRead,
    DriverProfileWrite,
    Requirements,
    VehicleRead,
    VehicleWrite,
    compact_upper,
)
from apps.files.schemas import UploadResponse
from apps.notifications import services as notifications
from apps.notifications import tasks as notification_tasks
from apps.users.models import User
from apps.users.schemas import UserRead
from kuulis.core import storage
from kuulis.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from kuulis.core.pagination import PageParams, paginate
from kuulis.settings import settings

CARACAS_TZ = ZoneInfo("America/Caracas")
MAX_VEHICLE_PHOTOS = 10


# --- Helpers -----------------------------------------------------------------------------------


def today_caracas() -> date:
    return datetime.now(CARACAS_TZ).date()


def age_on(birth_date: date, today: date) -> int:
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def normalize_plate(plate: str) -> str:
    return compact_upper(plate)


def document_folder(user_id: uuid.UUID, kind: DocumentKind) -> str:
    """Per-user, per-kind storage folder. Registration only accepts keys under it."""
    return f"drivers/{user_id}/{kind.value}"


def _now() -> datetime:
    return datetime.now(UTC)


def _full_query() -> Select[tuple[DriverProfile]]:
    return select(DriverProfile).options(
        selectinload(DriverProfile.vehicle),
        selectinload(DriverProfile.documents),
        selectinload(DriverProfile.user),
    )


async def get_by_user(session: AsyncSession, user_id: uuid.UUID) -> DriverProfile | None:
    return await session.scalar(
        _full_query()
        .where(DriverProfile.user_id == user_id)
        .execution_options(populate_existing=True)
    )


async def get_for_user_or_404(session: AsyncSession, user_id: uuid.UUID) -> DriverProfile:
    profile = await get_by_user(session, user_id)
    if profile is None:
        raise NotFoundError("Driver profile not found", code="driver_not_found")
    return profile


async def get_or_404(session: AsyncSession, profile_id: uuid.UUID) -> DriverProfile:
    profile = await session.scalar(
        _full_query()
        .where(DriverProfile.id == profile_id)
        .execution_options(populate_existing=True)
    )
    if profile is None:
        raise NotFoundError("Driver profile not found", code="driver_not_found")
    return profile


async def reload(session: AsyncSession, profile: DriverProfile) -> DriverProfile:
    await session.flush()
    return await get_or_404(session, profile.id)


def _ensure_editable(profile: DriverProfile) -> None:
    if profile.status not in EDITABLE_STATUSES:
        raise ConflictError(
            "The driver profile cannot be edited in its current status",
            code="driver_not_editable",
            details={"status": profile.status.value},
        )


def transition(profile: DriverProfile, target: DriverStatus) -> None:
    if target not in DRIVER_TRANSITIONS.get(profile.status, frozenset()):
        raise ConflictError(
            f"Cannot change driver status from {profile.status} to {target}",
            code="driver_invalid_transition",
            details={"from": profile.status.value, "to": target.value},
        )
    profile.status = target


async def _flush_unique(session: AsyncSession, message: str, code: str) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(message, code=code) from exc


# --- Requirements and serialization ------------------------------------------------------------


def requirements(profile: DriverProfile, config: AppConfig) -> Requirements:
    current = [d for d in profile.documents if d.status != DocumentStatus.REJECTED]
    kinds = {d.kind for d in current}
    required = config.driver_required_documents
    missing = [k for k in required if k not in MULTI_FILE_KINDS and k not in kinds]
    photos = sum(1 for d in current if d.kind == DocumentKind.VEHICLE_PHOTO)
    photos_required = (
        max(config.vehicle_photo_min_count, 1) if DocumentKind.VEHICLE_PHOTO in required else 0
    )
    age_ok = age_on(profile.birth_date, today_caracas()) >= config.driver_min_age
    vehicle = profile.vehicle
    vehicle_ok = (
        vehicle is not None
        and vehicle.type in config.enabled_vehicle_types
        and vehicle.year >= config.min_year(vehicle.type)
    )
    can_submit = (
        profile.status in EDITABLE_STATUSES
        and not missing
        and photos >= photos_required
        and age_ok
        and vehicle_ok
    )
    return Requirements(
        missing_documents=missing,
        vehicle_photos=photos,
        vehicle_photos_required=photos_required,
        age_ok=age_ok,
        vehicle_ok=vehicle_ok,
        can_submit=can_submit,
    )


def _base_fields(profile: DriverProfile, config: AppConfig) -> dict:
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "status": profile.status,
        "birth_date": profile.birth_date,
        "national_id": profile.national_id,
        "rif": profile.rif,
        "phone": profile.phone,
        "city": profile.city,
        "rejection_reason": profile.rejection_reason,
        "submitted_at": profile.submitted_at,
        "reviewed_at": profile.reviewed_at,
        "approved_at": profile.approved_at,
        "suspended_at": profile.suspended_at,
        "first_trip_completed_at": profile.first_trip_completed_at,
        "created_at": profile.created_at,
        "vehicle": VehicleRead.model_validate(profile.vehicle) if profile.vehicle else None,
        "requirements": requirements(profile, config),
    }


def to_read(profile: DriverProfile, config: AppConfig) -> DriverProfileRead:
    return DriverProfileRead(
        **_base_fields(profile, config),
        documents=[DocumentRead.model_validate(d) for d in profile.documents],
    )


def _download_url(key: str) -> str | None:
    try:
        return storage.presigned_download(key)
    except ServiceUnavailableError:
        return None  # Storage not configured (local development).


def to_admin_read(
    profile: DriverProfile, config: AppConfig, *, with_urls: bool = True
) -> DriverAdminRead:
    documents = [
        DocumentAdminRead.model_validate(d).model_copy(
            update={"download_url": _download_url(d.key) if with_urls else None}
        )
        for d in profile.documents
    ]
    return DriverAdminRead(
        **_base_fields(profile, config),
        user=UserRead.model_validate(profile.user),
        documents=documents,
    )


# --- Driver side ---------------------------------------------------------------------------------


async def upsert_profile(
    session: AsyncSession, user: User, data: DriverProfileWrite
) -> DriverProfile:
    profile = await get_by_user(session, user.id)
    taken = await session.scalar(
        select(DriverProfile.id).where(
            DriverProfile.national_id == data.national_id, DriverProfile.user_id != user.id
        )
    )
    if taken:
        raise ConflictError("National id already registered", code="national_id_taken")
    if profile is None:
        profile = DriverProfile(user_id=user.id, status=DriverStatus.DRAFT, **data.model_dump())
        session.add(profile)
    else:
        _ensure_editable(profile)
        for field, value in data.model_dump().items():
            setattr(profile, field, value)
    await _flush_unique(session, "National id already registered", "national_id_taken")
    return await reload(session, profile)


async def set_vehicle(
    session: AsyncSession, profile: DriverProfile, data: VehicleWrite, config: AppConfig
) -> DriverProfile:
    _ensure_editable(profile)
    if data.type not in config.enabled_vehicle_types:
        raise AppError(
            "This vehicle type is not accepted",
            code="vehicle_type_not_enabled",
            details={"enabled": [t.value for t in config.enabled_vehicle_types]},
        )
    min_year = config.min_year(data.type)
    if data.year < min_year:
        raise AppError(
            f"The vehicle must be from {min_year} or newer",
            code="vehicle_too_old",
            details={"min_year": min_year},
        )
    if data.year > today_caracas().year + 1:
        raise AppError("Invalid vehicle year", code="vehicle_year_invalid")
    plate = normalize_plate(data.plate)
    taken = await session.scalar(
        select(Vehicle.id).where(Vehicle.plate == plate, Vehicle.driver_id != profile.id)
    )
    if taken:
        raise ConflictError("Plate already registered", code="plate_taken")
    values = data.model_dump() | {"plate": plate}
    if profile.vehicle is None:
        session.add(Vehicle(driver_id=profile.id, **values))
    else:
        for field, value in values.items():
            setattr(profile.vehicle, field, value)
    await _flush_unique(session, "Plate already registered", "plate_taken")
    return await reload(session, profile)


def presign_document(
    user: User, profile: DriverProfile, data: DocumentPresignRequest
) -> UploadResponse:
    _ensure_editable(profile)
    if data.content_type not in DOCUMENT_CONTENT_TYPES:
        raise AppError("File type not allowed", code="file_type_not_allowed")
    if data.size > settings.STORAGE_MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError("File too large", code="file_too_large")
    key = storage.build_key(document_folder(user.id, data.kind), data.filename)
    return UploadResponse(
        key=key,
        upload_url=storage.presigned_upload(key, data.content_type),
        headers={"Content-Type": data.content_type},
        expires_in=settings.STORAGE_PRESIGN_TTL_SECONDS,
    )


async def register_document(
    session: AsyncSession, user: User, profile: DriverProfile, data: DocumentRegister
) -> DriverProfile:
    _ensure_editable(profile)
    if not storage.key_in_folder(data.key, document_folder(user.id, data.kind)):
        raise AppError("The file does not belong to this upload", code="document_key_invalid")
    if any(d.key == data.key for d in profile.documents):
        raise ConflictError("Document already registered", code="document_already_registered")
    head = storage.head_object(data.key)
    if head is None:
        raise AppError("The file was not uploaded", code="document_not_uploaded")
    content_type = str(head.get("ContentType", "")).split(";")[0].strip().lower()
    if content_type not in DOCUMENT_CONTENT_TYPES:
        raise AppError("File type not allowed", code="file_type_not_allowed")
    if int(head.get("ContentLength", 0)) > settings.STORAGE_MAX_UPLOAD_MB * 1024 * 1024:
        raise AppError("File too large", code="file_too_large")

    same_kind = [d for d in profile.documents if d.kind == data.kind]
    if data.kind in MULTI_FILE_KINDS:
        if len(same_kind) >= MAX_VEHICLE_PHOTOS:
            raise AppError("Too many files of this kind", code="too_many_documents")
    else:
        for old in same_kind:
            await session.delete(old)
    session.add(
        DriverDocument(
            driver_id=profile.id, kind=data.kind, key=data.key, content_type=content_type
        )
    )
    await _flush_unique(session, "Document already registered", "document_already_registered")
    return await reload(session, profile)


async def delete_document(
    session: AsyncSession, profile: DriverProfile, document_id: uuid.UUID
) -> DriverProfile:
    _ensure_editable(profile)
    document = next((d for d in profile.documents if d.id == document_id), None)
    if document is None:
        raise NotFoundError("Document not found", code="document_not_found")
    await session.delete(document)
    return await reload(session, profile)


async def submit(session: AsyncSession, profile: DriverProfile, config: AppConfig) -> DriverProfile:
    _ensure_editable(profile)
    reqs = requirements(profile, config)
    if not reqs.can_submit:
        raise AppError(
            "Some requirements are missing",
            code="driver_requirements_missing",
            details=reqs.model_dump(mode="json"),
        )
    transition(profile, DriverStatus.PENDING_REVIEW)
    profile.submitted_at = _now()
    profile.rejection_reason = None
    return await reload(session, profile)


# --- Admin side ----------------------------------------------------------------------------------


async def list_drivers(
    session: AsyncSession,
    params: PageParams,
    *,
    status: DriverStatus | None = None,
    q: str | None = None,
) -> tuple[list[DriverProfile], int]:
    stmt = (
        _full_query()
        .join(User, User.id == DriverProfile.user_id)
        .outerjoin(Vehicle, Vehicle.driver_id == DriverProfile.id)
        .order_by(DriverProfile.created_at.desc())
    )
    if status:
        stmt = stmt.where(DriverProfile.status == status)
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        compact = f"%{compact_upper(q)}%"
        stmt = stmt.where(
            or_(
                func.lower(User.full_name).like(term),
                func.lower(User.email).like(term),
                DriverProfile.national_id.like(compact),
                Vehicle.plate.like(compact),
            )
        )
    return await paginate(session, stmt, params)


def _mark_reviewed(profile: DriverProfile, admin: User) -> None:
    profile.reviewed_at = _now()
    profile.reviewed_by_id = admin.id


async def approve(session: AsyncSession, profile: DriverProfile, admin: User) -> DriverProfile:
    if profile.status == DriverStatus.PENDING_REVIEW and any(
        d.status == DocumentStatus.REJECTED for d in profile.documents
    ):
        raise ConflictError(
            "Some documents are rejected; reject the application instead",
            code="driver_documents_rejected",
        )
    transition(profile, DriverStatus.APPROVED)
    _mark_reviewed(profile, admin)
    profile.approved_at = _now()
    profile.rejection_reason = None
    for document in profile.documents:
        if document.status == DocumentStatus.PENDING:
            document.status = DocumentStatus.APPROVED
            document.reviewed_at = profile.reviewed_at
            document.reviewed_by_id = admin.id
    return await reload(session, profile)


async def reject(
    session: AsyncSession, profile: DriverProfile, admin: User, reason: str
) -> DriverProfile:
    transition(profile, DriverStatus.REJECTED)
    _mark_reviewed(profile, admin)
    profile.rejection_reason = reason
    return await reload(session, profile)


async def suspend(
    session: AsyncSession, profile: DriverProfile, admin: User, reason: str
) -> DriverProfile:
    transition(profile, DriverStatus.SUSPENDED)
    _mark_reviewed(profile, admin)
    profile.suspended_at = _now()
    profile.rejection_reason = reason
    return await reload(session, profile)


async def reinstate(session: AsyncSession, profile: DriverProfile, admin: User) -> DriverProfile:
    transition(profile, DriverStatus.APPROVED)
    _mark_reviewed(profile, admin)
    profile.suspended_at = None
    profile.rejection_reason = None
    return await reload(session, profile)


async def review_document(
    session: AsyncSession,
    profile: DriverProfile,
    document_id: uuid.UUID,
    admin: User,
    data: DocumentReview,
) -> tuple[DriverProfile, DriverDocument]:
    if profile.status == DriverStatus.DRAFT:
        raise ConflictError(
            "The application was not submitted yet",
            code="driver_invalid_status",
            details={"status": profile.status.value},
        )
    document = next((d for d in profile.documents if d.id == document_id), None)
    if document is None:
        raise NotFoundError("Document not found", code="document_not_found")
    document.status = data.status
    document.rejection_reason = data.reason if data.status == DocumentStatus.REJECTED else None
    document.reviewed_at = _now()
    document.reviewed_by_id = admin.id
    return await reload(session, profile), document


# --- Notifications -------------------------------------------------------------------------------

DOCUMENT_LABELS: dict[str, dict[DocumentKind, str]] = {
    "es": {
        DocumentKind.ID_CARD: "Cédula",
        DocumentKind.RIF: "RIF",
        DocumentKind.DRIVERS_LICENSE: "Licencia de conducir",
        DocumentKind.MEDICAL_CERTIFICATE: "Certificado médico",
        DocumentKind.VEHICLE_REGISTRATION: "Carnet de circulación",
        DocumentKind.SELFIE: "Selfie",
        DocumentKind.VEHICLE_PHOTO: "Foto del vehículo",
    },
    "en": {
        DocumentKind.ID_CARD: "ID card",
        DocumentKind.RIF: "RIF",
        DocumentKind.DRIVERS_LICENSE: "Driver's license",
        DocumentKind.MEDICAL_CERTIFICATE: "Medical certificate",
        DocumentKind.VEHICLE_REGISTRATION: "Vehicle registration",
        DocumentKind.SELFIE: "Selfie",
        DocumentKind.VEHICLE_PHOTO: "Vehicle photo",
    },
}

# event -> locale -> (title, body). Bodies are formatted with ``reason`` and ``document``.
TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "pending_review": {
        "es": ("Recibimos tu solicitud", "Revisaremos tus datos y documentos y te avisaremos."),
        "en": (
            "Application received",
            "We will review your details and documents and let you know.",
        ),
    },
    "approved": {
        "es": ("¡Fuiste aprobado!", "Ya puedes conectarte y recibir viajes."),
        "en": ("You're approved!", "You can now go online and receive rides."),
    },
    "rejected": {
        "es": ("Tu solicitud necesita cambios", "Motivo: {reason}. Corrígelo y vuelve a enviarla."),
        "en": ("Your application needs changes", "Reason: {reason}. Fix it and submit it again."),
    },
    "suspended": {
        "es": ("Tu cuenta de motorizado fue suspendida", "Motivo: {reason}."),
        "en": ("Your driver account was suspended", "Reason: {reason}."),
    },
    "reinstated": {
        "es": ("Tu cuenta de motorizado fue reactivada", "Ya puedes volver a recibir viajes."),
        "en": ("Your driver account was reinstated", "You can receive rides again."),
    },
    "document_rejected": {
        "es": ("Documento rechazado", "{document}: {reason}. Sube uno nuevo."),
        "en": ("Document rejected", "{document}: {reason}. Please upload a new one."),
    },
}


def render(event: str, locale: str, **values: str) -> tuple[str, str]:
    locale = locale if locale in ("es", "en") else "es"
    title, body = TEMPLATES[event][locale]
    document = values.pop("document", None)
    label = DOCUMENT_LABELS[locale][DocumentKind(document)] if document else ""
    return title, body.format(document=label, **values)


async def notify(
    session: AsyncSession,
    profile: DriverProfile,
    event: str,
    *,
    reason: str | None = None,
    document: DriverDocument | None = None,
) -> None:
    """Inbox row + push in the driver's language. Commits, so the change and its notice land
    together, then queues the push (the worker must see the committed rows)."""
    user = await session.get(User, profile.user_id)
    if user is None:
        return
    title, body = render(
        event, user.locale, reason=reason or "", document=document.kind.value if document else ""
    )
    data = {"type": "driver_status", "event": event, "status": profile.status.value}
    if document is not None:
        data |= {"type": "driver_document", "document_id": str(document.id)}
    await notifications.create_notifications(session, [user.id], title, body, data)
    await session.commit()
    await notification_tasks.send_push.kiq([str(user.id)], title, body, data)
