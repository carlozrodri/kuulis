"""Quality rates, levels and automatic pauses (doc 15).

Rates cover the last ``quality.window_days`` days:

- Driver: acceptance = accepted offers / offers answered or missed; cancellation = counted
  cancellations / accepted offers.
- Passenger: cancellation = counted cancellations / rides that got a driver; no-shows = rides a
  driver closed as "no se presentó".

Counted cancellations come from ``ride_cancellations`` (a cancellation inside the passenger's
grace period, a valid no-show, a safety concern or a moto that did not match never count).
"""

import contextlib
import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import Select, and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig, QualitySettings
from apps.drivers.models import DriverProfile
from apps.notifications import services as notifications
from apps.notifications import tasks as notification_tasks
from apps.quality.models import (
    LEVEL_ORDER,
    PauseReason,
    QualityLevel,
    QualityPause,
    QualityRole,
    QualityStats,
)
from apps.realtime.manager import publish
from apps.rides.models import (
    CancelReason,
    CancelSide,
    OfferStatus,
    Ride,
    RideCancellation,
    RideOffer,
    RideStatus,
)
from apps.rides.state import utcnow
from apps.users.models import User
from kuulis.core.calendar import CARACAS_TZ
from kuulis.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from kuulis.core.pagination import PageParams

logger = logging.getLogger(__name__)

PAUSED_EVENT = "quality.paused"
ANSWERED = (OfferStatus.ACCEPTED, OfferStatus.DECLINED, OfferStatus.EXPIRED)
# Drivers at low priority (or under review) are offered rides as if this much farther away.
LOW_PRIORITY_PENALTY = 0.5
WEEKS = 8


class TemporarilyPausedError(PermissionDeniedError):
    code = "temporarily_paused"
    message = "Paused for a moment: try again later"


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    message = "User not found"


class PauseNotFoundError(NotFoundError):
    code = "pause_not_found"
    message = "Pause not found"


class PauseNotActiveError(ConflictError):
    code = "pause_not_active"
    message = "This pause is already over"


# --- Pauses ------------------------------------------------------------------------------------


def _active(now: datetime):
    return and_(QualityPause.until > now, QualityPause.lifted_at.is_(None))


async def active_pause(
    session: AsyncSession, user_id: uuid.UUID, role: QualityRole
) -> QualityPause | None:
    return await session.scalar(
        select(QualityPause)
        .where(QualityPause.user_id == user_id, QualityPause.role == role, _active(utcnow()))
        .order_by(QualityPause.until.desc())
        .limit(1)
    )


async def ensure_not_paused(session: AsyncSession, user_id: uuid.UUID, role: QualityRole) -> None:
    pause = await active_pause(session, user_id, role)
    if pause is not None:
        raise TemporarilyPausedError(
            details={"until": pause.until.isoformat(), "reason": pause.reason.value}
        )


async def paused_user_ids(
    session: AsyncSession, user_ids: Sequence[uuid.UUID], role: QualityRole
) -> set[uuid.UUID]:
    if not user_ids:
        return set()
    rows = await session.scalars(
        select(QualityPause.user_id).where(
            QualityPause.user_id.in_(user_ids), QualityPause.role == role, _active(utcnow())
        )
    )
    return set(rows)


async def active_pauses(
    session: AsyncSession, user_ids: Sequence[uuid.UUID], role: QualityRole
) -> list[QualityPause]:
    if not user_ids:
        return []
    rows = await session.scalars(
        select(QualityPause).where(
            QualityPause.user_id.in_(user_ids), QualityPause.role == role, _active(utcnow())
        )
    )
    return list(rows)


async def _last_pause_end(
    session: AsyncSession, user_id: uuid.UUID, role: QualityRole
) -> datetime | None:
    """Events before the end of the last pause were already paid for with that pause."""
    return await session.scalar(
        select(
            func.max(
                func.least(
                    func.coalesce(QualityPause.lifted_at, QualityPause.until), QualityPause.until
                )
            )
        ).where(QualityPause.user_id == user_id, QualityPause.role == role)
    )


