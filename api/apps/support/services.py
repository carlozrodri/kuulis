"""Help center, saved replies, lost items, the public contact form and support metrics (doc 13)."""

import hashlib
import hmac
import re
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig
from apps.moderation.models import (
    OPEN_STATUSES,
    AuthorKind,
    Report,
    ReportCategory,
    ReportPriority,
    ReportSource,
    ReportStatus,
    WaitingOn,
)
from apps.rides.models import Ride, RideStatus
from apps.support import conversation
from apps.support.models import (
    CannedResponse,
    HelpArticle,
    HelpAudience,
    HelpTopic,
    LostItemAnswer,
    LostItemRequest,
)
from apps.support.schemas import (
    AgentMetrics,
    CannedCreate,
    CannedUpdate,
    ContactCreate,
    HelpArticleCreate,
    HelpArticleUpdate,
    LostItemRead,
    SupportDay,
    SupportMetrics,
)
from apps.users.models import User
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from kuulis.settings import settings

# --- Errors ------------------------------------------------------------------------------------


class HelpArticleNotFoundError(NotFoundError):
    code = "help_article_not_found"
    message = "Article not found"


class HelpSlugTakenError(ConflictError):
    code = "help_slug_taken"
    message = "There is already an article with this slug in this language"


class CannedNotFoundError(NotFoundError):
    code = "canned_not_found"
    message = "Saved reply not found"


class LostItemNotFoundError(NotFoundError):
    code = "lost_item_not_found"
    message = "No lost item request for this ride"


class LostItemExistsError(ConflictError):
    code = "lost_item_exists"
    message = "You already asked about a lost item on this ride"


class LostItemTooLateError(ConflictError):
    code = "lost_item_too_late"
    message = "This ride is too old to ask about a lost item"


class LostItemAnsweredError(ConflictError):
    code = "lost_item_answered"
    message = "The driver already answered"


class NotRideParticipantError(PermissionDeniedError):
    code = "not_ride_participant"
    message = "You were not part of this ride"


class RideNotCompletedError(ConflictError):
    code = "ride_not_completed"
    message = "The ride is not completed"


class RideWithoutDriverError(ConflictError):
    code = "ride_without_driver"
    message = "This ride never had a driver"


class CaptchaInvalidError(AppError):
    code = "captcha_invalid"
    message = "The verification failed, please try again"


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Help center -------------------------------------------------------------------------------

_MARKDOWN = re.compile(r"!?\[([^\]]*)\]\([^)]*\)|[#>*_`~|]+")
_SPACES = re.compile(r"\s+")


def excerpt(body_md: str, limit: int = 180) -> str:
    plain = _SPACES.sub(" ", _MARKDOWN.sub(lambda m: m.group(1) or " ", body_md)).strip()
    return plain if len(plain) <= limit else plain[: limit - 1].rsplit(" ", 1)[0] + "…"


def summary(article: HelpArticle) -> dict:
    return {
        "id": article.id,
        "slug": article.slug,
        "locale": article.locale,
        "topic": article.topic,
        "audience": article.audience,
        "title": article.title,
        "excerpt": excerpt(article.body_md),
        "position": article.position,
        "updated_at": article.updated_at,
    }


def _search(stmt, q: str | None):
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(HelpArticle.title).like(term), func.lower(HelpArticle.body_md).like(term)
            )
        )
    return stmt


async def published_articles(
    session: AsyncSession,
    locale: str,
    topic: HelpTopic | None,
    q: str | None,
    audience: HelpAudience | None,
) -> list[HelpArticle]:
    stmt = select(HelpArticle).where(HelpArticle.locale == locale, HelpArticle.published.is_(True))
    if topic:
        stmt = stmt.where(HelpArticle.topic == topic)
    if audience and audience != HelpAudience.ALL:
        stmt = stmt.where(HelpArticle.audience.in_([HelpAudience.ALL, audience]))
    stmt = _search(stmt, q)
    return list(
        await session.scalars(
            stmt.order_by(HelpArticle.topic, HelpArticle.position, HelpArticle.title).limit(200)
        )
    )


