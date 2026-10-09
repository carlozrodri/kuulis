import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.drivers.models import VehicleType
from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class PaymentMethod(enum.StrEnum):
    CASH_USD = "cash_usd"
    PAGO_MOVIL = "pago_movil"
    BINANCE = "binance"
    ZELLE = "zelle"
    CASH_VES = "cash_ves"


class RideStatus(enum.StrEnum):
    SEARCHING = "searching"
    DRIVER_ASSIGNED = "driver_assigned"
    DRIVER_ARRIVED = "driver_arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED_BY_PASSENGER = "cancelled_by_passenger"
    CANCELLED_BY_DRIVER = "cancelled_by_driver"
    CANCELLED_BY_ADMIN = "cancelled_by_admin"
    NO_DRIVERS = "no_drivers"


# The passenger has a ride "in flight" (blocks asking for another one).
ACTIVE_STATUSES = frozenset(
    {
        RideStatus.SEARCHING,
        RideStatus.DRIVER_ASSIGNED,
        RideStatus.DRIVER_ARRIVED,
        RideStatus.IN_PROGRESS,
    }
)
# A driver is attached to the ride (busy; location is forwarded to the passenger; chat is open).
ASSIGNED_STATUSES = frozenset(
    {RideStatus.DRIVER_ASSIGNED, RideStatus.DRIVER_ARRIVED, RideStatus.IN_PROGRESS}
)
FINAL_STATUSES = frozenset(set(RideStatus) - ACTIVE_STATUSES)

# Allowed status changes; anything else is rejected by services.transition().
RIDE_TRANSITIONS: dict[RideStatus, frozenset[RideStatus]] = {
    RideStatus.SEARCHING: frozenset(
        {
            RideStatus.DRIVER_ASSIGNED,
            RideStatus.CANCELLED_BY_PASSENGER,
            RideStatus.CANCELLED_BY_ADMIN,
            RideStatus.NO_DRIVERS,
        }
    ),
    RideStatus.DRIVER_ASSIGNED: frozenset(
        {
            RideStatus.DRIVER_ARRIVED,
            RideStatus.CANCELLED_BY_PASSENGER,
            RideStatus.CANCELLED_BY_DRIVER,
            RideStatus.CANCELLED_BY_ADMIN,
        }
    ),
    RideStatus.DRIVER_ARRIVED: frozenset(
        {
            RideStatus.IN_PROGRESS,
            RideStatus.CANCELLED_BY_PASSENGER,
            RideStatus.CANCELLED_BY_DRIVER,
            RideStatus.CANCELLED_BY_ADMIN,
        }
    ),
    RideStatus.IN_PROGRESS: frozenset({RideStatus.COMPLETED, RideStatus.CANCELLED_BY_ADMIN}),
}


def _status_list(statuses: frozenset[RideStatus]) -> str:
    return ", ".join(f"'{s.value}'" for s in sorted(statuses))


class OfferStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"  # the ride was cancelled or closed while the offer was open


class RatingRole(enum.StrEnum):
    """Who wrote the rating."""

    PASSENGER = "passenger"
    DRIVER = "driver"


class Ride(BaseModel):
    """One trip. ``driver_id`` is the driver's *user* id (like ``passenger_id``)."""

    __tablename__ = "rides"
    __table_args__ = (
        # One active ride per passenger and per driver, enforced by the database.
        Index(
            "uq_rides_active_passenger",
            "passenger_id",
            unique=True,
            postgresql_where=text(f"status IN ({_status_list(ACTIVE_STATUSES)})"),
        ),
        Index(
            "uq_rides_active_driver",
            "driver_id",
            unique=True,
            postgresql_where=text(f"status IN ({_status_list(ASSIGNED_STATUSES)})"),
        ),
        Index("ix_rides_passenger_status", "passenger_id", "status"),
        Index("ix_rides_driver_status", "driver_id", "status"),
    )

    passenger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[RideStatus] = mapped_column(
        _enum(RideStatus, "ride_status"), default=RideStatus.SEARCHING, index=True
    )
    vehicle_type: Mapped[VehicleType] = mapped_column(_enum(VehicleType, "vehicle_type"))
    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lng: Mapped[float] = mapped_column(Float)
    pickup_address: Mapped[str] = mapped_column(String(300), default="")
    dropoff_lat: Mapped[float] = mapped_column(Float)
    dropoff_lng: Mapped[float] = mapped_column(Float)
    dropoff_address: Mapped[str] = mapped_column(String(300), default="")
    distance_m: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[int] = mapped_column(Integer)
    fare: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    surge_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    # Promotion paid by Kuulis: the passenger pays ``total`` and the driver gets ``discount`` in
    # the wallet when the ride completes.
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("promotions.id", ondelete="RESTRICT"), index=True
    )
    discount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), server_default=text("0")
    )
    # Bolívares per USD when the ride was requested (None: rate unknown then).
    rate_bcv: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    rate_binance: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    payment_method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod, "payment_method"))
    polyline: Mapped[str | None] = mapped_column(Text)
    # Snapshot of the vehicle when the driver accepted (brand, model, color, plate, type).
    vehicle: Mapped[dict | None] = mapped_column(JSONB)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    search_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    rated_by_passenger: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    rated_by_driver: Mapped[bool] = mapped_column(default=False, server_default=text("false"))

    @property
    def total(self) -> Decimal:
        """What the passenger pays the driver."""
        return self.fare - (self.discount or Decimal("0"))


class RideOffer(BaseModel):
    """One offer of a ride to one driver (history kept for support and metrics)."""

    __tablename__ = "ride_offers"
    __table_args__ = (
        UniqueConstraint("ride_id", "driver_id"),
        Index("ix_ride_offers_driver_status", "driver_id", "status"),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[OfferStatus] = mapped_column(
        _enum(OfferStatus, "ride_offer_status"), default=OfferStatus.PENDING
    )
    pickup_distance_m: Mapped[int] = mapped_column(Integer)
    pickup_eta_s: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RideMessage(BaseModel):
    __tablename__ = "ride_messages"
    __table_args__ = (Index("ix_ride_messages_ride_created", "ride_id", "created_at"),)

    ride_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rides.id", ondelete="CASCADE"))
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(500))


class Rating(BaseModel):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("ride_id", "rater_id"),
        CheckConstraint("stars BETWEEN 1 AND 5", name="stars_range"),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), index=True
    )
    rater_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ratee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    rater_role: Mapped[RatingRole] = mapped_column(_enum(RatingRole, "rating_role"))
    stars: Mapped[int] = mapped_column(SmallInteger)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    comment: Mapped[str | None] = mapped_column(Text)
