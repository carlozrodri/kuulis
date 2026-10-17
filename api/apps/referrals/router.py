import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status

from apps.audit.services import audit, note
from apps.config import services as config_services
from apps.config.schemas import AppConfigUpdate, ReferralProgram
from apps.config.services import get_app_config
from apps.control import services as control
from apps.referrals import services
from apps.referrals.models import ReferralStatus
from apps.referrals.schemas import (
    PublicCode,
    RankingRow,
    RedeemRequest,
    ReferralAdminRead,
    ReferralsOverview,
    ReferralSummary,
    ReviewWrite,
)
from apps.users.dependencies import Can, CurrentUser, DBSession
from kuulis.core.pagination import Page, PageParams, page_params
from kuulis.core.rate_limit import limiter

router = APIRouter(prefix="/referrals", tags=["referrals"])
admin_router = APIRouter(prefix="/admin/referrals", tags=["referrals"])


@router.get("/me", response_model=ReferralSummary)
async def my_referrals(user: CurrentUser, session: DBSession) -> ReferralSummary:
    result = await services.summary(session, user, await get_app_config(session))
    await session.commit()  # a code created on first read
    return result


@router.post("/redeem", response_model=ReferralSummary, status_code=status.HTTP_200_OK)
async def redeem(data: RedeemRequest, user: CurrentUser, session: DBSession) -> ReferralSummary:
    config = await get_app_config(session)
    await services.redeem(session, user, data.code, config)
    result = await services.summary(session, user, config)
    await session.commit()
    return result


@router.get("/codes/{code}", response_model=PublicCode)
@limiter.limit("30/minute")
async def public_code(
    request: Request,
    session: DBSession,
    code: Annotated[str, Path(min_length=4, max_length=12)],
) -> PublicCode:
    """The web invite page ``/i/{code}`` (no account needed). 404 ``referral_code_invalid``."""
    return await services.public_code(session, code, await get_app_config(session))


# --- Admin -------------------------------------------------------------------------------------


@admin_router.get("/overview", response_model=ReferralsOverview)
async def overview(_: Can("referrals.view"), session: DBSession) -> ReferralsOverview:
    """The program, referrals by status, money paid and held, budget left and open alerts."""
    return await services.overview(session, await get_app_config(session))


@admin_router.get("", response_model=Page[ReferralAdminRead])
async def list_referrals(
    _: Can("referrals.view"),
    session: DBSession,
    params: PageParams = Depends(page_params),
    referral_status: ReferralStatus | None = Query(default=None, alias="status"),
    alerts: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
    user_id: uuid.UUID | None = None,
) -> Page[ReferralAdminRead]:
    """Newest first. ``alerts``: held rewards and unreviewed shared-identity rejections.
    ``user_id``: as inviter or invited."""
    items, total = await services.list_referrals(
        session,
        params,
        await get_app_config(session),
        status=referral_status,
        alerts=alerts,
        q=q,
        user_id=user_id,
    )
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@admin_router.get("/ranking", response_model=list[RankingRow])
async def ranking(
    _: Can("referrals.view"),
    session: DBSession,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[RankingRow]:
    """Who invites the most (rewarded first)."""
    return await services.ranking(session, limit)


@admin_router.put(
    "/program",
    response_model=ReferralProgram,
    dependencies=[audit("referrals.program_update", "config")],
)
async def update_program(
    data: ReferralProgram, _: Can("referrals.manage"), session: DBSession
) -> ReferralProgram:
    before = (await get_app_config(session)).referral_program
    config = await config_services.update_app_config(
        session, AppConfigUpdate(referral_program=data)
    )
    note(
        before=before.model_dump(mode="json"),
        after=config.referral_program.model_dump(mode="json"),
    )
    await session.commit()
    await config_services.invalidate_cache()
    await control.changed()
    return config.referral_program


@admin_router.get("/{referral_id}", response_model=ReferralAdminRead)
async def get_referral(
    referral_id: uuid.UUID, _: Can("referrals.view"), session: DBSession
) -> ReferralAdminRead:
    return await services.get_admin(session, referral_id, await get_app_config(session))


@admin_router.post(
    "/{referral_id}/release",
    response_model=ReferralAdminRead,
    dependencies=[audit("referrals.release", "referral", "referral_id")],
)
async def release(
    referral_id: uuid.UUID, data: ReviewWrite, user: Can("referrals.manage"), session: DBSession
) -> ReferralAdminRead:
    """Pays a held reward, or a qualified one waiting for the monthly cap. 409
    ``referral_budget_exhausted`` when the budget has no room."""
    config = await get_app_config(session)
    await services.release(session, user, referral_id, data.note, config)
    await session.commit()
    return await services.get_admin(session, referral_id, config)


@admin_router.post(
    "/{referral_id}/reject",
    response_model=ReferralAdminRead,
    dependencies=[audit("referrals.reject", "referral", "referral_id")],
)
async def reject(
    referral_id: uuid.UUID, data: ReviewWrite, user: Can("referrals.manage"), session: DBSession
) -> ReferralAdminRead:
    """No reward (an alert that was already rejected is marked as reviewed)."""
    await services.reject(session, user, referral_id, data.note)
    await session.commit()
    return await services.get_admin(session, referral_id, await get_app_config(session))


@admin_router.post(
    "/{referral_id}/reopen",
    response_model=ReferralAdminRead,
    dependencies=[audit("referrals.reopen", "referral", "referral_id")],
)
async def reopen(
    referral_id: uuid.UUID, data: ReviewWrite, user: Can("referrals.manage"), session: DBSession
) -> ReferralAdminRead:
    """A wrong rejection: evaluated again without the shared-identity check (and a new window
    when the old one ended)."""
    config = await get_app_config(session)
    await services.reopen(session, user, referral_id, data.note, config)
    await session.commit()
    return await services.get_admin(session, referral_id, config)
