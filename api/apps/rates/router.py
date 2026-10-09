from typing import Annotated

from fastapi import APIRouter, Depends, Query

from apps.rates import services
from apps.rates.models import RateSource
from apps.rates.schemas import (
    CurrentRates,
    ExchangeRateHistory,
    ExchangeRateRead,
    ManualRate,
    RefreshRequest,
)
from apps.users.dependencies import AdminUser, DBSession, StaffUser
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(tags=["rates"])


@router.get("/rates", response_model=CurrentRates)
async def current(session: DBSession) -> CurrentRates:
    """Bolívares per USD at the BCV and Binance rates (public: shown before login too)."""
    return await services.current_rates(session)


@router.get("/admin/rates/history", response_model=Page[ExchangeRateHistory])
async def history(
    _: StaffUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    source: Annotated[RateSource | None, Query()] = None,
) -> Page[ExchangeRateHistory]:
    items, total = await services.history(session, source, params)
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@router.post("/admin/rates", response_model=ExchangeRateRead, status_code=201)
async def set_manual(data: ManualRate, user: AdminUser, session: DBSession) -> ExchangeRateRead:
    rate = await services.set_manual(session, user, data.source, data.rate, data.note)
    await session.commit()
    await services.after_manual(session, data.source)
    return rate


@router.post("/admin/rates/refresh", response_model=CurrentRates)
async def refresh(data: RefreshRequest, _: AdminUser, session: DBSession) -> CurrentRates:
    return await services.refresh(session, data.source)
