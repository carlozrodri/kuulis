from typing import Annotated

from fastapi import APIRouter, Query

from apps.config.services import get_app_config
from apps.geo import clients
from apps.geo.schemas import GeoResult
from apps.users.dependencies import CurrentUser, DBSession

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/search", response_model=list[GeoResult])
async def search(
    _: CurrentUser,
    session: DBSession,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> list[GeoResult]:
    """Address search limited to the service area (biased to ``lat/lng`` when given)."""
    config = await get_app_config(session)
    return await clients.search(q, config.service_area, lat, lng)


@router.get("/reverse", response_model=GeoResult)
async def reverse(
    _: CurrentUser,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
) -> GeoResult:
    return await clients.reverse(lat, lng)
