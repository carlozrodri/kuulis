import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials

from apps.analytics import events, product, services
from apps.analytics.schemas import (
    DriverEconomics,
    FinanceSummary,
    Funnels,
    Metrics,
    Overview,
    PromotionRow,
    Retention,
    SupplyDemand,
)
from apps.audit.services import audit
from apps.config.services import get_app_config
from apps.users.dependencies import Can, DBSession, bearer
from apps.wallet.models import EntryKind, TopUpStatus
from kuulis.core.calendar import parse_month
from kuulis.core.exceptions import AppError
from kuulis.core.rate_limit import limiter
from kuulis.core.security import decode_token

router = APIRouter(prefix="/admin", tags=["analytics"])
events_router = APIRouter(prefix="/analytics", tags=["analytics"])

From = Annotated[date | None, Query(alias="from")]
To = Annotated[date | None, Query(alias="to")]


def _csv_response(body: str, name: str, first: date, last: date) -> Response:
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="kuulis-{name}-{first}_{last}.csv"'},
    )


@router.get("/finance/summary", response_model=FinanceSummary)
async def finance_summary(
    _: Can("finance.view"), session: DBSession, first: From = None, last: To = None
) -> FinanceSummary:
    first, last = services.check_range(first, last)
    return await services.finance_summary(session, first, last)


@router.get(
    "/finance/entries.csv",
    dependencies=[audit("finance.export_entries", "finance")],
    response_class=Response,
)
async def entries_csv(
    _: Can("finance.export"),
    session: DBSession,
    first: From = None,
    last: To = None,
    kind: EntryKind | None = None,
) -> Response:
    first, last = services.check_range(first, last)
    body = await services.entries_csv(session, first, last, kind)
    return _csv_response(body, "movimientos", first, last)


@router.get(
    "/finance/top-ups.csv",
    dependencies=[audit("finance.export_top_ups", "finance")],
    response_class=Response,
)
async def top_ups_csv(
    _: Can("finance.export"),
    session: DBSession,
    first: From = None,
    last: To = None,
    status: TopUpStatus | None = None,
) -> Response:
    first, last = services.check_range(first, last)
    body = await services.top_ups_csv(session, first, last, status)
    return _csv_response(body, "recargas", first, last)


@router.get("/metrics", response_model=Metrics)
async def metrics(
    _: Can("dashboard.view"),
    session: DBSession,
    first: From = None,
    last: To = None,
    area: Annotated[str | None, Query(max_length=60)] = None,
) -> Metrics:
    first, last = services.check_range(first, last)
    config = await get_app_config(session)
    return await services.metrics(session, first, last, services.find_area(config, area))


@router.get("/overview", response_model=Overview)
async def overview(_: Can("dashboard.view"), session: DBSession) -> Overview:
    return await services.overview(session)


# --- Product analytics (doc 19) ----------------------------------------------------------------


def _user_id(credentials: HTTPAuthorizationCredentials | None) -> uuid.UUID | None:
    if credentials is None:
        return None
    try:
        return uuid.UUID(str(decode_token(credentials.credentials, "access").get("sub")))
    except Exception:  # an expired token still sends the batch, as an anonymous one
        return None


@events_router.post(
    "/events", response_model=events.BatchResult, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("30/minute")
async def post_events(
    request: Request,
    data: events.EventBatch,
    session: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> events.BatchResult:
    """A batch of app events (up to 100). Never fails because of an unknown event or property:
    those are dropped and counted in ``dropped``."""
    config = await get_app_config(session)
    result = await events.ingest(session, data, _user_id(credentials), config)
    await session.commit()
    return result


class MonthInvalidError(AppError):
    status_code = 422
    code = "month_invalid"
    message = "Expected a month as YYYY-MM"


def _month(value: str | None) -> date:
    if not value:
        return product.default_month()
    try:
        return parse_month(value)
    except ValueError as exc:
        raise MonthInvalidError() from exc


Area = Annotated[str | None, Query(max_length=60)]
Hour = Annotated[int | None, Query(ge=0, le=23)]
MonthQuery = Annotated[str | None, Query(max_length=7)]


@router.get("/analytics/funnels", response_model=Funnels)
async def analytics_funnels(
    _: Can("analytics.view"),
    session: DBSession,
    first: From = None,
    last: To = None,
    area: Area = None,
) -> Funnels:
    first, last = services.check_range(first, last)
    config = await get_app_config(session)
    return await product.funnels(session, first, last, services.find_area(config, area))


@router.get("/analytics/retention", response_model=Retention)
async def analytics_retention(
    _: Can("analytics.view"),
    session: DBSession,
    first: From = None,
    last: To = None,
    area: Area = None,
) -> Retention:
    first, last = services.check_range(first, last)
    config = await get_app_config(session)
    return await product.retention(session, first, last, services.find_area(config, area))


@router.get("/analytics/supply-demand", response_model=SupplyDemand)
async def analytics_supply_demand(
    _: Can("analytics.view"),
    session: DBSession,
    first: From = None,
    last: To = None,
    area: Area = None,
    hour: Hour = None,
) -> SupplyDemand:
    first, last = services.check_range(first, last)
    config = await get_app_config(session)
    return await product.supply_demand(session, first, last, services.find_area(config, area), hour)


@router.get("/analytics/promotions", response_model=list[PromotionRow])
async def analytics_promotions(
    _: Can("analytics.view"), session: DBSession, first: From = None, last: To = None
) -> list[PromotionRow]:
    first, last = services.check_range(first, last)
    return await product.promotions(session, first, last)


@router.get("/analytics/drivers", response_model=DriverEconomics)
async def analytics_drivers(
    _: Can("analytics.view"), session: DBSession, month: MonthQuery = None, area: Area = None
) -> DriverEconomics:
    config = await get_app_config(session)
    return await product.drivers(session, _month(month), services.find_area(config, area))


@router.post(
    "/analytics/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[audit("analytics.refresh", "analytics")],
)
@limiter.limit("3/minute")
async def analytics_refresh(request: Request, _: Can("analytics.view")) -> dict[str, str]:
    """Recomputes funnels and retention now instead of waiting for the daily run."""
    from apps.analytics.tasks import refresh

    await refresh.kiq()
    return {"status": "queued"}


Report = Literal["funnels", "retention", "supply-demand", "promotions", "drivers"]


@router.get(
    "/analytics/{report}.csv",
    dependencies=[audit("analytics.export", "analytics")],
    response_class=Response,
)
async def analytics_csv(
    report: Report,
    _: Can("analytics.export"),
    session: DBSession,
    first: From = None,
    last: To = None,
    area: Area = None,
    hour: Hour = None,
    month: MonthQuery = None,
) -> Response:
    """Aggregated tables only (no person appears in them)."""
    config = await get_app_config(session)
    where = services.find_area(config, area)
    if report == "drivers":
        chosen = _month(month)
        body = product.drivers_csv(await product.drivers(session, chosen, where))
        return _csv_response(body, f"analitica-{report}", chosen, chosen)
    first, last = services.check_range(first, last)
    if report == "funnels":
        body = product.funnels_csv(await product.funnels(session, first, last, where))
    elif report == "retention":
        body = product.retention_csv(await product.retention(session, first, last, where))
    elif report == "supply-demand":
        data = await product.supply_demand(session, first, last, where, hour)
        body = product.supply_demand_csv(data)
    else:
        body = product.promotions_csv(await product.promotions(session, first, last))
    return _csv_response(body, f"analitica-{report}", first, last)
