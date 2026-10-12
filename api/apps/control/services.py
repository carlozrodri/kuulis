"""Remote control of the app (doc 10): maintenance and city pauses, feature flags, banners and the
bootstrap the app reads at start, every few minutes and on the ``config.updated`` event."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config import services as config_services
from apps.config.models import AppSetting
from apps.config.schemas import AppConfig
from apps.control.flags import FLAGS, Audience, evaluate
from apps.control.models import Announcement, FeatureFlag
from apps.control.schemas import (
    AnnouncementBase,
    AnnouncementRead,
    AppStatus,
    Bootstrap,
    FlagUpdate,
    Notice,
)
from apps.realtime.manager import publish
from apps.releases import services as releases
from apps.users.models import User
from kuulis.core.cache import cache_delete, cached
from kuulis.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from kuulis.core.redis import redis_client
from kuulis.settings import settings

FLAGS_CACHE = "control:flags"
ANNOUNCEMENTS_CACHE = "control:announcements"
CACHE_SECONDS = 30
REFRESH_SECONDS = 300  # the app re-reads the bootstrap this often (and on config.updated)
CONFIG_UPDATED = "config.updated"


class ServicePausedError(AppError):
    status_code = 503
    code = "service_paused"
    message = "New rides are paused here for now"
    planned = True


class FeatureDisabledError(PermissionDeniedError):
    code = "feature_disabled"
    message = "This feature is turned off"


class UnknownFlagError(NotFoundError):
    code = "flag_not_found"
    message = "Unknown feature flag"


class InvalidAreaError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Unknown service area"


def utcnow() -> datetime:
    return datetime.now(UTC)


async def changed() -> None:
    """Tells every open app to read the bootstrap again."""
    await publish(CONFIG_UPDATED, {"at": utcnow().isoformat()})


# --- Maintenance and city pauses -----------------------------------------------------------------


def notice(config: AppConfig, area: str | None) -> Notice | None:
    found = config.notice_for(area)
    if found is None:
        return None
    kind, pause = found
    return Notice(kind=kind, area=area, message=pause.message, eta=pause.eta)


def ensure_open(config: AppConfig, area: str | None) -> None:
    """Raises 503 ``service_paused`` when new rides are stopped in ``area`` (quote, request and
    going online call it; rides already under way are not affected)."""
    found = notice(config, area)
    if found is not None:
        raise ServicePausedError(details=found.model_dump(mode="json"))


def _check_areas(config: AppConfig, names: list[str]) -> None:
    known = {a.name for a in config.service_areas}
    unknown = sorted(set(names) - known)
    if unknown:
        raise InvalidAreaError(details={"areas": unknown, "known": sorted(known)})


async def set_status(session: AsyncSession, data: AppStatus) -> AppConfig:
    """Saves maintenance and the city pauses. The caller commits, then calls ``status_saved``."""
    config = await config_services.get_app_config(session)
    pauses = [p.area for p in data.area_pauses]
    if len(set(pauses)) != len(pauses):
        raise InvalidAreaError("One pause per city", details={"areas": pauses})
    _check_areas(config, data.maintenance.areas + pauses)
    values = data.model_dump(mode="json")
    for key in ("maintenance", "area_pauses"):
        stmt = insert(AppSetting).values(key=key, value=values[key])
        await session.execute(
            stmt.on_conflict_do_update(index_elements=[AppSetting.key], set_={"value": values[key]})
        )
    return AppConfig.model_validate(config.model_dump() | data.model_dump())


async def status_saved() -> None:
    await config_services.invalidate_cache()
    await changed()


# --- Feature flags -------------------------------------------------------------------------------


async def _flag_rows(session: AsyncSession) -> dict[str, dict]:
    async def load() -> dict[str, dict]:
        rows = await session.scalars(select(FeatureFlag))
        return {r.key: {"enabled": r.enabled, "rules": r.rules or {}} for r in rows}

    return await cached(FLAGS_CACHE, load, ttl=CACHE_SECONDS)


async def flags_for(session: AsyncSession, who: Audience) -> dict[str, bool]:
    rows = await _flag_rows(session)
    return {key: evaluate(key, rows.get(key), who) for key in FLAGS}


async def is_enabled(session: AsyncSession, key: str, who: Audience) -> bool:
    return evaluate(key, (await _flag_rows(session)).get(key), who)


async def ensure_enabled(session: AsyncSession, key: str, who: Audience) -> None:
    if not await is_enabled(session, key, who):
        raise FeatureDisabledError(details={"feature": key})


async def flags(session: AsyncSession) -> list[tuple[str, FeatureFlag | None, str | None]]:
    """Every known flag with its row (None while it follows the default) and who changed it."""
    rows = (
        await session.execute(
            select(FeatureFlag, User.email).outerjoin(User, User.id == FeatureFlag.updated_by_id)
        )
    ).all()
    by_key = {flag.key: (flag, email) for flag, email in rows}
    return [(key, *by_key.get(key, (None, None))) for key in FLAGS]


async def set_flag(session: AsyncSession, admin: User, key: str, data: FlagUpdate) -> FeatureFlag:
    if key not in FLAGS:
        raise UnknownFlagError(details={"key": key})
    if data.rules.areas:
        _check_areas(await config_services.get_app_config(session), data.rules.areas)
    flag = await session.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
    if flag is None:
        flag = FeatureFlag(key=key)
        session.add(flag)
    flag.enabled = data.enabled
    flag.rules = data.rules.model_dump(mode="json")
    flag.updated_by_id = admin.id
    flag.updated_at = utcnow()
    await session.flush()
    return flag


async def flags_saved() -> None:
    await cache_delete(FLAGS_CACHE)
    await changed()


# --- Announcements -------------------------------------------------------------------------------


def _seen_key(announcement_id: uuid.UUID | str) -> str:
    return f"{settings.APP_ENV}:announcement:{announcement_id}:seen"


def _dismissed_key(announcement_id: uuid.UUID | str) -> str:
    return f"{settings.APP_ENV}:announcement:{announcement_id}:dismissed"


# The counters outlive the banner so the admin can still see its reach afterwards.
STATS_KEEP = timedelta(days=90)


async def _live(session: AsyncSession) -> list[dict]:
    """Banners showing now or starting within a day (filtered by time on each read, so a
    scheduled banner shows at its time even though this list is cached)."""

    async def load() -> list[dict]:
        now = utcnow()
        rows = await session.scalars(
            select(Announcement)
            .where(Announcement.ends_at > now, Announcement.starts_at <= now + timedelta(days=1))
            .order_by(Announcement.starts_at.desc())
        )
        return [AnnouncementRead.model_validate(r).model_dump(mode="json") for r in rows]

    return await cached(ANNOUNCEMENTS_CACHE, load, ttl=CACHE_SECONDS)


def _targets(item: AnnouncementRead, who: Audience) -> bool:
    roles, areas = item.target.roles, item.target.areas
    if roles and who.role not in roles:
        return False
    return not areas or who.area in areas


async def announcements_for(session: AsyncSession, who: Audience) -> list[AnnouncementRead]:
    now = utcnow()
    items = [
        item
        for item in map(AnnouncementRead.model_validate, await _live(session))
        if item.starts_at <= now < item.ends_at and _targets(item, who)
    ]
    if not items or who.ident is None:
        return items
    async with redis_client.pipeline(transaction=False) as pipe:
        for item in items:
            pipe.sismember(_dismissed_key(item.id), who.ident)
        dismissed = await pipe.execute()
    shown = [item for item, gone in zip(items, dismissed, strict=True) if not gone]
    async with redis_client.pipeline(transaction=False) as pipe:
        for item in shown:
            pipe.pfadd(_seen_key(item.id), who.ident)
            pipe.expireat(_seen_key(item.id), item.ends_at + STATS_KEEP)
        await pipe.execute()
    return shown


async def dismiss(session: AsyncSession, announcement_id: uuid.UUID, ident: str) -> None:
    item = await session.get(Announcement, announcement_id)
    if item is None:
        raise NotFoundError()
    if not item.dismissible:
        raise AppError("This announcement cannot be closed", code="not_dismissible")
    key = _dismissed_key(item.id)
    await redis_client.sadd(key, ident)
    await redis_client.expireat(key, item.ends_at + STATS_KEEP)


async def announcement_stats(ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    if not ids:
        return {}
    async with redis_client.pipeline(transaction=False) as pipe:
        for item_id in ids:
            pipe.pfcount(_seen_key(item_id))
            pipe.scard(_dismissed_key(item_id))
        values = await pipe.execute()
    return {item_id: (values[2 * i], values[2 * i + 1]) for i, item_id in enumerate(ids)}


async def announcements(session: AsyncSession) -> list[tuple[Announcement, str | None]]:
    rows = await session.execute(
        select(Announcement, User.email)
        .outerjoin(User, User.id == Announcement.created_by_id)
        .order_by(Announcement.starts_at.desc())
        .limit(200)
    )
    return [(a, email) for a, email in rows.all()]


async def save_announcement(
    session: AsyncSession, data: AnnouncementBase, item: Announcement | None, admin: User
) -> Announcement:
    if data.target.areas:
        _check_areas(await config_services.get_app_config(session), data.target.areas)
    values = data.model_dump(mode="json")
    if item is None:
        item = Announcement(created_by_id=admin.id)
        session.add(item)
    item.title = values["title"]
    item.body = values["body"]
    item.target = values["target"]
    item.cta = values["cta"]
    item.starts_at = data.starts_at
    item.ends_at = data.ends_at
    item.dismissible = data.dismissible
    item.style = data.style
    await session.flush()
    return item


async def announcements_saved() -> None:
    await cache_delete(ANNOUNCEMENTS_CACHE)
    await changed()


# --- Bootstrap -----------------------------------------------------------------------------------


async def bootstrap(
    session: AsyncSession,
    user: User | None,
    *,
    mode: str | None,
    platform: str | None,
    build: int | None,
    channel: str | None,
    lat: float | None,
    lng: float | None,
    client_id: str | None,
) -> Bootstrap:
    config = await config_services.get_app_config(session)
    place = config.area_at(lat, lng) if lat is not None and lng is not None else None
    area = place.name if place else None
    who = Audience(
        ident=str(user.id) if user else client_id,
        role=mode,
        platform=platform,
        build=build,
        area=area,
    )
    paused = [n for a in config.service_areas if (n := notice(config, a.name)) is not None]
    minimum = 0
    if platform in releases.PLATFORMS:
        if channel not in ("qa", "beta", "production"):
            channel = releases.default_channel()
        minimum = await releases.minimum_build(session, platform, channel)
    return Bootstrap(
        area=area,
        maintenance=notice(config, None),
        paused_areas=paused,
        service=notice(config, area),
        flags=await flags_for(session, who),
        announcements=await announcements_for(session, who),
        links=config.app_links,
        location_intervals=config.location_intervals,
        min_build=minimum,
        refresh_seconds=REFRESH_SECONDS,
    )
