import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class ChargeStatus(enum.StrEnum):
    PAID = "paid"
    PENDING = "pending"  # not enough balance yet; blocks the driver after ``due_at``
    WAIVED = "waived"  # fee 0 (low earnings or free period) or forgiven by an admin


class FeeSchedule(BaseModel):
    """Fee tiers valid from ``effective_month`` (first day of a month) until the next schedule.
    New schedules can only start in a future month, so a closed month never changes."""

    __tablename__ = "fee_schedules"

    effective_month: Mapped[date] = mapped_column(Date, unique=True)
    # [{"above": "0.00", "fee": "0.00"}, {"above": "100.00", "fee": "5.00"}, ...]
    tiers: Mapped[list[dict]] = mapped_column(JSONB)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Charge(BaseModel):
    """The monthly fee of one driver for one month."""

    __tablename__ = "subscription_charges"
    __table_args__ = (
        UniqueConstraint("user_id", "month"),
        Index("ix_subscription_charges_status_due", "status", "due_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    month: Mapped[date] = mapped_column(Date, index=True)  # first day of the charged month
    earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[ChargeStatus] = mapped_column(
        Enum(ChargeStatus, name="charge_status", values_callable=lambda e: [m.value for m in e])
    )
    free_period: Mapped[bool] = mapped_column(default=False)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fee_schedules.id", ondelete="SET NULL")
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wallet_entries.id", ondelete="SET NULL")
    )
    waived_reason: Mapped[str | None] = mapped_column(String(500))
    waived_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    notified_due_soon: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    notified_overdue: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
