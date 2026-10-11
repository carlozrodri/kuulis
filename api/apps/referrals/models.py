import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class Referral(BaseModel):
    """A driver who joined with another user's invite code. The inviter earns a free month of
    subscription when the invited driver completes their first trip (``rewarded_at``)."""

    __tablename__ = "referrals"

    referrer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    referred_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    code: Mapped[str] = mapped_column(String(12))
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
