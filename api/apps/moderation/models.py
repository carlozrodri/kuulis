import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
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


class ReportSource(enum.StrEnum):
    APP = "app"  # "Reportar un problema" in the app
    HELP = "help"  # "Contactar" from a help article
    LOST_ITEM = "lost_item"  # the lost item flow (doc 13)
    WEB = "web"  # the public contact form, maybe without an account


class WaitingOn(enum.StrEnum):
    """Whose turn it is in an open ticket."""

    STAFF = "staff"
    USER = "user"


class AuthorKind(enum.StrEnum):
    USER = "user"
    STAFF = "staff"
    SYSTEM = "system"  # automatic lines: closed for inactivity, the driver has the lost item...


class NoteKind(enum.StrEnum):
    NOTE = "note"  # written by staff
    STATUS = "status"  # status, priority or assignee changes
    SUSPENSION = "suspension"  # an account suspension made from the report


class Report(BaseModel):
    """A support ticket (doc 13): a report about a ride or a general question, with a conversation
    between the user and the team. ``reporter_id`` is empty for the web form without an account,
    which answers by email (``contact_email``)."""

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_status_created", "status", "created_at"),
        Index("ix_reports_waiting_sla", "waiting_on", "sla_due_at"),
        # One open report per ride and reporter.
        Index(
            "uq_reports_open_ride_reporter",
            "ride_id",
            "reporter_id",
            unique=True,
            postgresql_where=text("ride_id IS NOT NULL AND status IN ('open', 'in_review')"),
        ),
    )

    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
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
    # --- Conversation and support (doc 13) ---
    source: Mapped[ReportSource] = mapped_column(
        _enum(ReportSource, "report_source"), default=ReportSource.APP, server_default="app"
    )
    waiting_on: Mapped[WaitingOn | None] = mapped_column(_enum(WaitingOn, "report_waiting_on"))
    waiting_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the team should have answered; cleared while the ticket waits on the user.
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The team's last message and when the user last opened the conversation: "new reply" badge.
    last_staff_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list, server_default="{}")
    csat: Mapped[int | None] = mapped_column(SmallInteger)
    csat_comment: Mapped[str | None] = mapped_column(String(500))
    csat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(5), default="es", server_default="es")
    help_article_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("help_articles.id", ondelete="SET NULL")
    )


class ReportMessage(BaseModel):
    """One message of a ticket's conversation, seen by the user (internal notes stay in
    ``report_notes``). Attachments are storage keys (photos)."""

    __tablename__ = "report_messages"
    __table_args__ = (Index("ix_report_messages_report_created", "report_id", "created_at"),)

    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    author_kind: Mapped[AuthorKind] = mapped_column(_enum(AuthorKind, "report_author_kind"))
    body: Mapped[str] = mapped_column(Text)
    attachments: Mapped[list[str]] = mapped_column(
        ARRAY(String(512)), default=list, server_default="{}"
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
