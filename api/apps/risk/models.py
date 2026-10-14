"""Anti-fraud (doc 16): device fingerprints, risk signals a person reviews, money held until that
review, and identifiers of banned accounts. Rules only; no paid services."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class RiskKind(enum.StrEnum):
    SHARED_DEVICE = "shared_device"  # more accounts than allowed on one phone
    FAKE_GPS = "fake_gps"  # simulated location or impossible jumps
    SUSPICIOUS_RIDE = "suspicious_ride"  # same phone, little movement, too short, same place
    FREQUENT_PAIR = "frequent_pair"  # a passenger and a driver always together
    TRANSFERS = "transfers"  # chains, many senders, new accounts receiving balance
    RATING_RING = "rating_ring"  # mutual 5 stars again and again


class SignalStatus(enum.StrEnum):
    OPEN = "open"
    DISMISSED = "dismissed"  # reviewed, nothing wrong: stops counting in the score
    CONFIRMED = "confirmed"  # reviewed, it was abuse: keeps counting


class HoldKind(enum.StrEnum):
    PROMO_CREDIT = "promo_credit"  # Kuulis' payment of a promotion discount to the driver
    TRANSFER = "transfer"  # money a driver sent, not yet in the recipient's wallet


class HoldStatus(enum.StrEnum):
    HELD = "held"
    RELEASED = "released"  # paid to the recipient (by a person or, for transfers, by time)
    VOIDED = "voided"  # not paid; a voided transfer goes back to the sender


class DeviceFingerprint(BaseModel):
    """A phone an account used, seen when tokens are issued (login and refresh). The install id
    is kept only as a keyed hash, the same one the identity marks use (doc 12)."""

    __tablename__ = "device_fingerprints"
    __table_args__ = (
        UniqueConstraint("user_id", "device_hash", name="uq_device_fingerprints_user_device"),
        Index("ix_device_fingerprints_device_hash", "device_hash"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    device_hash: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str] = mapped_column(String(20), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    app_version: Mapped[str] = mapped_column(String(32), default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskSignal(BaseModel):
    """Something that looks like abuse, for a person to review. ``dedupe_key`` keeps a rule from
    raising the same alert twice (one per ride, per device and count, per pair and window...)."""

    __tablename__ = "risk_signals"
    __table_args__ = (
        Index("ix_risk_signals_status_created", "status", "created_at"),
        Index("ix_risk_signals_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # The other account involved (the passenger of a ride, the other half of a pair...).
    related_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rides.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[RiskKind] = mapped_column(_enum(RiskKind, "risk_kind"))
    # Which rules fired, e.g. ["same_device", "little_movement"] or ["chain"].
    reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    score: Mapped[int] = mapped_column(SmallInteger)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[SignalStatus] = mapped_column(
        _enum(SignalStatus, "risk_signal_status"), default=SignalStatus.OPEN
    )
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(String(500))


class RiskHold(BaseModel):
    """Money that waits for a review (or, for a first transfer, for ``release_at``)."""

    __tablename__ = "risk_holds"
    __table_args__ = (
        Index("ix_risk_holds_status_release", "status", "release_at"),
        Index(
            "uq_risk_holds_promo_ride",
            "ride_id",
            unique=True,
            postgresql_where=text("kind = 'promo_credit'"),
        ),
    )

    kind: Mapped[HoldKind] = mapped_column(_enum(HoldKind, "risk_hold_kind"))
    status: Mapped[HoldStatus] = mapped_column(
        _enum(HoldStatus, "risk_hold_status"), default=HoldStatus.HELD
    )
    # Who gets the money when it is released.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Transfers: who sent it (and gets it back if voided).
    sender_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    ride_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rides.id", ondelete="SET NULL"))
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("promotions.id", ondelete="SET NULL")
    )
    # The sender's transfer_out entry (its note and names are copied to the credit).
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wallet_entries.id", ondelete="SET NULL")
    )
    reasons: Mapped[list[str]] = mapped_column(JSONB, default=list)
    release_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))


class BlockedIdentifier(BaseModel):
    """A keyed hash of an email, cédula, RIF, phone, plate, Binance Pay ID or device of an account
    banned for fraud: a new account with it cannot be created (``registration_blocked``)."""

    __tablename__ = "blocked_identifiers"
    __table_args__ = (UniqueConstraint("kind", "value_hash", name="uq_blocked_identifiers"),)

    kind: Mapped[str] = mapped_column(String(20))
    value_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(500))
    source_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
