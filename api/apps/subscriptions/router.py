import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from apps.subscriptions import services
from apps.subscriptions.models import ChargeStatus
from apps.subscriptions.schemas import (
    ChargeAdminRead,
    ChargeRead,
    ChargesPage,
    RunRequest,
    RunResultRead,
    ScheduleCreate,
    ScheduleRead,
    SubscriptionSummary,
    UserBrief,
)
from apps.users.dependencies import AdminUser, CurrentUser, DBSession, StaffUser
from apps.users.models import User
from apps.wallet.schemas import ReasonBody
from kuulis.core.calendar import local_now, month_start, parse_month
from kuulis.core.exceptions import AppError
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/wallet/me", tags=["subscriptions"])
admin_router = APIRouter(prefix="/admin/subscriptions", tags=["subscriptions"])


def _brief(user: User) -> UserBrief:
    return UserBrief(id=user.id, name=user.full_name or "", email=user.email)


def _month_query(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return parse_month(value)
    except ValueError as exc:
        raise AppError("Invalid month", code="validation_error", details={"month": value}) from exc


# --- Driver ------------------------------------------------------------------------------------


@router.get("/subscription", response_model=SubscriptionSummary)
async def my_subscription(user: CurrentUser, session: DBSession) -> SubscriptionSummary:
    data = await services.summary(session, user.id)
    return SubscriptionSummary(
        month=data.month,
        earnings=data.earnings,
        estimated_fee=data.estimated_fee,
        free_until=data.free_until,
        in_free_period=data.in_free_period,
        tiers=data.tiers,
        next_charge_at=data.next_charge_at,
        pending=[services.charge_read(c) for c in data.pending],
        overdue=data.overdue,
        blocked=data.overdue,
    )


@router.get("/charges", response_model=Page[ChargeRead])
async def my_charges(
    user: CurrentUser, session: DBSession, params: Annotated[PageParams, Depends(page_params)]
) -> Page[ChargeRead]:
    rows, total, _ = await services.list_charges(session, params, user_id=user.id)
    return Page(
        items=[services.charge_read(c) for c, _ in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


# --- Admin -------------------------------------------------------------------------------------


@admin_router.get("/charges", response_model=ChargesPage)
async def charges(
    _: StaffUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    month: Annotated[str | None, Query(max_length=7)] = None,
    status: Annotated[ChargeStatus | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> ChargesPage:
    rows, total, totals = await services.list_charges(
        session, params, month=_month_query(month), status=status, q=q
    )
    return ChargesPage(
        items=[
            ChargeAdminRead(**services.charge_read(c).model_dump(), user=_brief(u)) for c, u in rows
        ],
        total=total,
        limit=params.limit,
        offset=params.offset,
        totals=totals,
    )


@admin_router.post("/charges/{charge_id}/waive", response_model=ChargeRead)
async def waive(
    charge_id: uuid.UUID, data: ReasonBody, admin: AdminUser, session: DBSession
) -> ChargeRead:
    charge = await services.waive(session, admin, charge_id, data.reason)
    await session.commit()
    await session.refresh(charge)
    return services.charge_read(charge)


@admin_router.post("/run", response_model=RunResultRead)
async def run(data: RunRequest, _: AdminUser, session: DBSession) -> RunResultRead:
    result = await services.charge_month(session, data.month)
    return RunResultRead(**result.__dict__)


@admin_router.get("/schedules", response_model=list[ScheduleRead])
async def schedules(_: StaffUser, session: DBSession) -> list[ScheduleRead]:
    rows = await services.list_schedules(session)
    authors = {r.created_by_id for _, r in rows if r and r.created_by_id}
    users = {}
    if authors:
        users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(authors)))}
    current_month = month_start(local_now())
    result = []
    for index, (schedule, row) in enumerate(rows):
        author = users.get(row.created_by_id) if row and row.created_by_id else None
        result.append(
            ScheduleRead(
                id=schedule.id,
                effective_month=schedule.effective_month,
                tiers=schedule.tiers,
                current=index == 0 and schedule.effective_month <= current_month,
                created_by=_brief(author) if author else None,
                created_at=row.created_at if row else None,
            )
        )
    return result


@admin_router.post("/schedules", response_model=ScheduleRead, status_code=201)
async def create_schedule(
    data: ScheduleCreate, admin: AdminUser, session: DBSession
) -> ScheduleRead:
    row = await services.create_schedule(session, admin, data.effective_month, data.tiers)
    await session.commit()
    await session.refresh(row)
    return ScheduleRead(
        id=row.id,
        effective_month=row.effective_month,
        tiers=data.tiers,
        current=False,
        created_by=_brief(admin),
        created_at=row.created_at,
    )
