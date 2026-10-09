"""Push delivery and fan-out jobs."""

import logging
import uuid

from sqlalchemy import select

from apps.notifications import services
from apps.notifications.push import send_expo_push
from apps.users.models import Role, User
from kuulis.core.db import SessionLocal
from kuulis.tasks import broker

logger = logging.getLogger(__name__)
FANOUT_BATCH = 500


@broker.task(task_name="notifications.send_push", retry_on_error=True, max_retries=3)
async def send_push(
    user_ids: list[str],
    title: str,
    body: str,
    data: dict | None = None,
    options: dict | None = None,
) -> int:
    """``options`` adds Expo message fields (e.g. ``{"priority": "high", "ttl": 15}``)."""
    async with SessionLocal() as session:
        tokens = await services.active_push_tokens(session, [uuid.UUID(u) for u in user_ids])
        messages = [
            {"to": t, "title": title, "body": body, "data": data or {}, "sound": "default"}
            | (options or {})
            for t in tokens
        ]
        tickets = await send_expo_push(messages)
        invalid = [
            messages[i]["to"]
            for i, ticket in enumerate(tickets)
            if ticket.get("status") == "error"
            and ticket.get("details", {}).get("error") == "DeviceNotRegistered"
        ]
        await services.deactivate_tokens(session, invalid)
        await session.commit()
    return len(tokens)


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
