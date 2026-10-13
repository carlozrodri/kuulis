import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from apps.audit.services import audit, note, snapshot
from apps.config.services import get_app_config
from apps.drivers import checks as driver_checks
from apps.moderation import services
from apps.moderation.models import (
    AuthorKind,
    Report,
    ReportCategory,
    ReporterRole,
    ReportMessage,
    ReportPriority,
    ReportSource,
    ReportStatus,
    WaitingOn,
)
from apps.moderation.schemas import (
    AttachmentRead,
    CsatCreate,
    HelpArticleRef,
    MessageCreate,
    NoteCreate,
    PersonSummary,
    ReportAdminDetail,
    ReportAdminRead,
    ReportCounts,
    ReportCreate,
    ReportMessageAdminRead,
    ReportMessageRead,
    ReportNoteRead,
    ReportRead,
    ReportResolve,
    ReportsAgainst,
    ReportsPage,
    ReportUpdate,
    ReportUserRead,
    StaffMessageCreate,
    SuspendRequest,
    SuspensionHistoryRead,
    SuspensionRead,
)
from apps.rides import events
from apps.rides.models import Ride
from apps.rides.schemas import RideAdminRead
from apps.staff.permissions import SHORT_SUSPENSION_DAYS
from apps.staff.services import permissions_of
from apps.support import conversation
from apps.support import services as support
from apps.support.models import HelpArticle
from apps.users.dependencies import Can, CurrentUser, DBSession
from apps.users.models import User
from kuulis.core.exceptions import ConflictError, PermissionDeniedError
from kuulis.core.pagination import Page, PageParams, page_params
from kuulis.core.rate_limit import limiter

router = APIRouter(prefix="/reports", tags=["reports"])
admin_router = APIRouter(prefix="/admin", tags=["reports"])

Params = Annotated[PageParams, Depends(page_params)]


# --- Users -------------------------------------------------------------------------------------


class ReportNotClosedForCsatError(ConflictError):
    code = "report_not_closed"
    message = "You can rate once the conversation is closed"


class CsatAlreadyGivenError(ConflictError):
    code = "csat_already_given"
    message = "You already rated this conversation"


def _user_read(report: Report, config) -> ReportUserRead:
    return ReportUserRead(
        **ReportRead.model_validate(report).model_dump(),
        unread=conversation.unread(report),
        can_reply=conversation.can_reply(report, config),
        can_rate=conversation.can_rate(report),
    )


def _message_read(message: ReportMessage, user_id: uuid.UUID | None, users: dict) -> dict:
    author = users.get(message.author_id)
    return {
        "id": message.id,
        "author_kind": message.author_kind,
        "author_name": (
            conversation.first_name(author) or "Kuulis"
            if message.author_kind == AuthorKind.STAFF
            else None
        ),
        "mine": message.author_kind == AuthorKind.USER and message.author_id == user_id,
        "body": message.body,
        "attachments": [
            AttachmentRead(**a) for a in conversation.attachment_urls(message.attachments)
        ],
        "created_at": message.created_at,
    }


