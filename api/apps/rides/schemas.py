import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from apps.drivers.models import VehicleType
from apps.geo.schemas import Place, Point
from apps.promotions.schemas import PromotionBrief
from apps.rates.schemas import FrozenRates, VesAmount
from apps.rides.models import OfferStatus, PaymentMethod, RatingRole, RideStatus

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
    discount: MoneyStr = Decimal("0.00")
    total: MoneyStr  # what the passenger pays: fare - discount
    promotion: PromotionBrief | None = None
    total_ves: VesAmount
    polyline: str | None
    expires_at: datetime


class RideCreate(BaseModel):
    quote_id: str = Field(min_length=1, max_length=64)
    # Plain string: unknown or disabled methods answer 400 payment_method_invalid (contract).
    payment_method: str = Field(max_length=32)


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

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
    my_rating: RatingRead | None


class OfferPassenger(BaseModel):
    first_name: str
    rating: float | None


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


class RideAdminDetail(RideAdminRead):
    messages: list[MessageRead]
    ratings: list[RatingAdminRead]
    offers: list[OfferAdminRead]


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
    pass


class LocationUpdate(Point):
    """Position sent over HTTP by the background location service (the socket may be asleep)."""

    heading: float | None = Field(default=None, ge=0, le=360)
    speed: float | None = Field(default=None, ge=0, le=100)
