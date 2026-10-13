import re
from datetime import datetime, time
from decimal import Decimal
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from apps.drivers.models import DocumentKind, VehicleType
from apps.rates.models import RateSource
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
    name: str = Field(default="Caracas", min_length=1, max_length=60)
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


def _default_areas() -> list[ServiceArea]:
    return [
        ServiceArea(name="Caracas", min_lat=10.35, max_lat=10.56, min_lng=-67.10, max_lng=-66.70)
    ]


class Localized(BaseModel):
    """A text in both app languages (the app falls back to Spanish when ``en`` is empty)."""

    es: str = Field(default="", max_length=300)
    en: str = Field(default="", max_length=300)


class Maintenance(BaseModel):
    """Maintenance mode (doc 10): no new quotes, rides or drivers going online. ``areas`` empty
    means every city; rides already under way go on."""

    enabled: bool = False
    message: Localized = Field(default_factory=Localized)
    eta: datetime | None = None
    areas: list[str] = Field(default_factory=list, max_length=20)


class AreaPause(BaseModel):
    """Requests paused in one city (heavy rain, protests, curfew), with its own message."""

    area: str = Field(min_length=1, max_length=60)
    message: Localized = Field(default_factory=Localized)
    eta: datetime | None = None


class AppLinks(BaseModel):
    """Contact and legal links the app shows, editable without an app update."""

    support_whatsapp: str = Field(default="", max_length=20, pattern=r"^\+?\d*$")
    support_email: str = Field(default="", max_length=120)
    emergency_number: str = Field(default="911", max_length=10, pattern=r"^\d*$")
    terms_url: str = Field(default="", max_length=300)
    privacy_url: str = Field(default="", max_length=300)


class LocationIntervals(BaseModel):
    """How often the driver app sends its location, in seconds."""

    online_seconds: int = Field(default=10, ge=2, le=120)
    on_ride_seconds: int = Field(default=4, ge=1, le=60)


class SafetySettings(BaseModel):
    """Trip safety (doc 11): start PIN, passenger photo, anomaly rules and SOS location rate."""

    # Cities where the driver must type the passenger's PIN to start a ride.
    pin_areas: list[str] = Field(default_factory=lambda: ["Caracas"], max_length=20)
    # When the driver sees the passenger's photo (if any) with the offer and during the ride.
    passenger_photo: Literal["off", "night", "always"] = "night"
    night_start: str = "19:00"  # Caracas time
    night_end: str = "06:00"
    # Anomalies during ``in_progress``; each asks both "¿Todo bien?" before alerting the team.
    stop_minutes: int = Field(default=10, ge=2, le=60)
    deviation_m: int = Field(default=600, ge=100, le=10_000)
    deviation_minutes: int = Field(default=3, ge=1, le=30)
    overtime_factor: float = Field(default=2.0, ge=1.2, le=10)
    check_in_seconds: int = Field(default=120, ge=30, le=900)
    # How often the app sends its location while an SOS is active.
    sos_location_seconds: int = Field(default=5, ge=2, le=60)

    @field_validator("night_start", "night_end")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        if not _HHMM.match(value):
            raise ValueError("expected HH:MM (24h)")
        return value

    def is_night(self, now: time) -> bool:
        start, end = time.fromisoformat(self.night_start), time.fromisoformat(self.night_end)
        if start <= end:
            return start <= now < end
        return now >= start or now < end


NoticeKind = Literal["maintenance", "pause"]


