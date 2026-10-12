import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class AppUpdate(BaseModel):
    """A JavaScript update (OTA) offered to the installed apps of one channel (doc 09).

    The compiler exports every JS-only change and uploads it to S3 as a candidate; publishing one
    from the admin creates a row here. Its ``id`` and ``created_at`` are the manifest's id and
    date, so a row is never changed into another update: reverting publishes a new row (a copy of
    the previous update, or a ``rollback`` that tells the apps to go back to the code inside the
    APK). Only apps with the same ``runtime_version`` (native code fingerprint) receive it."""

    __tablename__ = "app_updates"

    platform: Mapped[str] = mapped_column(String(16), default="android")
    channel: Mapped[str] = mapped_column(String(16), index=True)
    runtime_version: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="update")  # update | rollback
    source_key: Mapped[str | None] = mapped_column(String(512))
    commit: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(Text)
    launch_asset: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    assets: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    rollout_percent: Mapped[int] = mapped_column(Integer, default=100)
    reverted_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_updates.id", ondelete="SET NULL")
    )
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