def _since(*moments: datetime | None) -> datetime:
    return max(m for m in moments if m is not None)


async def after_driver_cancel(
    session: AsyncSession, driver_id: uuid.UUID, q: QualitySettings
) -> None:
    """Several counted cancellations within an hour pause the driver."""
    if not q.driver_cancel_burst:
        return
    now = utcnow()
    since = _since(
        now - timedelta(hours=1), await _last_pause_end(session, driver_id, QualityRole.DRIVER)
    )
    count = await session.scalar(
        select(func.count()).where(
            RideCancellation.user_id == driver_id,
            RideCancellation.side == CancelSide.DRIVER,
            RideCancellation.counted.is_(True),
            RideCancellation.created_at > since,
        )
    )
    if (count or 0) >= q.driver_cancel_burst:
        await pause(session, driver_id, QualityRole.DRIVER, PauseReason.CANCEL_BURST, q)


async def after_offer_missed(
    session: AsyncSession, driver_id: uuid.UUID, q: QualitySettings
) -> None:
    """Offers declined or left to expire in a row pause the driver."""
    if not q.driver_decline_streak:
        return
    since = await _last_pause_end(session, driver_id, QualityRole.DRIVER)
    stmt = select(RideOffer.status).where(
        RideOffer.driver_id == driver_id, RideOffer.status.in_(ANSWERED)
    )
    if since is not None:
        stmt = stmt.where(RideOffer.created_at > since)
    last = list(
        await session.scalars(
            stmt.order_by(RideOffer.created_at.desc()).limit(q.driver_decline_streak)
        )
    )
    if len(last) == q.driver_decline_streak and OfferStatus.ACCEPTED not in last:
        await pause(session, driver_id, QualityRole.DRIVER, PauseReason.DECLINE_STREAK, q)


async def after_no_show(session: AsyncSession, passenger_id: uuid.UUID, q: QualitySettings) -> None:
    """Enough no-shows in the window pause the passenger."""
    if not q.passenger_no_show_pause:
        return
    now = utcnow()
    since = _since(
        now - timedelta(days=q.window_days),
        await _last_pause_end(session, passenger_id, QualityRole.PASSENGER),
    )
    count = await session.scalar(
        select(func.count()).where(
            RideCancellation.passenger_id == passenger_id,
            RideCancellation.reason_code == CancelReason.NO_SHOW,
            RideCancellation.created_at > since,
        )
    )
    if (count or 0) >= q.passenger_no_show_pause:
        await pause(session, passenger_id, QualityRole.PASSENGER, PauseReason.NO_SHOWS, q)


async def pause(
    session: AsyncSession,
    user_id: uuid.UUID,
    role: QualityRole,
    reason: PauseReason,
    q: QualitySettings,
) -> QualityPause | None:
    """Starts a pause (none if one is running) and tells the person on every channel."""
    if await active_pause(session, user_id, role) is not None:
        return None
    now = utcnow()
    length = (
        timedelta(minutes=q.driver_pause_minutes)
        if role == QualityRole.DRIVER
        else timedelta(hours=q.passenger_pause_hours)
    )
    row = QualityPause(user_id=user_id, role=role, reason=reason, until=now + length)
    session.add(row)
    await session.commit()
    logger.info("Quality pause for %s (%s, %s) until %s", user_id, role, reason, row.until)

    if role == QualityRole.DRIVER:
        await _take_offline(session, user_id)
    payload = {"role": role.value, "reason": reason.value, "until": row.until.isoformat()}
    await publish(PAUSED_EVENT, payload, user_ids=[str(user_id)])
    user = await session.get(User, user_id)
    if user is not None:
        title, body = render(f"pause_{role.value}", user.locale, until=row.until)
        await _notify(session, user, title, body, {"type": "quality", "event": "paused", **payload})
    return row


