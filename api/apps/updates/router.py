import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Response

from apps.audit.services import audit, note, snapshot
from apps.releases.schemas import Channel
from apps.releases.services import PLATFORMS, default_channel
from apps.updates import services
from apps.updates.models import AppUpdate
from apps.updates.schemas import (
    AdminUpdateRead,
    CandidateRead,
    UpdatePatch,
    UpdatePublish,
    UpdateUsage,
)
from apps.users.dependencies import Can, DBSession
from kuulis.core.redis import redis_client

router = APIRouter(tags=["updates"])

AUDIT_FIELDS = ("channel", "runtime_version", "kind", "commit", "rollout_percent", "withdrawn_at")
CHANNELS = ("qa", "beta", "production")


@router.get("/updates/manifest", include_in_schema=False)
async def update_manifest(
    session: DBSession,
    expo_platform: Annotated[str | None, Header()] = None,
    expo_runtime_version: Annotated[str | None, Header()] = None,
    expo_channel_name: Annotated[str | None, Header()] = None,
    expo_expect_signature: Annotated[str | None, Header()] = None,
    eas_client_id: Annotated[str | None, Header()] = None,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """Expo Updates protocol v1: the newest update for this binary, or 204 when there is none.

    Answers ``multipart/mixed`` (what expo-updates asks for), which also carries the
    ``rollBackToEmbedded`` directive. The body is signed when the app expects a signature."""
    if expo_platform not in PLATFORMS or not expo_runtime_version:
        raise services.UpdateRequestError()
    channel = expo_channel_name if expo_channel_name in CHANNELS else default_channel()
    headers = {
        "expo-protocol-version": "1",
        "expo-sfv-version": "0",
        "cache-control": "private, max-age=0",
    }
    update = await services.select_update(
        session, expo_platform, channel, expo_runtime_version[:64], eas_client_id
    )
    if update is None:
        return Response(status_code=204, headers=headers)
    part = services.response_part(update, signed=expo_expect_signature is not None)
    if accept and "multipart/mixed" not in accept and "*/*" not in accept:
        if part[0] != "manifest":
            return Response(status_code=406, headers=headers)
        if part[2]:
            headers["expo-signature"] = part[2]
        return Response(part[1], media_type="application/expo+json", headers=headers)
    body, boundary = services.multipart([part])
    return Response(body, media_type=f"multipart/mixed; boundary={boundary}", headers=headers)


# --- Admin panel endpoints ---------------------------------------------------------------------


def _admin_read(update: AppUpdate, email: str | None = None) -> AdminUpdateRead:
    read = AdminUpdateRead.model_validate(update)
    read.published_by_email = email
    return read


@router.get("/admin/app/updates", response_model=list[AdminUpdateRead])
async def admin_updates(
    _: Can("releases.view"), session: DBSession, channel: Channel | None = None
) -> list[AdminUpdateRead]:
    return [_admin_read(u, email) for u, email in await services.updates(session, channel)]


@router.get("/admin/app/update-candidates", response_model=list[CandidateRead])
async def admin_candidates(_: Can("releases.view"), session: DBSession) -> list[CandidateRead]:
    """Updates the compiler exported for this environment, newest first."""
    return await services.candidates(session)


@router.get("/admin/app/update-usage", response_model=list[UpdateUsage])
async def admin_update_usage(_: Can("releases.view")) -> list[UpdateUsage]:
    return await services.usage(redis_client)


@router.post(
    "/admin/app/updates",
    response_model=AdminUpdateRead,
    status_code=201,
    dependencies=[audit("app_update.publish", "app_update")],
)
async def publish_update(
    data: UpdatePublish, admin: Can("releases.manage"), session: DBSession
) -> AdminUpdateRead:
    update = await services.publish(session, admin, data)
    await session.commit()
    note(entity_id=update.id, after=snapshot(update, AUDIT_FIELDS))
    return _admin_read(update, admin.email)


@router.patch(
    "/admin/app/updates/{update_id}",
    response_model=AdminUpdateRead,
    dependencies=[audit("app_update.update", "app_update", "update_id")],
)
async def change_update(
    update_id: uuid.UUID, data: UpdatePatch, _: Can("releases.manage"), session: DBSession
) -> AdminUpdateRead:
    existing = await session.get(AppUpdate, update_id)
    before = snapshot(existing, AUDIT_FIELDS) if existing else None
    update = await services.update(session, update_id, data)
    await session.commit()
    note(before=before, after=snapshot(update, AUDIT_FIELDS))
    return _admin_read(update)


@router.post(
    "/admin/app/updates/{update_id}/revert",
    response_model=AdminUpdateRead,
    status_code=201,
    dependencies=[audit("app_update.revert", "app_update", "update_id")],
)
async def revert_update(
    update_id: uuid.UUID, admin: Can("releases.manage"), session: DBSession
) -> AdminUpdateRead:
    """Withdraws the update; the apps go back to the previous one (or to the APK's own code)."""
    replacement = await services.revert(session, admin, update_id)
    await session.commit()
    note(after=snapshot(replacement, AUDIT_FIELDS))
    return _admin_read(replacement, admin.email)
