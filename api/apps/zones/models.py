"""Zones inside the cities (doc 21): surge, restricted and suggested pickup points.

Cities stay in the settings (``service_areas``, now with an optional polygon); a zone names its
city. Polygons are JSONB ``[[lat, lng], ...]`` checked in Python, so Postgres needs no PostGIS.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from kuulis.core.models import BaseModel


class ZoneKind(enum.StrEnum):
    SURGE = "surge"  # a multiplier while the zone is in force
    RESTRICTED = "restricted"  # no pickups and/or drop-offs (dangerous areas, airport...)
    PICKUP = "pickup"  # suggested pickup points (malls, metro stations)


class Zone(BaseModel):
    __tablename__ = "zones"

    kind: Mapped[ZoneKind] = mapped_column(
        Enum(ZoneKind, name="zone_kind", values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(60), index=True)
    polygon: Mapped[list] = mapped_column(JSONB)
    rules: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