async def _take_offline(session: AsyncSession, user_id: uuid.UUID) -> None:
    from apps.rides import services as rides
    from apps.rides.state import RideActiveError

    user = await session.get(User, user_id)
    if user is None:
        return
    # On a ride: they finish it, then cannot go online until the pause ends.
    with contextlib.suppress(RideActiveError):
        await rides.go_offline(session, user)


async def lift(session: AsyncSession, admin: User, pause_id: uuid.UUID) -> QualityPause:
    row = await session.get(QualityPause, pause_id, with_for_update=True)
    if row is None:
        raise PauseNotFoundError()
    now = utcnow()
    if row.lifted_at is not None or row.until <= now:
        raise PauseNotActiveError()
    row.lifted_at = now
    row.lifted_by_id = admin.id
    await session.commit()
    await publish(
        PAUSED_EVENT,
        {"role": row.role.value, "reason": row.reason.value, "until": None},
        user_ids=[str(row.user_id)],
    )
    return row


async def pauses_for(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 50
) -> list[QualityPause]:
    rows = await session.scalars(
        select(QualityPause)
        .where(QualityPause.user_id == user_id)
        .order_by(QualityPause.created_at.desc())
        .limit(limit)
    )
    return list(rows)


# --- Messages ----------------------------------------------------------------------------------

TEXTS: dict[str, dict[str, tuple[str, str]]] = {
    "pause_driver": {
        "es": (
            "Te desconectamos un momento",
            "Para no hacer esperar a los pasajeros, podrás conectarte de nuevo a las {time}.",
        ),
        "en": (
            "We took you offline for a moment",
            "So passengers don't wait, you can go online again at {time}.",
        ),
    },
    "pause_passenger": {
        "es": (
            "Tu cuenta está en pausa",
            "No te presentaste a varios viajes. Podrás pedir de nuevo el {day} a las {time}.",
        ),
        "en": (
            "Your account is paused",
            "You missed several rides. You can request again on {day} at {time}.",
        ),
    },
    "warn_driver": {
        "es": (
            "Cuida tu tasa de cancelación",
            "Cancelaste el {rate}% de los viajes que aceptaste en los últimos {days} días. "
            "Si sigue subiendo, recibirás menos viajes.",
        ),
        "en": (
            "Watch your cancellation rate",
            "You cancelled {rate}% of the rides you accepted in the last {days} days. "
            "If it keeps going up, you will get fewer rides.",
        ),
    },
    "low_priority_driver": {
        "es": (
            "Recibirás menos viajes por ahora",
            "Tu tasa de cancelación ({rate}%) es alta: los viajes se ofrecen primero a otros "
            "motorizados hasta que baje.",
        ),
        "en": (
            "You will get fewer rides for now",
            "Your cancellation rate ({rate}%) is high: rides go to other drivers first until it "
            "comes down.",
        ),
    },
    "warn_passenger": {
        "es": (
            "No te presentaste a {n} viajes",
            "Si vuelve a pasar, pausaremos tu cuenta por {hours} horas.",
        ),
        "en": (
            "You missed {n} rides",
            "If it happens again, we will pause your account for {hours} hours.",
        ),
    },
}


def render(
    key: str, locale: str, *, until: datetime | None = None, **values: object
) -> tuple[str, str]:
    locale = locale if locale in ("es", "en") else "es"
    if until is not None:
        local = until.astimezone(CARACAS_TZ)
        values |= {"time": local.strftime("%I:%M %p").lstrip("0"), "day": local.strftime("%d/%m")}
    title, body = TEXTS[key][locale]
    return title.format(**values), body.format(**values)


async def _notify(session: AsyncSession, user: User, title: str, body: str, data: dict) -> None:
    await notifications.create_notifications(session, [user.id], title, body, data)
    await session.commit()
    await notification_tasks.send_push.kiq([str(user.id)], title, body, data)


# --- Rates -------------------------------------------------------------------------------------


