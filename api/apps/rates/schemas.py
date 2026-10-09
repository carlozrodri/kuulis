import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

from apps.rates.models import RateOrigin, RateSource

# Bolívares travel as 2-decimal strings, like USD amounts.
BsStr = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]


class ExchangeRateRead(BaseModel):
    source: RateSource
    rate: BsStr
    origin: RateOrigin
    as_of: datetime
    fetched_at: datetime
    stale: bool


class CurrentRates(BaseModel):
    bcv: ExchangeRateRead | None
    binance: ExchangeRateRead | None


class VesAmount(BaseModel):
    """An USD amount in bolívares at each rate (None when that rate is unknown)."""

    bcv: BsStr | None
    binance: BsStr | None


class FrozenRates(VesAmount):
    """The rates themselves (Bs per USD), frozen on a ride when it was requested."""


class UserBrief(BaseModel):
    id: uuid.UUID
    name: str


class ExchangeRateHistory(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: RateSource
    rate: BsStr
    origin: RateOrigin
    as_of: datetime
    fetched_at: datetime
    created_by: UserBrief | None = None
    note: str | None


class ManualRate(BaseModel):
    source: RateSource
    rate: Decimal = Field(gt=0, lt=Decimal("10000000"), decimal_places=4, allow_inf_nan=False)
    note: str | None = Field(default=None, max_length=300)

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class RefreshRequest(BaseModel):
    source: RateSource | None = None
