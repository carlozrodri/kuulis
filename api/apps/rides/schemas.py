import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from apps.drivers.models import VehicleType
from apps.geo.schemas import Place, Point
from apps.promotions.schemas import PromotionBrief
from apps.rates.schemas import FrozenRates, VesAmount
from apps.rides.models import (
    CancelReason,
    CancelSide,
    OfferStatus,
    PaymentMethod,
    RatingRole,
    RideStatus,
)

# Amounts travel as 2-decimal strings ("2.40") so clients never do float math with money.
MoneyStr = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]
_TAG_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

PASSENGER_TAGS = ("safe_driving", "on_time", "friendly", "clean_helmet")  # passenger -> driver
DRIVER_TAGS = ("on_time", "respectful", "ready_at_pickup")  # driver -> passenger


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


# --- Quote and request -------------------------------------------------------------------------


class QuoteRequest(BaseModel):
    pickup: Place
    dropoff: Place
    vehicle_type: VehicleType
    promo_code: str | None = Field(default=None, max_length=40)


class Quote(BaseModel):
    quote_id: str
    vehicle_type: VehicleType
    pickup: Place
    dropoff: Place
    distance_m: int
    duration_s: int
    fare: MoneyStr
    surge_multiplier: MoneyStr
    # Why there is a surge (doc 21): a zone ("Alta demanda en esta zona"), the hour or the
    # manual multiplier; None without surge.
    surge_reason: Literal["zone", "time", "manual"] | None = None
    surge_zone: str | None = None
    discount: MoneyStr = Decimal("0.00")
    total: MoneyStr  # what the passenger pays: fare - discount
    promotion: PromotionBrief | None = None
    total_ves: VesAmount
    polyline: str | None
    expires_at: datetime


class RiderInfo(BaseModel):
    """Doc 23: who actually rides when the passenger requests for someone else."""

    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(pattern=r"^\+\d{10,15}$")  # E.164 ("+584121234567")

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _strip_required(value)


class RideCreate(BaseModel):
    quote_id: str = Field(min_length=1, max_length=64)
    # Plain string: unknown or disabled methods answer 400 payment_method_invalid (contract).
    payment_method: str = Field(max_length=32)
    # Doc 23: a note the driver sees before accepting, and the person riding (None: the passenger).
    note: str | None = Field(default=None, max_length=140)
    rider: RiderInfo | None = None

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        return " ".join((value or "").split()) or None


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    # Doc 15. Optional so older apps keep working; ``no_show`` needs the wait to be over.
    reason_code: CancelReason | None = None

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class AdminCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _strip_required(value)


# --- Ride --------------------------------------------------------------------------------------


class PersonBrief(BaseModel):
    id: uuid.UUID
    first_name: str
    rating: float | None
    # Passenger: shown to the driver only when the city's safety rule allows it (doc 11).
    photo_url: str | None = None


class VehicleBrief(BaseModel):
    brand: str
    model: str
    color: str
    plate: str


class DriverBrief(PersonBrief):
    photo_url: str | None
    vehicle: VehicleBrief | None


class DriverLocation(BaseModel):
    lat: float
    lng: float
    heading: float | None


class RatingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ride_id: uuid.UUID
    stars: int
    tags: list[str]
    comment: str | None
    created_at: datetime


class RideRead(BaseModel):
    id: uuid.UUID
    status: RideStatus
    vehicle_type: VehicleType
    pickup: Place
    dropoff: Place
    distance_m: int
    duration_s: int
    fare: MoneyStr
    surge_multiplier: MoneyStr
    discount: MoneyStr
    total: MoneyStr
    promotion: PromotionBrief | None
    rates: FrozenRates
    total_ves: VesAmount
    payment_method: PaymentMethod
    polyline: str | None
    passenger: PersonBrief
    driver: DriverBrief | None
    driver_location: DriverLocation | None
    requested_at: datetime
    assigned_at: datetime | None
    arrived_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    cancel_reason_code: CancelReason | None = None
    my_rating: RatingRead | None
    # Start PIN (doc 11): the driver must type it to start; only the passenger receives the code.
    pin_required: bool = False
    start_pin: str | None = None
    # Doc 15: drivers who cancelled after accepting (the ride went back to searching).
    reassign_count: int = 0
    # When the driver may mark "no se presentó" (arrived_at + the configured wait).
    no_show_at: datetime | None = None
    # Until then the passenger may cancel without it counting.
    cancel_free_until: datetime | None = None
    # Doc 23: note for the driver and the person riding when it is not the passenger. The phone
    # only reaches the passenger who requested (to send the live link) and the team.
    note: str | None = None
    rider_name: str | None = None
    rider_phone: str | None = None


class OfferPassenger(BaseModel):
    first_name: str
    rating: float | None
    photo_url: str | None = None


class Offer(BaseModel):
    ride_id: uuid.UUID
    pickup: Place
    dropoff: Place
    distance_m: int
    duration_s: int
    pickup_distance_m: int
    pickup_eta_s: int
    fare: MoneyStr
    discount: MoneyStr  # credited by Kuulis to the driver's wallet when the ride completes
    total: MoneyStr  # what the driver collects from the passenger
    total_ves: VesAmount
    payment_method: PaymentMethod
    passenger: OfferPassenger
    expires_at: datetime
    note: str | None = None
    rider_name: str | None = None  # doc 23: the ride is for this person, not the passenger


class DriverState(BaseModel):
    online: bool
    active_ride_id: uuid.UUID | None
    current_offer: Offer | None


# --- Chat and ratings --------------------------------------------------------------------------


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _strip_required(value)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ride_id: uuid.UUID
    sender_id: uuid.UUID
    text: str
    created_at: datetime


