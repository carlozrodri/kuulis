import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class Platform(enum.StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class Device(BaseModel):
    """A push token registered by the mobile app (Expo push token)."""

    __tablename__ = "devices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    push_token: Mapped[str] = mapped_column(String(255), unique=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, name="device_platform", values_callable=lambda e: [m.value for m in e])
    )
    app_version: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)


class Notification(BaseModel):
    """In-app notification inbox; also delivered by push and WebSocket."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
