import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select

from apps.approvals import services as approvals
from apps.audit.services import audit, note
from apps.config.services import get_app_config
from apps.notifications import campaigns, emails, services, tasks
from apps.notifications.models import Campaign, CampaignStatus
from apps.notifications.schemas import (
    AudienceCount,
    CampaignCreate,
    CampaignRead,
    CampaignSchedule,
    CampaignUpdate,
    DeviceRead,
    DeviceRegister,
    EmailPreview,
    EmailTemplateInfo,
    NotificationRead,
    NotificationSend,
    PreferencesRead,
    PreferencesUpdate,
    Segment,
    UnreadCount,
)
from apps.users import services as users
from apps.users.dependencies import Can, CurrentUser, DBSession
from apps.users.models import User
from kuulis.core.exceptions import NotFoundError
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/notifications", tags=["notifications"])
admin_router = APIRouter(prefix="/admin", tags=["admin: notifications"])


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


@router.get("/preferences", response_model=PreferencesRead)
async def get_preferences(user: CurrentUser, session: DBSession) -> PreferencesRead:
    return await services.preferences_read(session, user.id)


@router.put("/preferences", response_model=PreferencesRead)
async def put_preferences(
    data: PreferencesUpdate, user: CurrentUser, session: DBSession
) -> PreferencesRead:
    return await services.update_preferences(session, user.id, data)


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


@router.post(
    "/send",
    dependencies=[audit("notification.send", "notification")],
    status_code=status.HTTP_202_ACCEPTED,
    response_model=None,
)
async def send(
    data: NotificationSend, admin: Can("notifications.send"), session: DBSession
) -> dict | JSONResponse:
    """Admin panel: send a notification to one user, a role, or everyone."""
    if data.user_id:
        target = await users.get_or_404(session, data.user_id)
        await services.create_notifications(session, [target.id], data.title, data.body, data.data)
        await session.commit()
        await tasks.send_push.kiq([str(target.id)], data.title, data.body, data.data)
        return {"queued": 1}
    if await approvals.required(session, "notification.broadcast"):
        audience = data.role.value if data.role else "todos"
        return await approvals.hold(
            session,
            admin,
            "notification.broadcast",
            entity_type="notification",
            summary=f"Notificación a {audience}: {data.title}",
            payload={
                "title": data.title,
                "body": data.body,
                "data": data.data,
                "role": data.role.value if data.role else None,
            },
        )
    await tasks.broadcast.kiq(
        data.title, data.body, data.data, data.role.value if data.role else None
    )
    return {"queued": "broadcast"}


# --- Campaigns (doc 14) -------------------------------------------------------------------------

CAMPAIGN_FIELDS = (
    "name",
    "status",
    "segment",
    "channels",
    "title_es",
    "body_es",
    "title_en",
    "body_en",
    "deep_link",
    "scheduled_at",
)


async def _campaign_read(session: DBSession, campaign: Campaign) -> CampaignRead:
    await session.flush()
    await session.refresh(campaign)  # updated_at is set by the database
    read = CampaignRead.model_validate(campaign)
    if campaign.created_by_id:
        author = await session.get(User, campaign.created_by_id)
        read.created_by_name = (author.full_name or author.email) if author else None
    return read


