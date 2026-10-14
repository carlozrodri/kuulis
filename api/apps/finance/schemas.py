import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field

from apps.subscriptions.schemas import ChargeRead, MoneyStr, Month, Tier, UserBrief
from apps.wallet.models import ReceiptKind

Money = Annotated[Decimal, MoneyStr]


class ReceiptRead(BaseModel):
    id: uuid.UUID
    number: str  # "000123"
    kind: ReceiptKind
    concept: str
    amount: Money
    balance_after: Money
    reference: str | None
    issued_at: datetime
    entry_id: uuid.UUID
    driver: UserBrief
    issuer: str = "Kuulis"
    fiscal: bool = False  # no company yet: every receipt is "no fiscal" (doc 17, Carlos)


class StatementMovements(BaseModel):
    top_ups: Money
    promo_credits: Money
    transfers_in: Money
    transfers_out: Money  # positive: what left
    fees: Money  # positive: what was paid
    adjustments: Money  # signed


class StatementRead(BaseModel):
    month: Month
    months: list[Month]  # months with a statement, newest first
    opening_balance: Money
    closing_balance: Money
    earned: Money
    counted: Money
    trips: int
    tier: Tier | None
    fee: Money
    estimated: bool  # the month is still open: the fee is what it would be today
    charge: ChargeRead | None
    movements: StatementMovements


class ClosingRead(BaseModel):
    month: Month
    totals: dict[str, Any]
    hash: str
    previous_hash: str | None
    hash_ok: bool
    closed_by: UserBrief | None
    closed_at: datetime
    statement_uploaded_at: datetime | None
    has_statement_file: bool
    differences: dict[str, Any] | None
    has_differences: bool
    reconciled_at: datetime | None
    reconciled_by: UserBrief | None
    reconcile_note: str | None


class ClosingCreate(BaseModel):
    month: Month


class StatementUpload(BaseModel):
    """The Binance Pay history as text: the admin reads the CSV in the browser."""

    csv: str = Field(min_length=1, max_length=3_000_000)
    filename: str | None = Field(default=None, max_length=120)


class ReconcileBody(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class InvariantsRead(BaseModel):
    ok: bool
    checked_at: datetime
    wallets: int
    issues: list[dict[str, Any]]
