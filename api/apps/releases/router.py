import uuid

from fastapi import APIRouter, Query, Response
from fastapi.responses import RedirectResponse

from apps.audit.services import audit, note, snapshot
from apps.releases import services
from apps.releases.models import AppRelease
from apps.releases.schemas import (
    AdminReleaseRead,
    BuildRead,
    Channel,
    Platform,
    ReleaseCreate,
    ReleaseRead,
    ReleaseUpdate,
    VersionCheck,
    VersionUsage,
)
from apps.users.dependencies import Can, DBSession
from kuulis.core.exceptions import NotFoundError
from kuulis.core.redis import redis_client

router = APIRouter(tags=["releases"])

AUDIT_FIELDS = ("channel", "version", "build", "is_mandatory", "notes", "withdrawn_at")


def _read(release: AppRelease, with_link: bool = True) -> ReleaseRead:
    read = ReleaseRead.model_validate(release)
    if with_link:
        read.download_url = services.download_url(release)
    return read


@router.get("/app/version", response_model=VersionCheck)
async def version_check(
    session: DBSession,
    response: Response,
    platform: Platform = "android",
    channel: Channel | None = None,
    build: int = Query(default=0, ge=0),
) -> VersionCheck:
    """The newest APK of the channel and the minimum build (no account needed: the website and the
    app before login ask too)."""
    response.headers["Cache-Control"] = "no-store"
    channel = channel or services.default_channel()
    release = await services.latest(session, platform, channel)
    minimum = await services.minimum_build(session, platform, channel)
    return VersionCheck(
        latest=_read(release) if release else None,
        minimum_build=minimum,
        update_available=bool(release and build and release.build > build),
        update_required=bool(build and build < minimum),
    )


@router.get("/app/download", response_class=RedirectResponse, status_code=302)
async def download_latest(
    session: DBSession, platform: Platform = "android", channel: Channel | None = None
) -> RedirectResponse:
    """Stable link for the website's download button: redirects to the newest APK."""
    release = await services.latest(session, platform, channel or services.default_channel())
    url = services.download_url(release) if release else None
    if url is None:
        raise NotFoundError(code="no_release", message="There is no APK published yet")
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


# --- Admin panel endpoints ---------------------------------------------------------------------


def _admin_read(release: AppRelease, email: str | None = None) -> AdminReleaseRead:
    read = AdminReleaseRead.model_validate(release)
    read.published_by_email = email
    return read


@router.get("/admin/app/releases", response_model=list[AdminReleaseRead])
async def admin_releases(
    _: Can("releases.view"), session: DBSession, channel: Channel | None = None
) -> list[AdminReleaseRead]:
    return [_admin_read(r, email) for r, email in await services.releases(session, channel)]


@router.get("/admin/app/builds", response_model=list[BuildRead])
async def admin_builds(_: Can("releases.view"), session: DBSession) -> list[BuildRead]:
    """APKs the compiler uploaded for this environment, newest first."""
    return await services.builds(session)


@router.get("/admin/app/usage", response_model=list[VersionUsage])
async def admin_usage(_: Can("releases.view")) -> list[VersionUsage]:
    return await services.usage(redis_client)


@router.post(
    "/admin/app/releases",
    response_model=AdminReleaseRead,
    status_code=201,
    dependencies=[audit("app_release.publish", "app_release")],
)
async def publish_release(
    data: ReleaseCreate, admin: Can("releases.manage"), session: DBSession
) -> AdminReleaseRead:
    release = await services.publish(session, admin, data)
    await session.commit()
    note(entity_id=release.id, after=snapshot(release, AUDIT_FIELDS))
    return _admin_read(release, admin.email)


@router.patch(
    "/admin/app/releases/{release_id}",
    response_model=AdminReleaseRead,
    dependencies=[audit("app_release.update", "app_release", "release_id")],
)
async def update_release(
    release_id: uuid.UUID, data: ReleaseUpdate, _: Can("releases.manage"), session: DBSession
) -> AdminReleaseRead:
    existing = await session.get(AppRelease, release_id)
    before = snapshot(existing, AUDIT_FIELDS) if existing else None
    release = await services.update(session, release_id, data)
    await session.commit()
    note(before=before, after=snapshot(release, AUDIT_FIELDS))
    return _admin_read(release)
