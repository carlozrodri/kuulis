import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from apps.moderation import services as moderation
from apps.users import services
from apps.users.dependencies import AdminUser, CurrentUser, DBSession, StaffUser
from apps.users.models import Role
from apps.users.schemas import (
    ChangePassword,
    UserAdminCreate,
    UserAdminUpdate,
    UserRead,
    UserStats,
    UserUpdateMe,
)
from kuulis.core.exceptions import PermissionDeniedError
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(user: CurrentUser, session: DBSession) -> UserRead:
    return await moderation.user_read(session, user)


@router.patch("/me", response_model=UserRead)
async def update_me(data: UserUpdateMe, user: CurrentUser, session: DBSession) -> UserRead:
    return await moderation.user_read(session, await services.update_me(user, data))


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(data: ChangePassword, user: CurrentUser) -> None:
    await services.change_password(user, data.current_password, data.new_password)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_me(user: CurrentUser) -> None:
    user.is_active = False


# --- Admin panel endpoints (staff / admin roles) -----------------------------------------------


@router.get("", response_model=Page[UserRead])
async def list_users(
    _: StaffUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    search: Annotated[str | None, Query(max_length=100)] = None,
    role: Role | None = None,
    is_active: bool | None = None,
    suspended: bool | None = None,
) -> Page[UserRead]:
    items, total = await services.list_users(
        session,
        params,
        search=search,
        role=role,
        is_active=is_active,
        where=moderation.suspended_filter(suspended) if suspended is not None else None,
    )
    return Page[UserRead](
        items=await moderation.user_reads(session, items, staff_view=True),
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/stats", response_model=UserStats)
async def user_stats(_: StaffUser, session: DBSession) -> UserStats:
    return UserStats(**await services.stats(session))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserAdminCreate, _: AdminUser, session: DBSession) -> UserRead:
    return UserRead.model_validate(await services.admin_create_user(session, data))


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, _: StaffUser, session: DBSession) -> UserRead:
    return await moderation.user_read(
        session, await services.get_or_404(session, user_id), staff_view=True
    )


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, data: UserAdminUpdate, admin: AdminUser, session: DBSession
) -> UserRead:
    user = await services.get_or_404(session, user_id)
    if user.id == admin.id and (data.role not in (None, Role.ADMIN) or data.is_active is False):
        raise PermissionDeniedError("You cannot demote or disable yourself", code="self_demotion")
    updated = await services.admin_update_user(user, data)
    return await moderation.user_read(session, updated, staff_view=True)
