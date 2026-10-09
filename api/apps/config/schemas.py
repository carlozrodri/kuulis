import re
from datetime import time
from decimal import Decimal
from itertools import pairwise
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from apps.drivers.models import DocumentKind, VehicleType
from apps.rides.models import PaymentMethod

MinYear = Annotated[int, Field(ge=1950, le=2100)]

_CENT = Decimal("0.01")


def _two_places(value: Decimal) -> Decimal:
    return value.quantize(_CENT)


# JSON shows amounts as fixed 2-decimal strings ("0.80"), like the rest of the money in the API.
AsMoneyString = PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")
Money = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1000"), decimal_places=2, allow_inf_nan=False),
    AfterValidator(_two_places),
    AsMoneyString,
]
Multiplier = Annotated[
    Decimal,
    Field(ge=Decimal("1"), le=Decimal("3"), decimal_places=2, allow_inf_nan=False),
    AfterValidator(_two_places),
    AsMoneyString,
]
Rounding = Annotated[
    Decimal,
    Field(ge=Decimal("0.01"), le=Decimal("10"), decimal_places=2, allow_inf_nan=False),
    AfterValidator(_two_places),
    AsMoneyString,
]
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class FareConfig(BaseModel):
    base: Money
    per_km: Money
    per_minute: Money
    minimum: Money


class SurgeRule(BaseModel):
    """Time window in Caracas time. ``days``: 0 = Monday. ``end`` < ``start`` crosses midnight
    (the window belongs to the day it starts)."""

    days: list[Annotated[int, Field(ge=0, le=6)]] = Field(min_length=1, max_length=7)
    start: str
    end: str
    multiplier: Multiplier

    @field_validator("days")
    @classmethod
    def _days(cls, value: list[int]) -> list[int]:
        return sorted(_unique(value))

    @field_validator("start", "end")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        if not _HHMM.match(value):
            raise ValueError("expected HH:MM (24h)")
        return value

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if self.start == self.end:
            raise ValueError("start and end must differ")
        return self

    @property
    def start_time(self) -> time:
        return time.fromisoformat(self.start)

    @property
    def end_time(self) -> time:
        return time.fromisoformat(self.end)


