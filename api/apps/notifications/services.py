import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.notifications.models import Device, Notification
from apps.notifications.schemas import DeviceRegister, NotificationRead
from apps.realtime.manager import publish
from kuulis.core.exceptions import NotFoundError
from kuulis.core.pagination import PageParams, paginate


async def register_device(
    session: AsyncSession, user_id: uuid.UUID, data: DeviceRegister
) -> Device:
    device = await session.scalar(select(Device).where(Device.push_token == data.push_token))
    if device is None:
        device = Device(user_id=user_id, **data.model_dump())
        session.add(device)
    else:
        # The same phone may now belong to a different account.
        device.user_id = user_id
        device.platform = data.platform
        device.app_version = data.app_version
        device.is_active = True
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
) -> list[Notification]:
    """Stores inbox rows and pushes them over WebSocket. Push is sent by a background task."""
    items = [Notification(user_id=uid, title=title, body=body, data=data or {}) for uid in user_ids]
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
    item.read_at = item.read_at or datetime.now(UTC)
    return item


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
