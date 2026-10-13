import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from apps.audit.services import audit
from apps.config.services import get_app_config
from apps.drivers import checks, services, verification
from apps.drivers.models import CheckKind, CheckStatus, DocumentStatus, DriverStatus
from apps.drivers.schemas import (
    AssignRequest,
    CheckPresignRequest,
    CheckReview,
    CheckSubmit,
    DocumentPresignRequest,
    DocumentRegister,
    DocumentReview,
    DriverAdminRead,
    DriverCheckAdminRead,
    DriverCheckRead,
    DriverProfileRead,
    DriverProfileWrite,
    ExpiryUpdate,
    InductionRequest,
    ReasonRequest,
    VehicleChange,
    VehicleWrite,
)
from apps.files.schemas import UploadResponse
from apps.rides import presence
from apps.users.dependencies import Can, CurrentUser, DBSession
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/drivers", tags=["drivers"])
admin_router = APIRouter(prefix="/admin/drivers", tags=["drivers"])
# Included before admin_router: /admin/drivers/checks must win over /admin/drivers/{driver_id}.
checks_admin_router = APIRouter(prefix="/admin/drivers/checks", tags=["drivers"])


# --- Driver (mobile app) -----------------------------------------------------------------------


@router.get("/me", response_model=DriverProfileRead)
async def read_me(user: CurrentUser, session: DBSession) -> DriverProfileRead:
    profile = await services.get_for_user_or_404(session, user.id)
    return await services.read(session, profile, await get_app_config(session))