@dataclass
class Values:
    offers: int = 0
    accepted: int = 0
    rides: int = 0
    cancels: int = 0
    no_shows: int = 0
    completed: int = 0
    rating_avg: float | None = None
    rating_count: int = 0
    acceptance_rate: float | None = None
    cancel_rate: float | None = None
    level: QualityLevel = QualityLevel.OK
    reasons: list[str] = field(default_factory=list)


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _filter(column, ids: Sequence[uuid.UUID] | None):
    return column.in_(ids) if ids is not None else True


async def _counts(session: AsyncSession, stmt: Select) -> dict[uuid.UUID, tuple]:
    return {row[0]: tuple(row[1:]) for row in await session.execute(stmt)}


async def compute(
    session: AsyncSession,
    role: QualityRole,
    q: QualitySettings,
    user_ids: Sequence[uuid.UUID] | None = None,
    now: datetime | None = None,
) -> dict[uuid.UUID, Values]:
    """Rates for ``user_ids`` (everyone active in the window when None)."""
    now = now or utcnow()
    start = now - timedelta(days=q.window_days)
    if role == QualityRole.DRIVER:
        found = await _driver_counts(session, start, user_ids)
    else:
        found = await _passenger_counts(session, start, user_ids)
    ids = set(found) | set(user_ids or ())
    ratings = await _ratings(session, role, ids)
    result: dict[uuid.UUID, Values] = {}
    for uid in ids:
        v = found.get(uid, Values())
        v.rating_avg, v.rating_count = ratings.get(uid, (None, 0))
        if role == QualityRole.DRIVER:
            v.acceptance_rate = _rate(v.accepted, v.offers)
            v.cancel_rate = _rate(v.cancels, v.accepted)
        else:
            v.cancel_rate = _rate(v.cancels, v.rides)
        v.level, v.reasons = level_for(role, v, q)
        result[uid] = v
    return result


async def _driver_counts(
    session: AsyncSession, start: datetime, ids: Sequence[uuid.UUID] | None
) -> dict[uuid.UUID, Values]:
    offers = await _counts(
        session,
        select(
            RideOffer.driver_id,
            func.count(),
            func.count().filter(RideOffer.status == OfferStatus.ACCEPTED),
        )
        .where(
            RideOffer.created_at >= start,
            RideOffer.status.in_(ANSWERED),
            _filter(RideOffer.driver_id, ids),
        )
        .group_by(RideOffer.driver_id),
    )
    cancels = await _counts(
        session,
        select(RideCancellation.user_id, func.count())
        .where(
            RideCancellation.created_at >= start,
            RideCancellation.side == CancelSide.DRIVER,
            RideCancellation.counted.is_(True),
            _filter(RideCancellation.user_id, ids),
        )
        .group_by(RideCancellation.user_id),
    )
    completed = await _counts(
        session,
        select(Ride.driver_id, func.count())
        .where(
            Ride.status == RideStatus.COMPLETED,
            Ride.completed_at >= start,
            _filter(Ride.driver_id, ids),
        )
        .group_by(Ride.driver_id),
    )
    result: dict[uuid.UUID, Values] = {}
    for uid in set(offers) | set(cancels) | set(completed):
        total, accepted = offers.get(uid, (0, 0))
        result[uid] = Values(
            offers=total,
            accepted=accepted,
            rides=accepted,
            cancels=cancels.get(uid, (0,))[0],
            completed=completed.get(uid, (0,))[0],
        )
    return result


