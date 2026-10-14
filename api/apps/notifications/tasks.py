"""Push delivery, fan-out, emails and the notifications loop (doc 14).

The loop, started with each worker, sends due campaigns every 30 s (one process at a time, by a
Redis lock), reads Expo push receipts every 15 min (dead tokens are deactivated), and once a
day deletes old inbox rows, deactivates idle phones and, on the 1st, emails drivers their
monthly summary.
"""

import asyncio
import contextlib
import json
import logging
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, func, select, update
from taskiq import TaskiqEvents, TaskiqState

from apps.notifications import delivery, emails, services
from apps.notifications.push import send_expo_push
from apps.users.models import Role, User
from kuulis.core.db import SessionLocal
from kuulis.core.email import send_email
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)
FANOUT_BATCH = 500
TICK_SECONDS = 30
RECEIPTS_EVERY = 15 * 60
RECEIPTS_AFTER = 15 * 60  # Expo has receipts ready ~15 min after sending
TICKETS_TTL = 6 * 3600
RECEIPTS_BATCH = 1000
_task: asyncio.Task | None = None


def _key(*parts: str) -> str:
    return ":".join((settings.APP_ENV, "notifications", *parts))


# --- Push -----------------------------------------------------------------------------------------


async def _remember_tickets(entries: list[tuple[str, str, str | None]]) -> None:
    """(ticket id, token, campaign recipient id) kept in a per-minute Redis hash until the
    receipts job reads them."""
    if not entries:
        return
    from kuulis.core.redis import redis_client

    bucket = _key("tickets", str(int(time.time() // 60)))
    await redis_client.hset(
        bucket, mapping={t: json.dumps([token, rid]) for t, token, rid in entries}
    )
    await redis_client.expire(bucket, TICKETS_TTL)


async def deliver(
    jobs: list[dict[str, Any]], options: dict[str, Any] | None = None
) -> tuple[int, dict[str, int]]:
    """Pushes each job ``{user_id, title, body, data, recipient_id?}`` to every active phone of
    its user, on the Android channel that phone has. Returns (messages, phones per recipient)."""
    if not jobs:
        return 0, {}
    async with SessionLocal() as session:
        devices = await services.active_devices(
            session, list({uuid.UUID(j["user_id"]) for j in jobs})
        )
        by_user: dict[uuid.UUID, list[tuple[str, list[str]]]] = {}
        for user_id, token, channels in devices:
            by_user.setdefault(user_id, []).append((token, channels))
        messages: list[dict[str, Any]] = []
        owners: list[str | None] = []
        for job in jobs:
            data = job.get("data") or {}
            wanted = delivery.wanted_channel(data)
            for token, channels in by_user.get(uuid.UUID(job["user_id"]), []):
                message = {
                    "to": token,
                    "title": job["title"],
                    "body": job["body"],
                    "data": data,
                    "sound": "default",
                    "channelId": delivery.pick_channel(wanted, channels),
                } | (options or {})
                messages.append(message)
                owners.append(job.get("recipient_id"))
        tickets = await send_expo_push(messages)
        invalid: list[str] = []
        remember: list[tuple[str, str, str | None]] = []
        per_recipient: dict[str, int] = {}
        for i, ticket in enumerate(tickets):
            if ticket.get("status") == "error":
                if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                    invalid.append(messages[i]["to"])
                continue
            if ticket.get("id"):
                remember.append((ticket["id"], messages[i]["to"], owners[i]))
            if owners[i]:
                per_recipient[owners[i]] = per_recipient.get(owners[i], 0) + 1
        await services.deactivate_tokens(session, invalid)
        await session.commit()
    try:
        await _remember_tickets(remember)
    except Exception:
        logger.warning("Could not store push tickets", exc_info=True)
    return len(messages), per_recipient


@broker.task(task_name="notifications.send_push", retry_on_error=True, max_retries=3)
async def send_push(
    user_ids: list[str],
    title: str,
    body: str,
    data: dict | None = None,
    options: dict | None = None,
) -> int:
    """``options`` adds Expo message fields (e.g. ``{"priority": "high", "ttl": 15}``). The
    Android channel follows ``data.type`` (doc 14) unless ``options`` names one."""
    jobs = [{"user_id": u, "title": title, "body": body, "data": data or {}} for u in user_ids]
    sent, _ = await deliver(jobs, options)
    return sent


@broker.task(task_name="notifications.send_campaign_pushes", retry_on_error=True, max_retries=3)
async def send_campaign_pushes(jobs: list[dict[str, Any]]) -> int:
    from apps.notifications.models import CampaignRecipient

    sent, per_recipient = await deliver(jobs)
    if per_recipient:
        async with SessionLocal() as session:
            for recipient_id, phones in per_recipient.items():
                await session.execute(
                    update(CampaignRecipient)
                    .where(CampaignRecipient.id == uuid.UUID(recipient_id))
                    .values(pushed=phones)
                )
            await session.commit()
    return sent


@broker.task(task_name="notifications.broadcast")
async def broadcast(
    title: str, body: str, data: dict | None = None, role: str | None = None
) -> int:
    """Creates inbox rows and pushes for every active user (optionally one role), in batches."""
    sent = 0
    last_id: uuid.UUID | None = None
    while True:
        async with SessionLocal() as session:
            stmt = select(User.id).where(User.is_active).order_by(User.id).limit(FANOUT_BATCH)
            if role:
                stmt = stmt.where(User.role == Role(role))
            if last_id:
                stmt = stmt.where(User.id > last_id)
            ids = list((await session.scalars(stmt)).all())
            if not ids:
                break
            await services.create_notifications(session, ids, title, body, data)
            await session.commit()
        await send_push.kiq([str(i) for i in ids], title, body, data)
        sent += len(ids)
        last_id = ids[-1]
    logger.info("Broadcast '%s' sent to %s users", title, sent)
    return sent


# --- Email ----------------------------------------------------------------------------------------


def first_name(user: User) -> str:
    name = (user.full_name or "").strip()
    return name.split()[0] if name else user.email.split("@")[0]


@broker.task(task_name="notifications.send_user_email", retry_on_error=True, max_retries=3)
async def send_user_email(user_id: str, template: str, values: dict[str, str]) -> bool:
    """Template ``template`` to the user's address, in their language."""
    async with SessionLocal() as session:
        user = await session.get(User, uuid.UUID(user_id))
        if user is None or user.deleted_at is not None:
            return False
        to, locale, name = user.email, user.locale, first_name(user)
    subject, html, text = emails.render(template, locale, {"name": name} | values)
    return await send_email(to, subject, html, text)


@broker.task(task_name="notifications.send_address_email", retry_on_error=True, max_retries=3)
async def send_address_email(
    to: str, template: str, locale: str, values: dict[str, str], reply_to: str | None = None
) -> bool:
    """For addresses without an account yet (web contact form) or set before the account."""
    subject, html, text = emails.render(template, locale, values)
    return await send_email(to, subject, html, text, reply_to=reply_to)


# --- Campaigns ------------------------------------------------------------------------------------


async def run_campaigns_once(max_batches: int = 8) -> int:
    """Starts due campaigns and sends up to ``max_batches`` batches. Returns users handled."""
    from apps.config.services import get_app_config
    from apps.notifications import campaigns
    from kuulis.core.redis import redis_client

    if not await redis_client.set(_key("campaigns", "lock"), "1", nx=True, ex=TICK_SECONDS * 4):
        return 0
    handled = 0
    try:
        async with SessionLocal() as session:
            ids = [c.id for c in await campaigns.due(session)]
        for campaign_id in ids:
            for _ in range(max_batches):
                async with SessionLocal() as session:
                    config = await get_app_config(session)
                    campaign = await campaigns.get(session, campaign_id)
                    if campaign.status.value == "scheduled":
                        targeted = await campaigns.start(session, campaign, config)
                        logger.info("Campaign %s started: %s users", campaign.name, targeted)
                    n, pushes, mails = await campaigns.send_batch(session, campaign, config)
                    done = await campaigns.finish_if_done(session, campaign)
                    await session.commit()
                if pushes:
                    await send_campaign_pushes.kiq(pushes)
                for user_id, values in mails:
                    await send_user_email.kiq(user_id, "campaign", values)
                handled += n
                if done or n == 0:
                    break
    finally:
        await redis_client.delete(_key("campaigns", "lock"))
    return handled


# --- Receipts -------------------------------------------------------------------------------------


def receipts_url() -> str:
    return settings.EXPO_PUSH_URL.rsplit("/", 1)[0] + "/getReceipts"


async def run_receipts_once() -> tuple[int, int]:
    """Reads receipts of tickets older than 15 min. Returns (ok, dead tokens)."""
    from apps.notifications import campaigns
    from kuulis.core.redis import redis_client

    if not settings.PUSH_ENABLED:
        return 0, 0
    now_minute = int(time.time() // 60)
    ok = dead = 0
    async for bucket in redis_client.scan_iter(match=_key("tickets", "*"), count=200):
        minute = int(bucket.rsplit(":", 1)[1])
        if now_minute - minute < RECEIPTS_AFTER // 60:
            continue
        entries = await redis_client.hgetall(bucket)
        ids = list(entries)
        delivered: dict[str, int] = {}
        dead_tokens: list[str] = []
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if settings.EXPO_ACCESS_TOKEN:
            headers["Authorization"] = f"Bearer {settings.EXPO_ACCESS_TOKEN}"
        async with httpx.AsyncClient(timeout=15) as client:
            for start in range(0, len(ids), RECEIPTS_BATCH):
                chunk = ids[start : start + RECEIPTS_BATCH]
                response = await client.post(receipts_url(), json={"ids": chunk}, headers=headers)
                response.raise_for_status()
                receipts = response.json().get("data", {}) or {}
                for ticket_id, receipt in receipts.items():
                    token, recipient_id = json.loads(entries.get(ticket_id, "[null, null]"))
                    if receipt.get("status") == "ok":
                        ok += 1
                        if recipient_id:
                            delivered[recipient_id] = delivered.get(recipient_id, 0) + 1
                    elif receipt.get("details", {}).get("error") == "DeviceNotRegistered" and token:
                        dead_tokens.append(token)
        async with SessionLocal() as session:
            await services.deactivate_tokens(session, dead_tokens)
            await campaigns.add_delivered(session, delivered)
            await session.commit()
        dead += len(dead_tokens)
        await redis_client.delete(bucket)
    return ok, dead


# --- Daily housekeeping ---------------------------------------------------------------------------


async def cleanup(now: datetime | None = None) -> tuple[int, int]:
    """Deletes inbox rows older than the retention and deactivates idle phones."""
    from apps.config.services import get_app_config
    from apps.notifications.models import Device, Notification

    now = now or datetime.now(UTC)
    deleted = 0
    async with SessionLocal() as session:
        config = (await get_app_config(session)).notifications
        cutoff = now - timedelta(days=config.inbox_retention_days)
        idle = now - timedelta(days=config.device_idle_days)
        while True:
            ids = select(Notification.id).where(Notification.created_at < cutoff).limit(5000)
            result = await session.execute(delete(Notification).where(Notification.id.in_(ids)))
            await session.commit()
            deleted += result.rowcount or 0
            if (result.rowcount or 0) < 5000:
                break
        result = await session.execute(
            update(Device)
            .where(
                Device.is_active,
                func.coalesce(Device.last_seen_at, Device.updated_at) < idle,
            )
            .values(is_active=False)
        )
        await session.commit()
    return deleted, result.rowcount or 0


def previous_month(today: date) -> date:
    first = today.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


async def monthly_summaries(today: date) -> int:
    """Emails each driver with a charge for last month their statement (doc 17): rides,
    earnings, tier and fee, wallet movements and the closing balance."""
    from apps.config.services import get_app_config
    from apps.finance import statements
    from apps.subscriptions.models import Charge
    from apps.wallet.models import EntryKind
    from apps.wallet.notify import month_label

    month = previous_month(today)
    sent = 0
    async with SessionLocal() as session:
        if not (await get_app_config(session)).notifications.monthly_summary:
            return 0
        rows = await session.execute(
            select(Charge.user_id, User.locale)
            .join(User, User.id == Charge.user_id)
            .where(Charge.month == month, User.is_active, User.deleted_at.is_(None))
        )
        for user_id, locale in rows.all():
            st = await statements.build(session, user_id, month)
            moved = st.movements
            await send_user_email.kiq(
                str(user_id),
                "monthly_summary",
                {
                    "month": month_label(month, locale),
                    "rides": str(st.trips),
                    "earnings": f"{st.earned:.2f}",
                    "tier": f"{st.tier.above:.2f}" if st.tier else "0.00",
                    "fee": f"{st.fee:.2f}",
                    "top_ups": f"{moved[EntryKind.TOP_UP]:.2f}",
                    "promo": f"{moved[EntryKind.PROMO_CREDIT]:.2f}",
                    "transfers_in": f"{moved[EntryKind.TRANSFER_IN]:.2f}",
                    "transfers_out": f"{-moved[EntryKind.TRANSFER_OUT]:.2f}",
                    "balance": f"{st.closing_balance:.2f}",
                },
            )
            sent += 1
    return sent


async def run_monthly_once(now: datetime | None = None) -> int | None:
    """Last month's statements, once its fees were charged (the subscription job marks it)."""
    from apps.subscriptions import tasks as subscription_tasks
    from kuulis.core.calendar import CARACAS_TZ, format_month
    from kuulis.core.redis import redis_client

    now = now or datetime.now(UTC)
    today = now.astimezone(CARACAS_TZ).date()
    label = format_month(previous_month(today))
    if not await redis_client.exists(subscription_tasks._done_key(label)):
        return None
    if not await redis_client.set(_key("monthly", label), "1", nx=True, ex=60 * 86400):
        return None
    try:
        sent = await monthly_summaries(today)
    except Exception:
        await redis_client.delete(_key("monthly", label))
        raise
    logger.info("Monthly statements for %s: %s emails", label, sent)
    return sent


async def run_daily_once(now: datetime | None = None) -> dict[str, int] | None:
    from kuulis.core.calendar import CARACAS_TZ
    from kuulis.core.redis import redis_client

    now = now or datetime.now(UTC)
    today = now.astimezone(CARACAS_TZ).date()
    key = _key("daily", today.isoformat())
    if not await redis_client.set(key, "1", nx=True, ex=3 * 86400):
        return None
    try:
        deleted, idle = await cleanup(now)
    except Exception:
        await redis_client.delete(key)
        raise
    result = {"deleted": deleted, "idle_devices": idle}
    logger.info("Notifications daily: %s", result)
    return result


async def loop() -> None:
    from apps.monitoring import stats

    last_receipts = 0.0
    while True:
        try:
            await run_campaigns_once()
            if time.monotonic() - last_receipts >= RECEIPTS_EVERY:
                last_receipts = time.monotonic()
                await run_receipts_once()
            await run_daily_once()
            await run_monthly_once()
            await stats.beat("notifications")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notifications loop failed")
        await asyncio.sleep(TICK_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="notifications-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
