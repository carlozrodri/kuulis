import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    and_,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

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
    CRIMINAL_RECORD = "criminal_record"  # certificado de antecedentes (optional, doc 12)


# Kinds that can have several files at once; the rest replace the previous file.
MULTI_FILE_KINDS = frozenset({DocumentKind.VEHICLE_PHOTO})


# Photos taken on the spot: never a PDF.
PHOTO_KINDS = frozenset({DocumentKind.SELFIE, DocumentKind.VEHICLE_PHOTO})
# What an approved driver may renew on their own (selfie and moto photos go through checks).
RENEWABLE_KINDS = frozenset(
    {
        DocumentKind.ID_CARD,
        DocumentKind.RIF,
        DocumentKind.DRIVERS_LICENSE,
        DocumentKind.MEDICAL_CERTIFICATE,
        DocumentKind.VEHICLE_REGISTRATION,
        DocumentKind.CRIMINAL_RECORD,
    }
)


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class VehicleStatus(enum.StrEnum):
    ACTIVE = "active"  # the one used for rides
    PENDING = (
        "pending"  # a moto change waiting for review; the driver keeps working with the active
    )
    RETIRED = "retired"


class CheckKind(enum.StrEnum):
    """Re-verifications of an approved driver (doc 12)."""

    SELFIE = "selfie"  # random live selfie
    REVERIFICATION = "reverification"  # selfie + new moto photos (reports or the team asked)
    DOCUMENT_RENEWAL = "document_renewal"  # a new file for a document (expired or about to)
    VEHICLE_CHANGE = "vehicle_change"


# Checks that keep the driver offline until they send the photos.
BLOCKING_CHECKS = frozenset({CheckKind.SELFIE, CheckKind.REVERIFICATION})


class CheckStatus(enum.StrEnum):
    REQUESTED = "requested"  # waiting for the driver's photos
    PENDING = "pending"  # sent, waiting for a verifier
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


OPEN_CHECK_STATUSES = frozenset({CheckStatus.REQUESTED, CheckStatus.PENDING})


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
    # Free months of subscription earned by inviting drivers (apps.referrals), not used yet.
    free_months_credit: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Rating received as a driver (see apps/rides). ``rating_avg`` = sum / count, 2 decimals.
    rating_sum: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    rating_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    rating_avg: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    # Doc 12: when the next live selfie is asked (on going online), induction and who reviews.
    selfie_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    induction_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    induction_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="raise")
    # The moto in use. Changes go through ``pending_vehicle`` (a new row) and a review.
    vehicle: Mapped["Vehicle | None"] = relationship(
        primaryjoin=lambda: and_(
            foreign(Vehicle.driver_id) == DriverProfile.id,
            Vehicle.status == VehicleStatus.ACTIVE,
        ),
        uselist=False,
        viewonly=True,
        lazy="raise",
    )
    pending_vehicle: Mapped["Vehicle | None"] = relationship(
        primaryjoin=lambda: and_(
            foreign(Vehicle.driver_id) == DriverProfile.id,
            Vehicle.status == VehicleStatus.PENDING,
        ),
        uselist=False,
        viewonly=True,
        lazy="raise",
    )
    documents: Mapped[list["DriverDocument"]] = relationship(
        back_populates="driver",
        cascade="all, delete-orphan",
        order_by="DriverDocument.created_at",
        lazy="raise",
    )


class Vehicle(BaseModel):
    __tablename__ = "vehicles"
    __table_args__ = (
        # One moto in use and one change under review per driver; a plate belongs to one live moto
        # (a retired one can be sold and registered again by someone else).
        Index(
            "uq_vehicles_driver_status",
            "driver_id",
            "status",
            unique=True,
            postgresql_where=text("status IN ('active', 'pending')"),
        ),
        Index(
            "uq_vehicles_plate_live",
            "plate",
            unique=True,
            postgresql_where=text("status IN ('active', 'pending')"),
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[VehicleStatus] = mapped_column(
        _enum(VehicleStatus, "vehicle_status"),
        default=VehicleStatus.ACTIVE,
        server_default=VehicleStatus.ACTIVE.value,
    )
    type: Mapped[VehicleType] = mapped_column(_enum(VehicleType, "vehicle_type"))
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    year: Mapped[int] = mapped_column(Integer)
    # Normalized: uppercase, no spaces or dashes (see services.normalize_plate).
    plate: Mapped[str] = mapped_column(String(12))
    color: Mapped[str] = mapped_column(String(30))


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
    # Doc 12: expiry of the license, medical certificate and registration. The driver types it;
    # a verifier confirms it (``expiry_confirmed``) when approving.
    expires_on: Mapped[date | None] = mapped_column(Date)
    expiry_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    # Smallest "expires in N days" notice already sent (30, 7, 1; 0 = the expiry notice).
    expiry_notice_days: Mapped[int | None] = mapped_column(Integer)
    # A renewal or a moto change replaced this file; it stays as history.
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("driver_documents.id", ondelete="SET NULL")
    )

    driver: Mapped[DriverProfile] = relationship(back_populates="documents", lazy="raise")


class DriverCheck(BaseModel):
    """A re-verification of an approved driver: live selfie, moto photos, a renewed document or a
    moto change. Files live in private S3 under ``drivers/<user_id>/checks/``."""

    __tablename__ = "driver_checks"
    __table_args__ = (Index("ix_driver_checks_status_created", "status", "created_at"),)

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[CheckKind] = mapped_column(_enum(CheckKind, "driver_check_kind"))
    status: Mapped[CheckStatus] = mapped_column(
        _enum(CheckStatus, "driver_check_status"), default=CheckStatus.REQUESTED
    )
    # Why it was asked: random, reports, team, expiry, driver.
    reason: Mapped[str] = mapped_column(String(20), default="driver")
    # [{"kind": "selfie", "key": "...", "content_type": "image/jpeg"}, ...]
    files: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("driver_documents.id", ondelete="SET NULL")
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL")
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_reason: Mapped[str | None] = mapped_column(Text)


class MarkKind(enum.StrEnum):
    NATIONAL_ID = "national_id"
    RIF = "rif"
    PLATE = "plate"
    PHONE = "phone"
    BINANCE_PAY_ID = "binance_pay_id"
    DEVICE = "device"


class IdentityMark(BaseModel):
    """A keyed hash of something that identifies a person or a moto (cédula, plate, phone,
    device...). Kept when the account is erased, so a new account with the same data shows up as a
    duplicate (doc 12) without storing the value itself."""

    __tablename__ = "identity_marks"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "value_hash", name="uq_identity_marks_user_value"),
        Index("ix_identity_marks_kind_hash", "kind", "value_hash"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[MarkKind] = mapped_column(_enum(MarkKind, "identity_mark_kind"))
    value_hash: Mapped[str] = mapped_column(String(64))
