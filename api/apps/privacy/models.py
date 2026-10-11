import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class DataExport(BaseModel):
    """A "download my data" request (doc 07): a JSON file in private S3, emailed as a link that
    expires after 24 h; the retention job deletes the file then."""

    __tablename__ = "data_exports"
    __table_args__ = (Index("ix_data_exports_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    file_key: Mapped[str | None] = mapped_column(String(512))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(64))


class ErasedEmail(BaseModel):
    """SHA-256 of the email of every erased account, so a suspended person cannot simply delete the
    account and sign up again (doc 16 decides what to do with a match)."""

    __tablename__ = "erased_emails"

    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    was_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    erased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserConsent(BaseModel):
    """An explicit permission the user gave or withdrew in the app (e.g. the driver's location
    while the app is minimized). The latest row per kind is in force."""

    __tablename__ = "user_consents"
    __table_args__ = (Index("ix_user_consents_user_kind", "user_id", "kind"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    granted: Mapped[bool] = mapped_column(Boolean)
    ip: Mapped[str | None] = mapped_column(String(45))
    platform: Mapped[str | None] = mapped_column(String(20))
