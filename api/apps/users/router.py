import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status

from apps.audit.services import audit, note, snapshot
from apps.auth import services as auth
from apps.auth import totp
from apps.moderation import services as moderation
from apps.releases import services as releases
from apps.rides import presence
from apps.staff.services import permissions_of
from apps.updates import services as updates
from apps.users import services
from apps.users.dependencies import (
    AdminUser,
    Can,
    CurrentUser,
    DBSession,
    VerifiedAdminUser,
    ensure_recently_verified,
)
from apps.users.models import Role
from apps.users.schemas import (
    ChangePassword,
    DeletionScheduled,
    UserAdminCreate,
    UserAdminUpdate,
    UserRead,
    UserStats,
    UserUpdateMe,
)
from kuulis.core.exceptions import PermissionDeniedError
from kuulis.core.pagination import Page, PageParams, page_params
from kuulis.core.redis import redis_client

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(
    user: CurrentUser,
    session: DBSession,
    x_app_platform: Annotated[str | None, Header()] = None,
    x_app_build: Annotated[str | None, Header()] = None,
    x_app_update: Annotated[str | None, Header()] = None,
) -> UserRead:
    # The apps load the profile on start: a cheap place to count which builds are in use (doc 09).
    await releases.record_usage(redis_client, x_app_platform, x_app_build, user.id)
    await updates.record_usage(redis_client, x_app_platform, x_app_update, user.id)
    read = await moderation.user_read(session, user)
    if user.can_access_admin:
        read.permissions = sorted(await permissions_of(session, user))
    return read


@router.patch("/me", response_model=UserRead)
async def update_me(data: UserUpdateMe, user: CurrentUser, session: DBSession) -> UserRead:
    return await moderation.user_read(session, await services.update_me(user, data))


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(data: ChangePassword, user: CurrentUser) -> None:
    await services.change_password(user, data.current_password, data.new_password)
    await auth.revoke_others(str(user.id), user.auth_sid)  # other devices sign in again


@router.delete("/me", response_model=DeletionScheduled)
async def delete_me(user: CurrentUser, session: DBSession) -> DeletionScheduled:
    """Deactivates the account now and erases the personal data after the grace period; signing
    in before then restores it. Every session is closed."""
    erase_at = await services.request_deletion(session, user)
    await auth.revoke_all(str(user.id))
    await presence.go_offline(user.id)
    return DeletionScheduled(erase_at=erase_at)


# --- Admin panel endpoints (staff / admin roles) -----------------------------------------------


@router.get("", response_model=Page[UserRead])
async def list_users(
    _: Can("users.view"),
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
async def user_stats(_: Can("users.view"), session: DBSession) -> UserStats:
    return UserStats(**await services.stats(session))


@router.post(
    "",
    dependencies=[audit("user.create", "user")],
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(data: UserAdminCreate, _: VerifiedAdminUser, session: DBSession) -> UserRead:
    user = await services.admin_create_user(session, data)
    note(entity_id=user.id)
    return UserRead.model_validate(user)


@router.get(
    "/{user_id}",
    dependencies=[audit("user.view", "user", "user_id")],  # full personal data
    response_model=UserRead,
)
async def get_user(user_id: uuid.UUID, _: Can("users.view"), session: DBSession) -> UserRead:
    return await moderation.user_read(
        session, await services.get_or_404(session, user_id), staff_view=True
    )


@router.patch(
    "/{user_id}", dependencies=[audit("user.update", "user", "user_id")], response_model=UserRead
)
async def update_user(
    user_id: uuid.UUID, data: UserAdminUpdate, admin: AdminUser, session: DBSession
) -> UserRead:
    user = await services.get_or_404(session, user_id)
    if data.role is not None and data.role != user.role:
        await ensure_recently_verified(admin)
    if user.id == admin.id and (data.role not in (None, Role.ADMIN) or data.is_active is False):
        raise PermissionDeniedError("You cannot demote or disable yourself", code="self_demotion")
    changed = data.model_dump(exclude_unset=True).keys()
    before = snapshot(user, changed)
    updated = await services.admin_update_user(user, data)
    note(before=before, after=snapshot(updated, changed))
    return await moderation.user_read(session, updated, staff_view=True)


@router.post(
    "/{user_id}/totp/reset",
    dependencies=[audit("user.totp_reset", "user", "user_id")],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reset_totp(user_id: uuid.UUID, _: VerifiedAdminUser, session: DBSession) -> None:
    """Removes a staff member's authenticator (lost phone); they set it up at their next sign-in."""
    await totp.reset(session, await services.get_or_404(session, user_id))
    await session.commit()
