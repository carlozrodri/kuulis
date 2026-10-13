"""Marketing campaigns (doc 14): who they reach, and sending them in batches.

Sending freezes the audience into ``campaign_recipients`` (one INSERT ... SELECT), then the
worker loop sends pending recipients in batches. A recipient who turned marketing off, or
already got a marketing message in the last 24 h, is skipped; one in their quiet hours waits.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    ARRAY,
    Integer,
    Select,
    and_,
    case,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig
from apps.drivers.models import DriverProfile, DriverStatus
from apps.notifications import delivery, services
from apps.notifications.models import (
    Campaign,
    CampaignRecipient,
    CampaignStatus,
    Category,
    Device,
    NotificationPreference,
    RecipientStatus,
)
from apps.notifications.schemas import AudienceCount, CampaignStats, Segment
from apps.rides.models import Ride, RideStatus
from apps.subscriptions.models import Charge, ChargeStatus
from apps.users.models import Role, User
from kuulis.core.email import is_undeliverable
from kuulis.core.exceptions import ConflictError, NotFoundError

logger = logging.getLogger(__name__)

BATCH = 500
CITY_RIDES_DAYS = 90
EDITABLE = frozenset({CampaignStatus.DRAFT, CampaignStatus.SCHEDULED})


class CampaignNotEditable(ConflictError):
    code = "campaign_not_editable"
    message = "The campaign is already sending or sent"


def _now() -> datetime:
    return datetime.now(UTC)


def _is_driver():
    return exists().where(
        DriverProfile.user_id == User.id, DriverProfile.status == DriverStatus.APPROVED
    )


def _version_array(column: Any) -> Any:
    digits = func.regexp_replace(column, r"[^0-9.]", "", "g")
    return func.string_to_array(digits, ".").cast(ARRAY(Integer))


def audience(segment: Segment, config: AppConfig, now: datetime | None = None) -> Select:
    """SELECT of the user ids in ``segment`` (real, active, non-staff accounts)."""
    now = now or _now()
    stmt = select(User.id).where(
        User.is_active,
        User.deleted_at.is_(None),
        User.role == Role.USER,
        User.is_test_account.is_(False),
    )
    if segment.audience == "drivers":
        stmt = stmt.where(_is_driver())
    elif segment.audience == "passengers":
        stmt = stmt.where(~_is_driver())
    if segment.cities:
        wanted = {c.strip().lower() for c in segment.cities}
        areas = [a for a in config.service_areas if a.name.strip().lower() in wanted]
        by_profile = exists().where(
            DriverProfile.user_id == User.id,
            func.lower(DriverProfile.city).in_(
                wanted | {a.name.split(",")[0].strip().lower() for a in areas}
            ),
        )
        boxes = [
            and_(
                Ride.pickup_lat.between(a.min_lat, a.max_lat),
                Ride.pickup_lng.between(a.min_lng, a.max_lng),
            )
            for a in areas
        ]
        conditions = [by_profile]
        if boxes:
            conditions.append(
                exists().where(
                    Ride.passenger_id == User.id,
                    Ride.created_at >= now - timedelta(days=CITY_RIDES_DAYS),
                    or_(*boxes),
                )
            )
        stmt = stmt.where(or_(*conditions))
    if segment.active_days:
        stmt = stmt.where(User.last_login_at >= now - timedelta(days=segment.active_days))
    if segment.inactive_days:
        cutoff = now - timedelta(days=segment.inactive_days)
        stmt = stmt.where(or_(User.last_login_at.is_(None), User.last_login_at < cutoff))
    if segment.fee_pending:
        stmt = stmt.where(
            exists().where(Charge.user_id == User.id, Charge.status == ChargeStatus.PENDING)
        )
    if segment.new_without_ride_days:
        stmt = stmt.where(
            User.created_at >= now - timedelta(days=segment.new_without_ride_days),
            ~exists().where(
                or_(Ride.passenger_id == User.id, Ride.driver_id == User.id),
                Ride.status == RideStatus.COMPLETED,
            ),
        )
    if segment.app_version_below:
        target = [int(p) for p in segment.app_version_below.split(".")]
        stmt = stmt.where(
            exists().where(
                Device.user_id == User.id,
                Device.is_active,
                Device.app_version.is_not(None),
                _version_array(Device.app_version) < literal(target, ARRAY(Integer)),
            )
        )
    if segment.locale:
        stmt = stmt.where(User.locale == segment.locale)
    return stmt


async def audience_count(
    session: AsyncSession, segment: Segment, config: AppConfig
) -> AudienceCount:
    ids = audience(segment, config).subquery()
    has_push = exists().where(Device.user_id == ids.c.id, Device.is_active)
    is_driver = exists().where(
        DriverProfile.user_id == ids.c.id, DriverProfile.status == DriverStatus.APPROVED
    )
    row = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(has_push),
                func.count().filter(is_driver),
            ).select_from(ids)
        )
    ).one()
    total, with_push, drivers = (int(v or 0) for v in row)
    return AudienceCount(
        total=total, with_push=with_push, drivers=drivers, passengers=total - drivers
    )


# --- CRUD ---------------------------------------------------------------------------------------


async def get(session: AsyncSession, campaign_id: uuid.UUID) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise NotFoundError("Campaign not found", code="campaign_not_found")
    return campaign


def ensure_editable(campaign: Campaign) -> None:
    if campaign.status not in EDITABLE:
        raise CampaignNotEditable()


async def schedule(campaign: Campaign, when: datetime | None) -> None:
    """Scheduled campaigns go out when ``scheduled_at`` passes (now if empty)."""
    ensure_editable_or_pending(campaign)
    campaign.scheduled_at = when or _now()
    campaign.status = CampaignStatus.SCHEDULED


def ensure_editable_or_pending(campaign: Campaign) -> None:
    if campaign.status not in EDITABLE | {CampaignStatus.PENDING_APPROVAL}:
        raise CampaignNotEditable()


def cancel(campaign: Campaign) -> None:
    """Stops a scheduled or sending campaign; recipients not reached yet are not sent."""
    if campaign.status in (CampaignStatus.SENT, CampaignStatus.CANCELLED):
        raise CampaignNotEditable()
    campaign.status = CampaignStatus.CANCELLED
    campaign.finished_at = _now()


# --- Sending ------------------------------------------------------------------------------------


def localized(campaign: Campaign, locale: str) -> tuple[str, str]:
    if locale == "en" and campaign.title_en:
        return campaign.title_en, campaign.body_en or ""
    return campaign.title_es, campaign.body_es


def push_data(campaign: Campaign, notification_id: uuid.UUID | None) -> dict[str, Any]:
    data: dict[str, Any] = {"type": "campaign", "campaign_id": str(campaign.id)}
    if notification_id:
        data["notification_id"] = str(notification_id)
    if campaign.deep_link:
        data["deep_link"] = campaign.deep_link
    return data


async def start(session: AsyncSession, campaign: Campaign, config: AppConfig) -> int:
    """Freezes the audience; returns how many users it has."""
    ids = audience(Segment.model_validate(campaign.segment), config).subquery()
    await session.execute(_insert_recipients(campaign.id, ids))
    campaign.status = CampaignStatus.SENDING
    campaign.started_at = _now()
    await refresh_stats(session, campaign)
    return campaign.stats.get("targeted", 0)


def _insert_recipients(campaign_id: uuid.UUID, ids: Any) -> Any:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    return (
        pg_insert(CampaignRecipient)
        .from_select(
            ["id", "campaign_id", "user_id"],
            select(func.gen_random_uuid(), literal(campaign_id), ids.c.id),
        )
        .on_conflict_do_nothing()
    )


async def refresh_stats(session: AsyncSession, campaign: Campaign) -> CampaignStats:
    r = CampaignRecipient
    row = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(r.status == RecipientStatus.PENDING),
                func.count().filter(r.status == RecipientStatus.SENT),
                func.count().filter(r.status == RecipientStatus.SKIPPED),
                func.count().filter(r.skip_reason == "opt_out"),
                func.count().filter(r.skip_reason == "cap"),
                func.count().filter(r.skip_reason == "no_channel"),
                func.coalesce(func.sum(r.pushed), 0),
                func.coalesce(func.sum(r.delivered), 0),
                func.count().filter(r.emailed),
                func.count().filter(r.opened_at.is_not(None)),
            ).where(r.campaign_id == campaign.id)
        )
    ).one()
    keys = list(CampaignStats.model_fields)
    stats = CampaignStats(**{k: int(v or 0) for k, v in zip(keys, row, strict=True)})
    campaign.stats = stats.model_dump()
    return stats


async def _recent_marketing(
    session: AsyncSession, campaign_id: uuid.UUID, user_ids: list[uuid.UUID], now: datetime
) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(CampaignRecipient.user_id, func.count())
        .where(
            CampaignRecipient.user_id.in_(user_ids),
            CampaignRecipient.campaign_id != campaign_id,
            CampaignRecipient.status == RecipientStatus.SENT,
            CampaignRecipient.sent_at >= now - timedelta(hours=24),
        )
        .group_by(CampaignRecipient.user_id)
    )
    return {uid: int(n) for uid, n in rows.all()}


async def send_batch(
    session: AsyncSession, campaign: Campaign, config: AppConfig, now: datetime | None = None
) -> tuple[int, list[dict[str, Any]], list[tuple[str, dict[str, str]]]]:
    """Handles up to BATCH pending recipients outside their quiet hours. Returns (handled,
    push jobs [{user_id, recipient_id, title, body, data}], emails [(user id, values)]).
    The caller commits, then queues the pushes and emails."""
    now = now or _now()
    settings = config.notifications
    rows = (
        await session.execute(
            select(CampaignRecipient, User, NotificationPreference)
            .join(User, User.id == CampaignRecipient.user_id)
            .outerjoin(NotificationPreference, NotificationPreference.user_id == User.id)
            .where(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.status == RecipientStatus.PENDING,
            )
            .order_by(CampaignRecipient.id)
            .limit(BATCH * 4)
        )
    ).all()
    awake = []
    for recipient, user, pref in rows:
        start_, end_ = (
            (pref.quiet_start if pref else None) or settings.quiet_start,
            (pref.quiet_end if pref else None) or settings.quiet_end,
        )
        if not delivery.in_quiet_hours(now, start_, end_):
            awake.append((recipient, user, pref))
        if len(awake) >= BATCH:
            break
    if not awake:
        return 0, [], []
    recent = (
        await _recent_marketing(session, campaign.id, [u.id for _, u, _ in awake], now)
        if settings.marketing_daily_cap
        else {}
    )
    pushes: list[dict[str, Any]] = []
    emails: list[tuple[str, dict[str, str]]] = []
    wants_app = bool({"push", "inbox"} & set(campaign.channels))
    for recipient, user, pref in awake:
        app_ok = wants_app and (pref.marketing_push if pref else True)
        email_ok = (
            "email" in campaign.channels
            and (pref.marketing_email if pref else True)
            and user.is_verified
            and not is_undeliverable(user.email)
        )
        if not app_ok and not email_ok:
            opted_out = (wants_app and pref is not None and not pref.marketing_push) or (
                "email" in campaign.channels and pref is not None and not pref.marketing_email
            )
            recipient.status = RecipientStatus.SKIPPED
            recipient.skip_reason = "opt_out" if opted_out else "no_channel"
            continue
        if settings.marketing_daily_cap and recent.get(user.id, 0) >= settings.marketing_daily_cap:
            recipient.status = RecipientStatus.SKIPPED
            recipient.skip_reason = "cap"
            continue
        title, body = localized(campaign, user.locale)
        if app_ok:
            data = push_data(campaign, None)
            [item] = await services.create_notifications(
                session,
                [user.id],
                title,
                body,
                data,
                category=Category.MARKETING,
                deep_link=campaign.deep_link,
            )
            item.data = push_data(campaign, item.id)
            recipient.notification_id = item.id
            if "push" in campaign.channels:
                pushes.append(
                    {
                        "user_id": str(user.id),
                        "recipient_id": str(recipient.id),
                        "title": title,
                        "body": body,
                        "data": item.data,
                    }
                )
        if email_ok:
            recipient.emailed = True
            emails.append((str(user.id), campaign_email_values(campaign, user.locale)))
        recipient.status = RecipientStatus.SENT
        recipient.sent_at = now
    await session.flush()
    return len(awake), pushes, emails


def campaign_email_values(campaign: Campaign, locale: str) -> dict[str, str]:
    from kuulis.settings import settings as app_settings

    title, body = localized(campaign, locale)
    link = campaign.deep_link or ""
    if link.startswith("/"):
        link = app_settings.FRONTEND_URL.rstrip("/")
    return {"title": title, "body": body, "link": link, "campaign_id": str(campaign.id)}


async def finish_if_done(session: AsyncSession, campaign: Campaign) -> bool:
    stats = await refresh_stats(session, campaign)
    if stats.pending == 0 and campaign.status == CampaignStatus.SENDING:
        campaign.status = CampaignStatus.SENT
        campaign.finished_at = _now()
        return True
    return False


async def due(session: AsyncSession, now: datetime | None = None) -> list[Campaign]:
    now = now or _now()
    rows = await session.scalars(
        select(Campaign)
        .where(
            or_(
                and_(Campaign.status == CampaignStatus.SCHEDULED, Campaign.scheduled_at <= now),
                Campaign.status == CampaignStatus.SENDING,
            )
        )
        .order_by(
            case((Campaign.status == CampaignStatus.SENDING, 0), else_=1), Campaign.scheduled_at
        )
    )
    return list(rows.all())


async def add_delivered(session: AsyncSession, counts: dict[str, int]) -> None:
    """Expo receipts "ok" per recipient id."""
    for recipient_id, n in counts.items():
        await session.execute(
            update(CampaignRecipient)
            .where(CampaignRecipient.id == uuid.UUID(recipient_id))
            .values(delivered=CampaignRecipient.delivered + n)
        )
