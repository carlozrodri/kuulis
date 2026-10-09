import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class DiscountType(enum.StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class Promotion(BaseModel):
    """A discount paid by Kuulis. Usage is derived from ``rides.promotion_id``: rides in flight
    reserve their discount, completed rides consume it, cancelled ones release it."""

    __tablename__ = "promotions"
    __table_args__ = (
        Index("uq_promotions_code", "code", unique=True, postgresql_where=text("code IS NOT NULL")),
        CheckConstraint("ends_at > starts_at", name="dates_ordered"),
        CheckConstraint("budget > 0", name="budget_positive"),
    )

    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(String(20))  # None: applied automatically
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, name="discount_type", values_callable=lambda e: [m.value for m in e])
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    min_fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    budget: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    max_uses_per_passenger: Mapped[int] = mapped_column(Integer, default=1)
    max_total_uses: Mapped[int | None] = mapped_column(Integer)
    first_ride_only: Mapped[bool] = mapped_column(default=False)
    service_areas: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    vehicle_types: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
