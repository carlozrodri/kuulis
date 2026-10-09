import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from apps.users.schemas import UserBrief
from apps.wallet.models import EntryKind, TopUpMethod, TopUpStatus

MoneyStr = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]
_CENT = Decimal("0.01")
_PAY_ID = re.compile(r"^\d{6,20}$")


def _cents(value: Decimal) -> Decimal:
    return value.quantize(_CENT)


Amount = Annotated[
    Decimal,
    Field(gt=Decimal("0"), le=Decimal("100000"), decimal_places=2, allow_inf_nan=False),
    AfterValidator(_cents),
]


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


Reference = Annotated[str | None, Field(default=None, max_length=64), AfterValidator(_clean)]
Note = Annotated[str | None, Field(default=None, max_length=140), AfterValidator(_clean)]


class TransferLimit(BaseModel):
    limit: MoneyStr
    sent_this_month: MoneyStr
    available: MoneyStr


class WalletRead(BaseModel):
    balance: MoneyStr
    currency: Literal["USDT"] = "USDT"
    binance_pay_id: str | None = None
    transfer: TransferLimit | None = None


class WalletEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EntryKind
    amount: MoneyStr
    balance_after: MoneyStr
    ride_id: uuid.UUID | None
    description: str
    details: dict[str, Any]
    created_at: datetime


class BinancePayIdWrite(BaseModel):
    binance_pay_id: str

    @field_validator("binance_pay_id")
    @classmethod
    def _digits(cls, value: str) -> str:
        value = "".join(value.split())
        if not _PAY_ID.match(value):
            raise ValueError("6 to 20 digits")
        return value


class TopUpInfo(BaseModel):
    method: TopUpMethod = TopUpMethod.BINANCE_PAY
    pay_id: str
    account_name: str
    min_amount: MoneyStr
    automatic: bool


class TopUpCreate(BaseModel):
    amount: Amount
    reference: Reference = None


class TopUpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: TopUpStatus
    amount: MoneyStr
    method: TopUpMethod
    reference: str | None
    payer_binance_id: str | None
    payer_name: str | None
    note: str | None
    rejection_reason: str | None
    created_at: datetime
    completed_at: datetime | None


class TopUpAdminRead(TopUpRead):
    transaction_id: str | None
    user: UserBrief | None


class TopUpConfirm(BaseModel):
    amount: Amount
    reference: Reference = None


class ReasonBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class TopUpAssign(BaseModel):
    user_id: uuid.UUID


class Recipient(BaseModel):
    user_id: uuid.UUID
    name: str


class TransferCreate(BaseModel):
    to_user_id: uuid.UUID
    amount: Amount
    note: Note = None


class TransferAdminRead(BaseModel):
    id: uuid.UUID
    sender: UserBrief
    recipient: UserBrief | None
    amount: MoneyStr
    note: str | None
    created_at: datetime


class Adjustment(BaseModel):
    amount: Annotated[
        Decimal,
        Field(ge=Decimal("-100000"), le=Decimal("100000"), decimal_places=2, allow_inf_nan=False),
        AfterValidator(_cents),
    ]
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("amount")
    @classmethod
    def _not_zero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("must not be 0")
        return value

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value
