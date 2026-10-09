import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from apps.moderation import services
from apps.moderation.models import (
    Report,
    ReportCategory,
    ReporterRole,
    ReportPriority,
    ReportStatus,
)
from apps.moderation.schemas import (
    NoteCreate,
    PersonSummary,
    ReportAdminDetail,
    ReportAdminRead,
    ReportCounts,
    ReportCreate,
    ReportNoteRead,
    ReportRead,
    ReportResolve,
    ReportsAgainst,
    ReportsPage,
    ReportUpdate,
    SuspendRequest,
    SuspensionHistoryRead,
    SuspensionRead,
)
from apps.rides import events
from apps.rides.models import Ride
from apps.rides.schemas import RideAdminRead
from apps.users.dependencies import CurrentUser, DBSession, StaffUser
from apps.users.models import User
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/reports", tags=["reports"])
admin_router = APIRouter(prefix="/admin", tags=["reports"])

Params = Annotated[PageParams, Depends(page_params)]


# --- Users -------------------------------------------------------------------------------------


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def create(data: ReportCreate, user: CurrentUser, session: DBSession) -> ReportRead:
    report = await services.create_report(
        session, user, data.category, data.description, data.ride_id
    )
    await session.commit()
    await session.refresh(report)
    return ReportRead.model_validate(report)


@router.get("/me", response_model=Page[ReportRead])
async def mine(user: CurrentUser, session: DBSession, params: Params) -> Page[ReportRead]:
    rows, total = await services.my_reports(session, user.id, params)
    return Page(
        items=[ReportRead.model_validate(r) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/me/{report_id}", response_model=ReportRead)
async def my_report(report_id: uuid.UUID, user: CurrentUser, session: DBSession) -> ReportRead:
    return ReportRead.model_validate(await services.my_report(session, user.id, report_id))


# --- Admin: reports ----------------------------------------------------------------------------


async def _admin_reads(session: DBSession, reports: list[Report]) -> list[ReportAdminRead]:
    users = await services.users_by_id(
        session,
        [r.reporter_id for r in reports]
        + [r.reported_user_id for r in reports]
        + [r.assigned_to_id for r in reports],
    )
    notes = await services.notes_counts(session, [r.id for r in reports])
    return [
        ReportAdminRead(
            **ReportRead.model_validate(r).model_dump(),
            reporter=services.brief(users.get(r.reporter_id)),
            reported=services.brief(users.get(r.reported_user_id)),
            assigned_to=services.brief(users.get(r.assigned_to_id)),
            notes_count=notes.get(r.id, 0),
        )
        for r in reports
    ]


@admin_router.get("/reports", response_model=ReportsPage)
async def admin_reports(
    _: StaffUser,
    session: DBSession,
    params: Params,
    status: ReportStatus | None = None,
    category: ReportCategory | None = None,
    priority: ReportPriority | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    user_id: uuid.UUID | None = None,
    ride_id: uuid.UUID | None = None,
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
    )
    return ReportsPage(
        items=await _admin_reads(session, rows),
        total=total,
        limit=params.limit,
        offset=params.offset,
        counts=ReportCounts(**await services.counts(session)),
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
    users = await services.users_by_id(
        session, [n.author_id for n in notes] + [report.reporter_id, report.reported_user_id]
    )
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
        reported_summary=await _summary(
            session,
            users.get(report.reported_user_id),
            _other(report.reporter_role),
            suspensions,
        ),
        reporter_summary=await _summary(  # type: ignore[arg-type]
            session, users.get(report.reporter_id), report.reporter_role, suspensions
        ),
    )


@admin_router.get("/reports/{report_id}", response_model=ReportAdminDetail)
async def admin_report(report_id: uuid.UUID, _: StaffUser, session: DBSession) -> ReportAdminDetail:
    return await _detail(session, await services.get_report(session, report_id))


@admin_router.patch("/reports/{report_id}", response_model=ReportAdminDetail)
async def admin_update(
    report_id: uuid.UUID, data: ReportUpdate, admin: StaffUser, session: DBSession
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
    )
    await session.commit()
    await session.refresh(report)
    return await _detail(session, report)


@admin_router.post(
    "/reports/{report_id}/notes", response_model=ReportNoteRead, status_code=status.HTTP_201_CREATED
)
async def admin_note(
    report_id: uuid.UUID, data: NoteCreate, admin: StaffUser, session: DBSession
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


@admin_router.post("/reports/{report_id}/resolve", response_model=ReportAdminDetail)
async def admin_resolve(
    report_id: uuid.UUID, data: ReportResolve, admin: StaffUser, session: DBSession
) -> ReportAdminDetail:
    report = await services.get_report(session, report_id)
    await services.resolve(session, admin, report, data.status, data.resolution)
    await session.commit()
    await session.refresh(report)
    return await _detail(session, report)


@admin_router.post("/reports/{report_id}/reopen", response_model=ReportAdminDetail)
async def admin_reopen(
    report_id: uuid.UUID, admin: StaffUser, session: DBSession
) -> ReportAdminDetail:
    report = await services.get_report(session, report_id)
    await services.reopen(session, admin, report)
    await session.commit()
    await session.refresh(report)
    return await _detail(session, report)


# --- Admin: suspensions ------------------------------------------------------------------------


@admin_router.post("/users/{user_id}/suspend", response_model=SuspensionRead)
async def suspend(
    user_id: uuid.UUID, data: SuspendRequest, admin: StaffUser, session: DBSession
) -> SuspensionRead:
    suspension = await services.suspend(
        session, admin, user_id, data.reason, data.until, data.report_id
    )
    await session.commit()
    await session.refresh(suspension)
    return services.suspension_read(suspension, {admin.id: admin})


@admin_router.post("/users/{user_id}/unsuspend", status_code=status.HTTP_204_NO_CONTENT)
async def unsuspend(user_id: uuid.UUID, admin: StaffUser, session: DBSession) -> None:
    await services.unsuspend(session, admin, user_id)
    await session.commit()


@admin_router.get("/users/{user_id}/suspensions", response_model=list[SuspensionHistoryRead])
async def suspensions(
    user_id: uuid.UUID, _: StaffUser, session: DBSession
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
