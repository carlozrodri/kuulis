"""Product analytics (doc 19): app events, drivers' online sessions, supply per cell and hour,
and the cohort tables the daily job precomputes for the admin."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    DDL,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import Base, BaseModel


class AnalyticsEvent(Base):
    """One event sent by the app. Partitioned by month on ``occurred_at`` (one table per month,
    created ahead by the daily job; the default partition catches anything outside them), so the
    13-month retention drops whole partitions. No email, phone or exact coordinates: ``cell`` is a
    ~1 km square (see ``apps.analytics.events.cell_of``)."""

    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_events_event_occurred", "event", "occurred_at"),
        Index("ix_analytics_events_user", "user_id"),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    # No foreign key: inserts stay cheap and erasing an account deletes its events explicitly.
    user_id: Mapped[uuid.UUID | None] = mapped_column()
    # Random id of the installation, so events before signing in can be joined to the funnel.
    anon_id: Mapped[str] = mapped_column(String(64))
    event: Mapped[str] = mapped_column(String(40))
    props: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    platform: Mapped[str | None] = mapped_column(String(10))
    app_version: Mapped[str | None] = mapped_column(String(40))
    area: Mapped[str | None] = mapped_column(String(60))
    cell: Mapped[str | None] = mapped_column(String(20))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# Tests (and a fresh database) create the table with ``metadata.create_all``: give it a default
# partition so inserts work before the first monthly ones exist. The migration does the same.
event.listen(
    AnalyticsEvent.__table__,
    "after_create",
    DDL(
        "CREATE TABLE IF NOT EXISTS analytics_events_default PARTITION OF analytics_events DEFAULT"
    ),
)


class DriverOnlineSession(BaseModel):
    """From going online to going offline (utilization = time in rides / time online). Opened and
    closed by the sampler in ``apps.analytics.tasks``, which compares the online drivers in Redis
    with the open sessions every minute, so every way of going offline is covered."""

    __tablename__ = "driver_online_sessions"
    __table_args__ = (
        Index(
            "ix_driver_online_sessions_open",
            "driver_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index("ix_driver_online_sessions_started", "started_at"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    area: Mapped[str | None] = mapped_column(String(60))


class SupplyHour(BaseModel):
    """Minutes of online drivers in one cell during one hour (the supply side of the heat map)."""

    __tablename__ = "supply_hours"
    __table_args__ = (UniqueConstraint("hour", "cell"),)

    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cell: Mapped[str] = mapped_column(String(20))
    area: Mapped[str | None] = mapped_column(String(60))
    driver_minutes: Mapped[int] = mapped_column(Integer, default=0)


class AnalyticsCohort(BaseModel):
    """People of one cohort who reached one step, precomputed every day.

    - ``passenger_funnel`` / ``driver_funnel``: cohort = local day of signing up / of the driver
      application; steps in ``apps.analytics.product.PASSENGER_STEPS`` / ``DRIVER_STEPS``.
    - ``passenger_retention`` / ``driver_retention``: cohort = Monday of the week of the first
      completed ride; step ``w0`` is the cohort size, ``wN`` those who rode again N weeks later
      (only stored once that week is over for the whole cohort).

    ``area`` is the person's city ("" when unknown); every person is in one city only, so the
    totals for all cities are the sum of the rows."""

    __tablename__ = "analytics_cohorts"
    __table_args__ = (UniqueConstraint("kind", "cohort", "area", "step"),)

    kind: Mapped[str] = mapped_column(String(32))
    cohort: Mapped[date] = mapped_column(Date)
    area: Mapped[str] = mapped_column(String(60), default="")
    step: Mapped[str] = mapped_column(String(32))
    users: Mapped[int] = mapped_column(Integer)