async def published_article(session: AsyncSession, slug: str, locale: str) -> HelpArticle:
    """The article in ``locale``, else in Spanish. Counts a view."""
    rows = list(
        await session.scalars(
            select(HelpArticle).where(
                HelpArticle.slug == slug,
                HelpArticle.published.is_(True),
                HelpArticle.locale.in_([locale, "es"]),
            )
        )
    )
    article = next((a for a in rows if a.locale == locale), None) or next(iter(rows), None)
    if article is None:
        raise HelpArticleNotFoundError()
    await session.execute(
        update(HelpArticle)
        .where(HelpArticle.id == article.id)
        .values(views=HelpArticle.views + 1, updated_at=HelpArticle.updated_at)
    )
    return article


async def feedback(session: AsyncSession, article_id: uuid.UUID, helpful: bool) -> None:
    column = HelpArticle.helpful_yes if helpful else HelpArticle.helpful_no
    result = await session.execute(
        update(HelpArticle)
        .where(HelpArticle.id == article_id, HelpArticle.published.is_(True))
        .values({column.key: column + 1, "updated_at": HelpArticle.updated_at})
    )
    if not result.rowcount:  # type: ignore[attr-defined]
        raise HelpArticleNotFoundError()


async def admin_articles(
    session: AsyncSession, locale: str | None, topic: HelpTopic | None, q: str | None
) -> list[HelpArticle]:
    stmt = select(HelpArticle)
    if locale:
        stmt = stmt.where(HelpArticle.locale == locale)
    if topic:
        stmt = stmt.where(HelpArticle.topic == topic)
    stmt = _search(stmt, q)
    return list(
        await session.scalars(
            stmt.order_by(HelpArticle.topic, HelpArticle.position, HelpArticle.slug).limit(500)
        )
    )


async def get_article(session: AsyncSession, article_id: uuid.UUID) -> HelpArticle:
    article = await session.get(HelpArticle, article_id)
    if article is None:
        raise HelpArticleNotFoundError()
    return article


async def _slug_free(
    session: AsyncSession, slug: str, locale: str, exclude: uuid.UUID | None = None
) -> None:
    stmt = select(HelpArticle.id).where(HelpArticle.slug == slug, HelpArticle.locale == locale)
    if exclude:
        stmt = stmt.where(HelpArticle.id != exclude)
    if await session.scalar(stmt):
        raise HelpSlugTakenError()


async def create_article(
    session: AsyncSession, admin: User, data: HelpArticleCreate
) -> HelpArticle:
    await _slug_free(session, data.slug, data.locale)
    article = HelpArticle(**data.model_dump(), updated_by_id=admin.id)
    session.add(article)
    await session.flush()
    return article


async def update_article(
    session: AsyncSession, admin: User, article: HelpArticle, data: HelpArticleUpdate
) -> HelpArticle:
    values = data.model_dump(exclude_unset=True, exclude_none=True)
    slug, locale = values.get("slug", article.slug), values.get("locale", article.locale)
    if (slug, locale) != (article.slug, article.locale):
        await _slug_free(session, slug, locale, exclude=article.id)
    for key, value in values.items():
        setattr(article, key, value)
    article.updated_by_id = admin.id
    article.updated_at = utcnow()
    await session.flush()
    return article


# --- Saved replies -----------------------------------------------------------------------------


async def canned_list(session: AsyncSession, locale: str | None) -> list[CannedResponse]:
    stmt = select(CannedResponse)
    if locale:
        stmt = stmt.where(CannedResponse.locale == locale)
    return list(
        await session.scalars(stmt.order_by(CannedResponse.uses.desc(), CannedResponse.title))
    )


async def get_canned(session: AsyncSession, canned_id: uuid.UUID) -> CannedResponse:
    canned = await session.get(CannedResponse, canned_id)
    if canned is None:
        raise CannedNotFoundError()
    return canned


def _tags(tags: list[str]) -> list[str]:
    return sorted({t.strip().lower() for t in tags if t.strip()})


async def create_canned(session: AsyncSession, admin: User, data: CannedCreate) -> CannedResponse:
    values = data.model_dump()
    values["tags"] = _tags(values["tags"])
    canned = CannedResponse(**values, created_by_id=admin.id)
    session.add(canned)
    await session.flush()
    return canned


async def update_canned(
    session: AsyncSession, canned: CannedResponse, data: CannedUpdate
) -> CannedResponse:
    for key, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(canned, key, _tags(value) if key == "tags" else value)
    canned.updated_at = utcnow()
    await session.flush()
    return canned


