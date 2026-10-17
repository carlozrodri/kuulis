"""Zones (doc 21): admin CRUD, GeoJSON import/export, city polygons and the rules a quote applies.

The quote path reads the zones from a Redis cache (one GET); every write clears it.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig, AppConfigUpdate, SurgeRule
from apps.config.services import get_app_config, invalidate_cache, update_app_config
from apps.rides import pricing
from apps.safety.geo import distance_m
from apps.zones import geometry
from apps.zones.models import Zone, ZoneKind
from apps.zones.schemas import (
    CityRead,
    ImportResult,
    ImportSkipped,
    Restriction,
    Suggestion,
    ZoneCheck,
    ZoneRules,
    ZoneSurge,
    ZoneUpdate,
    ZoneWrite,
)
from kuulis.core.cache import cache_delete, cached
from kuulis.core.exceptions import AppError, NotFoundError

CACHE_KEY = "zones:live"
CACHE_TTL_SECONDS = 300
SUGGEST_RADIUS_M = 1500  # suggested points farther than this are not offered
ALREADY_THERE_M = 30  # no suggestion when the pickup is this close to a point


class ZoneNotFoundError(NotFoundError):
    code = "zone_not_found"
    message = "Zone not found"


class CityNotFoundError(NotFoundError):
    code = "city_not_found"
    message = "City not found"


class ZoneInvalidError(AppError):
    status_code = 422
    code = "zone_invalid"
    message = "The zone is not valid"


class GeoJSONInvalidError(AppError):
    status_code = 422
    code = "geojson_invalid"
    message = "The file is not a GeoJSON FeatureCollection"


class PickupRestrictedError(AppError):
    status_code = 422
    code = "pickup_restricted"
    message = "Pickups are not allowed there; choose a nearby point"
    planned = True


class DropoffRestrictedError(AppError):
    status_code = 422
    code = "dropoff_restricted"
    message = "Drop-offs are not allowed there"
    planned = True


# --- Live zones (cached) -------------------------------------------------------------------------


@dataclass(frozen=True)
class LiveZone:
    id: str
    kind: ZoneKind
    name: str
    city: str
    polygon: list[tuple[float, float]]
    rules: ZoneRules
    starts_at: datetime | None
    ends_at: datetime | None

    def in_force(self, now: datetime) -> bool:
        return (self.starts_at is None or self.starts_at <= now) and (
            self.ends_at is None or now < self.ends_at
        )

    def contains(self, lat: float, lng: float) -> bool:
        return geometry.contains(self.polygon, lat, lng)


def _row(zone: Zone) -> dict[str, Any]:
    return {
        "id": str(zone.id),
        "kind": zone.kind.value,
        "name": zone.name,
        "city": zone.city,
        "polygon": zone.polygon,
        "rules": zone.rules,
        "starts_at": zone.starts_at.isoformat() if zone.starts_at else None,
        "ends_at": zone.ends_at.isoformat() if zone.ends_at else None,
    }


async def _load(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await session.scalars(select(Zone).where(Zone.active))).all()
    return [_row(z) for z in rows]


async def live_zones(session: AsyncSession, now: datetime | None = None) -> list[LiveZone]:
    """Active zones in force at ``now``."""
    now = now or datetime.now(UTC)
    zones = []
    for raw in await cached(CACHE_KEY, lambda: _load(session), ttl=CACHE_TTL_SECONDS):
        zone = LiveZone(
            id=raw["id"],
            kind=ZoneKind(raw["kind"]),
            name=raw["name"],
            city=raw["city"],
            polygon=geometry.ring(raw["polygon"]),
            rules=ZoneRules.model_validate(raw["rules"]),
            starts_at=datetime.fromisoformat(raw["starts_at"]) if raw["starts_at"] else None,
            ends_at=datetime.fromisoformat(raw["ends_at"]) if raw["ends_at"] else None,
        )
        if zone.in_force(now):
            zones.append(zone)
    return zones


async def clear_cache() -> None:
    await cache_delete(CACHE_KEY)


# --- Rules ---------------------------------------------------------------------------------------


def _surge_active(rules: ZoneRules, at: datetime) -> bool:
    if rules.start is None or rules.end is None:
        local = at.astimezone(pricing.CARACAS_TZ)
        return not rules.days or local.weekday() in rules.days
    rule = SurgeRule(
        days=rules.days or list(range(7)),
        start=rules.start,
        end=rules.end,
        multiplier=rules.multiplier,
    )
    return pricing.rule_active(rule, at.astimezone(pricing.CARACAS_TZ))


def zone_surge(
    zones: list[LiveZone], lat: float, lng: float, at: datetime | None = None
) -> ZoneSurge | None:
    """The highest surge of the zones containing the point (the pickup), if any is on now."""
    at = at or datetime.now(UTC)
    best: ZoneSurge | None = None
    for zone in zones:
        if zone.kind != ZoneKind.SURGE or not zone.contains(lat, lng):
            continue
        if _surge_active(zone.rules, at) and (
            best is None or zone.rules.multiplier > best.multiplier
        ):
            best = ZoneSurge(multiplier=zone.rules.multiplier, zone=zone.name)
    return best


def restriction(zones: list[LiveZone], lat: float, lng: float, *, pickup: bool) -> LiveZone | None:
    for zone in zones:
        if zone.kind != ZoneKind.RESTRICTED:
            continue
        if (zone.rules.pickup if pickup else zone.rules.dropoff) and zone.contains(lat, lng):
            return zone
    return None


def suggestion(zones: list[LiveZone], lat: float, lng: float) -> Suggestion | None:
    """The closest suggested pickup point: from the pickup zone the point is in, or, inside a
    restricted zone, its exits and the pickup points nearby that are not restricted."""
    blocked = restriction(zones, lat, lng, pickup=True)
    candidates: list[tuple[float, str, str, float, float]] = []
    if blocked is not None:
        for p in blocked.rules.points:
            candidates.append(
                (distance_m(lat, lng, p.lat, p.lng), p.name, blocked.name, p.lat, p.lng)
            )
        for zone in zones:
            if zone.kind != ZoneKind.PICKUP:
                continue
            for p in zone.rules.points:
                if restriction(zones, p.lat, p.lng, pickup=True) is None:
                    d = distance_m(lat, lng, p.lat, p.lng)
                    candidates.append((d, p.name, zone.name, p.lat, p.lng))
    else:
        for zone in zones:
            if zone.kind == ZoneKind.PICKUP and zone.contains(lat, lng):
                for p in zone.rules.points:
                    d = distance_m(lat, lng, p.lat, p.lng)
                    candidates.append((d, p.name, zone.name, p.lat, p.lng))
    candidates = [c for c in candidates if c[0] <= SUGGEST_RADIUS_M]
    if not candidates:
        return None
    d, name, zone_name, plat, plng = min(candidates)
    if d < ALREADY_THERE_M and blocked is None:
        return None
    return Suggestion(name=name, lat=plat, lng=plng, distance_m=round(d), zone=zone_name)


async def check_point(session: AsyncSession, lat: float, lng: float) -> ZoneCheck:
    config = await get_app_config(session)
    city = config.area_at(lat, lng)
    if city is None:
        return ZoneCheck(city=None)
    zones = [z for z in await live_zones(session) if z.city == city.name]
    blocked = restriction(zones, lat, lng, pickup=True)
    return ZoneCheck(
        city=city.name,
        restricted=Restriction(zone=blocked.name, message=blocked.rules.message)
        if blocked
        else None,
        suggestion=suggestion(zones, lat, lng),
        surge=zone_surge(zones, lat, lng),
    )


async def ensure_allowed(
    session: AsyncSession, pickup: tuple[float, float], dropoff: tuple[float, float]
) -> list[LiveZone]:
    """Raises ``pickup_restricted`` / ``dropoff_restricted``; returns the zones in force."""
    zones = await live_zones(session)
    blocked = restriction(zones, *pickup, pickup=True)
    if blocked is not None:
        hint = suggestion(zones, *pickup)
        raise PickupRestrictedError(
            details={
                "zone": blocked.name,
                "message": blocked.rules.message.model_dump(),
                "suggestion": hint.model_dump() if hint else None,
            }
        )
    blocked = restriction(zones, *dropoff, pickup=False)
    if blocked is not None:
        raise DropoffRestrictedError(
            details={"zone": blocked.name, "message": blocked.rules.message.model_dump()}
        )
    return zones


def surge_for(
    config: AppConfig, zones: list[LiveZone], lat: float, lng: float, at: datetime | None = None
) -> tuple[Decimal, str | None, str | None]:
    """(multiplier, reason, zone): the highest of the time rules, the manual multiplier and the
    surge zones containing the pickup. ``reason`` is None without surge."""
    at = at or datetime.now(UTC)
    local = at.astimezone(pricing.CARACAS_TZ)
    options: list[tuple[Decimal, str, str | None]] = [
        (r.multiplier, "time", None) for r in config.surge_rules if pricing.rule_active(r, local)
    ]
    options.append((config.surge_manual_multiplier, "manual", None))
    found = zone_surge(zones, lat, lng, at)
    if found is not None:
        options.append((found.multiplier, "zone", found.zone))
    # Ties go to the zone, the most specific explanation for the passenger.
    order = {"zone": 0, "time": 1, "manual": 2}
    value, reason, zone = max(options, key=lambda o: (o[0], -order[o[1]]))
    value = value.quantize(pricing.CENT)
    if value <= 1:
        return value, None, None
    return value, reason, zone


# --- Admin CRUD ----------------------------------------------------------------------------------


def _invalid(exc: ValidationError | ValueError) -> ZoneInvalidError:
    if isinstance(exc, ValidationError):
        details = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
    else:
        details = [{"loc": [], "msg": str(exc), "type": "value_error"}]
    return ZoneInvalidError(details=details)


def _ensure_city(config: AppConfig, name: str) -> None:
    if config.city_named(name) is None:
        raise ZoneInvalidError(
            details=[
                {
                    "loc": ["body", "city"],
                    "msg": "unknown city; known: "
                    + ", ".join(a.name for a in config.service_areas),
                    "type": "value_error",
                }
            ]
        )


async def list_zones(
    session: AsyncSession, city: str | None = None, kind: ZoneKind | None = None
) -> list[Zone]:
    stmt = select(Zone).order_by(Zone.city, Zone.kind, Zone.name)
    if city:
        stmt = stmt.where(Zone.city == city)
    if kind:
        stmt = stmt.where(Zone.kind == kind)
    return list((await session.scalars(stmt)).all())


async def get_or_404(session: AsyncSession, zone_id: uuid.UUID) -> Zone:
    zone = await session.get(Zone, zone_id)
    if zone is None:
        raise ZoneNotFoundError()
    return zone


def _apply(zone: Zone, data: ZoneWrite) -> None:
    zone.kind = data.kind
    zone.name = data.name
    zone.city = data.city
    zone.polygon = data.polygon
    zone.rules = data.rules.model_dump(mode="json")
    zone.active = data.active
    zone.starts_at = data.starts_at
    zone.ends_at = data.ends_at


async def create(session: AsyncSession, data: ZoneWrite) -> Zone:
    _ensure_city(await get_app_config(session), data.city)
    zone = Zone()
    _apply(zone, data)
    session.add(zone)
    await session.flush()
    return zone


async def update(session: AsyncSession, zone: Zone, data: ZoneUpdate) -> Zone:
    current = {
        "kind": zone.kind,
        "name": zone.name,
        "city": zone.city,
        "polygon": zone.polygon,
        "rules": zone.rules,
        "active": zone.active,
        "starts_at": zone.starts_at,
        "ends_at": zone.ends_at,
    }
    changes = data.model_dump(exclude_unset=True)
    for key in ("kind", "name", "city", "polygon", "rules", "active"):
        if key in changes and changes[key] is None:
            del changes[key]  # null only clears the dates
    try:
        merged = ZoneWrite.model_validate(current | changes)
    except ValidationError as exc:
        raise _invalid(exc) from exc
    _ensure_city(await get_app_config(session), merged.city)
    _apply(zone, merged)
    await session.flush()
    return zone


async def remove(session: AsyncSession, zone: Zone) -> None:
    await session.delete(zone)
    await session.flush()


# --- Cities --------------------------------------------------------------------------------------


def city_read(area: Any) -> CityRead:
    lat, lng = area.center
    return CityRead(
        name=area.name,
        polygon=area.polygon,
        min_lat=area.min_lat,
        max_lat=area.max_lat,
        min_lng=area.min_lng,
        max_lng=area.max_lng,
        center=[lat, lng],
    )


async def cities(session: AsyncSession) -> list[CityRead]:
    return [city_read(a) for a in (await get_app_config(session)).service_areas]


async def set_city_polygon(
    session: AsyncSession, name: str, polygon: list[list[float]] | None
) -> CityRead:
    """Saves the polygon (None: back to the box, which keeps the polygon's enclosing rectangle).
    The caller commits and then calls ``config_changed``."""
    config = await get_app_config(session)
    if config.city_named(name) is None:
        raise CityNotFoundError(details={"cities": [a.name for a in config.service_areas]})
    areas = []
    for area in config.service_areas:
        raw = area.model_dump()
        if area.name == name:
            raw["polygon"] = polygon
        areas.append(raw)
    merged = await update_app_config(
        session, AppConfigUpdate.model_validate({"service_areas": areas})
    )
    area = merged.city_named(name)
    assert area is not None
    return city_read(area)


async def config_changed() -> None:
    from apps.control import services as control

    await invalidate_cache()
    await control.changed()


# --- GeoJSON -------------------------------------------------------------------------------------


def _feature(kind: str, polygon: list[list[float]], properties: dict[str, Any]) -> dict[str, Any]:
    ring = [[lng, lat] for lat, lng in polygon]
    ring.append(ring[0])
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"kind": kind} | properties,
    }


async def export_geojson(session: AsyncSession, city: str | None = None) -> dict[str, Any]:
    config = await get_app_config(session)
    features = []
    for area in config.service_areas:
        if city and area.name != city:
            continue
        polygon = area.polygon or [
            [area.min_lat, area.min_lng],
            [area.min_lat, area.max_lng],
            [area.max_lat, area.max_lng],
            [area.max_lat, area.min_lng],
        ]
        features.append(_feature("city", polygon, {"name": area.name}))
    for zone in await list_zones(session, city=city):
        features.append(
            _feature(
                zone.kind.value,
                zone.polygon,
                {
                    "id": str(zone.id),
                    "name": zone.name,
                    "city": zone.city,
                    "rules": zone.rules,
                    "active": zone.active,
                    "starts_at": zone.starts_at.isoformat() if zone.starts_at else None,
                    "ends_at": zone.ends_at.isoformat() if zone.ends_at else None,
                },
            )
        )
    return {"type": "FeatureCollection", "features": features}


def _polygon_of(feature: dict[str, Any]) -> list[list[float]]:
    geometry_ = feature.get("geometry") or {}
    coords = geometry_.get("coordinates")
    if geometry_.get("type") == "MultiPolygon" and coords and len(coords) == 1:
        coords = coords[0]
    elif geometry_.get("type") != "Polygon":
        raise ValueError("only Polygon geometries are supported")
    if not coords or not coords[0]:
        raise ValueError("empty polygon")
    if len(coords) > 1:
        raise ValueError("polygons with holes are not supported")
    return [[float(p[1]), float(p[0])] for p in coords[0]]  # [lng, lat] -> [lat, lng]


async def import_geojson(
    session: AsyncSession, geojson: dict[str, Any], replace: bool = False
) -> tuple[ImportResult, bool]:
    """Returns the result and whether the city settings changed (the caller commits and, if so,
    calls ``config_changed``)."""
    if geojson.get("type") != "FeatureCollection" or not isinstance(geojson.get("features"), list):
        raise GeoJSONInvalidError()
    config = await get_app_config(session)
    city_polygons: dict[str, list[list[float]]] = {}
    zones: list[tuple[int, str | None, ZoneWrite]] = []
    skipped: list[ImportSkipped] = []
    for index, feature in enumerate(geojson["features"]):
        try:
            if not isinstance(feature, dict):
                raise ValueError("not a feature")
            props = feature.get("properties") or {}
            polygon = _polygon_of(feature)
            if props.get("kind") == "city":
                name = str(props.get("name") or "")
                if config.city_named(name) is None:
                    raise ValueError(f"unknown city {name!r}; add it in the settings first")
                if reason := geometry.problem(geometry.ring(polygon)):
                    raise ValueError(reason)
                city_polygons[name] = polygon
                continue
            data = ZoneWrite.model_validate(
                {
                    "kind": props.get("kind"),
                    "name": props.get("name"),
                    "city": props.get("city"),
                    "polygon": polygon,
                    "rules": props.get("rules") or {},
                    "active": props.get("active", True),
                    "starts_at": props.get("starts_at"),
                    "ends_at": props.get("ends_at"),
                }
            )
            if config.city_named(data.city) is None:
                raise ValueError(f"unknown city {data.city!r}")
            zones.append((index, props.get("id"), data))
        except (ValidationError, ValueError, TypeError, IndexError) as exc:
            reason = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
            skipped.append(ImportSkipped(index=index, reason=reason))

    for name, polygon in city_polygons.items():
        await set_city_polygon(session, name, polygon)
    if replace:
        touched = {d.city for _, _, d in zones} | set(city_polygons)
        if touched:
            await session.execute(delete(Zone).where(Zone.city.in_(touched)))
    created = updated = 0
    for _, raw_id, data in zones:
        zone = None
        if raw_id and not replace:
            try:
                zone = await session.get(Zone, uuid.UUID(str(raw_id)))
            except ValueError:
                zone = None
        if zone is None:
            zone = Zone()
            session.add(zone)
            created += 1
        else:
            updated += 1
        _apply(zone, data)
    await session.flush()
    result = ImportResult(
        cities=len(city_polygons), created=created, updated=updated, skipped=skipped
    )
    return result, bool(city_polygons)
