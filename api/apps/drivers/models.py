import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.users.models import User
from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class DriverStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


# Allowed status changes; anything else is rejected by services.transition().
DRIVER_TRANSITIONS: dict[DriverStatus, frozenset[DriverStatus]] = {
    DriverStatus.DRAFT: frozenset({DriverStatus.PENDING_REVIEW}),
    DriverStatus.PENDING_REVIEW: frozenset({DriverStatus.APPROVED, DriverStatus.REJECTED}),
    DriverStatus.REJECTED: frozenset({DriverStatus.PENDING_REVIEW}),
    DriverStatus.APPROVED: frozenset({DriverStatus.SUSPENDED}),
    DriverStatus.SUSPENDED: frozenset({DriverStatus.APPROVED}),
}
# The driver can edit data and documents only while not under review / approved.
EDITABLE_STATUSES = frozenset({DriverStatus.DRAFT, DriverStatus.REJECTED})


class VehicleType(enum.StrEnum):
    MOTO = "moto"
    CAR = "car"


class DocumentKind(enum.StrEnum):
    ID_CARD = "id_card"  # cédula
    RIF = "rif"
    DRIVERS_LICENSE = "drivers_license"
    MEDICAL_CERTIFICATE = "medical_certificate"
    VEHICLE_REGISTRATION = "vehicle_registration"  # carnet de circulación
    SELFIE = "selfie"
    VEHICLE_PHOTO = "vehicle_photo"  # several allowed


# Kinds that can have several files at once; the rest replace the previous file.
MULTI_FILE_KINDS = frozenset({DocumentKind.VEHICLE_PHOTO})


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DriverProfile(BaseModel):
    """Driver application and state. One per user; created as ``draft`` by the driver."""

    __tablename__ = "driver_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[DriverStatus] = mapped_column(
        _enum(DriverStatus, "driver_status"), default=DriverStatus.DRAFT, index=True
    )
    birth_date: Mapped[date] = mapped_column(Date)
    national_id: Mapped[str] = mapped_column(String(20), unique=True)
    rif: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(32), default="caracas")
    # Reason of the last rejection or suspension (the admin panel reads both from here).
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_trip_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="raise")
    vehicle: Mapped["Vehicle | None"] = relationship(
        back_populates="driver", cascade="all, delete-orphan", uselist=False, lazy="raise"
    )
    documents: Mapped[list["DriverDocument"]] = relationship(
        back_populates="driver",
        cascade="all, delete-orphan",
        order_by="DriverDocument.created_at",
        lazy="raise",
    )


class Vehicle(BaseModel):
    __tablename__ = "vehicles"

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="CASCADE"), unique=True
    )
    type: Mapped[VehicleType] = mapped_column(_enum(VehicleType, "vehicle_type"))
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    year: Mapped[int] = mapped_column(Integer)
    # Normalized: uppercase, no spaces or dashes (see services.normalize_plate).
    plate: Mapped[str] = mapped_column(String(12), unique=True)
    color: Mapped[str] = mapped_column(String(30))

    driver: Mapped[DriverProfile] = relationship(back_populates="vehicle", lazy="raise")


class DriverDocument(BaseModel):
    """A file uploaded to private S3 under ``drivers/<user_id>/<kind>/``."""

    __tablename__ = "driver_documents"

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[DocumentKind] = mapped_column(_enum(DocumentKind, "driver_document_kind"))
    status: Mapped[DocumentStatus] = mapped_column(
        _enum(DocumentStatus, "driver_document_status"), default=DocumentStatus.PENDING
    )
    key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    driver: Mapped[DriverProfile] = relationship(back_populates="documents", lazy="raise")
