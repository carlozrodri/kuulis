import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer

from apps.wallet.models import EntryKind

MoneyStr = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]


class WalletRead(BaseModel):
    balance: MoneyStr
    currency: Literal["USDT"] = "USDT"


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
