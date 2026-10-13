"""Service quality (doc 15): per-person rates refreshed in the background and short automatic
pauses. Nothing here costs money."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class QualityRole(enum.StrEnum):
    DRIVER = "driver"
    PASSENGER = "passenger"


class QualityLevel(enum.StrEnum):
    """Ordered from fine to worst; see ``LEVEL_ORDER``."""

    OK = "ok"
    WARN = "warn"
    LOW_PRIORITY = "low_priority"  # drivers only: offered rides after better-rated drivers
    REVIEW = "review"  # shows in the admin's Quality list


LEVEL_ORDER = {level: i for i, level in enumerate(QualityLevel)}


class PauseReason(enum.StrEnum):
    CANCEL_BURST = "cancel_burst"  # driver: several cancellations in an hour
    DECLINE_STREAK = "decline_streak"  # driver: offers declined or ignored in a row
    NO_SHOWS = "no_shows"  # passenger: did not show up several times


class QualityStats(BaseModel):
    """Rates of one person in one role over the configured window. Refreshed every few minutes
    by the worker; the person's own screen and the admin's detail compute them live."""

    __tablename__ = "quality_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "role"),
        Index("ix_quality_stats_role_level", "role", "level"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[QualityRole] = mapped_column(_enum(QualityRole, "quality_role"))
    # Driver: offers answered or missed, accepted rides, counted cancellations, completed rides.
    # Passenger: rides that got a driver, counted cancellations, no-shows, completed rides.
    offers: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    accepted: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    rides: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    cancels: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    no_shows: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    completed: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    acceptance_rate: Mapped[float | None] = mapped_column(Float)
    cancel_rate: Mapped[float | None] = mapped_column(Float)
    rating_avg: Mapped[float | None] = mapped_column(Float)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    level: Mapped[QualityLevel] = mapped_column(
        _enum(QualityLevel, "quality_level"), default=QualityLevel.OK
    )
    # Which rules set the level: cancel_rate, rating, no_shows.
    reasons: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), default=list, server_default=text("'{}'")
    )
    # Highest level the person was told about, so each warning goes out once.
    warned_level: Mapped[QualityLevel] = mapped_column(
        _enum(QualityLevel, "quality_level"), default=QualityLevel.OK
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QualityPause(BaseModel):
    """A short automatic pause: a driver cannot go online, a passenger cannot request rides."""

    __tablename__ = "quality_pauses"
    __table_args__ = (Index("ix_quality_pauses_user_until", "user_id", "until"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[QualityRole] = mapped_column(_enum(QualityRole, "quality_role"))
    reason: Mapped[PauseReason] = mapped_column(_enum(PauseReason, "pause_reason"))
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lifted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    @property
    def ends_at(self) -> datetime:
        """When it stopped applying: lifted early or ran out."""
        return self.lifted_at if self.lifted_at and self.lifted_at < self.until else self.until
