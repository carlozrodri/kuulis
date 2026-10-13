"""Admin side of the re-verification queue (doc 12): what a verifier sees and the notices each
decision sends. The rules live in ``apps.drivers.verification``."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.drivers import services, verification
from apps.drivers.models import (
    CheckKind,
    DocumentKind,
    DriverCheck,
    DriverProfile,
    DriverStatus,
    Vehicle,
    VehicleStatus,
)
from apps.drivers.schemas import (
    CheckFileRead,
    CheckReview,
    DocumentAdminRead,
    DriverBrief,
    DriverCheckAdminRead,
    DriverCheckRead,
    VehicleRead,
)
from apps.users.models import ADMIN_PANEL_ROLES, User
from kuulis.core.exceptions import AppError, ConflictError


async def ensure_reviewer(session: AsyncSession, user_id: uuid.UUID | None) -> None:
    if user_id is None:
        return
    user = await session.get(User, user_id)
    if user is None or user.role not in ADMIN_PANEL_ROLES or not user.is_active:
        raise AppError("Only team members can review", code="not_staff")


async def admin_reads(
    session: AsyncSession, checks: list[DriverCheck]
) -> list[DriverCheckAdminRead]:
    """The queue: who, which check, who has it. No file links (the detail is audited)."""
    profile_ids = {c.driver_id for c in checks}
    profiles = {
        p.id: p
        for p in await session.scalars(
            select(DriverProfile).where(DriverProfile.id.in_(profile_ids))
        )
    }
    user_ids = {p.user_id for p in profiles.values()} | {
        uid for c in checks for uid in (c.assigned_to_id, c.reviewed_by_id) if uid
    }
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(user_ids)))}
    plates = dict(
        (
            await session.execute(
                select(Vehicle.driver_id, Vehicle.plate).where(
                    Vehicle.driver_id.in_(profile_ids), Vehicle.status == VehicleStatus.ACTIVE
                )
            )
        ).all()
    )
    reads = []
    for check in checks:
        profile = profiles[check.driver_id]
        user = users.get(profile.user_id)
        reads.append(
            DriverCheckAdminRead(
                **DriverCheckRead.model_validate(check).model_dump(),
                driver=DriverBrief(
                    id=profile.id,
                    user_id=profile.user_id,
                    full_name=user.full_name if user else "",
                    email=user.email if user else "",
                    status=profile.status,
                    plate=plates.get(profile.id),
                ),
                assigned_to=services.staff_brief(users.get(check.assigned_to_id)),
                reviewed_by=services.staff_brief(users.get(check.reviewed_by_id)),
                files=[
                    CheckFileRead(kind=f["kind"], content_type=f["content_type"])
                    for f in check.files
                ],
                expires_on=_typed_expiry(check),
            )
        )
    return reads


def _typed_expiry(check: DriverCheck) -> date | None:
    value = next((f.get("expires_on") for f in check.files if f.get("expires_on")), None)
    return date.fromisoformat(value) if value else None


def _document_read(document) -> DocumentAdminRead:
    return DocumentAdminRead.model_validate(document).model_copy(
        update={"download_url": services._download_url(document.key)}
    )


async def admin_detail(session: AsyncSession, check: DriverCheck) -> DriverCheckAdminRead:
    """With the photos and what to compare them with: the approved selfie and cédula, the
    document in use next to its renewal, and the new moto."""
    (base,) = await admin_reads(session, [check])
    profile = await services.get_or_404(session, check.driver_id)
    references = [
        _document_read(d)
        for kind in (DocumentKind.SELFIE, DocumentKind.ID_CARD)
        if (d := verification.in_force(profile, kind)) is not None
    ]
    document = None
    expires_on = base.expires_on
    if check.document_id is not None:
        renewal = next((d for d in profile.documents if d.id == check.document_id), None)
        if renewal is not None:
            document = _document_read(renewal)
            expires_on = renewal.expires_on
            in_use = verification.in_force(profile, renewal.kind)
            if in_use is not None and in_use.id != renewal.id:
                references.append(_document_read(in_use))
    if check.kind in (CheckKind.REVERIFICATION, CheckKind.VEHICLE_CHANGE):
        references += [
            _document_read(d)
            for d in verification.current_documents(profile)
            if d.kind == DocumentKind.VEHICLE_PHOTO
        ][:4]
    vehicle = await session.get(Vehicle, check.vehicle_id) if check.vehicle_id else None
    return base.model_copy(
        update={
            "files": [
                CheckFileRead(
                    kind=f["kind"],
                    content_type=f["content_type"],
                    download_url=services._download_url(f["key"]),
                )
                for f in check.files
            ],
            "references": references,
            "document": document,
            "vehicle": VehicleRead.model_validate(vehicle) if vehicle else None,
            "expires_on": expires_on,
        }
    )


async def review(session: AsyncSession, check: DriverCheck, admin: User, data: CheckReview) -> None:
    approved = data.status.value == "approved"
    profile, event = await verification.review_check(
        session, check, admin, approved, data.reason, data.expires_on
    )
    if event is None:
        await session.commit()
        return
    document = None
    if check.document_id is not None:
        document = next((d for d in profile.documents if d.id == check.document_id), None)
    values = {}
    if event == "vehicle_approved" and profile.vehicle is not None:
        values["plate"] = profile.vehicle.plate
    await services.notify(
        session,
        profile,
        event,
        reason=data.reason,
        document=document,
        values=values,
        data={"check_id": str(check.id)},
    )


async def request_reverification(
    session: AsyncSession, profile: DriverProfile, reason: str
) -> DriverCheck:
    if profile.status != DriverStatus.APPROVED:
        raise ConflictError("Only approved drivers", code="driver_not_approved")
    check = await verification.request_check(session, profile, CheckKind.REVERIFICATION, reason)
    await services.notify(session, profile, "selfie_requested", data={"check_id": str(check.id)})
    return check


async def after_mismatch_report(session: AsyncSession, driver_user_id: uuid.UUID) -> None:
    if await verification.on_mismatch_report(session, driver_user_id):
        profile = await services.get_by_user(session, driver_user_id)
        if profile is not None:
            checks = await verification.open_checks(session, profile.id)
            check = next(c for c in checks if c.kind == CheckKind.REVERIFICATION)
            await services.notify(
                session, profile, "selfie_requested", data={"check_id": str(check.id)}
            )
