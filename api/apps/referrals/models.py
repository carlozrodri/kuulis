import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class ReferralStatus(enum.StrEnum):
    PENDING = "pending"  # the invited driver is on the way (not approved yet, or few trips)
    QUALIFIED = "qualified"  # met the requirements; the reward waits for a monthly cap or budget
    HELD = "held"  # met the requirements; the reward waits for a person (high risk)
    REWARDED = "rewarded"
    REJECTED = "rejected"  # expired, shared identity with the inviter, or rejected by staff


class RewardKind(enum.StrEnum):
    FREE_MONTH = "free_month"  # before doc 22: a free month for the invited driver's first trip
    WALLET_CREDIT = "wallet_credit"  # doc 22: ``referral_bonus`` credit in the inviter's wallet


class Referral(BaseModel):
    """A driver who joined with another driver's invite code (doc 22). The inviter earns wallet
    credit once the invited driver completes ``required_trips`` within ``window_days`` of their
    approval (``AppConfig.referral_program``)."""

    __tablename__ = "referrals"
    __table_args__ = (Index("ix_referrals_status_created", "status", "created_at"),)

    referrer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    referred_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    code: Mapped[str] = mapped_column(String(12))
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(
            ReferralStatus,
            name="referral_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ReferralStatus.PENDING,
        server_default=ReferralStatus.PENDING.value,
    )
    # Trips that count (completed in the window, not with the inviter as passenger, not flagged).
    trips: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # The invited driver's approval plus ``window_days``; set at the first evaluation after it.
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reward_kind: Mapped[RewardKind | None] = mapped_column(
        Enum(
            RewardKind, name="referral_reward_kind", values_callable=lambda e: [m.value for m in e]
        )
    )
    # Reserved when held, paid when rewarded; counts against the program budget.
    reward_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    reward_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("wallet_entries.id", ondelete="SET NULL")
    )
    # Why it waits or was rejected: monthly_cap, budget, program_off, risk_score, expired,
    # shared_identity, inviter_inactive (closed or deleted account), staff.
    reason: Mapped[str | None] = mapped_column(String(40))
    # Evidence for the admin: shared identity kinds, risk scores, the invitee's free month.
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))
