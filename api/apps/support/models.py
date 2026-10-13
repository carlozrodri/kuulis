"""Help center, saved replies and lost items (doc 13). Tickets themselves are ``reports``
(apps.moderation)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class HelpTopic(enum.StrEnum):
    ACCOUNT = "account"
    RIDES = "rides"
    PAYMENTS = "payments"  # paying the driver
    WALLET = "wallet"  # balance and the monthly fee (drivers)
    SAFETY = "safety"
    DOCUMENTS = "documents"  # driver documents and verification
    APP = "app"  # problems with the app


class HelpAudience(enum.StrEnum):
    ALL = "all"
    PASSENGER = "passenger"
    DRIVER = "driver"


class HelpArticle(BaseModel):
    """A help center article in one language. The same ``slug`` links its translations."""

    __tablename__ = "help_articles"
    __table_args__ = (
        Index("uq_help_articles_slug_locale", "slug", "locale", unique=True),
        Index("ix_help_articles_listing", "locale", "published", "topic", "position"),
    )

    slug: Mapped[str] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(5))
    topic: Mapped[HelpTopic] = mapped_column(_enum(HelpTopic, "help_topic"))
    audience: Mapped[HelpAudience] = mapped_column(
        _enum(HelpAudience, "help_audience"), default=HelpAudience.ALL, server_default="all"
    )
    title: Mapped[str] = mapped_column(String(200))
    body_md: Mapped[str] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    views: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    helpful_yes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    helpful_no: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class CannedAction(enum.StrEnum):
    """What a saved reply does besides answering (a macro)."""

    NONE = "none"
    WAIT_USER = "wait_user"  # answer and wait for the user (the default for any answer)
    RESOLVE = "resolve"  # answer and close as resolved


class CannedResponse(BaseModel):
    """A saved reply. ``{nombre}`` and ``{viaje}`` are filled in when sent."""

    __tablename__ = "canned_responses"

    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(5), default="es", server_default="es")
    action: Mapped[CannedAction] = mapped_column(
        _enum(CannedAction, "canned_action"), default=CannedAction.NONE, server_default="none"
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list, server_default="{}")
    uses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class LostItemAnswer(enum.StrEnum):
    HAS_IT = "has_it"
    NOT_FOUND = "not_found"


class LostItemRequest(BaseModel):
    """A passenger forgot something on a ride. The driver answers; with "Lo tengo" the ride chat
    opens again until ``chat_until`` so they agree on the hand-over without sharing phones."""

    __tablename__ = "lost_item_requests"

    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), unique=True
    )
    passenger_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(500))
    answer: Mapped[LostItemAnswer | None] = mapped_column(_enum(LostItemAnswer, "lost_item_answer"))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chat_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
