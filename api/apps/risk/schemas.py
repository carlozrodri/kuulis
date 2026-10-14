import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.drivers.schemas import Duplicate
from apps.risk.models import HoldKind, HoldStatus, RiskKind, SignalStatus
from apps.wallet.schemas import MoneyStr


class RiskUser(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None  # None once the account was erased
    risk_score: int
    driver_profile_id: uuid.UUID | None = None


class SignalRead(BaseModel):
    id: uuid.UUID
    kind: RiskKind
    reasons: list[str]
    score: int
    status: SignalStatus
    evidence: dict[str, Any]
    user: RiskUser
    related_user: RiskUser | None
    ride_id: uuid.UUID | None
    created_at: datetime
    reviewed_by_name: str | None
    reviewed_at: datetime | None
    review_note: str | None


class RideEvidence(BaseModel):
    id: uuid.UUID
    status: str
    pickup: list[float]  # [lat, lng]
    dropoff: list[float]
    distance_m: int
    duration_s: int
    discount: MoneyStr
    started_at: datetime | None
    completed_at: datetime | None
    # The driver's real path, [[lat, lng, unix_seconds], ...] (empty when nothing was recorded).
    track: list[list[float]]


class HoldRead(BaseModel):
    id: uuid.UUID
    kind: HoldKind
    status: HoldStatus
    amount: MoneyStr
    user: RiskUser
    sender: RiskUser | None
    ride_id: uuid.UUID | None
    reasons: list[str]
    release_at: datetime | None
    created_at: datetime
    resolved_at: datetime | None
    resolved_by_name: str | None
    note: str | None


class SignalDetail(SignalRead):
    ride: RideEvidence | None
    # Shared device: every account on the phone; otherwise the two people involved.
    accounts: list[RiskUser]
    holds: list[HoldRead]


class ReviewWrite(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class BanWrite(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class DeviceRead(BaseModel):
    id: uuid.UUID
    platform: str
    model: str
    app_version: str
    first_seen: datetime
    last_seen: datetime
    other_accounts: list[RiskUser]


class BlockedRead(BaseModel):
    id: uuid.UUID
    kind: str
    reason: str
    source_user: RiskUser | None
    created_at: datetime
    created_by_name: str | None


class RiskUserDetail(BaseModel):
    user: RiskUser
    frozen: bool  # promotion credits wait and outgoing transfers are blocked
    suspended: bool
    signals: list[SignalRead]
    devices: list[DeviceRead]
    duplicates: list[Duplicate]
    holds: list[HoldRead]
    blocked: list[BlockedRead]


class KindCount(BaseModel):
    kind: RiskKind
    open: int


class RiskSummary(BaseModel):
    open: list[KindCount]
    holds: int
    held_amount: MoneyStr
