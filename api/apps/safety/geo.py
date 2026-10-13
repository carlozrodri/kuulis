"""Small geometry helpers for the anomaly rules (distances in metres, good enough inside a city)."""

import math
from itertools import pairwise

EARTH_RADIUS_M = 6_371_000


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Google encoded polyline (what OSRM returns) -> [(lat, lng), ...]."""
    points: list[tuple[float, float]] = []
    index = lat = lng = 0
    factor = 10**precision
    while index < len(encoded):
        values = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            values.append(~(result >> 1) if result & 1 else result >> 1)
        lat += values[0]
        lng += values[1]
        points.append((lat / factor, lng / factor))
    return points


def distance_to_path_m(lat: float, lng: float, path: list[tuple[float, float]]) -> float:
    """Shortest distance from a point to a polyline (flat projection around the point)."""
    if not path:
        return math.inf
    if len(path) == 1:
        return distance_m(lat, lng, *path[0])
    kx = math.cos(math.radians(lat)) * EARTH_RADIUS_M * math.pi / 180
    ky = EARTH_RADIUS_M * math.pi / 180
    best = math.inf
    for (alat, alng), (blat, blng) in pairwise(path):
        ax, ay = (alng - lng) * kx, (alat - lat) * ky
        bx, by = (blng - lng) * kx, (blat - lat) * ky
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length))
        px, py = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(px, py))
    return best
