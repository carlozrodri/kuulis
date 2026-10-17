import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    Sequence,
    String,
    text,
)
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
    # Doc 22: Kuulis' reward for inviting a driver (not part of the month's earnings).
    REFERRAL_BONUS = "referral_bonus"


class TopUpStatus(enum.StrEnum):
    PENDING = "pending"  # the driver says they paid; waiting for the payment
    COMPLETED = "completed"
    REJECTED = "rejected"
    UNMATCHED = "unmatched"  # a payment arrived and no driver owns the payer's Binance Pay ID


class TopUpMethod(enum.StrEnum):
    BINANCE_PAY = "binance_pay"


class ReceiptKind(enum.StrEnum):
    TOP_UP = "top_up"
    SUBSCRIPTION_FEE = "subscription_fee"


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
    # The driver's Binance Pay ID. Anyone can type any id, so payments from it are credited
    # automatically only once staff matched a first payment from it to this driver (verified).
    binance_pay_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    binance_pay_id_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    # The driver's last "my top-up did not arrive" ticket (doc 17), in Support.
    dispute_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL")
    )


RECEIPT_NUMBER = Sequence("wallet_receipt_number_seq")


class Receipt(BaseModel):
    """A non-fiscal receipt (doc 17) for a credited top-up or a paid fee. ``number`` is a
    correlative across every driver; the receipt is written with its ledger entry and never
    changes."""

    __tablename__ = "wallet_receipts"

    number: Mapped[int] = mapped_column(
        BigInteger, RECEIPT_NUMBER, server_default=RECEIPT_NUMBER.next_value(), unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wallet_entries.id", ondelete="CASCADE"), unique=True
    )
    kind: Mapped[ReceiptKind] = mapped_column(
        Enum(ReceiptKind, name="receipt_kind", values_callable=lambda e: [m.value for m in e])
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # positive
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # "Recarga Binance Pay" / "Cuota de septiembre 2026", in the driver's language at issue time.
    concept: Mapped[str] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
