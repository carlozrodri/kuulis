from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.config.schemas import Localized, Multiplier, Polygon, check_polygon
from apps.zones.models import ZoneKind

_HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class Point(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ZoneRules(BaseModel):
    """Every kind reads only its own keys; the rest keep their defaults."""

    # surge
    multiplier: Multiplier = Decimal("1.00")
    days: list[int] = Field(default_factory=list, max_length=7)  # 0 = Monday; empty = every day
    start: str | None = Field(default=None, pattern=_HHMM)  # Caracas time; none = all day
    end: str | None = Field(default=None, pattern=_HHMM)
    # restricted
    pickup: bool = True
    dropoff: bool = True
    message: Localized = Field(default_factory=Localized)
    # pickup (and the suggested exits of a restricted zone)
    points: list[Point] = Field(default_factory=list, max_length=20)

    @field_validator("days")
    @classmethod
    def _days(cls, value: list[int]) -> list[int]:
        if any(not 0 <= d <= 6 for d in value):
            raise ValueError("days go from 0 (Monday) to 6")
        return sorted(set(value))

    @model_validator(mode="after")
    def _hours(self) -> Self:
        if (self.start is None) != (self.end is None) or (self.start and self.start == self.end):
            raise ValueError("start and end go together and must differ")
        return self


def _check_rules(kind: ZoneKind, rules: ZoneRules) -> None:
    if kind == ZoneKind.SURGE and rules.multiplier <= 1:
        raise ValueError("a surge zone needs a multiplier above 1.00")
    if kind == ZoneKind.PICKUP and not rules.points:
        raise ValueError("a pickup zone needs at least one point")
    if kind == ZoneKind.RESTRICTED and not (rules.pickup or rules.dropoff):
        raise ValueError("a restricted zone must forbid pickups, drop-offs or both")


class ZoneWrite(BaseModel):
    kind: ZoneKind
    name: str = Field(min_length=1, max_length=80)
    city: str = Field(min_length=1, max_length=60)
    polygon: Polygon
    rules: ZoneRules = Field(default_factory=ZoneRules)
    active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("polygon")
    @classmethod
    def _polygon(cls, value: list[list[float]]) -> list[list[float]]:
        return check_polygon(value) or []

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _check_rules(self.kind, self.rules)
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class ZoneUpdate(BaseModel):
    """Partial; the result is validated as a whole (``ZoneWrite``)."""

    kind: ZoneKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=80)
    city: str | None = Field(default=None, min_length=1, max_length=60)
    polygon: Polygon | None = None
    rules: ZoneRules | None = None
    active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ZoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Any
    kind: ZoneKind
    name: str
    city: str
    polygon: list[list[float]]
    rules: ZoneRules
    active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CityRead(BaseModel):
    name: str
    polygon: list[list[float]] | None
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float
    center: list[float]


class CityPolygonWrite(BaseModel):
    polygon: Polygon | None = None


class ImportWrite(BaseModel):
    geojson: dict[str, Any]
    replace: bool = False


class ImportSkipped(BaseModel):
    index: int
    reason: str


class ImportResult(BaseModel):
    cities: int
    created: int
    updated: int
    skipped: list[ImportSkipped]


# --- Passenger -----------------------------------------------------------------------------------


class Suggestion(BaseModel):
    name: str
    lat: float
    lng: float
    distance_m: int
    zone: str


class Restriction(BaseModel):
    zone: str
    message: Localized


class ZoneSurge(BaseModel):
    multiplier: Multiplier
    zone: str


class ZoneCheck(BaseModel):
    city: str | None
    restricted: Restriction | None = None
    suggestion: Suggestion | None = None
    surge: ZoneSurge | None = None


# --- Demand --------------------------------------------------------------------------------------


class DemandCell(BaseModel):
    cell: str
    boundary: list[list[float]]
    center: list[float]
    level: Literal[1, 2, 3]
    requests: int
    unmatched: int
    drivers: int | None = None  # only for the admin
    name: str | None = None


class HotSpot(BaseModel):
    name: str
    level: int
    distance_m: int
    center: list[float]


class DemandSnapshot(BaseModel):
    enabled: bool
    updated_at: datetime | None = None
    window_minutes: int
    cells: list[DemandCell] = Field(default_factory=list)
    hot: HotSpot | None = None


class SimulateWrite(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    requests: int = Field(default=10, ge=1, le=200)
    unmatched: int = Field(default=3, ge=0, le=200)
