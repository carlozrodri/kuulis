import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Field,
    PlainSerializer,
    model_validator,
)

from apps.subscriptions.models import ChargeStatus
from kuulis.core.calendar import format_month, parse_month

MoneyStr = PlainSerializer(lambda v: f"{v:.2f}", return_type=str, when_used="json")
MonthStr = PlainSerializer(format_month, return_type=str, when_used="json")
_CENT = Decimal("0.01")


def _cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT)


def _month(value: object) -> object:
    return parse_month(value) if isinstance(value, str) else value


Money = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1000000"), decimal_places=2, allow_inf_nan=False),
    AfterValidator(_cents),
    MoneyStr,
]
Month = Annotated[date, BeforeValidator(_month), MonthStr]


class Tier(BaseModel):
    above: Money  # earnings strictly above this amount pay ``fee``
    fee: Annotated[
        Decimal,
        Field(ge=Decimal("0"), le=Decimal("1000"), decimal_places=2),
        AfterValidator(_cents),
        MoneyStr,
    ]


class ScheduleCreate(BaseModel):
    effective_month: Month
    tiers: list[Tier] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.tiers[0].above != 0:
            raise ValueError("the first tier must start at 0")
        if any(b.above <= a.above for a, b in zip(self.tiers, self.tiers[1:], strict=False)):
            raise ValueError("tiers must be sorted by 'above' without repeats")
        return self


class UserBrief(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class ScheduleRead(BaseModel):
    id: uuid.UUID | None  # None: the built-in default (nothing stored yet)
    effective_month: Month
    tiers: list[Tier]
    current: bool
    created_by: UserBrief | None = None
    created_at: datetime | None = None


class ChargeRead(BaseModel):
    id: uuid.UUID
    month: Month
    earnings: Annotated[Decimal, MoneyStr]
    fee: Annotated[Decimal, MoneyStr]
    status: ChargeStatus
    free_period: bool
    due_at: datetime
    paid_at: datetime | None
    waived_reason: str | None
    overdue: bool = False


class ChargeAdminRead(ChargeRead):
    user: UserBrief


class ChargesPage(BaseModel):
    items: list[ChargeAdminRead]
    total: int
    limit: int
    offset: int
    totals: dict[ChargeStatus, Annotated[Decimal, MoneyStr]]


class SubscriptionSummary(BaseModel):
    month: Month
    earnings: Annotated[Decimal, MoneyStr]
    estimated_fee: Annotated[Decimal, MoneyStr]
    free_until: datetime | None
    in_free_period: bool
    tiers: list[Tier]
    next_charge_at: datetime
    pending: list[ChargeRead]
    overdue: bool
    blocked: bool


class RunRequest(BaseModel):
    month: Month


class RunResultRead(BaseModel):
    created: int
    paid: int
    pending: int
    waived: int