Radius = Annotated[int, Field(ge=100, le=50_000)]
StaleMinutes = Annotated[int, Field(ge=5, le=30 * 24 * 60)]


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
    service_areas: list[ServiceArea] = Field(
        default_factory=_default_areas, min_length=1, max_length=20
    )
    offer_timeout_seconds: int = Field(default=15, ge=5, le=120)
    search_radius_m: list[Radius] = Field(
        default_factory=lambda: [2000, 4000, 7000], min_length=1, max_length=6
    )
    search_timeout_seconds: int = Field(default=180, ge=30, le=1800)
    quote_ttl_seconds: int = Field(default=300, ge=30, le=3600)

    # --- Rates and promotions (phase 1C) -------------------------------------------------------
    rates_stale_minutes: dict[RateSource, StaleMinutes] = Field(
        default_factory=lambda: {RateSource.BCV: 36 * 60, RateSource.BINANCE: 120}
    )
    rates_manual_hold_hours: int = Field(default=6, ge=1, le=168)
    promo_pair_alert_threshold: int = Field(default=3, ge=2, le=100)
    promo_pair_alert_days: int = Field(default=30, ge=1, le=365)

    # --- Wallet and subscription (phase 1D) ----------------------------------------------------
    topup_min_amount: Money = Decimal("5.00")
    topup_binance_pay_id: str = Field(default="", max_length=30, pattern=r"^\d*$")
    topup_account_name: str = Field(default="Kuulis", max_length=60)
    transfer_monthly_limit: Money = Decimal("50.00")
    subscription_free_months: int = Field(default=3, ge=0, le=24)
    subscription_grace_days: int = Field(default=7, ge=0, le=60)

    # --- Four-eyes approvals (doc 06) ---------------------------------------------------------
    # Balance adjustments above this many USD wait for a second person (0: never).
    approval_adjust_limit: Money = Decimal("20.00")
    # Fare and fee schedule changes, and notifications to a whole role or everyone.
    approval_fares: bool = True
    approval_broadcasts: bool = True

    # --- Remote control (doc 10) ----------------------------------------------------------------
    # maintenance and area_pauses change only through PUT /admin/app/status (not in the update).
    maintenance: Maintenance = Field(default_factory=Maintenance)
    area_pauses: list[AreaPause] = Field(default_factory=list, max_length=20)
    app_links: AppLinks = Field(default_factory=AppLinks)
    location_intervals: LocationIntervals = Field(default_factory=LocationIntervals)

    # --- Trip safety (doc 11) -------------------------------------------------------------------
    safety: SafetySettings = Field(default_factory=SafetySettings)

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

    def stale_minutes(self, source: RateSource) -> int:
        return self.rates_stale_minutes.get(source, 24 * 60)

    def min_year(self, vehicle_type: VehicleType) -> int:
        return self.vehicle_min_year.get(vehicle_type, 0)

    def area_at(self, lat: float, lng: float) -> ServiceArea | None:
        return next((area for area in self.service_areas if area.contains(lat, lng)), None)

    def notice_for(self, area: str | None) -> tuple[NoticeKind, AreaPause] | None:
        """Why new rides are stopped in ``area`` (None: unknown place), if they are."""
        m = self.maintenance
        if m.enabled and (not m.areas or area in m.areas):
            return "maintenance", AreaPause(area=area or "*", message=m.message, eta=m.eta)
        pause = next((p for p in self.area_pauses if p.area == area), None)
        return ("pause", pause) if pause else None


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
    service_areas: list[ServiceArea] | None = Field(default=None, min_length=1, max_length=20)
    offer_timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    search_radius_m: list[Radius] | None = Field(default=None, min_length=1, max_length=6)
    search_timeout_seconds: int | None = Field(default=None, ge=30, le=1800)
    quote_ttl_seconds: int | None = Field(default=None, ge=30, le=3600)
    rates_stale_minutes: dict[RateSource, StaleMinutes] | None = None  # merged per source
    rates_manual_hold_hours: int | None = Field(default=None, ge=1, le=168)
    promo_pair_alert_threshold: int | None = Field(default=None, ge=2, le=100)
    promo_pair_alert_days: int | None = Field(default=None, ge=1, le=365)
    topup_min_amount: Money | None = None
    topup_binance_pay_id: str | None = Field(default=None, max_length=30, pattern=r"^\d*$")
    topup_account_name: str | None = Field(default=None, max_length=60)
    transfer_monthly_limit: Money | None = None
    subscription_free_months: int | None = Field(default=None, ge=0, le=24)
    subscription_grace_days: int | None = Field(default=None, ge=0, le=60)
    approval_adjust_limit: Money | None = None
    approval_fares: bool | None = None
    approval_broadcasts: bool | None = None
    app_links: AppLinks | None = None
    location_intervals: LocationIntervals | None = None
    safety: SafetySettings | None = None

    @field_validator("enabled_vehicle_types", "driver_required_documents", "payment_methods")
    @classmethod
    def check_unique(cls, value: list | None) -> list | None:
        return value if value is None else _unique(value)

    @field_validator("search_radius_m")
    @classmethod
    def check_increasing(cls, value: list[int] | None) -> list[int] | None:
        return value if value is None else _increasing(value)


class PublicDriverRequirements(BaseModel):
    min_age: int
    vehicle_types: list[VehicleType]
    vehicle_min_year: dict[VehicleType, int]
    documents: list[DocumentKind]
    vehicle_photo_min_count: int


class PublicFeeTier(BaseModel):
    above: Decimal
    fee: Decimal


class PublicSite(BaseModel):
    """What the public website shows (doc 08): cities, driver requirements and the fee tiers."""

    cities: list[str]
    driver: PublicDriverRequirements
    free_months: int
    fee_tiers: list[PublicFeeTier]
    payment_methods: list[PaymentMethod]
