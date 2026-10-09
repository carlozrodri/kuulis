import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from apps.config.services import get_app_config
from apps.drivers import services
from apps.drivers.models import DocumentStatus, DriverStatus
from apps.drivers.schemas import (
    DocumentPresignRequest,
    DocumentRegister,
    DocumentReview,
    DriverAdminRead,
    DriverProfileRead,
    DriverProfileWrite,
    ReasonRequest,
    VehicleWrite,
)
from apps.files.schemas import UploadResponse
from apps.rides import presence
from apps.users.dependencies import CurrentUser, DBSession, StaffUser
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/drivers", tags=["drivers"])
admin_router = APIRouter(prefix="/admin/drivers", tags=["drivers"])


# --- Driver (mobile app) -----------------------------------------------------------------------


@router.get("/me", response_model=DriverProfileRead)
async def read_me(user: CurrentUser, session: DBSession) -> DriverProfileRead:
    profile = await services.get_for_user_or_404(session, user.id)
    return services.to_read(profile, await get_app_config(session))


@router.put("/me", response_model=DriverProfileRead)
async def upsert_me(
    data: DriverProfileWrite, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    profile = await services.upsert_profile(session, user, data)
    return services.to_read(profile, await get_app_config(session))


@router.put("/me/vehicle", response_model=DriverProfileRead)
async def set_vehicle(
    data: VehicleWrite, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    config = await get_app_config(session)
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.set_vehicle(session, profile, data, config)
    return services.to_read(profile, config)


@router.post("/me/documents/presign", response_model=UploadResponse)
async def presign_document(
    data: DocumentPresignRequest, user: CurrentUser, session: DBSession
) -> UploadResponse:
    """Presigned PUT to private S3 under ``drivers/<user_id>/<kind>/``, then POST /documents."""
    profile = await services.get_for_user_or_404(session, user.id)
    return services.presign_document(user, profile, data)


@router.post("/me/documents", response_model=DriverProfileRead, status_code=status.HTTP_201_CREATED)
async def register_document(
    data: DocumentRegister, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.register_document(session, user, profile, data)
    return services.to_read(profile, await get_app_config(session))


@router.delete("/me/documents/{document_id}", response_model=DriverProfileRead)
async def delete_document(
    document_id: uuid.UUID, user: CurrentUser, session: DBSession
) -> DriverProfileRead:
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.delete_document(session, profile, document_id)
    return services.to_read(profile, await get_app_config(session))


@router.post("/me/submit", response_model=DriverProfileRead)
async def submit(user: CurrentUser, session: DBSession) -> DriverProfileRead:
    config = await get_app_config(session)
    profile = await services.get_for_user_or_404(session, user.id)
    profile = await services.submit(session, profile, config)
    await services.notify(session, profile, "pending_review")
    return services.to_read(profile, config)


# --- Admin panel (staff / admin roles) ---------------------------------------------------------


@admin_router.get("", response_model=Page[DriverAdminRead])
async def list_drivers(
    _: StaffUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status: DriverStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[DriverAdminRead]:
    """Items carry ``user`` and ``vehicle``; ``download_url`` is only filled in the detail."""
    items, total = await services.list_drivers(session, params, status=status, q=q)
    config = await get_app_config(session)
    return Page[DriverAdminRead](
        items=[services.to_admin_read(p, config, with_urls=False) for p in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@admin_router.get("/{driver_id}", response_model=DriverAdminRead)
async def get_driver(driver_id: uuid.UUID, _: StaffUser, session: DBSession) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    return services.to_admin_read(profile, await get_app_config(session))


@admin_router.post("/{driver_id}/approve", response_model=DriverAdminRead)
async def approve(driver_id: uuid.UUID, admin: StaffUser, session: DBSession) -> DriverAdminRead:
    profile = await services.approve(session, await services.get_or_404(session, driver_id), admin)
    await services.notify(session, profile, "approved")
    return services.to_admin_read(profile, await get_app_config(session))


@admin_router.post("/{driver_id}/reject", response_model=DriverAdminRead)
async def reject(
    driver_id: uuid.UUID, data: ReasonRequest, admin: StaffUser, session: DBSession
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile = await services.reject(session, profile, admin, data.reason)
    await services.notify(session, profile, "rejected", reason=data.reason)
    return services.to_admin_read(profile, await get_app_config(session))


@admin_router.post("/{driver_id}/suspend", response_model=DriverAdminRead)
async def suspend(
    driver_id: uuid.UUID, data: ReasonRequest, admin: StaffUser, session: DBSession
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile = await services.suspend(session, profile, admin, data.reason)
    await presence.go_offline(profile.user_id)  # stop offers right away
    await services.notify(session, profile, "suspended", reason=data.reason)
    return services.to_admin_read(profile, await get_app_config(session))


@admin_router.post("/{driver_id}/reinstate", response_model=DriverAdminRead)
async def reinstate(driver_id: uuid.UUID, admin: StaffUser, session: DBSession) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile = await services.reinstate(session, profile, admin)
    await services.notify(session, profile, "reinstated")
    return services.to_admin_read(profile, await get_app_config(session))


@admin_router.post("/{driver_id}/documents/{document_id}/review", response_model=DriverAdminRead)
async def review_document(
    driver_id: uuid.UUID,
    document_id: uuid.UUID,
    data: DocumentReview,
    admin: StaffUser,
    session: DBSession,
) -> DriverAdminRead:
    profile = await services.get_or_404(session, driver_id)
    profile, document = await services.review_document(session, profile, document_id, admin, data)
    if document.status == DocumentStatus.REJECTED:
        await services.notify(
            session, profile, "document_rejected", reason=data.reason, document=document
        )
    return services.to_admin_read(profile, await get_app_config(session))
