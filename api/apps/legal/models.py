import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class LegalDocument(BaseModel):
    """One published version of a legal text in one language (doc 07). Versions only grow; an old
    version stays so every acceptance can be traced to the exact text."""

    __tablename__ = "legal_documents"
    __table_args__ = (UniqueConstraint("kind", "version", "locale"),)

    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(120))
    body_md: Mapped[str] = mapped_column(Text)
    # What changed, shown on the "we updated our terms" screen.
    summary: Mapped[str] = mapped_column(String(500), default="")
    # Everyone who accepted an earlier version must accept this one before riding again.
    requires_reacceptance: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class LegalAcceptance(BaseModel):
    """A user accepted a version of a legal text (append-only)."""

    __tablename__ = "legal_acceptances"
    __table_args__ = (Index("ix_legal_acceptances_user_kind", "user_id", "kind"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(45))
    platform: Mapped[str | None] = mapped_column(String(20))
