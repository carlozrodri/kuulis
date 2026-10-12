import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from apps.audit.services import audit, note, snapshot
from apps.config import services as config_services
from apps.control import services
from apps.control.flags import FLAGS, Audience, evaluate
from apps.control.models import Announcement
from apps.control.schemas import (
    AnnouncementAdminRead,
    AnnouncementCreate,
    AnnouncementUpdate,
    AppStatus,
    AppStatusRead,
    Bootstrap,
    FlagCheck,
    FlagRead,
    FlagRules,
    FlagUpdate,
    Mode,
)
from apps.drivers.models import DriverProfile, DriverStatus
from apps.rides import dispatch
from apps.users import services as user_services
from apps.users.dependencies import Can, DBSession, bearer, user_from_token
from apps.users.models import User
from kuulis.core.exceptions import AppError, NotFoundError

router = APIRouter(tags=["control"])

ANNOUNCEMENT_FIELDS = ("title", "target", "cta", "starts_at", "ends_at", "dismissible", "style")


async def _optional_user(
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User | None:
    """The account behind the token, or None (the app also asks before login)."""
    if credentials is None:
        return None
    try:
        return await user_from_token(session, credentials.credentials)
    except AppError:
        return None


OptionalUser = Annotated[User | None, Depends(_optional_user)]
ClientId = Annotated[str | None, Query(max_length=100)]


@router.get("/app/bootstrap", response_model=Bootstrap)
async def bootstrap(
    session: DBSession,
    user: OptionalUser,
    response: Response,
    mode: Mode | None = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    client_id: ClientId = None,
    x_app_platform: Annotated[str | None, Header()] = None,
    x_app_build: Annotated[str | None, Header()] = None,
    x_app_channel: Annotated[str | None, Header()] = None,
) -> Bootstrap:
    """Maintenance, city pauses, feature flags, banners and remote settings for this app.

    The app reads it at start, every ``refresh_seconds`` and on the ``config.updated`` event."""
    response.headers["Cache-Control"] = "no-store"
    build = int(x_app_build) if x_app_build and x_app_build.isdigit() else None
    return await services.bootstrap(
        session,
        user,
        mode=mode,
        platform=x_app_platform,
        build=build,
        channel=x_app_channel,
        lat=lat,
        lng=lng,
        client_id=client_id,
    )


@router.post("/app/announcements/{announcement_id}/dismiss", status_code=204)
async def dismiss_announcement(
    announcement_id: uuid.UUID, session: DBSession, user: OptionalUser, client_id: ClientId = None
) -> None:
    """Closed banners do not come back (per account, or per device before login)."""
    ident = str(user.id) if user else client_id
    if ident is None:
        raise AppError("client_id is required without an account", code="client_id_required")
    await services.dismiss(session, announcement_id, ident)


# --- Admin: app status ---------------------------------------------------------------------------


def _status(config) -> AppStatusRead:
    return AppStatusRead(
        maintenance=config.maintenance,
        area_pauses=config.area_pauses,
        areas=[a.name for a in config.service_areas],
    )


@router.get("/admin/app/status", response_model=AppStatusRead)
async def app_status(_: Can("app_status.view"), session: DBSession) -> AppStatusRead:
    return _status(await config_services.get_app_config(session))


@router.put(
    "/admin/app/status",
    response_model=AppStatusRead,
    dependencies=[audit("app_status.update", "config")],
)
async def set_app_status(
    data: AppStatus, _: Can("app_status.manage"), session: DBSession
) -> AppStatusRead:
    """Maintenance (global or per city) and city pauses: no new quotes, rides or drivers going
    online there. Drivers already online are taken offline once their ride ends."""
    before = await config_services.get_app_config(session)
    config = await services.set_status(session, data)
    keys = ("maintenance", "area_pauses")
    note(before=snapshot(before.model_dump(mode="json"), keys), after=data.model_dump(mode="json"))
    await session.commit()
    await services.status_saved()
    await dispatch.offline_paused()  # the dispatcher repeats it every 30 s for rides that end
    return _status(config)


# --- Admin: feature flags ------------------------------------------------------------------------


def _flag_read(key: str, flag, email: str | None) -> FlagRead:
    spec = FLAGS[key]
    return FlagRead(
        key=key,
        description=spec.description,
        default=spec.default,
        enabled=flag.enabled if flag else spec.default,
        rules=FlagRules.model_validate(flag.rules or {}) if flag else FlagRules(),
        changed=flag is not None,
        updated_at=flag.updated_at if flag else None,
        updated_by_email=email,
    )


@router.get("/admin/flags", response_model=list[FlagRead])
async def admin_flags(_: Can("flags.view"), session: DBSession) -> list[FlagRead]:
    return [_flag_read(key, flag, email) for key, flag, email in await services.flags(session)]


@router.put(
    "/admin/flags/{key}",
    response_model=FlagRead,
    dependencies=[audit("flag.update", "feature_flag", "key")],
)
async def set_flag(
    key: str, data: FlagUpdate, admin: Can("flags.manage"), session: DBSession
) -> FlagRead:
    rows = {k: (f, e) for k, f, e in await services.flags(session)}
    before = rows.get(key, (None, None))[0]
    if before is not None:
        note(before={"enabled": before.enabled, "rules": dict(before.rules or {})})
    flag = await services.set_flag(session, admin, key, data)
    note(after=data.model_dump(mode="json"))
    await session.commit()
    await services.flags_saved()
    return _flag_read(key, flag, admin.email)


@router.get("/admin/flags/{key}/check", response_model=FlagCheck)
async def check_flag(
    key: str,
    _: Can("flags.view"),
    session: DBSession,
    email: Annotated[str, Query(min_length=3, max_length=320)],
    mode: Mode | None = None,
) -> FlagCheck:
    """Whether one account gets the flag. Without ``mode``, an approved driver counts as driver."""
    if key not in FLAGS:
        raise services.UnknownFlagError(details={"key": key})
    user = await user_services.get_by_email(session, email.strip().lower())
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    if mode is None:
        approved = await session.scalar(
            select(DriverProfile.id).where(
                DriverProfile.user_id == user.id, DriverProfile.status == DriverStatus.APPROVED
            )
        )
        mode = "driver" if approved else "passenger"
    rows = {k: f for k, f, _ in await services.flags(session)}
    row = rows.get(key)
    raw = {"enabled": row.enabled, "rules": row.rules or {}} if row else None
    enabled = evaluate(key, raw, Audience(ident=str(user.id), role=mode))
    return FlagCheck(email=user.email, role=mode, enabled=enabled)


# --- Admin: announcements ------------------------------------------------------------------------


@router.get("/admin/announcements", response_model=list[AnnouncementAdminRead])
async def admin_announcements(
    _: Can("announcements.view"), session: DBSession
) -> list[AnnouncementAdminRead]:
    rows = await services.announcements(session)
    stats = await services.announcement_stats([a.id for a, _ in rows])
    reads = []
    for item, email in rows:
        read = AnnouncementAdminRead.model_validate(item)
        read.created_by_email = email
        read.seen, read.dismissed = stats.get(item.id, (0, 0))
        reads.append(read)
    return reads


async def _get_announcement(session, announcement_id: uuid.UUID) -> Announcement:
    item = await session.get(Announcement, announcement_id)
    if item is None:
        raise NotFoundError()
    return item


@router.post(
    "/admin/announcements",
    response_model=AnnouncementAdminRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[audit("announcement.create", "announcement")],
)
async def create_announcement(
    data: AnnouncementCreate, admin: Can("announcements.manage"), session: DBSession
) -> AnnouncementAdminRead:
    item = await services.save_announcement(session, data, None, admin)
    note(entity_id=item.id, after=snapshot(item, ANNOUNCEMENT_FIELDS))
    await session.commit()
    await services.announcements_saved()
    read = AnnouncementAdminRead.model_validate(item)
    read.created_by_email = admin.email
    return read


@router.put(
    "/admin/announcements/{announcement_id}",
    response_model=AnnouncementAdminRead,
    dependencies=[audit("announcement.update", "announcement", "announcement_id")],
)
async def update_announcement(
    announcement_id: uuid.UUID,
    data: AnnouncementUpdate,
    admin: Can("announcements.manage"),
    session: DBSession,
) -> AnnouncementAdminRead:
    item = await _get_announcement(session, announcement_id)
    note(before=snapshot(item, ANNOUNCEMENT_FIELDS))
    item = await services.save_announcement(session, data, item, admin)
    note(after=snapshot(item, ANNOUNCEMENT_FIELDS))
    await session.commit()
    await services.announcements_saved()
    read = AnnouncementAdminRead.model_validate(item)
    read.seen, read.dismissed = (await services.announcement_stats([item.id]))[item.id]
    return read


@router.delete(
    "/admin/announcements/{announcement_id}",
    status_code=204,
    dependencies=[audit("announcement.delete", "announcement", "announcement_id")],
)
async def delete_announcement(
    announcement_id: uuid.UUID, _: Can("announcements.manage"), session: DBSession
) -> None:
    item = await _get_announcement(session, announcement_id)
    note(before=snapshot(item, ANNOUNCEMENT_FIELDS))
    await session.delete(item)
    await session.commit()
    await services.announcements_saved()
