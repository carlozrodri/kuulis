"""Exchange rates: current values (Redis, falling back to the newest row), history, manual
corrections and the polling job.

A manual rate "holds" for ``rates_manual_hold_hours``: automatic results are still fetched but
not stored, so a bad source cannot overwrite the correction an admin just made.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import orjson
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig
from apps.config.services import get_app_config
from apps.rates import sources
from apps.rates.models import ExchangeRate, RateOrigin, RateSource
from apps.rates.schemas import (
    CurrentRates,
    ExchangeRateHistory,
    ExchangeRateRead,
    FrozenRates,
    UserBrief,
    VesAmount,
)
from apps.users.models import User
from kuulis.core.pagination import PageParams, paginate
from kuulis.core.redis import redis_client
from kuulis.settings import settings

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
_PREFIX = f"{settings.APP_ENV}:rates"
# An automatic value this far from the current one (while the current one is recent) is treated
# as a broken source and skipped. Real moves this large within a day do not happen.
MAX_JUMP = Decimal("0.25")
JUMP_WINDOW = timedelta(hours=24)


def _current_key(source: RateSource) -> str:
    return f"{_PREFIX}:current:{source.value}"


def _hold_key(source: RateSource) -> str:
    return f"{_PREFIX}:hold:{source.value}"


def _due_key(source: RateSource) -> str:
    return f"{_PREFIX}:due:{source.value}"


def _snapshot(row: ExchangeRate) -> dict:
    return {
        "source": row.source.value,
        "rate": str(row.rate),
        "origin": row.origin.value,
        "as_of": row.as_of.isoformat(),
        "fetched_at": row.fetched_at.isoformat(),
    }


async def _cache(row: ExchangeRate) -> None:
    await redis_client.set(_current_key(row.source), orjson.dumps(_snapshot(row)).decode())


async def _latest_row(session: AsyncSession, source: RateSource) -> ExchangeRate | None:
    return await session.scalar(
        select(ExchangeRate)
        .where(ExchangeRate.source == source)
        .order_by(ExchangeRate.fetched_at.desc())
        .limit(1)
    )


async def _current_snapshot(session: AsyncSession, source: RateSource) -> dict | None:
    raw = await redis_client.get(_current_key(source))
    if raw:
        return orjson.loads(raw)
    row = await _latest_row(session, source)
    if row is None:
        return None
    await _cache(row)
    return _snapshot(row)


def _read(snapshot: dict, config: AppConfig, now: datetime) -> ExchangeRateRead:
    source = RateSource(snapshot["source"])
    fetched_at = datetime.fromisoformat(snapshot["fetched_at"])
    return ExchangeRateRead(
        source=source,
        rate=Decimal(snapshot["rate"]),
        origin=RateOrigin(snapshot["origin"]),
        as_of=datetime.fromisoformat(snapshot["as_of"]),
        fetched_at=fetched_at,
        stale=now - fetched_at > timedelta(minutes=config.stale_minutes(source)),
    )


async def current_rates(session: AsyncSession) -> CurrentRates:
    config = await get_app_config(session)
    now = datetime.now(UTC)
    values: dict[str, ExchangeRateRead | None] = {}
    for source in RateSource:
        snapshot = await _current_snapshot(session, source)
        values[source.value] = _read(snapshot, config, now) if snapshot else None
    return CurrentRates(**values)


async def current_values(session: AsyncSession) -> FrozenRates:
    """The rates (Bs per USD) to freeze on a ride or show on a quote."""
    values: dict[str, Decimal | None] = {}
    for source in RateSource:
        snapshot = await _current_snapshot(session, source)
        values[source.value] = Decimal(snapshot["rate"]) if snapshot else None
    return FrozenRates(**values)


def to_ves(amount: Decimal, rates: FrozenRates) -> VesAmount:
    def convert(rate: Decimal | None) -> Decimal | None:
        return (amount * rate).quantize(CENT, rounding=ROUND_HALF_UP) if rate else None

    return VesAmount(bcv=convert(rates.bcv), binance=convert(rates.binance))


# --- Writes ------------------------------------------------------------------------------------


async def set_manual(
    session: AsyncSession, user: User, source: RateSource, rate: Decimal, note: str | None
) -> ExchangeRateRead:
    """Stores a manual rate; the caller commits, then calls ``after_manual``."""
    config = await get_app_config(session)
    now = datetime.now(UTC)
    row = ExchangeRate(
        source=source,
        rate=rate,
        origin=RateOrigin.MANUAL,
        as_of=now,
        fetched_at=now,
        created_by_id=user.id,
        note=note,
    )
    session.add(row)
    await session.flush()
    return _read(_snapshot(row), config, now)


async def after_manual(session: AsyncSession, source: RateSource) -> None:
    """After the commit: publish the manual rate and hold it."""
    config = await get_app_config(session)
    row = await _latest_row(session, source)
    if row is not None:
        await _cache(row)
    await redis_client.set(_hold_key(source), "1", ex=config.rates_manual_hold_hours * 3600)


async def record_auto(
    session: AsyncSession, source: RateSource, rate: Decimal, as_of: datetime
) -> bool:
    """Stores an automatic result unless a manual rate holds or the value looks broken."""
    if await redis_client.exists(_hold_key(source)):
        logger.info("Rate %s: manual rate on hold, skipping %s", source, rate)
        return False
    now = datetime.now(UTC)
    current = await _latest_row(session, source)
    if current is not None and now - current.fetched_at < JUMP_WINDOW:
        change = abs(rate - current.rate) / current.rate
        if change > MAX_JUMP:
            logger.error(
                "Rate %s: %s is %.0f%% away from %s, skipped",
                source,
                rate,
                change * 100,
                current.rate,
            )
            return False
    row = ExchangeRate(
        source=source,
        rate=rate.quantize(Decimal("0.0001")),
        origin=RateOrigin.AUTO,
        as_of=as_of,
        fetched_at=now,
    )
    session.add(row)
    await session.commit()
    await _cache(row)
    return True


async def fetch(session: AsyncSession, source: RateSource) -> bool:
    try:
        rate, as_of = await sources.FETCHERS[source]()
    except sources.RateFetchError:
        logger.warning("Rate %s: fetch failed", source, exc_info=True)
        return False
    await record_auto(session, source, rate, as_of)
    return True


async def refresh(session: AsyncSession, source: RateSource | None = None) -> CurrentRates:
    for item in [source] if source else list(RateSource):
        await fetch(session, item)
    return await current_rates(session)


# --- History -----------------------------------------------------------------------------------


async def history(
    session: AsyncSession, source: RateSource | None, params: PageParams
) -> tuple[list[ExchangeRateHistory], int]:
    stmt = select(ExchangeRate).order_by(ExchangeRate.fetched_at.desc())
    if source is not None:
        stmt = stmt.where(ExchangeRate.source == source)
    rows, total = await paginate(session, stmt, params)
    authors = {r.created_by_id for r in rows if r.created_by_id}
    users: dict[uuid.UUID, User] = {}
    if authors:
        users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(authors)))}
    items = []
    for row in rows:
        item = ExchangeRateHistory.model_validate(row)
        author = users.get(row.created_by_id) if row.created_by_id else None
        if author is not None:
            item.created_by = UserBrief(id=author.id, name=author.full_name or author.email)
        items.append(item)
    return items, total


# --- Polling (worker) --------------------------------------------------------------------------

RETRY_AFTER_FAILURE = timedelta(minutes=5)


def _interval(source: RateSource) -> timedelta:
    minutes = (
        settings.RATES_BCV_INTERVAL_MINUTES
        if source == RateSource.BCV
        else settings.RATES_BINANCE_INTERVAL_MINUTES
    )
    return timedelta(minutes=minutes)


async def poll_due(session: AsyncSession) -> None:
    """Fetches every source whose interval elapsed. The Redis key is both the timer and the lock,
    so with several workers each source is fetched once per interval."""
    for source in RateSource:
        interval = _interval(source)
        if not await redis_client.set(
            _due_key(source), "1", nx=True, ex=int(interval.total_seconds())
        ):
            continue
        if not await fetch(session, source):
            # Try again sooner than the full interval.
            await redis_client.set(
                _due_key(source), "1", ex=int(RETRY_AFTER_FAILURE.total_seconds())
            )