async def _passenger_counts(
    session: AsyncSession, start: datetime, ids: Sequence[uuid.UUID] | None
) -> dict[uuid.UUID, Values]:
    rides = await _counts(
        session,
        select(
            Ride.passenger_id,
            func.count(),
            func.count().filter(Ride.status == RideStatus.COMPLETED),
        )
        .where(
            Ride.requested_at >= start,
            or_(Ride.assigned_at.is_not(None), Ride.reassign_count > 0),
            _filter(Ride.passenger_id, ids),
        )
        .group_by(Ride.passenger_id),
    )
    cancels = await _counts(
        session,
        select(RideCancellation.user_id, func.count())
        .where(
            RideCancellation.created_at >= start,
            RideCancellation.side == CancelSide.PASSENGER,
            RideCancellation.counted.is_(True),
            _filter(RideCancellation.user_id, ids),
        )
        .group_by(RideCancellation.user_id),
    )
    no_shows = await _counts(
        session,
        select(RideCancellation.passenger_id, func.count())
        .where(
            RideCancellation.created_at >= start,
            RideCancellation.reason_code == CancelReason.NO_SHOW,
            _filter(RideCancellation.passenger_id, ids),
        )
        .group_by(RideCancellation.passenger_id),
    )
    result: dict[uuid.UUID, Values] = {}
    for uid in set(rides) | set(cancels) | set(no_shows):
        total, completed = rides.get(uid, (0, 0))
        result[uid] = Values(
            rides=total,
            completed=completed,
            cancels=cancels.get(uid, (0,))[0],
            no_shows=no_shows.get(uid, (0,))[0],
        )
    return result


async def _ratings(
    session: AsyncSession, role: QualityRole, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, tuple[float | None, int]]:
    ids = list(ids)
    if not ids:
        return {}
    if role == QualityRole.DRIVER:
        stmt = select(
            DriverProfile.user_id, DriverProfile.rating_avg, DriverProfile.rating_count
        ).where(DriverProfile.user_id.in_(ids))
    else:
        stmt = select(User.id, User.rating_avg, User.rating_count).where(User.id.in_(ids))
    return {
        uid: (float(avg) if avg is not None else None, count or 0)
        for uid, avg, count in await session.execute(stmt)
    }


def level_for(role: QualityRole, v: Values, q: QualitySettings) -> tuple[QualityLevel, list[str]]:
    level, reasons = QualityLevel.OK, []

    def bump(to: QualityLevel, reason: str) -> None:
        nonlocal level
        if LEVEL_ORDER[to] > LEVEL_ORDER[level]:
            level = to
        if reason not in reasons:
            reasons.append(reason)

    if (
        v.rating_avg is not None
        and v.rating_count >= q.rating_min_count
        and v.rating_avg < q.rating_review_below
    ):
        bump(QualityLevel.REVIEW, "rating")
    if role == QualityRole.DRIVER:
        if v.cancel_rate is not None and v.accepted >= q.min_rides:
            if v.cancel_rate >= q.driver_cancel_review:
                bump(QualityLevel.REVIEW, "cancel_rate")
            elif v.cancel_rate >= q.driver_cancel_low_priority:
                bump(QualityLevel.LOW_PRIORITY, "cancel_rate")
            elif v.cancel_rate >= q.driver_cancel_warn:
                bump(QualityLevel.WARN, "cancel_rate")
    elif q.passenger_no_show_warn and v.no_shows >= q.passenger_no_show_warn:
        bump(QualityLevel.WARN, "no_shows")
    return level, reasons


# --- Background refresh ------------------------------------------------------------------------


async def refresh(session: AsyncSession, config: AppConfig, now: datetime | None = None) -> int:
    """Recomputes everyone active in the window (and everyone with a stored row), stores the
    rows and sends each new warning once. Returns the rows written."""
    now = now or utcnow()
    q = config.quality
    written = 0
    to_warn: list[tuple[uuid.UUID, QualityRole, QualityLevel, Values]] = []
    for role in QualityRole:
        stored = {
            row.user_id: row
            for row in await session.scalars(select(QualityStats).where(QualityStats.role == role))
        }
        values = await compute(session, role, q, now=now)
        missing = [uid for uid in stored if uid not in values]
        if missing:
            values |= await compute(session, role, q, missing, now=now)
        for uid, v in values.items():
            row = stored.get(uid)
            if row is None:
                if v.level == QualityLevel.OK and not (v.rides or v.offers):
                    continue
                row = QualityStats(user_id=uid, role=role, warned_level=QualityLevel.OK)
                session.add(row)
            _store(row, v, now)
            if LEVEL_ORDER[v.level] < LEVEL_ORDER[row.warned_level]:
                row.warned_level = v.level  # got better: a later rise warns again
            elif LEVEL_ORDER[v.level] > LEVEL_ORDER[row.warned_level]:
                row.warned_level = v.level
                to_warn.append((uid, role, v.level, v))
            written += 1
    await session.commit()
    for uid, role, level, v in to_warn:
        await _warn(session, uid, role, level, v, q)
    return written