async def tag_counts(session: AsyncSession) -> list[tuple[str, int]]:
    rows = await session.execute(
        text(
            "SELECT tag, count(*) FROM reports, unnest(tags) AS tag "
            "GROUP BY tag ORDER BY count(*) DESC, tag LIMIT 100"
        )
    )
    return [(r[0], r[1]) for r in rows.all()]


# --- Lost items --------------------------------------------------------------------------------

LOST_TEXTS = {
    "asked": {
        "es": ("Un pasajero olvidó algo", "Dice: «{description}». ¿Lo tienes?"),
        "en": ("A passenger left something", "They say: “{description}”. Do you have it?"),
    },
    "found": {
        "es": (
            "¡El motorizado tiene tu objeto!",
            "Escríbele por el chat del viaje para acordar la entrega.",
        ),
        "en": ("The driver has your item!", "Write to them in the ride chat to arrange it."),
    },
    "not_found": {
        "es": (
            "El motorizado no encontró tu objeto",
            "Si quieres, cuéntanos más en tu conversación con soporte.",
        ),
        "en": (
            "The driver did not find your item",
            "If you want, tell us more in your support conversation.",
        ),
    },
}
LOST_TEMPLATES = {
    "lost_item_asked": LOST_TEXTS["asked"],
    "lost_item_found": LOST_TEXTS["found"],
    "lost_item_not_found": LOST_TEXTS["not_found"],
}
LOST_SYSTEM = {
    "found": {
        "es": "El motorizado tiene tu objeto. Escríbele por el chat del viaje para acordar la "
        "entrega; queda abierto {hours} horas.",
        "en": "The driver has your item. Write to them in the ride chat to arrange the hand-over; "
        "it stays open for {hours} hours.",
    },
    "not_found": {
        "es": "El motorizado dice que no encontró el objeto. Si quieres, cuéntanos más aquí.",
        "en": "The driver says they did not find the item. If you want, tell us more here.",
    },
}


def lost_item_read(item: LostItemRequest, now: datetime | None = None) -> LostItemRead:
    now = now or utcnow()
    return LostItemRead(
        id=item.id,
        ride_id=item.ride_id,
        description=item.description,
        answer=item.answer,
        answered_at=item.answered_at,
        chat_until=item.chat_until,
        chat_open=item.chat_until is not None and item.chat_until > now,
        report_id=item.report_id,
        created_at=item.created_at,
    )


async def lost_item_for_ride(session: AsyncSession, ride_id: uuid.UUID) -> LostItemRequest | None:
    return await session.scalar(select(LostItemRequest).where(LostItemRequest.ride_id == ride_id))


async def lost_item_chat_open(session: AsyncSession, ride_id: uuid.UUID) -> bool:
    """The ride chat reopens after "Lo tengo" until ``chat_until``."""
    until = await session.scalar(
        select(LostItemRequest.chat_until).where(LostItemRequest.ride_id == ride_id)
    )
    return until is not None and until > utcnow()


async def ask_lost_item(
    session: AsyncSession, user: User, ride_id: uuid.UUID, description: str, config: AppConfig
) -> LostItemRequest:
    from apps.moderation import services as moderation
    from apps.wallet import notify

    ride = await session.get(Ride, ride_id)
    if ride is None or ride.passenger_id != user.id:
        raise NotRideParticipantError()
    if ride.status != RideStatus.COMPLETED:
        raise RideNotCompletedError(details={"status": ride.status.value})
    if ride.driver_id is None:
        raise RideWithoutDriverError()
    finished = ride.completed_at or ride.requested_at
    if finished < utcnow() - timedelta(days=config.support.lost_item_days):
        raise LostItemTooLateError(details={"days": config.support.lost_item_days})
    existing = await lost_item_for_ride(session, ride.id)
    if existing is not None:
        raise LostItemExistsError(details={"report_id": str(existing.report_id or "")})
    label = "Objeto olvidado" if user.locale != "en" else "Lost item"
    report = await moderation.create_report(
        session,
        user,
        ReportCategory.LOST_ITEM,
        f"{label}: {description}",
        ride.id,
        source=ReportSource.LOST_ITEM,
    )
    item = LostItemRequest(
        ride_id=ride.id,
        passenger_id=user.id,
        driver_id=ride.driver_id,
        report_id=report.id,
        description=description,
    )
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:  # a double tap
        raise LostItemExistsError() from exc
    await notify.send(
        session,
        ride.driver_id,
        "lost_item_asked",
        kind="lost_item",
        templates=LOST_TEMPLATES,
        data={"ride_id": str(ride.id)},
        description=description[:120],
    )
    return item


