import re
import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.rides.models import RideStatus
from apps.rides.schemas import DriverLocation, Place, VehicleBrief
from apps.safety.models import AlertKind, AlertStatus

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
Phone = Field(pattern=r"^\+\d{10,15}$")


# --- Trusted contacts --------------------------------------------------------------------------


class ContactWrite(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Phone  # E.164 ("+584121234567")
    auto_share: bool = False
    # Both set: offer to share only in that window (Caracas time, may cross midnight).
    auto_share_from: str | None = None
    auto_share_to: str | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("auto_share_from", "auto_share_to")
    @classmethod
    def _hhmm(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        if not _HHMM.match(value):
            raise ValueError("expected HH:MM (24h)")
        return value

    @model_validator(mode="after")
    def _window(self) -> Self:
        if (self.auto_share_from is None) != (self.auto_share_to is None):
            raise ValueError("auto_share_from and auto_share_to go together")
        if self.auto_share_from is not None and self.auto_share_from == self.auto_share_to:
            raise ValueError("auto_share_from and auto_share_to must differ")
        return self


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    auto_share: bool
    auto_share_from: str | None
    auto_share_to: str | None


# --- Sharing a ride ----------------------------------------------------------------------------


class ShareLink(BaseModel):
    url: str
    token: str


class SharedPerson(BaseModel):
    first_name: str
    photo_url: str | None = None
    rating: float | None = None


class SharedRide(BaseModel):
    """What ``/v/{token}`` shows: no ids, no phone numbers, no prices."""

    status: RideStatus
    pickup: Place
    dropoff: Place
    polyline: str | None
    passenger: SharedPerson
    driver: SharedPerson | None
    vehicle: VehicleBrief | None
    driver_location: DriverLocation | None
    started_at: datetime | None
    # Estimated arrival at the destination (null before the ride starts).
    eta: datetime | None
    # An SOS is open on this ride: the page shows it and its last known position.
    sos: bool
    sos_location: DriverLocation | None
    updated_at: datetime


# --- SOS and check-ins -------------------------------------------------------------------------


class Position(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SosRequest(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class AlertRead(BaseModel):
    """An alert as its own user sees it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ride_id: uuid.UUID | None
    kind: AlertKind
    status: AlertStatus
    created_at: datetime
    check_in_deadline: datetime | None = None


class SosRead(AlertRead):
    share_url: str | None  # to send to the trusted contacts
    location_seconds: int  # send POST /safety/location this often while the SOS is open


class CheckInAnswer(BaseModel):
    answer: Literal["ok", "help"]


# --- Admin -------------------------------------------------------------------------------------


class AlertParty(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None  # drivers only (from their profile)
    role: Literal["passenger", "driver"]


class AlertAdminRead(BaseModel):
    id: uuid.UUID
    ride_id: uuid.UUID | None
    ride_status: RideStatus | None
    kind: AlertKind
    status: AlertStatus
    raised_by: AlertParty | None
    passenger: AlertParty | None
    driver: AlertParty | None
    vehicle: VehicleBrief | None
    lat: float | None
    lng: float | None
    location_at: datetime | None
    driver_location: DriverLocation | None
    pickup: Place | None
    dropoff: Place | None
    polyline: str | None
    details: dict
    answers: dict
    check_in_deadline: datetime | None
    escalated_at: datetime | None
    acknowledged_at: datetime | None
    handled_by_id: uuid.UUID | None
    handled_by_name: str | None
    notes: str
    outcome: str | None
    created_at: datetime
    resolved_at: datetime | None


class AlertSummary(BaseModel):
    """Sidebar badge and sound: alerts that need the team."""

    open: int
    acknowledged: int
    latest_id: uuid.UUID | None  # newest open alert (a new id rings the bell)


Outcome = Literal["false_alarm", "assisted", "emergency_services", "no_answer", "other"]


class AlertResolve(BaseModel):
    outcome: Outcome
    notes: str = Field(default="", max_length=2000)


class AlertNotes(BaseModel):
    notes: str = Field(max_length=2000)