def _store(row: QualityStats, v: Values, now: datetime) -> None:
    for name in (
        "offers",
        "accepted",
        "rides",
        "cancels",
        "no_shows",
        "completed",
        "acceptance_rate",
        "cancel_rate",
        "rating_avg",
        "rating_count",
        "level",
        "reasons",
    ):
        setattr(row, name, getattr(v, name))
    row.computed_at = now


async def _warn(
    session: AsyncSession,
    user_id: uuid.UUID,
    role: QualityRole,
    level: QualityLevel,
    v: Values,
    q: QualitySettings,
) -> None:
    """Only the levels the person can act on get a message; review is for the team."""
    if role == QualityRole.DRIVER and level in (QualityLevel.WARN, QualityLevel.LOW_PRIORITY):
        key = "warn_driver" if level == QualityLevel.WARN else "low_priority_driver"
        values = {"rate": round((v.cancel_rate or 0) * 100), "days": q.window_days}
    elif role == QualityRole.PASSENGER and level == QualityLevel.WARN and "no_shows" in v.reasons:
        key, values = "warn_passenger", {"n": v.no_shows, "hours": q.passenger_pause_hours}
    else:
        return
    user = await session.get(User, user_id)
    if user is None:
        return
    title, body = render(key, user.locale, **values)
    await _notify(
        session, user, title, body, {"type": "quality", "event": level.value, "role": role.value}
    )


# --- Dispatch ----------------------------------------------------------------------------------


async def dispatch_factors(
    session: AsyncSession, driver_ids: Sequence[uuid.UUID], q: QualitySettings
) -> dict[uuid.UUID, float]:
    """Multiplier on each driver's distance to the pickup (1 = no change). New drivers without
    enough data are not pushed back."""
    if not driver_ids or not q.dispatch_quality_weight:
        rows = []
    else:
        rows = list(
            await session.scalars(
                select(QualityStats).where(
                    QualityStats.role == QualityRole.DRIVER, QualityStats.user_id.in_(driver_ids)
                )
            )
        )
    factors: dict[uuid.UUID, float] = {}
    for row in rows:
        badness = 0.0
        if row.acceptance_rate is not None and row.offers >= q.min_rides:
            badness += 0.5 * (1 - row.acceptance_rate)
        if row.rating_avg is not None and row.rating_count >= q.min_rides:
            badness += 0.5 * min(max((5 - row.rating_avg) / 4, 0), 1)
        factor = 1 + q.dispatch_quality_weight * badness
        if (
            row.level in (QualityLevel.LOW_PRIORITY, QualityLevel.REVIEW)
            and "cancel_rate" in row.reasons
        ):
            factor += LOW_PRIORITY_PENALTY
        factors[row.user_id] = factor
    return factors


# --- Admin -------------------------------------------------------------------------------------


def flagged_query(
    role: QualityRole, level: QualityLevel | None = None, q: str | None = None
) -> Select:
    now = utcnow()
    paused = (
        select(QualityPause.id)
        .where(
            QualityPause.user_id == QualityStats.user_id,
            QualityPause.role == QualityStats.role,
            _active(now),
        )
        .exists()
    )
    stmt = (
        select(QualityStats, User)
        .join(User, User.id == QualityStats.user_id)
        .where(QualityStats.role == role)
    )
    if level is not None:
        stmt = stmt.where(QualityStats.level == level)
    else:
        stmt = stmt.where(or_(QualityStats.level != QualityLevel.OK, paused))
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.full_name).like(term), func.lower(User.email).like(term))
        )
    severity = case({lv: -LEVEL_ORDER[lv] for lv in QualityLevel}, value=QualityStats.level)
    return stmt.order_by(severity, QualityStats.cancel_rate.desc().nulls_last(), User.full_name)