@admin_router.get("/campaigns", response_model=Page[CampaignRead])
async def list_campaigns(
    _: Can("notifications.send"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status_: Annotated[CampaignStatus | None, Query(alias="status")] = None,
) -> Page[CampaignRead]:
    stmt = select(Campaign).order_by(Campaign.created_at.desc())
    if status_:
        stmt = stmt.where(Campaign.status == status_)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(stmt.limit(params.limit).offset(params.offset))
    return Page[CampaignRead](
        items=[await _campaign_read(session, c) for c in rows.all()],
        total=int(total or 0),
        limit=params.limit,
        offset=params.offset,
    )


@admin_router.get("/campaigns/audience-count", response_model=AudienceCount)
async def preview_audience(
    _: Can("notifications.send"),
    session: DBSession,
    segment: Annotated[str, Query(max_length=2000, description="Segment as JSON")] = "{}",
) -> AudienceCount:
    """How many users a segment reaches right now (before saving the campaign)."""
    try:
        parsed = Segment.model_validate_json(segment)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    return await campaigns.audience_count(session, parsed, await get_app_config(session))


@admin_router.post(
    "/campaigns",
    dependencies=[audit("campaign.create", "campaign")],
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    data: CampaignCreate, admin: Can("notifications.send"), session: DBSession
) -> CampaignRead:
    campaign = Campaign(
        **data.model_dump(exclude={"segment", "scheduled_at"}),
        segment=data.segment.model_dump(),
        scheduled_at=data.scheduled_at,
        status=CampaignStatus.DRAFT,
        stats={},
        created_by_id=admin.id,
    )
    session.add(campaign)
    await session.flush()
    note(entity_id=campaign.id)
    return await _campaign_read(session, campaign)


@admin_router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: uuid.UUID, _: Can("notifications.send"), session: DBSession
) -> CampaignRead:
    campaign = await campaigns.get(session, campaign_id)
    if campaign.started_at is not None:  # deliveries and opens keep coming after it is sent
        await campaigns.refresh_stats(session, campaign)
    return await _campaign_read(session, campaign)


@admin_router.get("/campaigns/{campaign_id}/audience-count", response_model=AudienceCount)
async def campaign_audience(
    campaign_id: uuid.UUID, _: Can("notifications.send"), session: DBSession
) -> AudienceCount:
    campaign = await campaigns.get(session, campaign_id)
    segment = Segment.model_validate(campaign.segment)
    return await campaigns.audience_count(session, segment, await get_app_config(session))


@admin_router.patch(
    "/campaigns/{campaign_id}",
    dependencies=[audit("campaign.update", "campaign", "campaign_id")],
    response_model=CampaignRead,
)
async def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    _: Can("notifications.send"),
    session: DBSession,
) -> CampaignRead:
    """Only drafts and scheduled campaigns change; a change sends one waiting for approval
    back to draft (the approval was for the old text)."""
    campaign = await campaigns.get(session, campaign_id)
    campaigns.ensure_editable_or_pending(campaign)
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "segment" and value is not None:
            value = Segment.model_validate(value).model_dump()
        if field in ("name", "title_es", "channels", "segment") and value is None:
            continue
        setattr(campaign, field, value)
    if campaign.status == CampaignStatus.PENDING_APPROVAL:
        campaign.status = CampaignStatus.DRAFT
    await session.flush()
    return await _campaign_read(session, campaign)


@admin_router.delete(
    "/campaigns/{campaign_id}",
    dependencies=[audit("campaign.delete", "campaign", "campaign_id")],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_campaign(
    campaign_id: uuid.UUID, _: Can("notifications.send"), session: DBSession
) -> None:
    """Drafts only; sent campaigns stay for their results."""
    campaign = await campaigns.get(session, campaign_id)
    if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PENDING_APPROVAL):
        raise campaigns.CampaignNotEditable()
    await session.delete(campaign)


@admin_router.post(
    "/campaigns/{campaign_id}/schedule",
    dependencies=[audit("campaign.schedule", "campaign", "campaign_id")],
    response_model=None,
)
async def schedule_campaign(
    campaign_id: uuid.UUID,
    data: CampaignSchedule,
    admin: Can("notifications.send"),
    session: DBSession,
) -> CampaignRead | JSONResponse:
    """Sends now or at ``scheduled_at``; with four-eyes on for broadcasts it waits for a
    second person first."""
    campaign = await campaigns.get(session, campaign_id)
    campaigns.ensure_editable_or_pending(campaign)
    if await approvals.required(session, "campaign.send"):
        campaign.status = CampaignStatus.PENDING_APPROVAL
        count = await campaigns.audience_count(
            session, Segment.model_validate(campaign.segment), await get_app_config(session)
        )
        return await approvals.hold(
            session,
            admin,
            "campaign.send",
            entity_type="campaign",
            entity_id=campaign.id,
            summary=f"Campaña «{campaign.name}» a {count.total} usuarios: {campaign.title_es}",
            payload={
                "campaign_id": str(campaign.id),
                "scheduled_at": data.scheduled_at.isoformat() if data.scheduled_at else None,
            },
        )
    await campaigns.schedule(campaign, data.scheduled_at)
    await session.flush()
    return await _campaign_read(session, campaign)


