import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.notifications import delivery
from apps.notifications.models import (
    CampaignRecipient,
    Category,
    Device,
    Notification,
    NotificationPreference,
)
from apps.notifications.schemas import (
    DeviceRegister,
    NotificationRead,
    PreferencesRead,
    PreferencesUpdate,
)
from apps.realtime.manager import publish
from kuulis.core.exceptions import NotFoundError
from kuulis.core.pagination import PageParams, paginate


async def register_device(
    session: AsyncSession, user_id: uuid.UUID, data: DeviceRegister
) -> Device:
    now = datetime.now(UTC)
    device = await session.scalar(select(Device).where(Device.push_token == data.push_token))
    if device is None:
        device = Device(user_id=user_id, last_seen_at=now, **data.model_dump())
        session.add(device)
    else:
        # The same phone may now belong to a different account.
        device.user_id = user_id
        device.platform = data.platform
        device.app_version = data.app_version
        device.channels = data.channels
        device.is_active = True
        device.last_seen_at = now
    await session.flush()
    return device


async def unregister_device(session: AsyncSession, user_id: uuid.UUID, push_token: str) -> None:
    await session.execute(
        update(Device)
        .where(Device.user_id == user_id, Device.push_token == push_token)
        .values(is_active=False)
    )


async def active_push_tokens(session: AsyncSession, user_ids: Sequence[uuid.UUID]) -> list[str]:
    rows = await session.scalars(
        select(Device.push_token).where(Device.user_id.in_(user_ids), Device.is_active)
    )
    return list(rows.all())


async def active_devices(
    session: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> list[tuple[uuid.UUID, str, list[str]]]:
    """(user id, push token, Android channels) of the users' active phones."""
    rows = await session.execute(
        select(Device.user_id, Device.push_token, Device.channels).where(
            Device.user_id.in_(user_ids), Device.is_active
        )
    )
    return [(user_id, token, list(channels or [])) for user_id, token, channels in rows.all()]


async def deactivate_tokens(session: AsyncSession, tokens: Sequence[str]) -> None:
    if tokens:
        await session.execute(
            update(Device).where(Device.push_token.in_(tokens)).values(is_active=False)
        )


async def create_notifications(
    session: AsyncSession,
    user_ids: Sequence[uuid.UUID],
    title: str,
    body: str = "",
    data: dict | None = None,
    *,
    category: Category | None = None,
    deep_link: str | None = None,
) -> list[Notification]:
    """Stores inbox rows and pushes them over WebSocket. Push is sent by a background task.
    The category comes from ``data.type`` unless given."""
    category = category or delivery.category_of(data)
    items = [
        Notification(
            user_id=uid,
            title=title,
            body=body,
            data=data or {},
            category=category,
            deep_link=deep_link,
        )
        for uid in user_ids
    ]
    session.add_all(items)
    await session.flush()
    for item in items:
        await publish(
            "notification",
            NotificationRead.model_validate(item).model_dump(mode="json"),
            user_ids=[str(item.user_id)],
        )
    return items


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, params: PageParams, unread_only: bool = False
) -> tuple[list[Notification], int]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return await paginate(session, stmt, params)


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
    )
    return int(count or 0)


async def mark_read(
    session: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    item = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    if item is None:
        raise NotFoundError("Notification not found", code="notification_not_found")
    if item.read_at is None:
        item.read_at = datetime.now(UTC)
        await mark_campaign_opened(session, item)
    return item


async def mark_campaign_opened(session: AsyncSession, item: Notification) -> None:
    """A campaign notification read (in the inbox or by tapping its push) counts as opened."""
    campaign_id = (item.data or {}).get("campaign_id")
    if not campaign_id:
        return
    await session.execute(
        update(CampaignRecipient)
        .where(
            CampaignRecipient.notification_id == item.id,
            CampaignRecipient.opened_at.is_(None),
        )
        .values(opened_at=item.read_at)
    )


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> None:
    # "Read all" is not opening each campaign: only real reads count as opened.
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )


# --- Preferences (doc 14) -----------------------------------------------------------------------


async def get_preferences(session: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    """The user's row, or an unsaved one with the defaults."""
    row = await session.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return row or NotificationPreference(user_id=user_id, marketing_push=True, marketing_email=True)


async def preferences_read(session: AsyncSession, user_id: uuid.UUID) -> PreferencesRead:
    from apps.config.services import get_app_config

    settings = (await get_app_config(session)).notifications
    row = await get_preferences(session, user_id)
    return PreferencesRead(
        marketing_push=row.marketing_push,
        marketing_email=row.marketing_email,
        quiet_start=row.quiet_start or settings.quiet_start,
        quiet_end=row.quiet_end or settings.quiet_end,
        default_quiet_start=settings.quiet_start,
        default_quiet_end=settings.quiet_end,
    )


async def update_preferences(
    session: AsyncSession, user_id: uuid.UUID, data: PreferencesUpdate
) -> PreferencesRead:
    row = await get_preferences(session, user_id)
    if row not in session:
        session.add(row)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, field, value)
    await session.flush()
    return await preferences_read(session, user_id)
