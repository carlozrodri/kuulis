"""Social media content registry (docs/marketing/09): every piece, its versions per network, the
files in S3, where it was published and how it did.

Statuses and kinds are short strings validated by the schemas (``apps.marketing.schemas``), so the
agents' vocabulary can grow without a database enum migration."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class MarketingContent(BaseModel):
    """One piece of content (an idea until it is published or discarded). ``code`` names it
    everywhere: S3 folder, UTM ``utm_content``, the posting package."""

    __tablename__ = "marketing_contents"
    __table_args__ = (Index("ix_marketing_contents_status_scheduled", "status", "scheduled_for"),)

    code: Mapped[str] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    pillar: Mapped[str | None] = mapped_column(String(40))
    format: Mapped[str | None] = mapped_column(String(40))
    audience: Mapped[str] = mapped_column(String(16), default="ambos", server_default="ambos")
    status: Mapped[str] = mapped_column(String(16), default="idea", server_default="idea")
    # Hooks, on-screen text, subtitles, CTA... as the script template has them (marketing/guiones).
    script: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    uses_character: Mapped[bool] = mapped_column(Boolean, default=False)
    production: Mapped[str] = mapped_column(String(8), default="ia", server_default="ia")
    scheduled_for: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    # Last "changes requested" from the approval queue.
    review_note: Mapped[str | None] = mapped_column(Text)
    created_by_agent: Mapped[str | None] = mapped_column(String(40))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketingAsset(BaseModel):
    """A file of a piece in the marketing bucket: what a tool returned (``original``), a file ready
    for a network (``final``), a cover or an intermediate source. Discarded takes are kept too."""

    __tablename__ = "marketing_assets"

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("marketing_contents.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(8))  # video | imagen | audio
    role: Mapped[str] = mapped_column(String(10))  # original | final | portada | fuente
    source: Mapped[str] = mapped_column(String(32))  # remotion, higgsfield, buzzy, telefono...
    model: Mapped[str | None] = mapped_column(String(80))
    prompt: Mapped[str | None] = mapped_column(Text)
    credits_used: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rights: Mapped[str | None] = mapped_column(Text)  # licence or image release
    s3_key: Mapped[str] = mapped_column(String(512), unique=True)
    filename: Mapped[str] = mapped_column(String(160))
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    # Set when the upload is confirmed; until then the key may hold nothing.
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class MarketingVariant(BaseModel):
    """The version of a piece for one network: its file, cover, texts and posting time."""

    __tablename__ = "marketing_variants"
    __table_args__ = (UniqueConstraint("content_id", "platform", name="uq_marketing_variant"),)

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("marketing_contents.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(16))
    account: Mapped[str | None] = mapped_column(String(60))
    hook_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str | None] = mapped_column(String(100))
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    # Extra steps for the person posting ("pick a commercial sound"...); the AI label step is
    # always added.
    checklist: Mapped[list[str]] = mapped_column(ARRAY(String(160)), default=list)
    ai_label: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_s: Mapped[float | None] = mapped_column(Float)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marketing_assets.id", ondelete="SET NULL")
    )
    cover_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marketing_assets.id", ondelete="SET NULL")
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class MarketingPublication(BaseModel):
    """A variant that went out: by the person in Caracas (``manual``) or later by API."""

    __tablename__ = "marketing_publications"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("marketing_variants.id", ondelete="CASCADE"), unique=True
    )
    platform: Mapped[str] = mapped_column(String(16), index=True)
    account: Mapped[str | None] = mapped_column(String(60))
    external_id: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    method: Mapped[str] = mapped_column(String(8), default="manual", server_default="manual")
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class MarketingMetricSnapshot(BaseModel):
    """A publication's numbers at one moment (24 h, 72 h, 7 days...), typed in or read by API."""

    __tablename__ = "marketing_metric_snapshots"
    __table_args__ = (
        Index("ix_marketing_metric_snapshots_publication_taken", "publication_id", "taken_at"),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("marketing_publications.id", ondelete="CASCADE")
    )
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    age_h: Mapped[int] = mapped_column(Integer)
    views: Mapped[int | None] = mapped_column(BigInteger)
    reach: Mapped[int | None] = mapped_column(BigInteger)
    avg_watch_s: Mapped[float | None] = mapped_column(Float)
    completion_rate: Mapped[float | None] = mapped_column(Float)  # 0..1
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    follows: Mapped[int | None] = mapped_column(Integer)
    profile_visits: Mapped[int | None] = mapped_column(Integer)
    link_clicks: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(8), default="manual", server_default="manual")
    entered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class MarketingLearning(BaseModel):
    """Something the data suggests or proved ("hooks with a figure keep 30 % more viewers")."""

    __tablename__ = "marketing_learnings"

    statement: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)  # piece codes and numbers
    status: Mapped[str] = mapped_column(String(12), default="hipotesis", server_default="hipotesis")
    platform: Mapped[str | None] = mapped_column(String(16))
    pillar: Mapped[str | None] = mapped_column(String(40))
    format: Mapped[str | None] = mapped_column(String(40))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketingSpend(BaseModel):
    """Money spent on content: subscriptions, credit packs, ads."""

    __tablename__ = "marketing_spend"

    date: Mapped[date] = mapped_column(Date, index=True)
    tool: Mapped[str] = mapped_column(String(40))
    concept: Mapped[str] = mapped_column(String(16))  # suscripcion | creditos | pauta | otro
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class MarketingAccount(BaseModel):
    """A Kuulis account on a network. Tokens never live here (secrets manager, MK8)."""

    __tablename__ = "marketing_accounts"
    __table_args__ = (UniqueConstraint("platform", "handle", name="uq_marketing_account"),)

    platform: Mapped[str] = mapped_column(String(16))
    handle: Mapped[str] = mapped_column(String(60))
    url: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(12), default="pendiente", server_default="pendiente")
    connection: Mapped[str] = mapped_column(String(8), default="manual", server_default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