@admin_router.post(
    "/campaigns/{campaign_id}/cancel",
    dependencies=[audit("campaign.cancel", "campaign", "campaign_id")],
    response_model=CampaignRead,
)
async def cancel_campaign(
    campaign_id: uuid.UUID, _: Can("notifications.send"), session: DBSession
) -> CampaignRead:
    campaign = await campaigns.get(session, campaign_id)
    campaigns.cancel(campaign)
    await campaigns.refresh_stats(session, campaign)
    return await _campaign_read(session, campaign)


@admin_router.post(
    "/campaigns/{campaign_id}/duplicate",
    dependencies=[audit("campaign.create", "campaign")],
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_campaign(
    campaign_id: uuid.UUID, admin: Can("notifications.send"), session: DBSession
) -> CampaignRead:
    source = await campaigns.get(session, campaign_id)
    copy = Campaign(
        name=f"{source.name} (copia)"[:120],
        segment=dict(source.segment),
        channels=list(source.channels),
        title_es=source.title_es,
        body_es=source.body_es,
        title_en=source.title_en,
        body_en=source.body_en,
        deep_link=source.deep_link,
        status=CampaignStatus.DRAFT,
        stats={},
        created_by_id=admin.id,
    )
    session.add(copy)
    await session.flush()
    note(entity_id=copy.id)
    return await _campaign_read(session, copy)


@admin_router.post(
    "/campaigns/{campaign_id}/test",
    dependencies=[audit("campaign.test", "campaign", "campaign_id")],
    response_model=dict,
)
async def test_campaign(
    campaign_id: uuid.UUID, admin: Can("notifications.send"), session: DBSession
) -> dict:
    """Sends the campaign to me only (inbox, push and email as chosen), in my language. Does
    not count in the results."""
    campaign = await campaigns.get(session, campaign_id)
    title, body = campaigns.localized(campaign, admin.locale)
    title = f"[Prueba] {title}"
    pushed = emailed = False
    if {"push", "inbox"} & set(campaign.channels):
        [item] = await services.create_notifications(
            session,
            [admin.id],
            title,
            body,
            campaigns.push_data(campaign, None) | {"test": True},
            deep_link=campaign.deep_link,
        )
        item.data = campaigns.push_data(campaign, item.id) | {"test": True}
        await session.commit()
        if "push" in campaign.channels:
            await tasks.send_push.kiq([str(admin.id)], title, body, item.data)
            pushed = True
    if "email" in campaign.channels:
        values = campaigns.campaign_email_values(campaign, admin.locale)
        values["title"] = title
        await tasks.send_user_email.kiq(str(admin.id), "campaign", values)
        emailed = True
    return {"pushed": pushed, "emailed": emailed}


# --- Email templates (doc 14) -------------------------------------------------------------------


@admin_router.get("/email-templates", response_model=list[EmailTemplateInfo])
async def email_templates(_: Can("notifications.send")) -> list[EmailTemplateInfo]:
    return [
        EmailTemplateInfo(name=name, label=t.label, description=t.description)
        for name, t in emails.TEMPLATES.items()
    ]


@admin_router.get("/email-templates/{name}", response_model=EmailPreview)
async def email_preview(
    name: str,
    _: Can("notifications.send"),
    locale: Annotated[str, Query(pattern="^(es|en)$")] = "es",
) -> EmailPreview:
    """The template with sample data, as the user would get it."""
    if name not in emails.TEMPLATES:
        raise NotFoundError("Email template not found", code="email_template_not_found")
    subject, html, text = emails.render(name, locale, emails.sample(name, locale))
    return EmailPreview(name=name, locale=locale, subject=subject, html=html, text=text)
