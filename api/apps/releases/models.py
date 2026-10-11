import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class AppRelease(BaseModel):
    """An APK offered to the installed apps of one channel (doc 09).

    The compiler uploads every build to S3; one becomes a release when someone publishes it from
    the admin. A mandatory release makes every older build stop working for rides until it
    updates; withdrawing a release offers the previous one again."""

    __tablename__ = "app_releases"
    __table_args__ = (
        UniqueConstraint("platform", "channel", "build", name="uq_app_release_build"),
    )

    platform: Mapped[str] = mapped_column(String(16), default="android")
    channel: Mapped[str] = mapped_column(String(16), index=True)
    version: Mapped[str] = mapped_column(String(32))
    build: Mapped[int] = mapped_column(Integer)
    file_key: Mapped[str] = mapped_column(String(512))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    md5: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
