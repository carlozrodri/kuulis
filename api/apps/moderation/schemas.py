import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from apps.drivers.models import DriverStatus
from apps.moderation.models import (
    GENERAL_CATEGORIES,
    NoteKind,
    ReportCategory,
    ReporterRole,
    ReportPriority,
    ReportStatus,
)
from apps.rides.schemas import RideAdminRead
from apps.users.schemas import SuspensionRead, UserBrief


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _text(min_length: int, max_length: int):
    return Annotated[
        str, BeforeValidator(_strip), Field(min_length=min_length, max_length=max_length)
    ]


# --- Reports -----------------------------------------------------------------------------------


class ReportCreate(BaseModel):
    category: ReportCategory
    description: _text(10, 2000)  # type: ignore[valid-type]
    ride_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _general(self) -> "ReportCreate":
        if self.ride_id is None and self.category not in GENERAL_CATEGORIES:
            raise ValueError("This category needs a ride")
        return self


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: ReportCategory
    description: str
    status: ReportStatus
    priority: ReportPriority
    ride_id: uuid.UUID | None
    reporter_role: ReporterRole | None
    created_at: datetime
    updated_at: datetime
    resolution: str | None
    resolved_at: datetime | None


class ReportAdminRead(ReportRead):
    reporter: UserBrief
    reported: UserBrief | None
    assigned_to: UserBrief | None
    notes_count: int


class ReportCounts(BaseModel):
    open: int
    in_review: int
    urgent_open: int


class ReportsPage(BaseModel):
    items: list[ReportAdminRead]
    total: int
    limit: int
    offset: int
    counts: ReportCounts


class ReportNoteRead(BaseModel):
    id: uuid.UUID
    body: str
    kind: NoteKind
    author: UserBrief | None
    created_at: datetime


class SuspensionHistoryRead(SuspensionRead):
    lifted_at: datetime | None
    lifted_by: UserBrief | None
    report_id: uuid.UUID | None


class ReportsAgainst(BaseModel):
    total: int
    open: int
    last_90_days: int


class PersonSummary(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role_in_ride: ReporterRole | None
    rating_avg: float | None
    rating_count: int
    rides_completed: int
    reports_against: ReportsAgainst
    suspension: SuspensionRead | None
    driver_profile_id: uuid.UUID | None
    driver_status: DriverStatus | None


class ReportAdminDetail(ReportAdminRead):
    ride: RideAdminRead | None
    notes: list[ReportNoteRead]
    reported_summary: PersonSummary | None
    reporter_summary: PersonSummary


class ReportUpdate(BaseModel):
    status: Literal[ReportStatus.OPEN, ReportStatus.IN_REVIEW] | None = None
    priority: ReportPriority | None = None
    assigned_to_id: uuid.UUID | None = None


class NoteCreate(BaseModel):
    body: _text(1, 2000)  # type: ignore[valid-type]


class ReportResolve(BaseModel):
    status: Literal[ReportStatus.RESOLVED, ReportStatus.DISMISSED]
    resolution: _text(3, 1000)  # type: ignore[valid-type]


# --- Suspensions -------------------------------------------------------------------------------


class SuspendRequest(BaseModel):
    reason: _text(3, 500)  # type: ignore[valid-type]
    until: datetime | None = None
    report_id: uuid.UUID | None = None
