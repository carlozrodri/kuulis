from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response

from apps.analytics import services
from apps.analytics.schemas import FinanceSummary, Metrics, Overview
from apps.config.services import get_app_config
from apps.users.dependencies import DBSession, StaffUser
from apps.wallet.models import EntryKind, TopUpStatus

router = APIRouter(prefix="/admin", tags=["analytics"])

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
    _: StaffUser, session: DBSession, first: From = None, last: To = None
) -> FinanceSummary:
    first, last = services.check_range(first, last)
    return await services.finance_summary(session, first, last)


@router.get("/finance/entries.csv", response_class=Response)
async def entries_csv(
    _: StaffUser,
    session: DBSession,
    first: From = None,
    last: To = None,
    kind: EntryKind | None = None,
) -> Response:
    first, last = services.check_range(first, last)
    body = await services.entries_csv(session, first, last, kind)
    return _csv_response(body, "movimientos", first, last)


@router.get("/finance/top-ups.csv", response_class=Response)
async def top_ups_csv(
    _: StaffUser,
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
    _: StaffUser,
    session: DBSession,
    first: From = None,
    last: To = None,
    area: Annotated[str | None, Query(max_length=60)] = None,
) -> Metrics:
    first, last = services.check_range(first, last)
    config = await get_app_config(session)
    return await services.metrics(session, first, last, services.find_area(config, area))


@router.get("/overview", response_model=Overview)
async def overview(_: StaffUser, session: DBSession) -> Overview:
    return await services.overview(session)
