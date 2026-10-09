"""Routing (OSRM) and address search (Photon) clients.

Both providers are optional: without ``OSRM_URL`` routes are estimated from the straight-line
distance, and without ``PHOTON_URL`` search returns nothing. Provider failures never break a
request: routes fall back to the estimate, search to ``[]`` and reverse to the coordinates.
"""

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any

import httpx

from apps.config.schemas import ServiceArea
from apps.geo.schemas import GeoResult
from kuulis.core.cache import cache_get, cache_set
from kuulis.settings import settings

logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6_371_000
ROUTE_FACTOR = 1.3  # straight line -> street distance
ESTIMATE_SPEED_KMH = 22  # average moto speed in Caracas traffic
SEARCH_LIMIT = 10
SEARCH_CACHE_TTL = 3600
REVERSE_CACHE_TTL = 24 * 3600

_http: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    """One pooled client per process (keep-alive to the providers)."""
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.GEO_TIMEOUT_SECONDS),
            headers={"User-Agent": f"{settings.APP_NAME}/1.0 (+{settings.PUBLIC_URL})"},
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )
    return _http


async def aclose() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


# --- Routes ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Route:
    distance_m: int
    duration_s: int
    polyline: str | None  # Google encoded polyline, precision 5 (OSRM ``geometries=polyline``)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def estimate_route(lat1: float, lng1: float, lat2: float, lng2: float) -> Route:
    distance = haversine_m(lat1, lng1, lat2, lng2) * ROUTE_FACTOR
    duration = distance / (ESTIMATE_SPEED_KMH * 1000 / 3600)
    return Route(distance_m=round(distance), duration_s=round(duration), polyline=None)


async def route(lat1: float, lng1: float, lat2: float, lng2: float) -> Route:
    if not settings.OSRM_URL:
        return estimate_route(lat1, lng1, lat2, lng2)
    url = (
        f"{settings.OSRM_URL.rstrip('/')}/route/v1/driving/"
        f"{lng1:.6f},{lat1:.6f};{lng2:.6f},{lat2:.6f}"
    )
    try:
        response = await http().get(
            url, params={"overview": "simplified", "geometries": "polyline", "steps": "false"}
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != "Ok" or not body.get("routes"):
            raise ValueError(f"OSRM answered {body.get('code')}")
        best = body["routes"][0]
        return Route(
            distance_m=round(best["distance"]),
            duration_s=round(best["duration"]),
            polyline=best.get("geometry") or None,
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        logger.warning("OSRM route failed, using the estimate", exc_info=True)
        return estimate_route(lat1, lng1, lat2, lng2)


# --- Photon search / reverse -------------------------------------------------------------------


def _format(feature: dict[str, Any]) -> GeoResult | None:
    try:
        lng, lat = feature["geometry"]["coordinates"][:2]
        props = feature.get("properties") or {}
    except (KeyError, TypeError, ValueError):
        return None
    street = " ".join(p for p in (props.get("street"), props.get("housenumber")) if p)
    name = props.get("name") or street
    parts: list[str] = []
    for part in (
        street,
        props.get("district") or props.get("locality"),
        props.get("city"),
        props.get("state"),
    ):
        if part and part != name and part not in parts:
            parts.append(part)
    if not name:
        name = parts.pop(0) if parts else ""
    return GeoResult(name=name, address=", ".join(parts), lat=float(lat), lng=float(lng))


def _coords_result(lat: float, lng: float) -> GeoResult:
    label = f"{lat:.5f}, {lng:.5f}"
    return GeoResult(name=label, address=label, lat=lat, lng=lng)


async def search(
    q: str, area: ServiceArea, lat: float | None = None, lng: float | None = None
) -> list[GeoResult]:
    """Photon search biased to ``lat/lng`` (or the area center) and limited to the area box."""
    q = " ".join(q.split())
    if not settings.PHOTON_URL or len(q) < 2:
        return []
    bias_lat, bias_lng = (lat, lng) if lat is not None and lng is not None else area.center
    bbox = f"{area.min_lng},{area.min_lat},{area.max_lng},{area.max_lat}"
    digest = hashlib.sha1(
        f"{q.lower()}|{bias_lat:.2f}|{bias_lng:.2f}|{bbox}".encode(), usedforsecurity=False
    ).hexdigest()
    cache_key = f"geo:search:{digest}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return [GeoResult.model_validate(item) for item in cached]
    try:
        response = await http().get(
            f"{settings.PHOTON_URL.rstrip('/')}/api",
            params={
                "q": q,
                "lat": f"{bias_lat:.5f}",
                "lon": f"{bias_lng:.5f}",
                "limit": SEARCH_LIMIT,
                "bbox": bbox,
            },
        )
        response.raise_for_status()
        features = response.json().get("features") or []
    except (httpx.HTTPError, ValueError, AttributeError):
        logger.warning("Photon search failed", exc_info=True)
        return []
    results: list[GeoResult] = []
    seen: set[tuple[str, str]] = set()
    for feature in features:
        item = _format(feature)
        if item is None or not area.contains(item.lat, item.lng):
            continue
        if (item.name, item.address) in seen:
            continue
        seen.add((item.name, item.address))
        results.append(item)
    await cache_set(cache_key, [r.model_dump() for r in results], SEARCH_CACHE_TTL)
    return results


async def reverse(lat: float, lng: float) -> GeoResult:
    if not settings.PHOTON_URL:
        return _coords_result(lat, lng)
    cache_key = f"geo:reverse:{lat:.4f}:{lng:.4f}"  # ~11 m cells
    cached = await cache_get(cache_key)
    if cached is not None:
        return GeoResult.model_validate(cached | {"lat": lat, "lng": lng})
    try:
        response = await http().get(
            f"{settings.PHOTON_URL.rstrip('/')}/reverse",
            params={"lat": f"{lat:.6f}", "lon": f"{lng:.6f}", "limit": 1},
        )
        response.raise_for_status()
        features = response.json().get("features") or []
    except (httpx.HTTPError, ValueError, AttributeError):
        logger.warning("Photon reverse failed", exc_info=True)
        return _coords_result(lat, lng)
    item = _format(features[0]) if features else None
    if item is None or not item.name:
        return _coords_result(lat, lng)
    # Keep the exact point the user picked; the address describes it.
    result = GeoResult(name=item.name, address=item.address, lat=lat, lng=lng)
    await cache_set(cache_key, result.model_dump(), REVERSE_CACHE_TTL)
    return result
