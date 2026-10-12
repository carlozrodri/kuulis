import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class FeatureFlag(BaseModel):
    """A feature switch changed from the admin (doc 10). The keys and their defaults live in
    ``apps.control.flags.FLAGS``; a row exists once someone changes one. ``rules`` narrows who gets
    it when it is on: ``{platforms, min_build, areas, roles, percent}`` (empty: everyone)."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(40), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class Announcement(BaseModel):
    """A banner shown at the top of the app between ``starts_at`` and ``ends_at``.

    ``title``/``body`` are ``{es, en}``; ``target`` is ``{roles: [passenger|driver], areas: []}``
    (empty: everyone); ``cta`` is ``{label: {es, en}, url, screen}`` or null."""

    __tablename__ = "announcements"

    title: Mapped[dict[str, str]] = mapped_column(JSONB)
    body: Mapped[dict[str, str]] = mapped_column(JSONB)
    target: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    cta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dismissible: Mapped[bool] = mapped_column(Boolean, default=True)
    style: Mapped[str] = mapped_column(String(16), default="info")  # info | warning | promo
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
