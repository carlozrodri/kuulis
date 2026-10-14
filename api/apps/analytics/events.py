"""Product events sent by the app (doc 19): a closed list, minimal properties and no personal data.

The app batches events (every 30 s or when it goes to the background) and posts them to
``POST /analytics/events``. Unknown events and properties are dropped, not rejected, so an older
build never breaks; so are text values that look like an email or a phone number. Locations only
arrive as a ~1 km cell (``cell_of``), never as coordinates.

A signed-in user who switched off "Compartir datos de uso anónimos" (consent ``usage_data``) is
not recorded at all; the app also stops sending.
"""

import math
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.analytics.models import AnalyticsEvent
from apps.config.schemas import AppConfig
from kuulis.core.redis import redis_client
from kuulis.settings import settings

PropType = Literal["str", "int", "float", "bool"]

# Every event the app may send and the properties kept for each one. Adding an event here is the
# only way to start collecting it (and docs/produccion/19 lists them for the privacy policy).
EVENTS: dict[str, dict[str, PropType]] = {
    "app_open": {"mode": "str", "cold": "bool"},
    "screen_view": {"screen": "str", "mode": "str"},
    "signup_started": {"method": "str"},
    "signup_completed": {"method": "str"},
    "driver_onboarding_step": {"step": "str"},
    "search_opened": {},
    "quote_shown": {
        "vehicle_type": "str",
        "distance_km": "float",
        "fare": "float",
        "promo": "bool",
    },
    "ride_requested": {"vehicle_type": "str", "payment_method": "str", "promo": "bool"},
    "ride_matched": {"wait_s": "int"},
    "ride_completed": {"role": "str"},
    "rating_submitted": {"role": "str", "stars": "int"},
    "topup_started": {"amount": "float"},
    "topup_completed": {"amount": "float"},
    "report_created": {"category": "str"},
    "help_article_viewed": {"slug": "str"},
    "update_prompt_shown": {"kind": "str"},
}
# Never stored, whatever an event declares (the schema test checks the catalogue against it).
FORBIDDEN_KEYS = frozenset(
    {"email", "phone", "name", "full_name", "lat", "lng", "latitude", "longitude", "address"}
)
# Order of the driver application screens, as the app reports them in ``driver_onboarding_step``.
ONBOARDING_STEPS = ("intro", "personal", "vehicle", "documents", "review", "submitted")

MAX_BATCH = 100
MAX_TEXT = 64
MAX_AGE = timedelta(days=7)  # older events (a phone offline for weeks) are dropped
MAX_SKEW = timedelta(minutes=5)  # a clock ahead of ours is brought back to now
# A cell is 0.01° x 0.01° (~1.1 km in Venezuela), named "<floor(lat*100)>:<floor(lng*100)>". The
# app and the SQL in apps.analytics.product multiply by 100 the same way (dividing by 0.01 can land
# on the other side of a cell border).
CELLS_PER_DEGREE = 100
CELL_PATTERN = r"^-?\d{1,5}:-?\d{1,5}$"

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_LONG_NUMBER = re.compile(r"\d{4,}")


class EventIn(BaseModel):
    event: str = Field(max_length=40)
    occurred_at: datetime
    props: dict[str, Any] = Field(default_factory=dict, max_length=20)
    cell: str | None = Field(default=None, pattern=CELL_PATTERN, max_length=20)


class EventBatch(BaseModel):
    anon_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9:_-]+$")
    platform: Literal["android", "ios", "web"] | None = None
    app_version: str | None = Field(default=None, max_length=40)
    events: list[EventIn] = Field(max_length=MAX_BATCH)


class BatchResult(BaseModel):
    accepted: int
    dropped: int


def cell_of(lat: float, lng: float) -> str:
    return f"{math.floor(lat * CELLS_PER_DEGREE)}:{math.floor(lng * CELLS_PER_DEGREE)}"


def cell_center(cell: str) -> tuple[float, float]:
    i, j = (int(part) for part in cell.split(":"))
    return round((i + 0.5) / CELLS_PER_DEGREE, 5), round((j + 0.5) / CELLS_PER_DEGREE, 5)


def area_of(config: AppConfig, lat: float, lng: float) -> str | None:
    for area in config.service_areas:
        if area.contains(lat, lng):
            return area.name
    return None


def area_of_cell(config: AppConfig, cell: str | None) -> str | None:
    return area_of(config, *cell_center(cell)) if cell else None


def _clean_text(value: str) -> str | None:
    text = _UUID.sub(":id", value.strip())[:MAX_TEXT]
    if not text or _EMAIL.search(text) or _PHONE.search(text):
        return None
    # Routes like /reports/123456 keep their shape without the id.
    return _LONG_NUMBER.sub(":n", text)


def clean_props(event: str, props: dict[str, Any]) -> dict[str, Any]:
    """Keeps only the declared properties with the declared type."""
    spec = EVENTS[event]
    clean: dict[str, Any] = {}
    for key, kind in spec.items():
        if key in FORBIDDEN_KEYS or key not in props:
            continue
        value = props[key]
        if kind == "bool" and isinstance(value, bool):
            clean[key] = value
        elif kind == "int" and isinstance(value, int) and not isinstance(value, bool):
            clean[key] = max(min(value, 10**9), -(10**9))
        elif (
            kind == "float"
            and isinstance(value, int | float)
            and not isinstance(value, bool)
            and math.isfinite(value)
        ):
            clean[key] = round(float(value), 2)
        elif kind == "str" and isinstance(value, str):
            text = _clean_text(value)
            if text is not None:
                clean[key] = text
    return clean


# --- Opting out ---------------------------------------------------------------------------------


def _opt_out_key(user_id: uuid.UUID) -> str:
    return f"{settings.APP_ENV}:analytics:optout:{user_id}"


async def forget_opt_out(user_id: uuid.UUID) -> None:
    """Called when the user changes the ``usage_data`` consent."""
    await redis_client.delete(_opt_out_key(user_id))


async def opted_out(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """Cached for a day: the app posts a batch every 30 s."""
    from apps.privacy import services as privacy

    key = _opt_out_key(user_id)
    cached = await redis_client.get(key)
    if cached is not None:
        return cached == "1"
    out = not await privacy.consent_granted(session, user_id, "usage_data")
    await redis_client.set(key, "1" if out else "0", ex=86400)
    return out


# --- Ingest ------------------------------------------------------------------------------------


async def ingest(
    session: AsyncSession,
    batch: EventBatch,
    user_id: uuid.UUID | None,
    config: AppConfig,
    now: datetime | None = None,
) -> BatchResult:
    now = now or datetime.now(UTC)
    if user_id is not None and await opted_out(session, user_id):
        return BatchResult(accepted=0, dropped=len(batch.events))
    rows = []
    for item in batch.events:
        if item.event not in EVENTS:
            continue
        occurred = item.occurred_at
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=UTC)
        if occurred < now - MAX_AGE:
            continue
        rows.append(
            {
                "id": uuid.uuid4(),
                "occurred_at": now if occurred > now + MAX_SKEW else occurred,
                "user_id": user_id,
                "anon_id": batch.anon_id,
                "event": item.event,
                "props": clean_props(item.event, item.props),
                "platform": batch.platform,
                "app_version": batch.app_version,
                "cell": item.cell,
                "area": area_of_cell(config, item.cell),
                "received_at": now,
            }
        )
    if rows:
        await session.execute(insert(AnalyticsEvent), rows)
    return BatchResult(accepted=len(rows), dropped=len(batch.events) - len(rows))
