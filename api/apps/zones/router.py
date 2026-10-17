import uuid
from typing import Any

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from apps.audit.services import audit
from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile, DriverStatus
from apps.rides.state import DriverNotApprovedError
from apps.users.dependencies import Can, CurrentUser, DBSession
from apps.zones import demand, services
from apps.zones.models import ZoneKind
from apps.zones.schemas import (
    CityPolygonWrite,
    CityRead,
    DemandSnapshot,
    ImportResult,
    ImportWrite,
    SimulateWrite,
    ZoneCheck,
    ZoneRead,
    ZoneUpdate,
    ZoneWrite,
)
from kuulis.core.exceptions import NotFoundError
from kuulis.settings import settings

router = APIRouter(tags=["zones"])
admin_router = APIRouter(prefix="/admin/zones", tags=["zones"])

Lat = Query(ge=-90, le=90)
Lng = Query(ge=-180, le=180)


@router.get("/zones/check", response_model=ZoneCheck)
async def check(
    _: CurrentUser, session: DBSession, lat: float = Lat, lng: float = Lng
) -> ZoneCheck:
    """For the pickup the passenger chose: restricted zone, suggested point and zone surge."""
    return await services.check_point(session, lat, lng)


@router.get("/drivers/me/demand", response_model=DemandSnapshot)
async def driver_demand(
    user: CurrentUser, session: DBSession, lat: float = Lat, lng: float = Lng
) -> DemandSnapshot:
    """Busy cells around the driver (no passenger positions), rebuilt every minute."""
    profile_status = await session.scalar(
        select(DriverProfile.status).where(DriverProfile.user_id == user.id)
    )
    if profile_status != DriverStatus.APPROVED:
        raise DriverNotApprovedError()
    return await demand.for_driver(await get_app_config(session), lat, lng)


# --- Admin ---------------------------------------------------------------------------------------


@admin_router.get("", response_model=list[ZoneRead])
async def list_zones(
    _: Can("zones.view"),
    session: DBSession,
    city: str | None = None,
    kind: ZoneKind | None = None,
) -> list[Any]:
    return await services.list_zones(session, city=city, kind=kind)


@admin_router.post(
    "",
    response_model=ZoneRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[audit("zones.create", "zone")],
)
async def create_zone(data: ZoneWrite, _: Can("zones.manage"), session: DBSession) -> Any:
    zone = await services.create(session, data)
    await session.commit()
    await services.clear_cache()
    await session.refresh(zone)
    return zone


@admin_router.get("/cities", response_model=list[CityRead])
async def cities(_: Can("zones.view"), session: DBSession) -> list[CityRead]:
    return await services.cities(session)


@admin_router.put(
    "/cities/{name}",
    response_model=CityRead,
    dependencies=[audit("zones.city_polygon", "city", "name")],
)
async def set_city_polygon(
    name: str, data: CityPolygonWrite, _: Can("zones.manage"), session: DBSession
) -> CityRead:
    """Draws the city (null goes back to its box). Origins outside the polygon are rejected."""
    city = await services.set_city_polygon(session, name, data.polygon)
    await session.commit()
    await services.config_changed()
    return city


@admin_router.get("/export")
async def export(
    _: Can("zones.view"), session: DBSession, city: str | None = None
) -> dict[str, Any]:
    """Cities and zones as a GeoJSON FeatureCollection ([lng, lat], as the standard says)."""
    return await services.export_geojson(session, city)


@admin_router.post(
    "/import", response_model=ImportResult, dependencies=[audit("zones.import", "zone")]
)
async def import_zones(
    data: ImportWrite, _: Can("zones.manage"), session: DBSession
) -> ImportResult:
    result, cities_changed = await services.import_geojson(session, data.geojson, data.replace)
    await session.commit()
    await services.clear_cache()
    if cities_changed:
        await services.config_changed()
    return result


@admin_router.get("/demand", response_model=DemandSnapshot)
async def admin_demand(_: Can("live.view"), session: DBSession) -> DemandSnapshot:
    """Every cell with requests in the window, with the drivers connected in each."""
    return await demand.for_admin(await get_app_config(session))


@admin_router.post(
    "/demand/simulate",
    response_model=DemandSnapshot,
    dependencies=[audit("zones.demand_simulate", "zone")],
)
async def simulate(data: SimulateWrite, _: Can("zones.manage"), session: DBSession) -> Any:
    """Adds fake requests at a point to try the map (not in production)."""
    if settings.is_production:
        raise NotFoundError()
    await demand.record(demand.REQUESTS, data.lat, data.lng, data.requests)
    if data.unmatched:
        await demand.record(demand.UNMATCHED, data.lat, data.lng, data.unmatched)
    return DemandSnapshot.model_validate(await demand.compute(await get_app_config(session)))


@admin_router.get("/{zone_id}", response_model=ZoneRead)
async def get_zone(zone_id: uuid.UUID, _: Can("zones.view"), session: DBSession) -> Any:
    return await services.get_or_404(session, zone_id)


@admin_router.patch(
    "/{zone_id}", response_model=ZoneRead, dependencies=[audit("zones.update", "zone", "zone_id")]
)
async def update_zone(
    zone_id: uuid.UUID, data: ZoneUpdate, _: Can("zones.manage"), session: DBSession
) -> Any:
    zone = await services.update(session, await services.get_or_404(session, zone_id), data)
    await session.commit()
    await services.clear_cache()
    await session.refresh(zone)
    return zone


@admin_router.delete(
    "/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[audit("zones.delete", "zone", "zone_id")],
)
async def delete_zone(zone_id: uuid.UUID, _: Can("zones.manage"), session: DBSession) -> Response:
    await services.remove(session, await services.get_or_404(session, zone_id))
    await session.commit()
    await services.clear_cache()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
