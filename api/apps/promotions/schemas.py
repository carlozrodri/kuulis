import enum
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from apps.drivers.models import VehicleType
from apps.promotions.models import DiscountType
from apps.rides.models import RideStatus

MoneyStr = PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")
_CENT = Decimal("0.01")
_CODE_RE = re.compile(r"^[A-Z0-9]{3,20}$")


def _cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT)


Amount = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1000000"), decimal_places=2, allow_inf_nan=False),
    AfterValidator(_cents),
    MoneyStr,
]


def normalize_code(value: str | None) -> str | None:
    value = "".join((value or "").split()).upper()
    return value or None


class PromotionStatus(enum.StrEnum):
    ACTIVE = "active"
    SCHEDULED = "scheduled"
    ENDED = "ended"
    EXHAUSTED = "exhausted"  # budget or total uses spent
    INACTIVE = "inactive"  # switched off by an admin


class PromotionFields(BaseModel):
    """Every editable field with its validation (create body; update is merged into this)."""

    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    code: str | None = None
    discount_type: DiscountType
    discount_value: Amount
    max_discount: Amount | None = None
    min_fare: Amount = Decimal("0.00")
    starts_at: datetime
    ends_at: datetime
    budget: Amount
    max_uses_per_passenger: int = Field(default=1, ge=1, le=1000)
    max_total_uses: int | None = Field(default=None, ge=1, le=10_000_000)
    first_ride_only: bool = False
    service_areas: list[str] = Field(default_factory=list, max_length=20)
    vehicle_types: list[VehicleType] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        value = normalize_code(value)
        if value is not None and not _CODE_RE.match(value):
            raise ValueError("3 to 20 letters or digits")
        return value

    @field_validator("service_areas")
    @classmethod
    def _areas(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(v.strip() for v in value if v.strip()))

    @field_validator("vehicle_types")
    @classmethod
    def _types(cls, value: list[VehicleType]) -> list[VehicleType]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("dates must include a timezone")
        if self.budget <= 0:
            raise ValueError("budget must be greater than 0")
        if self.discount_type == DiscountType.PERCENT:
            if not Decimal("1") <= self.discount_value <= Decimal("100"):
                raise ValueError("a percent discount goes from 1 to 100")
            if self.max_discount is not None and self.max_discount <= 0:
                raise ValueError("max_discount must be greater than 0")
        else:
            if self.discount_value <= 0:
                raise ValueError("a fixed discount must be greater than 0")
            self.max_discount = None  # the fixed amount is already the cap
        return self


class PromotionCreate(PromotionFields):
    pass


class PromotionUpdate(BaseModel):
    """Partial update; merged into the stored promotion and validated as a whole."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    code: str | None = None
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = None
    max_discount: Decimal | None = None
    min_fare: Decimal | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    budget: Decimal | None = None
    max_uses_per_passenger: int | None = None
    max_total_uses: int | None = None
    first_ride_only: bool | None = None
    service_areas: list[str] | None = None
    vehicle_types: list[VehicleType] | None = None
    is_active: bool | None = None


class PromotionStats(BaseModel):
    uses: int
    completed: int
    credited: Annotated[Decimal, MoneyStr]
    reserved: Annotated[Decimal, MoneyStr]
    remaining: Annotated[Decimal, MoneyStr]


class PromotionRead(PromotionFields):
    id: uuid.UUID
    status: PromotionStatus
    stats: PromotionStats
    created_at: datetime
    updated_at: datetime


class PromotionBrief(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None


class PromotionRide(BaseModel):
    ride_id: uuid.UUID
    status: RideStatus
    passenger_name: str
    driver_name: str | None
    fare: Annotated[Decimal, MoneyStr]
    discount: Annotated[Decimal, MoneyStr]
    total: Annotated[Decimal, MoneyStr]
    requested_at: datetime
    completed_at: datetime | None


class AlertPerson(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class AlertDriver(AlertPerson):
    profile_id: uuid.UUID | None


class PairAlert(BaseModel):
    passenger: AlertPerson
    driver: AlertDriver
    rides: int
    discount_total: Annotated[Decimal, MoneyStr]
    last_ride_at: datetime
