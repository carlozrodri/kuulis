import re
from datetime import datetime, time
from decimal import Decimal
from itertools import pairwise
from typing import Annotated, Any, Literal, Self

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
from apps.zones import geometry

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


LatLngPair = Annotated[list[float], Field(min_length=2, max_length=2)]
Polygon = Annotated[list[LatLngPair], Field(min_length=3, max_length=300)]


def check_polygon(value: list[list[float]] | None) -> list[list[float]] | None:
    """Normalizes an open ring ``[[lat, lng], ...]`` and rejects crossing edges (doc 21)."""
    if value is None:
        return None
    points = geometry.ring(value)
    if reason := geometry.problem(points):
        raise ValueError(reason)
    return [[lat, lng] for lat, lng in points]


class ServiceArea(BaseModel):
    """A city. With ``polygon`` (doc 21) only the polygon counts and the box is the rectangle that
    encloses it (search bias and centre); without it the box is the city, as before."""

    name: str = Field(default="Caracas", min_length=1, max_length=60)
    min_lat: float = Field(ge=-90, le=90)
    max_lat: float = Field(ge=-90, le=90)
    min_lng: float = Field(ge=-180, le=180)
    max_lng: float = Field(ge=-180, le=180)
    polygon: Polygon | None = None

    @model_validator(mode="before")
    @classmethod
    def _box_from_polygon(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("polygon"):
            try:
                points = geometry.ring(data["polygon"])
                min_lat, max_lat, min_lng, max_lng = geometry.bbox(points)
            except (TypeError, ValueError, IndexError):
                return data  # the field validation explains what is wrong
            data = data | {
                "min_lat": min_lat,
                "max_lat": max_lat,
                "min_lng": min_lng,
                "max_lng": max_lng,
            }
        return data

    @field_validator("polygon")
    @classmethod
    def _polygon(cls, value: list[list[float]] | None) -> list[list[float]] | None:
        return check_polygon(value)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min_lat >= self.max_lat or self.min_lng >= self.max_lng:
            raise ValueError("min values must be lower than max values")
        return self

    def contains(self, lat: float, lng: float) -> bool:
        if not (self.min_lat <= lat <= self.max_lat and self.min_lng <= lng <= self.max_lng):
            return False
        if self.polygon is None:
            return True
        return geometry.contains([(p[0], p[1]) for p in self.polygon], lat, lng)

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


class CityPair(BaseModel):
    """Trips allowed between two cities, both ways (doc 21)."""

    a: str = Field(min_length=1, max_length=60)
    b: str = Field(min_length=1, max_length=60)

    def joins(self, one: str, other: str) -> bool:
        return {self.a, self.b} == {one, other}


class DemandSettings(BaseModel):
    """The drivers' demand map (doc 21): H3 cells counted over a sliding window."""

    enabled: bool = True
    window_minutes: int = Field(default=15, ge=5, le=60)
    # Requests in the window from which a cell counts as busy (level 2, or 3 with unmatched).
    hot_requests: int = Field(default=3, ge=1, le=100)
    notify: bool = True
    notify_radius_m: int = Field(default=3000, ge=500, le=20000)
    notify_every_minutes: int = Field(default=30, ge=5, le=24 * 60)


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
    # Someone on call answers SOS alerts: Telegram plus the admin alarm. Off (Carlos, 2026-10-13):
    # the SOS calls the emergency number and goes to the trusted contacts only; the admin keeps
    # the record.
    sos_team_alert: bool = False

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


class SupportSettings(BaseModel):
    """Support tickets (doc 13): response times, auto-close and how new tickets are assigned."""

    # Time to the team's answer, measured while the ticket waits on the team. Overdue tickets
    # are flagged in the admin; urgent ones also alert the team (03).
    sla_urgent_minutes: int = Field(default=15, ge=1, le=24 * 60)
    sla_normal_hours: int = Field(default=24, ge=1, le=24 * 14)
    # What the app and the web promise ("Respondemos en menos de 24 h"); empty hides it.
    response_promise_es: str = Field(default="Respondemos en menos de 24 horas.", max_length=120)
    response_promise_en: str = Field(default="We answer within 24 hours.", max_length=120)
    # A ticket waiting on the user this many days is closed (the user can still reply then).
    auto_close_days: int = Field(default=7, ge=1, le=60)
    # New tickets go to the staff member with support permission and the fewest open tickets.
    auto_assign: bool = False
    # Lost items: the passenger can ask up to this many days after the ride; the chat with the
    # driver stays open this many hours after "Lo tengo".
    lost_item_days: int = Field(default=7, ge=1, le=30)
    lost_item_chat_hours: int = Field(default=72, ge=1, le=24 * 14)


class NotificationSettings(BaseModel):
    """Notifications (doc 14): marketing limits, default quiet hours and housekeeping."""

    # Marketing (campaigns) never goes out in these hours, Caracas time; each user can change
    # their own window in the app. Equal values turn the default window off.
    quiet_start: str = Field(default="21:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_end: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    # At most this many marketing notifications per user per day (0 = no limit).
    marketing_daily_cap: int = Field(default=1, ge=0, le=10)
    # Inbox rows older than this are deleted; phones unused this long stop getting pushes.
    inbox_retention_days: int = Field(default=90, ge=7, le=730)
    device_idle_days: int = Field(default=60, ge=7, le=365)
    # Drivers get a summary email of their month on the 1st.
    monthly_summary: bool = True


class QualitySettings(BaseModel):
    """Cancellations and service quality (doc 15). Consequences never cost money: warnings,
    short pauses and a lower place in dispatch."""

    # The driver may mark "no se presentó" this long after arriving (the counter both apps show).
    pickup_wait_minutes: int = Field(default=5, ge=1, le=30)
    # A passenger cancellation this soon after a driver accepts does not count.
    passenger_cancel_grace_s: int = Field(default=120, ge=0, le=900)
    # Rates use rides of the last this many days.
    window_days: int = Field(default=30, ge=7, le=180)
    # Driver: this many counted cancellations in an hour, or this many offers declined or
    # ignored in a row, pause them for ``driver_pause_minutes`` (0 turns the rule off).
    driver_cancel_burst: int = Field(default=3, ge=0, le=20)
    driver_decline_streak: int = Field(default=5, ge=0, le=50)
    driver_pause_minutes: int = Field(default=15, ge=1, le=240)
    # Driver cancellation rate (share of accepted rides): warning, lower dispatch priority,
    # then review in the admin. Only once they have ``min_rides`` accepted rides in the window.
    driver_cancel_warn: float = Field(default=0.15, ge=0, le=1)
    driver_cancel_low_priority: float = Field(default=0.25, ge=0, le=1)
    driver_cancel_review: float = Field(default=0.35, ge=0, le=1)
    min_rides: int = Field(default=10, ge=1, le=200)
    # Passenger no-shows in the window: warning, then a pause to request rides.
    passenger_no_show_warn: int = Field(default=2, ge=0, le=50)
    passenger_no_show_pause: int = Field(default=3, ge=0, le=50)
    passenger_pause_hours: int = Field(default=24, ge=1, le=720)
    # Average rating under this with at least ``rating_min_count`` ratings: review in the admin.
    rating_review_below: float = Field(default=4.3, ge=1, le=5)
    rating_min_count: int = Field(default=20, ge=1, le=500)
    # How much rating and acceptance move a driver in dispatch, on top of distance (0: off).
    # A driver with the worst score is treated as up to this share farther away.
    dispatch_quality_weight: float = Field(default=0.2, ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not (
            self.driver_cancel_warn <= self.driver_cancel_low_priority <= self.driver_cancel_review
        ):
            raise ValueError(
                "driver cancellation thresholds must go warn <= low priority <= review"
            )
        if (
            self.passenger_no_show_pause
            and self.passenger_no_show_warn > self.passenger_no_show_pause
        ):
            raise ValueError("passenger_no_show_warn must be <= passenger_no_show_pause")
        return self


class RiskSettings(BaseModel):
    """Anti-fraud rules (doc 16): simple signals a person reviews, never automatic bans."""

    # Signals of the last this many days add up to a person's risk score (0-100).
    window_days: int = Field(default=90, ge=7, le=365)
    # From this score, promotion credits wait for review and outgoing transfers are blocked.
    freeze_score: int = Field(default=60, ge=10, le=100)
    # A ride whose findings add up to this holds its promotion credit until someone reviews it.
    ride_hold_score: int = Field(default=30, ge=5, le=100)
    # More accounts than this on one phone raise a "shared device" alert.
    max_accounts_per_device: int = Field(default=2, ge=1, le=20)
    # Suspicious ride: real path under this share of the estimate, real duration under this
    # share of the estimate, or start and end this close (only for rides of ``min_ride_m``+).
    min_path_share: float = Field(default=0.3, ge=0, le=1)
    min_duration_share: float = Field(default=0.3, ge=0, le=1)
    same_place_m: int = Field(default=150, ge=20, le=2000)
    min_ride_m: int = Field(default=1000, ge=100, le=20000)
    # A passenger and a driver with this many completed rides together in ``pair_days``.
    pair_rides: int = Field(default=5, ge=2, le=100)
    pair_days: int = Field(default=30, ge=1, le=180)
    # Fake GPS: this many jumps faster than 150 km/h within 10 minutes raise an alert.
    jump_alerts: int = Field(default=3, ge=1, le=50)
    # Transfers: the first one of each account waits this long (0: off); money passed on within
    # ``chain_minutes``; a driver receiving from this many senders in 7 days; accounts younger
    # than ``new_account_days`` receiving balance.
    first_transfer_hold_hours: int = Field(default=24, ge=0, le=168)
    chain_minutes: int = Field(default=60, ge=5, le=1440)
    fan_in_senders: int = Field(default=5, ge=2, le=100)
    new_account_days: int = Field(default=7, ge=0, le=90)
    # Mutual 5-star ratings between the same two people this many times in 30 days.
    rating_ring_rides: int = Field(default=3, ge=2, le=50)


Budget = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1000000"), decimal_places=2, allow_inf_nan=False),
    AfterValidator(_two_places),
    AsMoneyString,
]


class ReferralProgram(BaseModel):
    """Drivers inviting drivers (doc 22). The inviter earns ``reward_usd`` of wallet credit (not
    withdrawable, like promotion credits) once the invited driver completes ``required_trips``
    within ``window_days`` of being approved. Passenger referrals are not offered yet (Carlos,
    2026-10-11: drivers only at launch)."""

    enabled: bool = True
    reward_usd: Money = Decimal("5.00")
    required_trips: int = Field(default=20, ge=1, le=500)
    window_days: int = Field(default=30, ge=1, le=365)
    # The invited driver also gets a free month of subscription when they qualify.
    referred_free_month: bool = False
    # Rewards per inviter per month (0: no limit); the rest wait for the next month.
    monthly_cap: int = Field(default=10, ge=0, le=1000)
    # Paid plus held rewards never go over this; the rest wait until it is raised.
    budget_usd: Budget = Decimal("500.00")
    # New codes are accepted only between these dates (null: no limit). Invites made in time keep
    # their reward after ``ends_at``.
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self

    def accepting(self, now: datetime) -> bool:
        """New invite codes can be entered."""
        return (
            self.enabled
            and (self.starts_at is None or self.starts_at <= now)
            and (self.ends_at is None or now < self.ends_at)
        )


class VerificationSettings(BaseModel):
    """Ongoing driver verification (doc 12): expiring documents, the random live selfie,
    re-verification after reports and the optional induction."""

    # Documents that carry an expiry date; once expired the driver cannot go online.
    expiring_documents: list[DocumentKind] = Field(
        default_factory=lambda: [
            DocumentKind.DRIVERS_LICENSE,
            DocumentKind.MEDICAL_CERTIFICATE,
            DocumentKind.VEHICLE_REGISTRATION,
        ]
    )
    # Documents the driver may add without being asked (certificado de antecedentes).
    optional_documents: list[DocumentKind] = Field(
        default_factory=lambda: [DocumentKind.CRIMINAL_RECORD]
    )
    # "Expires in N days" notices before the expiry day.
    expiry_notice_days: list[int] = Field(default_factory=lambda: [30, 7, 1], max_length=5)
    # A live selfie roughly this often, on a random day, when going online (0: never). Weekly
    # (Carlos, 2026-10-13).
    selfie_every_days: int = Field(default=7, ge=0, le=90)
    # This many vehicle_mismatch reports in ``report_window_days`` ask for a selfie and new photos.
    mismatch_reports: int = Field(default=2, ge=1, le=20)
    report_window_days: int = Field(default=30, ge=1, le=365)
    # "Inducción completada" must be marked in the admin before approving a driver.
    induction_required: bool = False

    @field_validator("expiring_documents", "optional_documents")
    @classmethod
    def _unique_kinds(cls, value: list[DocumentKind]) -> list[DocumentKind]:
        return _unique(value)

    @field_validator("expiry_notice_days")
    @classmethod
    def _days(cls, value: list[int]) -> list[int]:
        if any(d < 1 or d > 120 for d in value):
            raise ValueError("days must be between 1 and 120")
        return sorted(set(value), reverse=True)


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
    # Waiving or lowering a driver's monthly fee (doc 17).
    approval_waivers: bool = True

    # --- Remote control (doc 10) ----------------------------------------------------------------
    # maintenance and area_pauses change only through PUT /admin/app/status (not in the update).
    maintenance: Maintenance = Field(default_factory=Maintenance)
    area_pauses: list[AreaPause] = Field(default_factory=list, max_length=20)
    app_links: AppLinks = Field(default_factory=AppLinks)
    location_intervals: LocationIntervals = Field(default_factory=LocationIntervals)

    # --- Trip safety (doc 11) -------------------------------------------------------------------
    safety: SafetySettings = Field(default_factory=SafetySettings)

    # --- Driver verification (doc 12) -----------------------------------------------------------
    verification: VerificationSettings = Field(default_factory=VerificationSettings)

    # --- Support (doc 13) -------------------------------------------------------------------------
    support: SupportSettings = Field(default_factory=SupportSettings)

    # --- Notifications (doc 14) ---------------------------------------------------------------
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)

    # --- Cancellations and quality (doc 15) -----------------------------------------------------
    quality: QualitySettings = Field(default_factory=QualitySettings)

    # --- Anti-fraud (doc 16) ----------------------------------------------------------------------
    risk: RiskSettings = Field(default_factory=RiskSettings)

    # --- Zones and demand (doc 21) --------------------------------------------------------------
    intercity_pairs: list[CityPair] = Field(default_factory=list, max_length=50)
    demand: DemandSettings = Field(default_factory=DemandSettings)

    # --- Referrals (doc 22) -----------------------------------------------------------------------
    referral_program: ReferralProgram = Field(default_factory=ReferralProgram)

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
        names = [a.name for a in self.service_areas]
        unknown = sorted({n for p in self.intercity_pairs for n in (p.a, p.b)} - set(names))
        if unknown:
            raise ValueError(f"intercity_pairs name unknown cities: {', '.join(unknown)}")
        return self

    def city_named(self, name: str) -> ServiceArea | None:
        return next((a for a in self.service_areas if a.name == name), None)

    def intercity_allowed(self, one: str, other: str) -> bool:
        return one == other or any(p.joins(one, other) for p in self.intercity_pairs)

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
    approval_waivers: bool | None = None
    app_links: AppLinks | None = None
    location_intervals: LocationIntervals | None = None
    safety: SafetySettings | None = None
    verification: VerificationSettings | None = None
    support: SupportSettings | None = None
    notifications: NotificationSettings | None = None
    quality: QualitySettings | None = None
    risk: RiskSettings | None = None
    intercity_pairs: list[CityPair] | None = Field(default=None, max_length=50)
    demand: DemandSettings | None = None
    referral_program: ReferralProgram | None = None

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