class RatingCreate(BaseModel):
    stars: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=10)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        tags = list(dict.fromkeys(t.strip().lower() for t in value))
        if any(not _TAG_RE.match(t) for t in tags):
            raise ValueError("tags must be snake_case identifiers (e.g. on_time)")
        return tags

    @field_validator("comment")
    @classmethod
    def _comment(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


# --- Admin -------------------------------------------------------------------------------------


class DriverAdminBrief(DriverBrief):
    profile_id: uuid.UUID | None  # DriverProfile id, for /admin/drivers/{id}


class RideAdminRead(RideRead):
    driver: DriverAdminBrief | None  # type: ignore[assignment]
    passenger_name: str
    passenger_email: str
    driver_name: str | None
    driver_email: str | None
    driver_profile_id: uuid.UUID | None
    cancelled_by_id: uuid.UUID | None
    pin_failures: int = 0
    reassigned_from_driver_id: uuid.UUID | None = None


class RatingAdminRead(RatingRead):
    rater_id: uuid.UUID
    ratee_id: uuid.UUID
    rater_role: RatingRole


class OfferAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    driver_name: str = ""
    status: OfferStatus
    pickup_distance_m: int
    pickup_eta_s: int
    sent_at: datetime
    expires_at: datetime
    responded_at: datetime | None


class RideSafetyAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    status: str
    user_id: uuid.UUID
    lat: float | None
    lng: float | None
    details: dict
    created_at: datetime
    resolved_at: datetime | None
    outcome: str | None


class CancellationAdminRead(BaseModel):
    """One cancellation of the ride (doc 15); a driver's sends the ride back to searching."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str = ""
    side: CancelSide
    reason_code: CancelReason | None
    reason: str | None
    stage: RideStatus
    counted: bool
    reassigned: bool
    created_at: datetime


class RideAdminDetail(RideAdminRead):
    messages: list[MessageRead]
    ratings: list[RatingAdminRead]
    offers: list[OfferAdminRead]
    # The driver's real path, [[lat, lng, unix_seconds], ...] (empty until the ride ends).
    track: list[list[float]] = Field(default_factory=list)
    safety_alerts: list[RideSafetyAlert] = Field(default_factory=list)
    cancellations: list[CancellationAdminRead] = Field(default_factory=list)


class StartRequest(BaseModel):
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")


class OnlineDriver(BaseModel):
    driver_id: uuid.UUID  # driver profile id (as in /admin/drivers/{id})
    driver_profile_id: uuid.UUID  # same value, explicit name
    user_id: uuid.UUID
    name: str
    vehicle_type: VehicleType
    lat: float | None
    lng: float | None
    last_seen_at: datetime | None
    active_ride_id: uuid.UUID | None


class GoOnline(Point):
    # Android reports positions from a mock location app; such a driver cannot go online.
    mocked: bool = False


class LocationUpdate(Point):
    """Position sent over HTTP by the background location service (the socket may be asleep)."""

    heading: float | None = Field(default=None, ge=0, le=360)
    speed: float | None = Field(default=None, ge=0, le=100)
    mocked: bool = False


# --- Driver stats ------------------------------------------------------------------------------


class PeriodStats(BaseModel):
    rides: int
    earnings: MoneyStr


class StatsDay(PeriodStats):
    date: date


class Compliment(BaseModel):
    tag: str  # one of PASSENGER_TAGS
    count: int


class DriverStats(BaseModel):
    """GET /drivers/me/stats: completed rides and earnings (fare - promo discount), Caracas time."""

    today: PeriodStats
    yesterday: PeriodStats
    week: PeriodStats  # Monday to today
    month: PeriodStats  # 1st to today
    last_month: PeriodStats
    by_day: list[StatsDay]  # last 7 days, oldest first
    total_rides: int
    rating: float | None
    # Doc 23: compliments (rating tags) passengers gave, most given first; ignored ratings out.
    compliments: list[Compliment] = Field(default_factory=list)


class FrequentPlace(BaseModel):
    address: str
    lat: float
    lng: float
    rides: int


class RideReceipt(BaseModel):
    """GET /rides/{id}/receipt (doc 23): what the shareable receipt image shows, and its link."""

    ride_id: uuid.UUID
    number: str  # short code for support, the start of the ride id
    completed_at: datetime
    pickup_address: str
    dropoff_address: str
    distance_m: int
    duration_s: int
    fare: MoneyStr
    discount: MoneyStr
    total: MoneyStr
    rates: FrozenRates
    total_ves: VesAmount
    payment_method: PaymentMethod
    passenger_name: str  # the person who rode (doc 23: may not be the account holder)
    driver_name: str
    plate: str | None
    # Signed PNG anyone with the link can open (sent by WhatsApp to whoever reimburses).
    image_url: str


class PassengerStats(BaseModel):
    """GET /rides/me/stats: what the passenger has done with Kuulis (completed rides only)."""

    rides: int
    distance_m: int
    spent: MoneyStr  # what the passenger paid: fare - promo discount
    frequent_places: list[FrequentPlace]  # most visited destinations, most rides first


# --- "Caracas en movimiento" (public, anonymous) -------------------------------------------------


class ActiveTrip(BaseModel):
    """A real trip in progress: approximate, delayed point; no names, plates or addresses."""

    id: str  # anonymous, changes every hour
    lat: float
    lng: float
    distance_m: int
    fare: MoneyStr  # what the passenger pays, all of it for the driver


class RecentTrip(BaseModel):
    minutes_ago: int  # in 5-minute steps
    distance_m: int
    fare: MoneyStr


class PublicActivity(BaseModel):
    live: bool  # False below the admin threshold: the app shows the honest message instead
    threshold: int
    trips_last_hour: int
    verified_drivers: int
    in_progress: list[ActiveTrip] = []
    recent: list[RecentTrip] = []
    updated_at: datetime
