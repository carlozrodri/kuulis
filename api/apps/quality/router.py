import uuid
from dataclasses import asdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from apps.audit.services import audit
from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile
from apps.quality import services
from apps.quality.models import QualityLevel, QualityRole
from apps.quality.schemas import (
    CancellationCount,
    DriverQualityRead,
    DriverThresholds,
    PauseRead,
    QualityDetail,
    QualityRowRead,
    QualityValues,
    QualityWeek,
)
from apps.users.dependencies import Can, CurrentUser, DBSession
from apps.users.models import User
from kuulis.core.calendar import CARACAS_TZ, local_now
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/drivers/me", tags=["quality"])
admin_router = APIRouter(prefix="/admin/quality", tags=["quality"])


@router.get("/quality", response_model=DriverQualityRead)
async def my_quality(user: CurrentUser, session: DBSession) -> DriverQualityRead:
    """The driver's "Mi calidad" panel: live rates, the thresholds that apply and any pause."""
    q = (await get_app_config(session)).quality
    values = (await services.compute(session, QualityRole.DRIVER, q, [user.id]))[user.id]
    pause = await services.active_pause(session, user.id, QualityRole.DRIVER)
    return DriverQualityRead(
        **asdict(values),
        thresholds=DriverThresholds(
            window_days=q.window_days,
            min_rides=q.min_rides,
            cancel_warn=q.driver_cancel_warn,
            cancel_low_priority=q.driver_cancel_low_priority,
            cancel_review=q.driver_cancel_review,
            rating_review_below=q.rating_review_below,
            rating_min_count=q.rating_min_count,
            cancel_burst=q.driver_cancel_burst,
            decline_streak=q.driver_decline_streak,
            pause_minutes=q.driver_pause_minutes,
            pickup_wait_minutes=q.pickup_wait_minutes,
        ),
        paused_until=pause.until if pause else None,
        pause_reason=pause.reason if pause else None,
    )


# --- Admin -------------------------------------------------------------------------------------


@admin_router.get("/users", response_model=Page[QualityRowRead])
async def flagged(
    _: Can("quality.view"),
    session: DBSession,
    params: PageParams = Depends(page_params),
    role: QualityRole = QualityRole.DRIVER,
    level: QualityLevel | None = None,
    q: str | None = Query(default=None, max_length=100),
) -> Page[QualityRowRead]:
    """People below a threshold or paused now, worst first (refreshed every few minutes)."""
    rows, total = await services.list_flagged(session, params, role, level=level, q=q)
    ids = [stats.user_id for stats, _ in rows]
    paused = {p.user_id: p.until for p in await services.active_pauses(session, ids, role)}
    profiles: dict[uuid.UUID, uuid.UUID] = {}
    if role == QualityRole.DRIVER and ids:
        rows_ = await session.execute(
            select(DriverProfile.user_id, DriverProfile.id).where(DriverProfile.user_id.in_(ids))
        )
        profiles = {uid: pid for uid, pid in rows_}
    items = [
        QualityRowRead(
            **QualityValues.model_validate(stats).model_dump(),
            user_id=stats.user_id,
            role=stats.role,
            name=user.full_name or "",
            email=user.email,
            driver_profile_id=profiles.get(stats.user_id),
            computed_at=stats.computed_at,
            paused_until=paused.get(stats.user_id),
        )
        for stats, user in rows
    ]
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@admin_router.get("/users/{user_id}", response_model=QualityDetail)
async def detail(user_id: uuid.UUID, _: Can("quality.view"), session: DBSession) -> QualityDetail:
    """Live rates for both roles, the last weeks and the pause history."""
    if await session.get(User, user_id) is None:
        raise services.UserNotFoundError()
    q = (await get_app_config(session)).quality
    drives = await session.scalar(select(DriverProfile.id).where(DriverProfile.user_id == user_id))
    driver = None
    if drives is not None:
        found = await services.compute(session, QualityRole.DRIVER, q, [user_id])
        driver = QualityValues(**asdict(found[user_id]))
    passenger = (await services.compute(session, QualityRole.PASSENGER, q, [user_id]))[user_id]
    return QualityDetail(
        user_id=user_id,
        driver=driver,
        passenger=QualityValues(**asdict(passenger)),
        weeks=[QualityWeek(**w) for w in await services.weekly(session, user_id)],
        pauses=[PauseRead.model_validate(p) for p in await services.pauses_for(session, user_id)],
        window_days=q.window_days,
    )


@admin_router.get("/cancellations", response_model=list[CancellationCount])
async def cancellations(
    _: Can("quality.view"),
    session: DBSession,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CancellationCount]:
    """Cancellations by side and reason, Caracas days, inclusive (default: the last 30 days)."""
    today = local_now().date()
    last = date_to or today
    first = date_from or last - timedelta(days=29)
    start = datetime.combine(first, time.min, tzinfo=CARACAS_TZ)
    end = datetime.combine(last + timedelta(days=1), time.min, tzinfo=CARACAS_TZ)
    return [
        CancellationCount(
            side=side, reason_code=code, total=total, counted=counted, reassigned=moved
        )
        for side, code, total, counted, moved in await services.cancellations_by_reason(
            session, start, end
        )
    ]


@admin_router.post(
    "/pauses/{pause_id}/lift",
    response_model=PauseRead,
    dependencies=[audit("quality.pause_lift", "quality_pause", "pause_id")],
)
async def lift(pause_id: uuid.UUID, admin: Can("quality.manage"), session: DBSession) -> PauseRead:
    """Ends an automatic pause early (the person can go online or request again)."""
    return PauseRead.model_validate(await services.lift(session, admin, pause_id))
