import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class UserTotp(BaseModel):
    """The authenticator app of a staff/admin account (apps/auth/totp.py)."""

    __tablename__ = "user_totp"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    secret: Mapped[str] = mapped_column(String(255))  # encrypted (kuulis.core.crypto)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_codes: Mapped[list[str]] = mapped_column(JSONB, default=list)  # sha256 hex, unused
    last_step: Mapped[int] = mapped_column(Integer, default=0)  # a code works only once