@router.put("/me", response_model=DriverProfileRead)
async def upsert_me(
    data: DriverProfileWrite, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    profile = await services.upsert_profile(session, user, data)
    return await services.read(session, profile, await get_app_config(session))


@router.put("/me/vehicle", response_model=DriverProfileRead)
async def set_vehicle(
    data: VehicleWrite, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    config = await get_app_config(session)
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.set_vehicle(session, profile, data, config)
    return await services.read(session, profile, config)


@router.post("/me/documents/presign", response_model=UploadResponse)
async def presign_document(
    data: DocumentPresignRequest, user: CurrentUser, session: DBSession
) -> UploadResponse:
    """Presigned PUT to private S3 under ``drivers/<user_id>/<kind>/``, then POST /documents."""
    profile = await services.get_for_user_or_404(session, user.id)
    return services.presign_document(user, profile, data, await get_app_config(session))


@router.post("/me/documents", response_model=DriverProfileRead, status_code=status.HTTP_201_CREATED)
async def register_document(
    data: DocumentRegister, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    config = await get_app_config(session)
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.register_document(session, user, profile, data, config)
    return await services.read(session, profile, config)


@router.delete("/me/documents/{document_id}", response_model=DriverProfileRead)
async def delete_document(
    document_id: uuid.UUID, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.delete_document(session, profile, document_id)
    return await services.read(session, profile, await get_app_config(session))


@router.post("/me/submit", response_model=DriverProfileRead)
async def submit(user: CurrentUser, session: DBSession) -> DriverProfileRead:
    config = await get_app_config(session)
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.submit(session, profile, config)
    await services.notify(session, profile, "pending_review")
    return await services.read(session, profile, config)


@router.patch("/me/documents/{document_id}", response_model=DriverProfileRead)
async def set_document_expiry(
    document_id: uuid.UUID, data: ExpiryUpdate, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    """The expiry of a document approved before doc 12; a verifier confirms it later."""
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await verification.set_expiry(session, profile, document_id, data.expires_on)
    return await services.read(session, profile, await get_app_config(session))


# --- Ongoing verification (doc 12) ---------------------------------------------------------------


@router.post("/me/checks/presign", response_model=UploadResponse)
async def presign_check_file(
    data: CheckPresignRequest, user: CurrentUser, session: DBSession
) -> UploadResponse:
    """Presigned PUT for a live selfie, moto photos or a new moto's registration."""
    profile = await services.get_for_user_or_404(session, user.id)
    return verification.presign_check_file(user, profile, data)


@router.post("/me/checks/{check_id}/submit", response_model=DriverCheckRead)
async def submit_check(
    check_id: uuid.UUID, data: CheckSubmit, user: CurrentUser, session: DBSession
) -> DriverCheckRead:
    """Sends the selfie (and moto photos) asked for; the driver can go online right after."""
    config = await get_app_config(session)
    profile = await services.get_for_user_or_404(session, user.id)
    check = await verification.submit_check(session, user, profile, check_id, data.files, config)
    return DriverCheckRead.model_validate(check)


@router.post("/me/vehicles", response_model=DriverProfileRead, status_code=status.HTTP_201_CREATED)
async def change_vehicle(
    data: VehicleChange, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    """A new moto waits for review; the driver keeps working with the current one."""
    config = await get_app_config(session)
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await verification.request_vehicle_change(session, user, profile, data, config)
    return await services.read(session, profile, config)


@router.delete("/me/vehicles/pending", response_model=DriverProfileRead)
async def cancel_vehicle_change(user: CurrentUser, session: DBSession) -> DriverProfileRead:
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await verification.cancel_vehicle_change(session, profile)
    return await services.read(session, profile, await get_app_config(session))


# --- Admin panel (staff / admin roles) ---------------------------------------------------------


@checks_admin_router.get("", response_model=Page[DriverCheckAdminRead])
async def list_checks(
    admin: Can("drivers.view"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status: CheckStatus | None = CheckStatus.PENDING,
    kind: CheckKind | None = None,
    mine: bool = False,
    unassigned: bool = False,
) -> Page[DriverCheckAdminRead]:
    """The re-verification queue (selfies, renewals, moto changes), oldest first."""
    items, total = await verification.list_checks(
        session,
        status=status,
        kind=kind,
        assigned_to=admin.id if mine else None,
        unassigned=unassigned,
        limit=params.limit,
        offset=params.offset,
    )
    return Page[DriverCheckAdminRead](
        items=await checks.admin_reads(session, items),
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@checks_admin_router.get(
    "/{check_id}",
    dependencies=[audit("driver.check_view", "driver_check", "check_id")],  # shows the photos
    response_model=DriverCheckAdminRead,
)
async def get_check(
    check_id: uuid.UUID, _: Can("drivers.view"), session: DBSession
) -> DriverCheckAdminRead:
    check = await verification.get_check_or_404(session, check_id)
    return await checks.admin_detail(session, check)


@checks_admin_router.post(
    "/{check_id}/review",
    dependencies=[audit("driver.check_review", "driver_check", "check_id")],
    response_model=DriverCheckAdminRead,
)
async def review_check(
    check_id: uuid.UUID, data: CheckReview, admin: Can("drivers.review"), session: DBSession
) -> DriverCheckAdminRead:
    check = await verification.get_check_or_404(session, check_id)
    await checks.review(session, check, admin, data)
    return await checks.admin_detail(
        session, await verification.get_check_or_404(session, check_id)
    )


@checks_admin_router.post(
    "/{check_id}/assign",
    dependencies=[audit("driver.check_assign", "driver_check", "check_id")],
    response_model=DriverCheckAdminRead,
)
async def assign_check(
    check_id: uuid.UUID, data: AssignRequest, _: Can("drivers.review"), session: DBSession
) -> DriverCheckAdminRead:
    check = await verification.get_check_or_404(session, check_id)
    await checks.ensure_reviewer(session, data.user_id)
    check.assigned_to_id = data.user_id
    await session.flush()
    return await checks.admin_detail(session, check)


@admin_router.get("", response_model=Page[DriverAdminRead])
async def list_drivers(
    _: Can("drivers.view"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status: DriverStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    assigned_to: uuid.UUID | None = None,
) -> Page[DriverAdminRead]:
    """Items carry ``user`` and ``vehicle``; ``download_url`` is only filled in the detail."""
    items, total = await services.list_drivers(
        session, params, status=status, q=q, assigned_to=assigned_to
    )
    config = await get_app_config(session)
    return Page[DriverAdminRead](
        items=[services.to_admin_read(p, config, with_urls=False) for p in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@admin_router.get(
    "/{driver_id}",
    dependencies=[audit("driver.view", "driver", "driver_id")],  # shows the documents
    response_model=DriverAdminRead,
)
async def get_driver(
    driver_id: uuid.UUID, _: Can("drivers.view"), session: DBSession
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    return await services.admin_read(session, profile, await get_app_config(session))


@admin_router.post(
    "/{driver_id}/approve",
    dependencies=[audit("driver.approve", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def approve(
    driver_id: uuid.UUID, admin: Can("drivers.review"), session: DBSession
) -> DriverAdminRead:
    config = await get_app_config(session)
    profile = await services.get_or_404(session, driver_id)
    profile = await services.approve(session, profile, admin, config)
    await services.notify(session, profile, "approved")
    return await services.admin_read(session, profile, config)


@admin_router.post(
    "/{driver_id}/reject",
    dependencies=[audit("driver.reject", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def reject(
    driver_id: uuid.UUID, data: ReasonRequest, admin: Can("drivers.review"), session: DBSession
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile = await services.reject(session, profile, admin, data.reason)
    await services.notify(session, profile, "rejected", reason=data.reason)
    return await services.admin_read(session, profile, await get_app_config(session))


@admin_router.post(
    "/{driver_id}/suspend",
    dependencies=[audit("driver.suspend", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def suspend(
    driver_id: uuid.UUID, data: ReasonRequest, admin: Can("drivers.suspend"), session: DBSession
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile = await services.suspend(session, profile, admin, data.reason)
    await presence.go_offline(profile.user_id)  # stop offers right away
    await services.notify(session, profile, "suspended", reason=data.reason)
    return await services.admin_read(session, profile, await get_app_config(session))


@admin_router.post(
    "/{driver_id}/reinstate",
    dependencies=[audit("driver.reinstate", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def reinstate(
    driver_id: uuid.UUID, admin: Can("drivers.suspend"), session: DBSession
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile = await services.reinstate(session, profile, admin)
    await services.notify(session, profile, "reinstated")
    return await services.admin_read(session, profile, await get_app_config(session))


@admin_router.post(
    "/{driver_id}/documents/{document_id}/review",
    dependencies=[audit("driver.document_review", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def review_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    data: DocumentReview,
    admin: Can("drivers.review"),
    session: DBSession,
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile, document = await services.review_document(session, profile, document_id, admin, data)
    if document.status == DocumentStatus.REJECTED:
        await services.notify(
            session, profile, "document_rejected", reason=data.reason, document=document
        )
    return await services.admin_read(session, profile, await get_app_config(session))


@admin_router.post(
    "/{driver_id}/assign",
    dependencies=[audit("driver.assign", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def assign(
    driver_id: uuid.UUID, data: AssignRequest, _: Can("drivers.review"), session: DBSession
) -> DriverAdminRead:
    """Who reviews this application (doc 12)."""
    profile = await services.get_or_404(session, driver_id)
    await checks.ensure_reviewer(session, data.user_id)
    profile.assigned_to_id = data.user_id
    profile = await services.reload(session, profile)
    return await services.admin_read(session, profile, await get_app_config(session))


@admin_router.post(
    "/{driver_id}/induction",
    dependencies=[audit("driver.induction", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def induction(
    driver_id: uuid.UUID, data: InductionRequest, admin: Can("drivers.review"), session: DBSession
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile.induction_completed_at = verification.services._now() if data.done else None
    profile.induction_by_id = admin.id if data.done else None
    profile = await services.reload(session, profile)
    return await services.admin_read(session, profile, await get_app_config(session))


@admin_router.post(
    "/{driver_id}/reverify",
    dependencies=[audit("driver.reverify", "driver", "driver_id")],
    response_model=DriverAdminRead,
)
async def reverify(
    driver_id: uuid.UUID, _: Can("drivers.review"), session: DBSession
) -> DriverAdminRead:
    """Asks an approved driver for a live selfie and new moto photos before going online again."""
    profile = await services.get_or_404(session, driver_id)
    await checks.request_reverification(session, profile, "team")
    return await services.admin_read(session, profile, await get_app_config(session))
