import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.drivers.models import (
    CheckKind,
    CheckStatus,
    DocumentKind,
    DocumentStatus,
    DriverStatus,
    MarkKind,
    VehicleStatus,
    VehicleType,
)
from apps.users.schemas import UserRead

# Same list as /files/presign-upload: photos and PDF scans.
DOCUMENT_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"}
)

_SEPARATORS = re.compile(r"[\s.\-]+")
NATIONAL_ID_RE = re.compile(r"^[VE]\d{6,9}$")  # V12345678 / E84123456
RIF_RE = re.compile(r"^[VEJPG]\d{9}$")  # V123456789 (8 digits + check digit)
PHONE_RE = re.compile(r"^\+\d{10,15}$")  # E.164
PLATE_RE = re.compile(r"^[A-Z0-9]{5,8}$")


def compact_upper(value: str) -> str:
    """Uppercase without spaces, dots or dashes ("v-12.345.678" -> "V12345678")."""
    return _SEPARATORS.sub("", value).upper()


class DriverProfileWrite(BaseModel):
    birth_date: date
    national_id: str = Field(max_length=20)
    rif: str = Field(max_length=20)
    phone: str = Field(max_length=20)

    @field_validator("birth_date")
    @classmethod
    def _birth_date(cls, value: date) -> date:
        if value.year < 1900 or value >= date.today():
            raise ValueError("invalid birth date")
        return value

    @field_validator("national_id")
    @classmethod
    def _national_id(cls, value: str) -> str:
        value = compact_upper(value)
        if not NATIONAL_ID_RE.match(value):
            raise ValueError("expected V or E followed by digits, e.g. V12345678")
        return value

    @field_validator("rif")
    @classmethod
    def _rif(cls, value: str) -> str:
        value = compact_upper(value)
        if not RIF_RE.match(value):
            raise ValueError("expected a letter (V, E, J, P, G) and 9 digits, e.g. V123456789")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        value = re.sub(r"[\s()\-]+", "", value)
        if not PHONE_RE.match(value):
            raise ValueError("expected international format, e.g. +584121234567")
        return value


class VehicleWrite(BaseModel):
    type: VehicleType
    brand: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=50)
    year: int = Field(ge=1950, le=2100)
    plate: str = Field(min_length=1, max_length=20)
    color: str = Field(min_length=1, max_length=30)

    @field_validator("brand", "model", "color")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("plate")
    @classmethod
    def _plate(cls, value: str) -> str:
        value = compact_upper(value)
        if not PLATE_RE.match(value):
            raise ValueError("invalid plate")
        return value


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: VehicleStatus = VehicleStatus.ACTIVE
    type: VehicleType
    brand: str
    model: str
    year: int
    plate: str
    color: str


class DocumentPresignRequest(BaseModel):
    kind: DocumentKind
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(pattern=r"^[\w.+-]+/[\w.+-]+$", max_length=100)
    size: int = Field(gt=0)


def _expiry(value: date | None) -> date | None:
    if value is not None and (value.year < 2000 or value.year > 2100):
        raise ValueError("invalid expiry date")
    return value


class DocumentRegister(BaseModel):
    kind: DocumentKind
    key: str = Field(min_length=1, max_length=512)
    # License, medical certificate and registration (doc 12); a verifier confirms it.
    expires_on: date | None = None

    _check_expiry = field_validator("expires_on")(classmethod(lambda cls, v: _expiry(v)))


class ExpiryUpdate(BaseModel):
    expires_on: date

    _check_expiry = field_validator("expires_on")(classmethod(lambda cls, v: _expiry(v)))


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: DocumentKind
    status: DocumentStatus
    content_type: str
    rejection_reason: str | None
    expires_on: date | None = None
    expiry_confirmed: bool = False
    created_at: datetime


class DocumentAdminRead(DocumentRead):
    reviewed_at: datetime | None
    superseded_by_id: uuid.UUID | None = None
    download_url: str | None = None


# --- Ongoing verification (doc 12) --------------------------------------------------------------


class DocumentAlert(BaseModel):
    kind: DocumentKind
    expires_on: date
    days_left: int  # negative: expired
    renewal_pending: bool


class VerificationState(BaseModel):
    """What the driver app shows on the dashboard and why going online is refused."""

    expired: list[DocumentKind]
    expiring: list[DocumentAlert]
    # Approved before doc 12, without a date: the driver is asked to type it.
    missing_expiry: list[DocumentKind]
    required_check_id: uuid.UUID | None
    required_check_kind: CheckKind | None
    can_go_online: bool


class CheckFile(BaseModel):
    kind: DocumentKind
    key: str = Field(min_length=1, max_length=512)


class CheckPresignRequest(BaseModel):
    kind: DocumentKind
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(pattern=r"^[\w.+-]+/[\w.+-]+$", max_length=100)
    size: int = Field(gt=0)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: DocumentKind) -> DocumentKind:
        allowed = {
            DocumentKind.SELFIE,
            DocumentKind.VEHICLE_PHOTO,
            DocumentKind.VEHICLE_REGISTRATION,
        }
        if value not in allowed:
            raise ValueError("only selfie, vehicle_photo or vehicle_registration")
        return value