async def list_flagged(
    session: AsyncSession, params: PageParams, role: QualityRole, **filters
) -> tuple[list[tuple[QualityStats, User]], int]:
    stmt = flagged_query(role, **filters)
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = await session.execute(stmt.limit(params.limit).offset(params.offset))
    return [(stats, user) for stats, user in rows], int(total or 0)


async def weekly(
    session: AsyncSession, user_id: uuid.UUID, now: datetime | None = None
) -> list[dict]:
    """The last weeks (Caracas, Monday first) for the trend in the admin."""
    now = now or utcnow()
    local_today = now.astimezone(CARACAS_TZ).date()
    first = local_today - timedelta(days=local_today.weekday() + 7 * (WEEKS - 1))
    start = datetime.combine(first, datetime.min.time(), tzinfo=CARACAS_TZ)

    def week(column):
        return func.date(func.date_trunc("week", func.timezone(str(CARACAS_TZ), column)))

    offers = await _counts(
        session,
        select(
            week(RideOffer.created_at),
            func.count(),
            func.count().filter(RideOffer.status == OfferStatus.ACCEPTED),
        )
        .where(
            RideOffer.driver_id == user_id,
            RideOffer.created_at >= start,
            RideOffer.status.in_(ANSWERED),
        )
        .group_by(text("1")),
    )
    cancels = await _counts(
        session,
        select(
            week(RideCancellation.created_at),
            func.count().filter(RideCancellation.side == CancelSide.DRIVER),
            func.count().filter(RideCancellation.side == CancelSide.PASSENGER),
        )
        .where(
            RideCancellation.user_id == user_id,
            RideCancellation.counted.is_(True),
            RideCancellation.created_at >= start,
        )
        .group_by(text("1")),
    )
    rides = await _counts(
        session,
        select(week(Ride.requested_at), func.count())
        .where(
            Ride.passenger_id == user_id,
            Ride.requested_at >= start,
            or_(Ride.assigned_at.is_not(None), Ride.reassign_count > 0),
        )
        .group_by(text("1")),
    )
    no_shows = await _counts(
        session,
        select(week(RideCancellation.created_at), func.count())
        .where(
            RideCancellation.passenger_id == user_id,
            RideCancellation.reason_code == CancelReason.NO_SHOW,
            RideCancellation.created_at >= start,
        )
        .group_by(text("1")),
    )
    result = []
    for i in range(WEEKS):
        day: date = first + timedelta(days=7 * i)
        total, accepted = offers.get(day, (0, 0))
        driver_cancels, passenger_cancels = cancels.get(day, (0, 0))
        requested = rides.get(day, (0,))[0]
        result.append(
            {
                "week": day,
                "offers": total,
                "accepted": accepted,
                "acceptance_rate": _rate(accepted, total),
                "driver_cancels": driver_cancels,
                "driver_cancel_rate": _rate(driver_cancels, accepted),
                "passenger_rides": requested,
                "passenger_cancels": passenger_cancels,
                "passenger_cancel_rate": _rate(passenger_cancels, requested),
                "no_shows": no_shows.get(day, (0,))[0],
            }
        )
    return result


async def cancellations_by_reason(
    session: AsyncSession, start: datetime, end: datetime
) -> list[tuple[CancelSide, CancelReason | None, int, int, int]]:
    rows = await session.execute(
        select(
            RideCancellation.side,
            RideCancellation.reason_code,
            func.count(),
            func.count().filter(RideCancellation.counted.is_(True)),
            func.count().filter(RideCancellation.reassigned.is_(True)),
        )
        .where(RideCancellation.created_at >= start, RideCancellation.created_at < end)
        .group_by(RideCancellation.side, RideCancellation.reason_code)
        .order_by(RideCancellation.side, func.count().desc())
    )
    return [tuple(r) for r in rows]
