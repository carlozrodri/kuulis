import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from apps.quality.models import PauseReason, QualityLevel, QualityRole
from apps.rides.models import CancelReason, CancelSide


class PauseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: QualityRole
    reason: PauseReason
    created_at: datetime
    until: datetime
    lifted_at: datetime | None
    lifted_by_id: uuid.UUID | None


class QualityValues(BaseModel):
    """Rates over the last ``window_days`` days (None: nothing to divide by yet)."""

    model_config = ConfigDict(from_attributes=True)

    offers: int = 0
    accepted: int = 0
    rides: int = 0
    cancels: int = 0
    no_shows: int = 0
    completed: int = 0
    acceptance_rate: float | None = None
    cancel_rate: float | None = None
    rating_avg: float | None = None
    rating_count: int = 0
    level: QualityLevel = QualityLevel.OK
    reasons: list[str] = []


class DriverThresholds(BaseModel):
    window_days: int
    min_rides: int
    cancel_warn: float
    cancel_low_priority: float
    cancel_review: float
    rating_review_below: float
    rating_min_count: int
    cancel_burst: int
    decline_streak: int
    pause_minutes: int
    pickup_wait_minutes: int


class DriverQualityRead(QualityValues):
    """``GET /drivers/me/quality``: the driver's own panel."""

    thresholds: DriverThresholds
    paused_until: datetime | None = None
    pause_reason: PauseReason | None = None


class QualityRowRead(QualityValues):
    """A row of the admin's Quality list."""

    user_id: uuid.UUID
    role: QualityRole
    name: str
    email: str
    driver_profile_id: uuid.UUID | None = None
    computed_at: datetime
    paused_until: datetime | None = None


class QualityWeek(BaseModel):
    week: date
    offers: int
    accepted: int
    acceptance_rate: float | None
    driver_cancels: int
    driver_cancel_rate: float | None
    passenger_rides: int
    passenger_cancels: int
    passenger_cancel_rate: float | None
    no_shows: int


class QualityDetail(BaseModel):
    """A person's quality in the admin (live, both roles when they drive)."""

    user_id: uuid.UUID
    driver: QualityValues | None
    passenger: QualityValues
    weeks: list[QualityWeek]
    pauses: list[PauseRead]
    window_days: int


class CancellationCount(BaseModel):
    side: CancelSide
    reason_code: CancelReason | None
    total: int
    counted: int
    reassigned: int