async def answer_lost_item(
    session: AsyncSession, user: User, ride_id: uuid.UUID, has_it: bool, config: AppConfig
) -> LostItemRequest:
    from apps.wallet import notify

    item = await session.scalar(
        select(LostItemRequest).where(LostItemRequest.ride_id == ride_id).with_for_update()
    )
    if item is None:
        raise LostItemNotFoundError()
    if item.driver_id != user.id:
        raise NotRideParticipantError()
    if item.answer is not None:
        raise LostItemAnsweredError()
    now = utcnow()
    item.answer = LostItemAnswer.HAS_IT if has_it else LostItemAnswer.NOT_FOUND
    item.answered_at = now
    hours = config.support.lost_item_chat_hours
    if has_it:
        item.chat_until = now + timedelta(hours=hours)
    report = await session.get(Report, item.report_id) if item.report_id else None
    if report is not None and report.status in OPEN_STATUSES:
        key = "found" if has_it else "not_found"
        body = LOST_SYSTEM[key].get(report.locale, LOST_SYSTEM[key]["es"]).format(hours=hours)
        conversation.add_message(session, report, AuthorKind.SYSTEM, body, now=now)
        if has_it:
            conversation.wait_on_user(report, now)
        else:
            conversation.wait_on_staff(report, config, now)
    await session.flush()
    await notify.send(
        session,
        item.passenger_id,
        "lost_item_found" if has_it else "lost_item_not_found",
        kind="lost_item",
        templates=LOST_TEMPLATES,
        data={"ride_id": str(item.ride_id)},
    )
    return item


# --- Public contact form -----------------------------------------------------------------------

CHALLENGE_TTL = 600
DIFFICULTY = 16  # leading zero bits: ~65k hashes on average, a second or two on a phone


def _sign(payload: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), f"contact:{payload}".encode(), hashlib.sha256
    ).hexdigest()[:32]


def new_challenge() -> tuple[str, int]:
    payload = f"{int(time.time())}.{secrets.token_hex(12)}.{DIFFICULTY}"
    return f"{payload}.{_sign(payload)}", DIFFICULTY


def leading_zero_bits(digest: bytes) -> int:
    bits = 0
    for byte in digest:
        if byte == 0:
            bits += 8
            continue
        return bits + 8 - byte.bit_length()
    return bits


def solve(challenge: str, difficulty: int) -> str:
    """For tests and scripts: the nonce a browser would find."""
    nonce = 0
    while leading_zero_bits(hashlib.sha256(f"{challenge}:{nonce}".encode()).digest()) < difficulty:
        nonce += 1
    return str(nonce)


async def check_proof(challenge: str, nonce: str) -> None:
    from kuulis.core.redis import redis_client

    try:
        stamp, rand, difficulty, signature = challenge.split(".")
        issued, bits = int(stamp), int(difficulty)
    except ValueError as exc:
        raise CaptchaInvalidError() from exc
    payload = f"{stamp}.{rand}.{difficulty}"
    if not hmac.compare_digest(signature, _sign(payload)):
        raise CaptchaInvalidError()
    if not 0 <= time.time() - issued <= CHALLENGE_TTL:
        raise CaptchaInvalidError(details={"reason": "expired"})
    digest = hashlib.sha256(f"{challenge}:{nonce}".encode()).digest()
    if leading_zero_bits(digest) < bits:
        raise CaptchaInvalidError()
    used = f"{settings.APP_ENV}:contact:pow:{rand}"
    if not await redis_client.set(used, "1", nx=True, ex=CHALLENGE_TTL * 2):
        raise CaptchaInvalidError(details={"reason": "used"})


async def public_contact(session: AsyncSession, data: ContactCreate, config: AppConfig) -> Report:
    """A ticket from the website, maybe from someone who cannot sign in. Answered by email."""
    from apps.support import tasks

    now = utcnow()
    report = Report(
        reporter_id=None,
        category=ReportCategory(data.category),
        description=data.message,
        status=ReportStatus.OPEN,
        priority=ReportPriority.NORMAL,
        source=ReportSource.WEB,
        contact_email=str(data.email).lower(),
        contact_name=data.name,
        locale=data.locale,
        tags=[],
        created_at=now,
    )
    session.add(report)
    await session.flush()
    await conversation.opened(session, report, config, author=None)
    await session.flush()
    await tasks.send_ticket_email.kiq(
        report.contact_email, report.locale, str(report.id), "received", data.message
    )
    return report


