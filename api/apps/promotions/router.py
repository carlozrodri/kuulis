import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from apps.config.services import get_app_config
from apps.promotions import services
from apps.promotions.schemas import (
    PairAlert,
    PromotionCreate,
    PromotionRead,
    PromotionRide,
    PromotionStatus,
    PromotionUpdate,
)
from apps.users.dependencies import AdminUser, DBSession, StaffUser
from kuulis.core.pagination import Page, PageParams, page_params

admin_router = APIRouter(prefix="/admin/promotions", tags=["promotions"])


@admin_router.get("", response_model=Page[PromotionRead])
async def list_promotions(
    _: StaffUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status: Annotated[PromotionStatus | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[PromotionRead]:
    items, total = await services.list_promotions(session, status, q, params)
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@admin_router.post("", response_model=PromotionRead, status_code=201)
async def create(data: PromotionCreate, user: AdminUser, session: DBSession) -> PromotionRead:
    promotion = await services.create(session, user, data, await get_app_config(session))
    await session.commit()
    await session.refresh(promotion)
    return await services.read(session, promotion)


# Before /{promotion_id} so "alerts" is not parsed as an id.
@admin_router.get("/alerts", response_model=list[PairAlert])
async def alerts(_: StaffUser, session: DBSession) -> list[PairAlert]:
    return await services.pair_alerts(session, await get_app_config(session))


@admin_router.get("/{promotion_id}", response_model=PromotionRead)
async def detail(promotion_id: uuid.UUID, _: StaffUser, session: DBSession) -> PromotionRead:
    return await services.read(session, await services.get_or_404(session, promotion_id))


@admin_router.patch("/{promotion_id}", response_model=PromotionRead)
async def update(
    promotion_id: uuid.UUID, data: PromotionUpdate, _: AdminUser, session: DBSession
) -> PromotionRead:
    promotion = await services.get_or_404(session, promotion_id)
    promotion = await services.update(session, promotion, data, await get_app_config(session))
    await session.commit()
    await session.refresh(promotion)
    return await services.read(session, promotion)


@admin_router.get("/{promotion_id}/rides", response_model=Page[PromotionRide])
async def rides(
    promotion_id: uuid.UUID,
    _: StaffUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[PromotionRide]:
    await services.get_or_404(session, promotion_id)
    items, total = await services.rides(session, promotion_id, params)
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)
