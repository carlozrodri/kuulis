from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from apps.approvals import services as approvals
from apps.approvals.schemas import ApprovalHeld
from apps.audit.services import audit, note, snapshot
from apps.config import services
from apps.config.schemas import AppConfig, AppConfigUpdate, PublicSite
from apps.control import services as control
from apps.users.dependencies import AdminUser, DBSession, StaffUser

router = APIRouter(tags=["config"])

# Settings whose changes need a second approval when ``approval_fares`` is on.
FARE_KEYS = {"fares", "fare_rounding"}


@router.get("/config/public", response_model=AppConfig)
async def public_config(session: DBSession) -> AppConfig:
    return await services.get_app_config(session)


@router.get("/public/site", response_model=PublicSite)
async def public_site(session: DBSession, response: Response) -> PublicSite:
    """What the public website shows (no account needed); browsers and proxies may keep it 5 min."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return await services.public_site(session)


@router.get("/admin/config", response_model=AppConfig)
async def admin_config(_: StaffUser, session: DBSession) -> AppConfig:
    # Every staff page reads its defaults from here; config.view only shows the settings page.
    return await services.get_app_config(session)


@router.patch(
    "/admin/config",
    dependencies=[audit("config.update", "config")],
    response_model=AppConfig,
    responses={202: {"model": ApprovalHeld, "description": "Waiting for a second approval"}},
)
async def update_config(
    data: AppConfigUpdate, admin: AdminUser, session: DBSession
) -> AppConfig | JSONResponse:
    changed = data.model_dump(exclude_unset=True).keys()
    before = await services.get_app_config(session)
    # The admin panel sends the whole object, so only values that really change count.
    after = await services.preview_app_config(session, data)
    real = [k for k in changed if getattr(before, k) != getattr(after, k)]
    fares = sorted(FARE_KEYS & set(real))
    if fares and await approvals.required(session, "config.update"):
        # The whole change waits and is applied as one piece once approved. Only the keys that
        # really change are kept, so approving later does not undo other edits made meanwhile.
        return await approvals.hold(
            session,
            admin,
            "config.update",
            entity_type="config",
            summary="Cambio de tarifas (" + ", ".join(fares) + ")",
            payload=after.model_dump(mode="json", include=set(real)),
        )
    config = await services.update_app_config(session, data)
    note(before=snapshot(before, changed), after=snapshot(config, changed))
    await session.commit()
    await services.invalidate_cache()
    await control.changed()
    return config
