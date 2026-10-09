import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class RateSource(enum.StrEnum):
    BCV = "bcv"  # official rate published by the central bank
    BINANCE = "binance"  # Binance P2P USDT/VES market


class RateOrigin(enum.StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class ExchangeRate(BaseModel):
    """History of bolívares per 1 USD. The newest row per source is the current rate."""

    __tablename__ = "exchange_rates"
    __table_args__ = (Index("ix_exchange_rates_source_fetched", "source", "fetched_at"),)

    source: Mapped[RateSource] = mapped_column(
        Enum(RateSource, name="rate_source", values_callable=lambda e: [m.value for m in e])
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    origin: Mapped[RateOrigin] = mapped_column(
        Enum(RateOrigin, name="rate_origin", values_callable=lambda e: [m.value for m in e])
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(String(300))
