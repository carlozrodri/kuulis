from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, status

from apps.privacy import services
from apps.privacy.models import DataExport
from apps.privacy.schemas import (
    AdminExportRead,
    ConsentUpdate,
    DataExportRead,
    DeletionRequestRead,
)
from apps.privacy.tasks import build_export
from apps.users.dependencies import Can, CurrentUser, DBSession
from apps.users.services import erase_at
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(tags=["privacy"])


def _read(export: DataExport) -> DataExportRead:
    read = DataExportRead.model_validate(export)
    if export.status != "failed":
        read.next_at = export.created_at + services.EXPORT_EVERY
    return read


@router.get("/users/me/export", response_model=DataExportRead | None)
async def my_export(user: CurrentUser, session: DBSession) -> DataExportRead | None:
    """The latest "download my data" request, to show its state in the app."""
    export = await services.latest_export(session, user.id)
    return _read(export) if export else None


@router.post(
    "/users/me/export", response_model=DataExportRead, status_code=status.HTTP_202_ACCEPTED
)
async def request_export(user: CurrentUser, session: DBSession) -> DataExportRead:
    """Builds a JSON file with the user's data and emails a link valid for 24 h (once a day)."""
    export = await services.request_export(session, user)
    await session.commit()
    await build_export.kiq(str(export.id))
    await session.refresh(export)
    return _read(export)


@router.put("/users/me/consents", response_model=list[str])
async def set_consent(
    data: ConsentUpdate, request: Request, user: CurrentUser, session: DBSession
) -> list[str]:
    """Records an explicit permission given (or withdrawn) in the app; answers those in force."""
    await services.record_consent(session, user, data.kind, data.granted, request)
    await session.commit()
    return await services.consents(session, user.id)


# --- Admin panel endpoints ---------------------------------------------------------------------


@router.get("/admin/privacy/deletions", response_model=Page[DeletionRequestRead])
async def deletion_requests(
    _: Can("users.view"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    state: Literal["scheduled", "erased"] | None = None,
) -> Page[DeletionRequestRead]:
    users, total = await services.deletion_requests(session, params, state)
    items = [
        DeletionRequestRead(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            requested_at=u.deletion_requested_at,
            erase_at=erase_at(u),
            erased_at=u.deleted_at,
        )
        for u in users
    ]
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@router.get("/admin/privacy/exports", response_model=Page[AdminExportRead])
async def exports(
    _: Can("users.view"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[AdminExportRead]:
    rows, total = await services.exports(session, params)
    items = [
        AdminExportRead.model_validate(
            {**_read(e).model_dump(), "user_id": e.user_id, "email": email, "error": e.error}
        )
        for e, email in rows
    ]
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)
