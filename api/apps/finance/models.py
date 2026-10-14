import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class MonthlyClosing(BaseModel):
    """The books of one Caracas month, frozen once the month ended (doc 17).

    ``totals`` is computed from the ledger when the month is closed and never recomputed, so later
    adjustments (which are dated today, so they land in the open month) or tier changes don't
    move it. ``hash`` covers the month, the totals and the previous closing's hash, so editing
    any stored closing breaks the chain. The Binance statement and its differences are added
    afterwards; reconciling only stamps who checked them.
    """

    __tablename__ = "monthly_closings"

    month: Mapped[date] = mapped_column(Date, unique=True)  # first day of the month
    totals: Mapped[dict[str, Any]] = mapped_column(JSONB)
    hash: Mapped[str] = mapped_column(String(64))
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    binance_statement_key: Mapped[str | None] = mapped_column(String(512))
    statement_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # {"missing_in_kuulis": [...], "missing_in_binance": [...], "amount_mismatch": [...]}
    differences: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciled_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reconcile_note: Mapped[str | None] = mapped_column(String(500))
