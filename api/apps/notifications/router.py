import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from apps.notifications import services, tasks
from apps.notifications.schemas import (
    DeviceRead,
    DeviceRegister,
    NotificationRead,
    NotificationSend,
    UnreadCount,
)
from apps.users import services as users
from apps.users.dependencies import CurrentUser, DBSession, StaffUser
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def register_device(
    data: DeviceRegister, user: CurrentUser, session: DBSession
) -> DeviceRead:
    return DeviceRead.model_validate(await services.register_device(session, user.id, data))


@router.delete("/devices/{push_token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(push_token: str, user: CurrentUser, session: DBSession) -> None:
    await services.unregister_device(session, user.id, push_token)


@router.get("", response_model=Page[NotificationRead])
async def list_notifications(
    user: CurrentUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    unread_only: bool = False,
) -> Page[NotificationRead]:
    items, total = await services.list_for_user(session, user.id, params, unread_only)
    return Page[NotificationRead](
        items=[NotificationRead.model_validate(i) for i in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(user: CurrentUser, session: DBSession) -> UnreadCount:
    return UnreadCount(unread=await services.unread_count(session, user.id))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(user: CurrentUser, session: DBSession) -> None:
    await services.mark_all_read(session, user.id)


@router.post("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: uuid.UUID, user: CurrentUser, session: DBSession
) -> NotificationRead:
    return NotificationRead.model_validate(
        await services.mark_read(session, user.id, notification_id)
    )


@router.post("/send", status_code=status.HTTP_202_ACCEPTED)
async def send(data: NotificationSend, _: StaffUser, session: DBSession) -> dict:
    """Admin panel: send a notification to one user, a role, or everyone."""
    if data.user_id:
        target = await users.get_or_404(session, data.user_id)
        await services.create_notifications(session, [target.id], data.title, data.body, data.data)
        await session.commit()
        await tasks.send_push.kiq([str(target.id)], data.title, data.body, data.data)
        return {"queued": 1}
    await tasks.broadcast.kiq(
        data.title, data.body, data.data, data.role.value if data.role else None
    )
    return {"queued": "broadcast"}
