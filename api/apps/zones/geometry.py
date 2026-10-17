"""Polygons as ``[(lat, lng), ...]`` (doc 21). Plain ray casting on degrees: exact enough inside a
city, and no PostGIS or shapely to install. The ring is open (the last vertex is not repeated)."""

from collections.abc import Sequence
from itertools import pairwise

LatLng = tuple[float, float]


def ring(points: Sequence[Sequence[float]]) -> list[LatLng]:
    """Normalizes to tuples and drops the closing vertex when it repeats the first one."""
    out = [(float(p[0]), float(p[1])) for p in points]
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def contains(polygon: Sequence[LatLng], lat: float, lng: float) -> bool:
    """Whether the point is inside (or on the border of) the polygon."""
    inside = False
    n = len(polygon)
    for i in range(n):
        (y1, x1), (y2, x2) = polygon[i], polygon[(i + 1) % n]
        if _on_segment(lat, lng, y1, x1, y2, x2):
            return True
        if (y1 > lat) != (y2 > lat):
            x = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lng < x:
                inside = not inside
    return inside


def bbox(polygon: Sequence[LatLng]) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lng, max_lng)."""
    lats = [p[0] for p in polygon]
    lngs = [p[1] for p in polygon]
    return min(lats), max(lats), min(lngs), max(lngs)


def problem(polygon: Sequence[LatLng]) -> str | None:
    """Why the ring is not a usable polygon, or None."""
    if len(set(polygon)) < 3:
        return "a polygon needs at least 3 different vertices"
    if any(not (-90 <= lat <= 90 and -180 <= lng <= 180) for lat, lng in polygon):
        return "coordinates out of range"
    edges = list(pairwise([*polygon, polygon[0]]))
    n = len(edges)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue  # neighbours share a vertex
            if _cross(*edges[i], *edges[j]):
                return "the polygon edges cross each other"
    if abs(_area2(polygon)) < 1e-12:
        return "the polygon has no area"
    return None


def _area2(polygon: Sequence[LatLng]) -> float:
    n = len(polygon)
    return sum(
        polygon[i][1] * polygon[(i + 1) % n][0] - polygon[(i + 1) % n][1] * polygon[i][0]
        for i in range(n)
    )


def _orient(a: LatLng, b: LatLng, c: LatLng) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _cross(a: LatLng, b: LatLng, c: LatLng, d: LatLng) -> bool:
    d1, d2 = _orient(c, d, a), _orient(c, d, b)
    d3, d4 = _orient(a, b, c), _orient(a, b, d)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and 0 not in (d1, d2, d3, d4)


def _on_segment(lat: float, lng: float, y1: float, x1: float, y2: float, x2: float) -> bool:
    if not (min(y1, y2) <= lat <= max(y1, y2) and min(x1, x2) <= lng <= max(x1, x2)):
        return False
    return abs((y2 - y1) * (lng - x1) - (x2 - x1) * (lat - y1)) < 1e-12
