import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class StaffRole(BaseModel):
    """A set of admin permissions given to staff accounts (``users.staff_role_id``)."""

    __tablename__ = "staff_roles"

    name: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)


class StaffServiceToken(BaseModel):
    """A long-lived key a program (the marketing agents) uses to act as a staff account on
    ``Can(...)`` endpoints only, limited to ``permissions``. Only the SHA-256 of the key is kept."""

    __tablename__ = "staff_service_tokens"

    name: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
