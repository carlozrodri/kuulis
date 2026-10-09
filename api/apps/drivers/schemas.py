import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.drivers.models import DocumentKind, DocumentStatus, DriverStatus, VehicleType
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


class DocumentRegister(BaseModel):
    kind: DocumentKind
    key: str = Field(min_length=1, max_length=512)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: DocumentKind
    status: DocumentStatus
    content_type: str
    rejection_reason: str | None
    created_at: datetime


class DocumentAdminRead(DocumentRead):
    reviewed_at: datetime | None
    download_url: str | None = None


class Requirements(BaseModel):
    missing_documents: list[DocumentKind]
    vehicle_photos: int
    vehicle_photos_required: int
    age_ok: bool
    vehicle_ok: bool
    can_submit: bool


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
    documents: list[DocumentRead]
    requirements: Requirements


class DriverAdminRead(DriverProfileRead):
    user: UserRead
    documents: list[DocumentAdminRead]  # type: ignore[assignment]


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
