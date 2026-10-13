import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Platform(enum.StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class Category(enum.StrEnum):
    """What a notification is about (doc 14). Only marketing can be turned off by the user."""

    TRANSACTIONAL = "transactional"  # rides, wallet, fee, account, documents
    SAFETY = "safety"
    SUPPORT = "support"
    MARKETING = "marketing"  # campaigns


class Device(BaseModel):
    """A push token registered by the mobile app (Expo push token)."""

    __tablename__ = "devices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    push_token: Mapped[str] = mapped_column(String(255), unique=True)
    platform: Mapped[Platform] = mapped_column(_enum(Platform, "device_platform"))
    app_version: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Android notification channels the app created on this phone (doc 14). A push names one of
    # them; a channel the phone does not have would hide the notification.
    channels: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    # Updated when the app registers (each start); idle phones are deactivated.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(BaseModel):
    """In-app notification inbox; also delivered by push and WebSocket."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_created", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    category: Mapped[Category] = mapped_column(
        _enum(Category, "notification_category"),
        default=Category.TRANSACTIONAL,
        server_default=Category.TRANSACTIONAL.value,
    )
    # A screen of the app to open ("/wallet"); campaigns set it. Other types are routed by
    # ``data.type`` in the app.
    deep_link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(BaseModel):
    """What one user wants to receive (doc 14). Missing row = defaults (everything on, the
    default quiet hours). Transactional, safety and support notices cannot be turned off."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    marketing_push: Mapped[bool] = mapped_column(default=True)
    marketing_email: Mapped[bool] = mapped_column(default=True)
    # "HH:MM" Caracas time; None = the default window from the settings.
    quiet_start: Mapped[str | None] = mapped_column(String(5))
    quiet_end: Mapped[str | None] = mapped_column(String(5))


class CampaignStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"


class Campaign(BaseModel):
    """A marketing message to a segment of users (doc 14), sent by the worker in batches."""

    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[CampaignStatus] = mapped_column(
        _enum(CampaignStatus, "campaign_status"), default=CampaignStatus.DRAFT, index=True
    )
    # {"audience": "all|passengers|drivers", "cities": [...], "active_days": int, ...}
    segment: Mapped[dict] = mapped_column(JSONB, default=dict)
    channels: Mapped[list[str]] = mapped_column(JSONB, default=list)  # push, inbox, email
    title_es: Mapped[str] = mapped_column(String(120))
    body_es: Mapped[str] = mapped_column(Text, default="")
    title_en: Mapped[str | None] = mapped_column(String(120))
    body_en: Mapped[str | None] = mapped_column(Text)
    deep_link: Mapped[str | None] = mapped_column(String(300))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Snapshot counters, recomputed from the recipients while sending.
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class RecipientStatus(enum.StrEnum):
    PENDING = "pending"  # waiting (quiet hours) or not reached yet
    SENT = "sent"
    SKIPPED = "skipped"  # turned marketing off, daily limit reached, no channel left


class CampaignRecipient(BaseModel):
    """One user of a campaign: frozen when sending starts, so results add up."""

    __tablename__ = "campaign_recipients"
    __table_args__ = (
        UniqueConstraint("campaign_id", "user_id"),
        Index("ix_campaign_recipients_pending", "campaign_id", "status"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Server defaults: recipients are inserted in bulk with INSERT ... SELECT.
    status: Mapped[RecipientStatus] = mapped_column(
        _enum(RecipientStatus, "campaign_recipient_status"),
        default=RecipientStatus.PENDING,
        server_default=RecipientStatus.PENDING.value,
    )
    skip_reason: Mapped[str | None] = mapped_column(String(32))
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notifications.id", ondelete="SET NULL")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Push messages sent (phones) and Expo receipts "ok".
    pushed: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    delivered: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    emailed: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