class CheckSubmit(BaseModel):
    files: list[CheckFile] = Field(min_length=1, max_length=12)


class CheckFileRead(BaseModel):
    kind: DocumentKind
    content_type: str
    download_url: str | None = None


class DriverCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: CheckKind
    status: CheckStatus
    reason: str
    document_id: uuid.UUID | None
    vehicle_id: uuid.UUID | None
    requested_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
    result_reason: str | None


class StaffBrief(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str


class DriverBrief(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    status: DriverStatus
    plate: str | None


class DriverCheckAdminRead(DriverCheckRead):
    driver: DriverBrief
    assigned_to: StaffBrief | None = None
    reviewed_by: StaffBrief | None = None
    files: list[CheckFileRead] = []
    # Detail only: the approved selfie and cédula to compare with, the document being renewed
    # and the one in use, and the new moto.
    references: list["DocumentAdminRead"] = []
    document: "DocumentAdminRead | None" = None
    vehicle: VehicleRead | None = None
    expires_on: date | None = None  # what the driver typed for a renewal or a new registration


class CheckReview(BaseModel):
    status: CheckStatus
    reason: str | None = Field(default=None, max_length=1000)
    expires_on: date | None = None

    _check_expiry = field_validator("expires_on")(classmethod(lambda cls, v: _expiry(v)))

    @field_validator("status")
    @classmethod
    def _decided(cls, value: CheckStatus) -> CheckStatus:
        if value not in (CheckStatus.APPROVED, CheckStatus.REJECTED):
            raise ValueError("status must be approved or rejected")
        return value

    @model_validator(mode="after")
    def _reason_when_rejected(self) -> "CheckReview":
        self.reason = (self.reason or "").strip() or None
        if self.status == CheckStatus.REJECTED and not self.reason:
            raise ValueError("reason is required to reject")
        return self


class AssignRequest(BaseModel):
    user_id: uuid.UUID | None = None


class InductionRequest(BaseModel):
    done: bool


class VehicleChange(BaseModel):
    vehicle: VehicleWrite
    registration_key: str = Field(min_length=1, max_length=512)
    registration_expires_on: date
    photo_keys: list[str] = Field(min_length=1, max_length=10)

    _check_expiry = field_validator("registration_expires_on")(
        classmethod(lambda cls, v: _expiry(v))
    )


class Duplicate(BaseModel):
    kind: MarkKind
    user_id: uuid.UUID
    name: str
    email: str | None  # None once the account was erased
    driver_id: uuid.UUID | None
    driver_status: DriverStatus | None
    deleted: bool
    suspended: bool


class Requirements(BaseModel):
    missing_documents: list[DocumentKind]
    vehicle_photos: int
    vehicle_photos_required: int
    age_ok: bool
    vehicle_ok: bool
    can_submit: bool


class DriverPreferences(BaseModel):
    """Driver-only switches. Only the fields sent change."""

    hide_from_public_activity: bool | None = None


class DriverProfileRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: DriverStatus
    birth_date: date
    national_id: str
    rif: str
    phone: str
    city: str
    rejection_reason: str | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    approved_at: datetime | None
    suspended_at: datetime | None
    first_trip_completed_at: datetime | None
    rating_avg: float | None = None
    rating_count: int = 0
    created_at: datetime
    vehicle: VehicleRead | None
    pending_vehicle: VehicleRead | None = None
    documents: list[DocumentRead]
    requirements: Requirements
    verification: VerificationState | None = None
    checks: list[DriverCheckRead] = []  # open ones for the driver; every one for the admin
    induction_completed_at: datetime | None = None
    hide_from_public_activity: bool = False


class DriverAdminRead(DriverProfileRead):
    user: UserRead
    documents: list[DocumentAdminRead]  # type: ignore[assignment]
    assigned_to: StaffBrief | None = None
    duplicates: list[Duplicate] = []


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class DocumentReview(BaseModel):
    status: DocumentStatus
    reason: str | None = Field(default=None, max_length=1000)
    # Confirms or corrects the expiry the driver typed (doc 12).
    expires_on: date | None = None

    _check_expiry = field_validator("expires_on")(classmethod(lambda cls, v: _expiry(v)))

    @field_validator("status")
    @classmethod
    def _not_pending(cls, value: DocumentStatus) -> DocumentStatus:
        if value == DocumentStatus.PENDING:
            raise ValueError("status must be approved or rejected")
        return value

    @model_validator(mode="after")
    def _reason_when_rejected(self) -> "DocumentReview":
        self.reason = (self.reason or "").strip() or None
        if self.status == DocumentStatus.REJECTED and not self.reason:
            raise ValueError("reason is required to reject a document")
        return self
