import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class TrustedContact(BaseModel):
    """Someone the user trusts, to share rides with through the phone's own messaging app."""

    __tablename__ = "trusted_contacts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20))  # E.164
    # Offer to share every ride with this contact; only between ``auto_share_from`` and
    # ``auto_share_to`` (Caracas time, "HH:MM") when both are set ("de noche").
    auto_share: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    auto_share_from: Mapped[str | None] = mapped_column(String(5))
    auto_share_to: Mapped[str | None] = mapped_column(String(5))


class RideShareLink(BaseModel):
    """A public link to follow one ride live (``/v/{token}``). Only the token's hash is stored."""

    __tablename__ = "ride_share_links"
    __table_args__ = (Index("ix_ride_share_links_ride_creator", "ride_id", "created_by_id"),)

    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Doc 23: sent to the person riding (ride requested for someone else); it shows the start PIN.
    for_rider: Mapped[bool] = mapped_column(default=False, server_default=text("false"))


class RideTrack(BaseModel):
    """The driver's real path during a ride, written once when the ride ends.

    ``points`` is ``[[lat, lng, unix_seconds], ...]``, already thinned (see ``apps.safety.track``).
    """

    __tablename__ = "ride_tracks"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), unique=True
    )
    points: Mapped[list] = mapped_column(JSONB, default=list)
    point_count: Mapped[int] = mapped_column(Integer, default=0)


class AlertKind(enum.StrEnum):
    SOS = "sos"
    STOP = "stop"  # stopped too long away from the destination
    DEVIATION = "deviation"  # far from the planned route for a while
    OVERTIME = "overtime"  # much longer than estimated


class AlertStatus(enum.StrEnum):
    # An anomaly waits for the "¿Todo bien?" answer; it reaches the team only if it escalates.
    CHECKING = "checking"
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"  # someone on the team is on it
    RESOLVED = "resolved"
    DISMISSED = "dismissed"  # the passenger answered "Estoy bien"


ACTIVE_ALERT_STATUSES = frozenset({AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED})


class SafetyAlert(BaseModel):
    __tablename__ = "safety_alerts"
    __table_args__ = (
        Index("ix_safety_alerts_status_created", "status", "created_at"),
        # One anomaly of each kind per ride (an SOS can repeat).
        Index(
            "uq_safety_alerts_ride_anomaly",
            "ride_id",
            "kind",
            unique=True,
            postgresql_where=text("kind <> 'sos'"),
        ),
    )

    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), index=True
    )
    # Who pressed SOS; for anomalies, the passenger.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[AlertKind] = mapped_column(_enum(AlertKind, "safety_alert_kind"))
    status: Mapped[AlertStatus] = mapped_column(_enum(AlertStatus, "safety_alert_status"))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What triggered an anomaly ({"minutes": 12, "distance_m": 840, ...}).
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    # "¿Todo bien?": deadline and answers ({"<user_id>": "ok" | "help"}).
    check_in_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    outcome: Mapped[str | None] = mapped_column(String(40))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
