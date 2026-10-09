import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class EntryKind(enum.StrEnum):
    PROMO_CREDIT = "promo_credit"  # Kuulis pays back a promotion discount to the driver
    TOP_UP = "top_up"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    SUBSCRIPTION_FEE = "subscription_fee"
    ADJUSTMENT = "adjustment"


class TopUpStatus(enum.StrEnum):
    PENDING = "pending"  # the driver says they paid; waiting for the payment
    COMPLETED = "completed"
    REJECTED = "rejected"
    UNMATCHED = "unmatched"  # a payment arrived and no driver owns the payer's Binance Pay ID


class TopUpMethod(enum.StrEnum):
    BINANCE_PAY = "binance_pay"


class Wallet(BaseModel):
    """USDT balance of a user (drivers). Changed only through ``services.post_entry``, which locks
    this row, so ``balance`` always equals the sum of the entries."""

    __tablename__ = "wallets"
    __table_args__ = (CheckConstraint("balance >= 0", name="balance_not_negative"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default=text("0")
    )
    # The driver's Binance Pay ID: payments from it are credited automatically.
    binance_pay_id: Mapped[str | None] = mapped_column(String(20), unique=True)


class WalletEntry(BaseModel):
    """Append-only ledger line."""

    __tablename__ = "wallet_entries"
    __table_args__ = (
        Index("ix_wallet_entries_wallet_created", "wallet_id", "created_at"),
        # A ride is credited at most once per kind (retries and races are harmless).
        Index(
            "uq_wallet_entries_kind_ride",
            "kind",
            "ride_id",
            unique=True,
            postgresql_where=text("ride_id IS NOT NULL"),
        ),
    )

    wallet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wallets.id", ondelete="CASCADE"))
    kind: Mapped[EntryKind] = mapped_column(
        Enum(EntryKind, name="wallet_entry_kind", values_callable=lambda e: [m.value for m in e])
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    ride_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rides.id", ondelete="SET NULL"))
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("promotions.id", ondelete="SET NULL")
    )
    # The other side of a transfer (its own transfer_in / transfer_out entry is on that wallet).
    counterpart_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(200), default="")
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class TopUp(BaseModel):
    """A top-up: a driver's notice that they paid, and/or a payment seen in Binance Pay."""

    __tablename__ = "wallet_top_ups"
    __table_args__ = (Index("ix_wallet_top_ups_user_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[TopUpStatus] = mapped_column(
        Enum(TopUpStatus, name="top_up_status", values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    method: Mapped[TopUpMethod] = mapped_column(
        Enum(TopUpMethod, name="top_up_method", values_callable=lambda e: [m.value for m in e]),
        default=TopUpMethod.BINANCE_PAY,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reference: Mapped[str | None] = mapped_column(
        String(64)
    )  # Binance order id typed by the driver
    # Set when the payment was seen in Binance Pay (unique: a payment is credited once).
    transaction_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    payer_binance_id: Mapped[str | None] = mapped_column(String(20))
    payer_name: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(300))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wallet_entries.id", ondelete="SET NULL")
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
