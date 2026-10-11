"""APK releases and the installed apps' version check (doc 09).

The compiler (``mobile/builder``) uploads every APK to ``builds/<APP_ENV>/`` next to a small JSON
file with its version, build number and hashes. Publishing one from the admin creates an
``AppRelease`` for a channel; the apps ask ``GET /app/version`` which release is the newest and
the minimum build they need. Which builds are in use is counted per day in Redis (HyperLogLog
of user ids, sent by the app in headers on ``GET /users/me``).
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.releases.models import AppRelease
from apps.releases.schemas import BuildRead, ReleaseCreate, ReleaseUpdate, VersionUsage
from apps.users.models import User
from kuulis.core import storage
from kuulis.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from kuulis.settings import settings

logger = logging.getLogger(__name__)

PLATFORMS = ("android",)
DOWNLOAD_LINK_SECONDS = 3600
USAGE_DAYS = 7


class UpdateRequiredError(AppError):
    status_code = 426
    code = "app_update_required"
    message = "This version of the app is too old; update it to continue"


class BuildNotFoundError(NotFoundError):
    code = "build_not_found"
    message = "That build is not in storage"


class ReleaseExistsError(ConflictError):
    code = "release_exists"
    message = "That build is already published in this channel"


def default_channel() -> str:
    return "production" if settings.APP_ENV == "production" else "qa"


def builds_prefix() -> str:
    """Where this environment's compiler leaves its APKs (``builds/qa/``)."""
    return f"builds/{settings.APP_ENV}/"


async def _current(session: AsyncSession, platform: str, channel: str) -> list[AppRelease]:
    rows = await session.scalars(
        select(AppRelease)
        .where(
            AppRelease.platform == platform,
            AppRelease.channel == channel,
            AppRelease.withdrawn_at.is_(None),
        )
        .order_by(AppRelease.build.desc())
    )
    return list(rows)


async def latest(session: AsyncSession, platform: str, channel: str) -> AppRelease | None:
    releases = await _current(session, platform, channel)
    return releases[0] if releases else None


async def minimum_build(session: AsyncSession, platform: str, channel: str) -> int:
    """Builds below this one must update: the newest mandatory release still offered."""
    value = await session.scalar(
        select(func.max(AppRelease.build)).where(
            AppRelease.platform == platform,
            AppRelease.channel == channel,
            AppRelease.is_mandatory.is_(True),
            AppRelease.withdrawn_at.is_(None),
        )
    )
    return int(value or 0)


def download_url(release: AppRelease) -> str | None:
    """A link valid for an hour; None when storage is off (local development, tests)."""
    try:
        return storage.presigned_download(release.file_key, DOWNLOAD_LINK_SECONDS)
    except ServiceUnavailableError:
        return None


async def ensure_up_to_date(
    session: AsyncSession, platform: str | None, build: str | None, channel: str | None
) -> None:
    """Raises 426 app_update_required when an app that says its build is below the minimum.

    Apps that send no build (the website, very old APKs) are let through.
    """
    if platform not in PLATFORMS or not build or not build.isdigit():
        return
    if channel not in ("qa", "beta", "production"):
        channel = default_channel()
    minimum = await minimum_build(session, platform, channel)
    if int(build) < minimum:
        raise UpdateRequiredError(details={"minimum_build": minimum})


# --- Builds uploaded by the compiler -------------------------------------------------------------


def _read_build(key: str) -> BuildRead:
    data = json.loads(storage.get_object_bytes(key))
    return BuildRead.model_validate({**data, "key": key})


def _list_builds(limit: int) -> list[BuildRead]:
    builds: list[BuildRead] = []
    for obj in storage.list_objects(builds_prefix(), limit=500):
        if not obj["Key"].endswith(".json"):
            continue
        try:
            builds.append(_read_build(obj["Key"]))
        except Exception:
            logger.warning("Unreadable build metadata %s", obj["Key"], exc_info=True)
        if len(builds) >= limit:
            break
    return builds


async def builds(session: AsyncSession, limit: int = 20) -> list[BuildRead]:
    try:
        found = await asyncio.to_thread(_list_builds, limit)
    except ServiceUnavailableError:
        raise
    except Exception as exc:
        logger.warning("Could not list builds", exc_info=True)
        raise ServiceUnavailableError(
            "Storage is not answering", code="storage_unavailable"
        ) from exc
    published = await session.execute(
        select(AppRelease.build, AppRelease.channel).where(AppRelease.withdrawn_at.is_(None))
    )
    channels: dict[int, list[str]] = {}
    for build, channel in published:
        channels.setdefault(build, []).append(channel)
    for item in found:
        item.published_channels = sorted(channels.get(item.build, []))
    return found


