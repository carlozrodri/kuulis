import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class ReportCategory(enum.StrEnum):
    SAFETY = "safety"
    HARASSMENT = "harassment"
    DRIVING = "driving"
    FARE = "fare"
    VEHICLE_MISMATCH = "vehicle_mismatch"
    LOST_ITEM = "lost_item"
    NO_SHOW = "no_show"
    APP_ISSUE = "app_issue"
    OTHER = "other"


URGENT_CATEGORIES = frozenset({ReportCategory.SAFETY, ReportCategory.HARASSMENT})
# Categories that make sense without a ride.
GENERAL_CATEGORIES = frozenset(
    {ReportCategory.APP_ISSUE, ReportCategory.LOST_ITEM, ReportCategory.OTHER}
)


class ReportStatus(enum.StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


OPEN_STATUSES = frozenset({ReportStatus.OPEN, ReportStatus.IN_REVIEW})


class ReportPriority(enum.StrEnum):
    NORMAL = "normal"
    URGENT = "urgent"


class ReporterRole(enum.StrEnum):
    PASSENGER = "passenger"
    DRIVER = "driver"


class NoteKind(enum.StrEnum):
    NOTE = "note"  # written by staff
    STATUS = "status"  # status, priority or assignee changes
    SUSPENSION = "suspension"  # an account suspension made from the report


class Report(BaseModel):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_status_created", "status", "created_at"),
        # One open report per ride and reporter.
        Index(
            "uq_reports_open_ride_reporter",
            "ride_id",
            "reporter_id",
            unique=True,
            postgresql_where=text("ride_id IS NOT NULL AND status IN ('open', 'in_review')"),
        ),
    )

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    reported_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rides.id", ondelete="SET NULL"), index=True
    )
    reporter_role: Mapped[ReporterRole | None] = mapped_column(_enum(ReporterRole, "reporter_role"))
    category: Mapped[ReportCategory] = mapped_column(_enum(ReportCategory, "report_category"))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(
        _enum(ReportStatus, "report_status"), default=ReportStatus.OPEN
    )
    priority: Mapped[ReportPriority] = mapped_column(
        _enum(ReportPriority, "report_priority"), default=ReportPriority.NORMAL
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class ReportNote(BaseModel):
    __tablename__ = "report_notes"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[NoteKind] = mapped_column(_enum(NoteKind, "report_note_kind"))
    body: Mapped[str] = mapped_column(Text)


class Suspension(BaseModel):
    """An account suspension. In force while not lifted and ``until`` is null or in the future;
    an expired one simply stops applying."""

    __tablename__ = "suspensions"
    __table_args__ = (Index("ix_suspensions_user_lifted", "user_id", "lifted_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(500))
    until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL")
    )
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lifted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