# --- Metrics -----------------------------------------------------------------------------------


def _minutes(column_a, column_b):
    return func.avg(func.extract("epoch", column_a - column_b)) / 60


async def metrics(session: AsyncSession, days: int) -> SupportMetrics:
    from apps.moderation import services as moderation

    now = utcnow()
    since = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    created = dict(
        (
            await session.execute(
                select(func.date(Report.created_at), func.count(Report.id))
                .where(Report.created_at >= since)
                .group_by(func.date(Report.created_at))
            )
        ).all()
    )
    resolved = dict(
        (
            await session.execute(
                select(func.date(Report.resolved_at), func.count(Report.id))
                .where(Report.resolved_at >= since)
                .group_by(func.date(Report.resolved_at))
            )
        ).all()
    )
    day_rows = []
    for i in range(days):
        day = (since + timedelta(days=i)).date()
        day_rows.append(
            SupportDay(
                date=day.isoformat(), created=created.get(day, 0), resolved=resolved.get(day, 0)
            )
        )
    first = await session.scalar(
        select(_minutes(Report.first_response_at, Report.created_at)).where(
            Report.created_at >= since, Report.first_response_at.is_not(None)
        )
    )
    resolution = await session.scalar(
        select(_minutes(Report.resolved_at, Report.created_at) / 60).where(
            Report.resolved_at >= since, Report.status == ReportStatus.RESOLVED
        )
    )
    csat_row = (
        await session.execute(
            select(func.avg(Report.csat), func.count(Report.csat)).where(Report.csat_at >= since)
        )
    ).one()
    agents = (
        await session.execute(
            select(
                Report.resolved_by_id,
                func.count(Report.id),
                _minutes(Report.first_response_at, Report.created_at),
                func.avg(Report.csat),
            )
            .where(Report.resolved_at >= since, Report.resolved_by_id.is_not(None))
            .group_by(Report.resolved_by_id)
            .order_by(func.count(Report.id).desc())
        )
    ).all()
    users = await moderation.users_by_id(session, [a[0] for a in agents])
    counts = await moderation.counts(session)

    def _num(value) -> float | None:
        return round(float(value), 1) if value is not None else None

    return SupportMetrics(
        days=day_rows,
        first_response_minutes_avg=_num(first),
        resolution_hours_avg=_num(resolution),
        csat_avg=_num(csat_row[0]),
        csat_count=csat_row[1] or 0,
        overdue_open=counts["overdue"],
        waiting_staff=counts["waiting_staff"],
        by_agent=[
            AgentMetrics(
                user=moderation.brief(users.get(a[0])),
                resolved=a[1],
                first_response_minutes_avg=_num(a[2]),
                csat_avg=_num(a[3]),
            )
            for a in agents
        ],
    )


# --- Worker: response times and auto-close ----------------------------------------------------


async def overdue_to_alert(session: AsyncSession, now: datetime) -> list[Report]:
    """Urgent tickets past their response time, not alerted yet (marked as alerted here)."""
    rows = list(
        await session.scalars(
            select(Report)
            .where(
                Report.status.in_(OPEN_STATUSES),
                Report.waiting_on == WaitingOn.STAFF,
                Report.priority == ReportPriority.URGENT,
                Report.sla_due_at <= now,
                Report.sla_alerted_at.is_(None),
            )
            .order_by(Report.sla_due_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
    )
    for report in rows:
        report.sla_alerted_at = now
    return rows


async def stale_waiting_on_user(
    session: AsyncSession, config: AppConfig, now: datetime
) -> list[Report]:
    limit = now - timedelta(days=config.support.auto_close_days)
    return list(
        await session.scalars(
            select(Report)
            .where(
                and_(
                    Report.status.in_(OPEN_STATUSES),
                    Report.waiting_on == WaitingOn.USER,
                    Report.waiting_since <= limit,
                )
            )
            .limit(200)
            .with_for_update(skip_locked=True)
        )
    )