@router.post("", response_model=ReportUserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def create(
    request: Request, data: ReportCreate, user: CurrentUser, session: DBSession
) -> ReportUserRead:
    if data.help_article_id and not await session.get(HelpArticle, data.help_article_id):
        raise support.HelpArticleNotFoundError()
    report = await services.create_report(
        session,
        user,
        data.category,
        data.description,
        data.ride_id,
        attachments=data.attachments,
        help_article_id=data.help_article_id,
    )
    await session.commit()
    await session.refresh(report)
    if (
        report.category == ReportCategory.VEHICLE_MISMATCH
        and report.reporter_role == ReporterRole.PASSENGER
        and report.reported_user_id is not None
    ):
        # Enough "it wasn't that moto" reports ask the driver for a selfie and new photos (doc 12).
        await driver_checks.after_mismatch_report(session, report.reported_user_id)
    return _user_read(report, await get_app_config(session))


@router.get("/me", response_model=Page[ReportUserRead])
async def mine(user: CurrentUser, session: DBSession, params: Params) -> Page[ReportUserRead]:
    rows, total = await services.my_reports(session, user.id, params)
    config = await get_app_config(session)
    return Page(
        items=[_user_read(r, config) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/me/{report_id}", response_model=ReportUserRead)
async def my_report(report_id: uuid.UUID, user: CurrentUser, session: DBSession) -> ReportUserRead:
    report = await services.my_report(session, user.id, report_id)
    return _user_read(report, await get_app_config(session))


@router.get("/me/{report_id}/messages", response_model=list[ReportMessageRead])
async def my_messages(
    report_id: uuid.UUID, user: CurrentUser, session: DBSession
) -> list[ReportMessageRead]:
    """The conversation, oldest first. Opening it marks the team's answers as read."""
    report = await services.my_report(session, user.id, report_id)
    rows = await conversation.messages(session, report.id)
    users = await services.users_by_id(session, [m.author_id for m in rows])
    report.user_seen_at = conversation.utcnow()
    await session.commit()
    return [ReportMessageRead(**_message_read(m, user.id, users)) for m in rows]


@router.post(
    "/me/{report_id}/messages",
    response_model=ReportMessageRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/hour")
async def reply(
    request: Request,
    report_id: uuid.UUID,
    data: MessageCreate,
    user: CurrentUser,
    session: DBSession,
) -> ReportMessageRead:
    report = await services.my_report(session, user.id, report_id)
    message = await conversation.user_reply(
        session, user, report, await get_app_config(session), data.body, data.attachments
    )
    await session.commit()
    await session.refresh(message)
    return ReportMessageRead(**_message_read(message, user.id, {user.id: user}))


@router.post("/me/{report_id}/csat", response_model=ReportUserRead)
async def rate(
    report_id: uuid.UUID, data: CsatCreate, user: CurrentUser, session: DBSession
) -> ReportUserRead:
    report = await services.my_report(session, user.id, report_id)
    if report.status != ReportStatus.RESOLVED:
        raise ReportNotClosedForCsatError()
    if report.csat is not None:
        raise CsatAlreadyGivenError()
    report.csat = data.score
    report.csat_comment = data.comment or None
    report.csat_at = conversation.utcnow()
    await session.commit()
    await session.refresh(report)
    return _user_read(report, await get_app_config(session))


# --- Admin: reports ----------------------------------------------------------------------------


async def _admin_reads(session: DBSession, reports: list[Report]) -> list[ReportAdminRead]:
    users = await services.users_by_id(
        session,
        [r.reporter_id for r in reports]
        + [r.reported_user_id for r in reports]
        + [r.assigned_to_id for r in reports],
    )
    ids = [r.id for r in reports]
    notes = await services.notes_counts(session, ids)
    messages = await conversation.messages_counts(session, ids)
    now = conversation.utcnow()
    return [
        ReportAdminRead(
            **ReportRead.model_validate(r).model_dump(),
            reporter=services.brief(users.get(r.reporter_id)),
            reported=services.brief(users.get(r.reported_user_id)),
            assigned_to=services.brief(users.get(r.assigned_to_id)),
            notes_count=notes.get(r.id, 0),
            waiting_since=r.waiting_since,
            first_response_at=r.first_response_at,
            sla_due_at=r.sla_due_at,
            overdue=conversation.is_overdue(r, now),
            tags=list(r.tags or []),
            csat_comment=r.csat_comment,
            contact_email=r.contact_email,
            contact_name=r.contact_name,
            messages_count=messages.get(r.id, 0),
        )
        for r in reports
    ]


@admin_router.get("/reports", response_model=ReportsPage)
async def admin_reports(
    admin: Can("reports.manage"),
    session: DBSession,
    params: Params,
    status: ReportStatus | None = None,
    category: ReportCategory | None = None,
    priority: ReportPriority | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    user_id: uuid.UUID | None = None,
    ride_id: uuid.UUID | None = None,
    waiting_on: WaitingOn | None = None,
    mine: bool = False,
    unassigned: bool = False,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    overdue: bool = False,
    source: ReportSource | None = None,
) -> ReportsPage:
    rows, total = await services.list_reports(
        session,
        params,
        status=status,
        category=category,
        priority=priority,
        q=q,
        user_id=user_id,
        ride_id=ride_id,
        waiting_on=waiting_on,
        assigned_to_id=admin.id if mine else None,
        unassigned=unassigned,
        tag=tag,
        overdue=overdue,
        source=source,
    )
    return ReportsPage(
        items=await _admin_reads(session, rows),
        total=total,
        limit=params.limit,
        offset=params.offset,
        counts=ReportCounts(**await services.counts(session, admin.id)),
    )


async def _summary(
    session: DBSession,
    user: User | None,
    role: ReporterRole | None,
    suspensions: dict[uuid.UUID, SuspensionRead],
) -> PersonSummary | None:
    if user is None:
        return None
    numbers = await services.person_numbers(session, user.id)
    profile = numbers["profile"]
    driver_side = role == ReporterRole.DRIVER
    rating_avg = profile.rating_avg if driver_side and profile else user.rating_avg
    rating_count = profile.rating_count if driver_side and profile else user.rating_count
    return PersonSummary(
        user_id=user.id,
        name=user.full_name or "",
        email=user.email,
        phone=profile.phone if profile else None,
        role_in_ride=role,
        rating_avg=float(rating_avg) if rating_avg is not None else None,
        rating_count=rating_count or 0,
        rides_completed=numbers["rides_completed"],
        reports_against=ReportsAgainst(**numbers["reports_against"]),
        suspension=suspensions.get(user.id),
        driver_profile_id=profile.id if profile else None,
        driver_status=profile.status if profile else None,
    )


def _other(role: ReporterRole | None) -> ReporterRole | None:
    if role is None:
        return None
    return ReporterRole.DRIVER if role == ReporterRole.PASSENGER else ReporterRole.PASSENGER


async def _detail(session: DBSession, report: Report) -> ReportAdminDetail:
    base = (await _admin_reads(session, [report]))[0]
    ride = await session.get(Ride, report.ride_id) if report.ride_id else None
    ride_read = None
    if ride is not None:
        ride_read = (await events.serialize_rides(session, [ride], admin=True))[0]
    notes = await services.notes(session, report.id)
    messages = await conversation.messages(session, report.id)
    users = await services.users_by_id(
        session,
        [n.author_id for n in notes]
        + [m.author_id for m in messages]
        + [report.reporter_id, report.reported_user_id],
    )
    article = (
        await session.get(HelpArticle, report.help_article_id) if report.help_article_id else None
    )
    lost = await support.lost_item_for_ride(session, report.ride_id) if report.ride_id else None
    suspensions = await services.suspension_reads(
        session, [u for u in (report.reporter_id, report.reported_user_id) if u]
    )
    return ReportAdminDetail(
        **base.model_dump(),
        ride=ride_read if isinstance(ride_read, RideAdminRead) else None,
        notes=[
            ReportNoteRead(
                id=n.id,
                body=n.body,
                kind=n.kind,
                author=services.brief(users.get(n.author_id)),
                created_at=n.created_at,
            )
            for n in notes
        ],
        messages=[
            ReportMessageAdminRead(
                **_message_read(m, report.reporter_id, users),
                author=services.brief(users.get(m.author_id)),
            )
            for m in messages
        ],
        help_article=(
            HelpArticleRef(id=article.id, slug=article.slug, title=article.title)
            if article
            else None
        ),
        lost_item=(support.lost_item_read(lost) if lost and lost.report_id == report.id else None),
        reported_summary=await _summary(
            session,
            users.get(report.reported_user_id),
            _other(report.reporter_role),
            suspensions,
        ),
        reporter_summary=await _summary(
            session, users.get(report.reporter_id), report.reporter_role, suspensions
        ),
    )


@admin_router.get("/reports/{report_id}", response_model=ReportAdminDetail)
async def admin_report(
    report_id: uuid.UUID, _: Can("reports.manage"), session: DBSession
) -> ReportAdminDetail:
    return await _detail(session, await services.get_report(session, report_id))


@admin_router.patch(
    "/reports/{report_id}",
    dependencies=[audit("report.update", "report", "report_id")],
    response_model=ReportAdminDetail,
)
async def admin_update(
    report_id: uuid.UUID, data: ReportUpdate, admin: Can("reports.manage"), session: DBSession
) -> ReportAdminDetail:
    report = await services.get_report(session, report_id)
    await services.update_report(
        session,
        admin,
        report,
        status=data.status,
        priority=data.priority,
        assign="assigned_to_id" in data.model_fields_set,
        assigned_to_id=data.assigned_to_id,
        tags=data.tags,
    )
    await session.commit()
    await session.refresh(report)
    return await _detail(session, report)


@admin_router.post(
    "/reports/{report_id}/notes",
    dependencies=[audit("report.note", "report", "report_id")],
    response_model=ReportNoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_note(
    report_id: uuid.UUID, data: NoteCreate, admin: Can("reports.manage"), session: DBSession
) -> ReportNoteRead:
    report = await services.get_report(session, report_id)
    note = await services.add_note(session, admin, report, data.body)
    await session.commit()
    await session.refresh(note)
    return ReportNoteRead(
        id=note.id,
        body=note.body,
        kind=note.kind,
        author=services.brief(admin),
        created_at=note.created_at,
    )


@admin_router.post(
    "/reports/{report_id}/messages",
    dependencies=[audit("report.message", "report", "report_id")],
    response_model=ReportAdminDetail,
)
async def admin_message(
    report_id: uuid.UUID,
    data: StaffMessageCreate,
    admin: Can("reports.manage"),
    session: DBSession,
) -> ReportAdminDetail:
    """The team answers in the conversation (push to the user, or email for web tickets)."""
    report = await services.get_report(session, report_id)
    add_tags = list(data.add_tags)
    if data.canned_response_id:
        canned = await support.get_canned(session, data.canned_response_id)
        canned.uses += 1
        add_tags += canned.tags
    await conversation.staff_reply(
        session,
        admin,
        report,
        await get_app_config(session),
        data.body,
        data.attachments,
        then=data.then,
        add_tags=add_tags,
    )
    await session.commit()
    await session.refresh(report)
    return await _detail(session, report)


@admin_router.post(
    "/reports/{report_id}/resolve",
    dependencies=[audit("report.resolve", "report", "report_id")],
    response_model=ReportAdminDetail,
)
async def admin_resolve(
    report_id: uuid.UUID, data: ReportResolve, admin: Can("reports.manage"), session: DBSession
) -> ReportAdminDetail:
    report = await services.get_report(session, report_id)
    await services.resolve(session, admin, report, data.status, data.resolution)
    await session.commit()
    await session.refresh(report)
    return await _detail(session, report)


@admin_router.post(
    "/reports/{report_id}/reopen",
    dependencies=[audit("report.reopen", "report", "report_id")],
    response_model=ReportAdminDetail,
)
async def admin_reopen(
    report_id: uuid.UUID, admin: Can("reports.manage"), session: DBSession
) -> ReportAdminDetail:
    report = await services.get_report(session, report_id)
    await services.reopen(session, admin, report)
    await session.commit()
    await session.refresh(report)
    return await _detail(session, report)


# --- Admin: suspensions ------------------------------------------------------------------------


@admin_router.post(
    "/users/{user_id}/suspend",
    dependencies=[audit("user.suspend", "user", "user_id")],
    response_model=SuspensionRead,
)
async def suspend(
    user_id: uuid.UUID, data: SuspendRequest, admin: Can("users.suspend"), session: DBSession
) -> SuspensionRead:
    limit = datetime.now(UTC) + timedelta(days=SHORT_SUSPENSION_DAYS, minutes=5)
    until = data.until
    if until is not None and until.tzinfo is None:
        until = until.replace(tzinfo=UTC)  # as services.suspend reads it
    if (until is None or until > limit) and "users.suspend_long" not in (
        await permissions_of(session, admin)
    ):
        raise PermissionDeniedError(
            f"Your role can suspend for up to {SHORT_SUSPENSION_DAYS} days",
            details={"permission": "users.suspend_long", "max_days": SHORT_SUSPENSION_DAYS},
        )
    suspension = await services.suspend(
        session, admin, user_id, data.reason, data.until, data.report_id
    )
    await session.commit()
    await session.refresh(suspension)
    note(after=snapshot(suspension, ("id", "until", "report_id")))
    return services.suspension_read(suspension, {admin.id: admin})


@admin_router.post(
    "/users/{user_id}/unsuspend",
    dependencies=[audit("user.unsuspend", "user", "user_id")],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unsuspend(user_id: uuid.UUID, admin: Can("users.suspend"), session: DBSession) -> None:
    await services.unsuspend(session, admin, user_id)
    await session.commit()


@admin_router.get("/users/{user_id}/suspensions", response_model=list[SuspensionHistoryRead])
async def suspensions(
    user_id: uuid.UUID, _: Can("users.view"), session: DBSession
) -> list[SuspensionHistoryRead]:
    rows = await services.suspension_history(session, user_id)
    users = await services.users_by_id(
        session, [r.created_by_id for r in rows] + [r.lifted_by_id for r in rows]
    )
    return [
        SuspensionHistoryRead(
            **services.suspension_read(r, users).model_dump(),
            lifted_at=r.lifted_at,
            lifted_by=services.brief(users.get(r.lifted_by_id)),
            report_id=r.report_id,
        )
        for r in rows
    ]