def _valid_build_key(key: str) -> bool:
    rest = key[len(builds_prefix()) :]
    return key.startswith(builds_prefix()) and key.endswith(".json") and "/" not in rest


async def publish(session: AsyncSession, admin: User, data: ReleaseCreate) -> AppRelease:
    if not _valid_build_key(data.build_key):
        raise BuildNotFoundError()
    try:
        build = await asyncio.to_thread(_read_build, data.build_key)
    except Exception as exc:
        raise BuildNotFoundError() from exc
    file_key = builds_prefix() + build.file_name
    if "/" in build.file_name or not build.file_name.endswith(".apk"):
        raise BuildNotFoundError()
    exists = await session.scalar(
        select(AppRelease).where(
            AppRelease.platform == "android",
            AppRelease.channel == data.channel,
            AppRelease.build == build.build,
        )
    )
    if exists is not None and exists.withdrawn_at is None:
        raise ReleaseExistsError()
    release = exists or AppRelease(platform="android", channel=data.channel, build=build.build)
    release.version = build.version
    release.file_key = file_key
    release.size = build.size
    release.sha256 = build.sha256
    release.md5 = build.md5
    release.notes = data.notes
    release.is_mandatory = data.is_mandatory
    release.published_by_id = admin.id
    release.withdrawn_at = None
    if exists is not None:
        release.created_at = datetime.now(UTC)  # published again: it counts from now
    session.add(release)
    await session.flush()
    return release


async def update(session: AsyncSession, release_id: uuid.UUID, data: ReleaseUpdate) -> AppRelease:
    release = await session.get(AppRelease, release_id)
    if release is None:
        raise NotFoundError()
    changes = data.model_dump(exclude_unset=True)
    if "notes" in changes:
        release.notes = data.notes
    if data.is_mandatory is not None:
        release.is_mandatory = data.is_mandatory
    if data.withdrawn is not None:
        release.withdrawn_at = datetime.now(UTC) if data.withdrawn else None
    await session.flush()
    return release


async def releases(
    session: AsyncSession, channel: str | None = None
) -> list[tuple[AppRelease, str | None]]:
    query = (
        select(AppRelease, User.email)
        .outerjoin(User, User.id == AppRelease.published_by_id)
        .order_by(AppRelease.created_at.desc())
        .limit(100)
    )
    if channel:
        query = query.where(AppRelease.channel == channel)
    return [(r, email) for r, email in await session.execute(query)]


# --- Which builds are in use ---------------------------------------------------------------------


def _usage_key(day: str, platform: str, build: int) -> str:
    return f"{settings.APP_ENV}:appver:{day}:{platform}:{build}"


def _builds_key(day: str) -> str:
    return f"{settings.APP_ENV}:appver:{day}:builds"


async def record_usage(
    redis: Redis, platform: str | None, build: str | None, user_id: uuid.UUID
) -> None:
    if platform not in PLATFORMS or not build or not build.isdigit() or len(build) > 9:
        return
    day = datetime.now(UTC).date().isoformat()
    ttl = (USAGE_DAYS + 1) * 86400
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.pfadd(_usage_key(day, platform, int(build)), user_id.hex)
            pipe.expire(_usage_key(day, platform, int(build)), ttl)
            pipe.sadd(_builds_key(day), f"{platform}:{int(build)}")
            pipe.expire(_builds_key(day), ttl)
            await pipe.execute()
    except Exception:
        logger.warning("Could not record app version usage", exc_info=True)


async def usage(redis: Redis) -> list[VersionUsage]:
    """Distinct users per build over the last 7 days."""
    today = datetime.now(UTC).date()
    days = [(today - timedelta(days=i)).isoformat() for i in range(USAGE_DAYS)]
    seen: set[str] = set()
    for day in days:
        seen |= {
            m.decode() if isinstance(m, bytes) else m
            for m in await redis.smembers(_builds_key(day))
        }
    result = []
    for member in seen:
        platform, build = member.split(":", 1)
        keys = [_usage_key(day, platform, int(build)) for day in days]
        result.append(
            VersionUsage(platform=platform, build=int(build), users=await redis.pfcount(*keys))
        )
    return sorted(result, key=lambda u: (u.platform, -u.build))