class ServiceArea(BaseModel):
    min_lat: float = Field(ge=-90, le=90)
    max_lat: float = Field(ge=-90, le=90)
    min_lng: float = Field(ge=-180, le=180)
    max_lng: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min_lat >= self.max_lat or self.min_lng >= self.max_lng:
            raise ValueError("min values must be lower than max values")
        return self

    def contains(self, lat: float, lng: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lng <= lng <= self.max_lng

    @property
    def center(self) -> tuple[float, float]:
        return (self.min_lat + self.max_lat) / 2, (self.min_lng + self.max_lng) / 2


def _default_fares() -> dict[VehicleType, FareConfig]:
    return {
        VehicleType.MOTO: FareConfig(
            base=Decimal("0.80"),
            per_km=Decimal("0.35"),
            per_minute=Decimal("0.05"),
            minimum=Decimal("1.50"),
        ),
        VehicleType.CAR: FareConfig(
            base=Decimal("1.50"),
            per_km=Decimal("0.60"),
            per_minute=Decimal("0.08"),
            minimum=Decimal("2.50"),
        ),
    }


def _default_area() -> ServiceArea:
    return ServiceArea(min_lat=10.35, max_lat=10.56, min_lng=-67.10, max_lng=-66.70)


Radius = Annotated[int, Field(ge=100, le=50_000)]


def _unique[T](values: list[T]) -> list[T]:
    if len(set(values)) != len(values):
        raise ValueError("values must be unique")
    return values


def _increasing(values: list[int]) -> list[int]:
    if any(b <= a for a, b in pairwise(values)):
        raise ValueError("radii must be strictly increasing")
    return values


class AppConfig(BaseModel):
    """Every admin-editable setting with its default. Adding a key here is enough to expose it."""

    driver_min_age: int = Field(default=21, ge=16, le=99)
    vehicle_min_year: dict[VehicleType, MinYear] = Field(
        default_factory=lambda: {VehicleType.MOTO: 2013, VehicleType.CAR: 1993}
    )
    enabled_vehicle_types: list[VehicleType] = Field(
        default_factory=lambda: [VehicleType.MOTO], min_length=1
    )
    driver_required_documents: list[DocumentKind] = Field(
        default_factory=lambda: [
            DocumentKind.ID_CARD,
            DocumentKind.RIF,
            DocumentKind.DRIVERS_LICENSE,
            DocumentKind.MEDICAL_CERTIFICATE,
            DocumentKind.VEHICLE_REGISTRATION,
            DocumentKind.SELFIE,
            DocumentKind.VEHICLE_PHOTO,
        ]
    )
    vehicle_photo_min_count: int = Field(default=2, ge=0, le=10)

    # --- Rides (phase 1B) ---------------------------------------------------------------------
    fares: dict[VehicleType, FareConfig] = Field(default_factory=_default_fares)
    surge_rules: list[SurgeRule] = Field(default_factory=list, max_length=50)
    surge_manual_multiplier: Multiplier = Decimal("1.00")
    fare_rounding: Rounding = Decimal("0.10")
    payment_methods: list[PaymentMethod] = Field(
        default_factory=lambda: list(PaymentMethod), min_length=1
    )
    service_area: ServiceArea = Field(default_factory=_default_area)
    offer_timeout_seconds: int = Field(default=15, ge=5, le=120)
    search_radius_m: list[Radius] = Field(
        default_factory=lambda: [2000, 4000, 7000], min_length=1, max_length=6
    )
    search_timeout_seconds: int = Field(default=180, ge=30, le=1800)
    quote_ttl_seconds: int = Field(default=300, ge=30, le=3600)

    @field_validator("enabled_vehicle_types", "driver_required_documents", "payment_methods")
    @classmethod
    def check_unique(cls, value: list) -> list:
        return _unique(value)

    @field_validator("search_radius_m")
    @classmethod
    def check_increasing(cls, value: list[int]) -> list[int]:
        return _increasing(value)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        missing = [t.value for t in self.enabled_vehicle_types if t not in self.fares]
        if missing:
            raise ValueError(f"fares missing for enabled vehicle types: {', '.join(missing)}")
        if self.search_timeout_seconds < self.offer_timeout_seconds:
            raise ValueError("search_timeout_seconds must be >= offer_timeout_seconds")
        return self

    def min_year(self, vehicle_type: VehicleType) -> int:
        return self.vehicle_min_year.get(vehicle_type, 0)


class AppConfigUpdate(BaseModel):
    """Partial update. ``vehicle_min_year`` and ``fares`` are merged per vehicle type."""

    driver_min_age: int | None = Field(default=None, ge=16, le=99)
    vehicle_min_year: dict[VehicleType, MinYear] | None = None
    enabled_vehicle_types: list[VehicleType] | None = Field(default=None, min_length=1)
    driver_required_documents: list[DocumentKind] | None = None
    vehicle_photo_min_count: int | None = Field(default=None, ge=0, le=10)
    fares: dict[VehicleType, FareConfig] | None = None  # merged per vehicle type
    surge_rules: list[SurgeRule] | None = Field(default=None, max_length=50)
    surge_manual_multiplier: Multiplier | None = None
    fare_rounding: Rounding | None = None
    payment_methods: list[PaymentMethod] | None = Field(default=None, min_length=1)
    service_area: ServiceArea | None = None
    offer_timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    search_radius_m: list[Radius] | None = Field(default=None, min_length=1, max_length=6)
    search_timeout_seconds: int | None = Field(default=None, ge=30, le=1800)
    quote_ttl_seconds: int | None = Field(default=None, ge=30, le=3600)

    @field_validator("enabled_vehicle_types", "driver_required_documents", "payment_methods")
    @classmethod
    def check_unique(cls, value: list | None) -> list | None:
        return value if value is None else _unique(value)

    @field_validator("search_radius_m")
    @classmethod
    def check_increasing(cls, value: list[int] | None) -> list[int] | None:
        return value if value is None else _increasing(value)
