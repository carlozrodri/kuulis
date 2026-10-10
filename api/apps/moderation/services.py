"""Reports from riders and drivers, and account suspensions."""

import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.drivers.models import DriverProfile
from apps.moderation.models import (
    OPEN_STATUSES,
    URGENT_CATEGORIES,
    NoteKind,
    Report,
    ReportCategory,
    ReporterRole,
    ReportNote,
    ReportPriority,
    ReportStatus,
    Suspension,
)
from apps.rides import presence
from apps.rides.models import Ride, RideStatus
from apps.users.models import Role, User
from apps.users.schemas import SuspensionRead, UserBrief, UserRead
from apps.wallet import notify
from kuulis.core import storage
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from kuulis.core.pagination import PageParams

MAX_OPEN_REPORTS = 5

TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "report_resolved": {
        "es": ("Revisamos tu reporte", "{resolution}"),
        "en": ("We reviewed your report", "{resolution}"),
    },
    "suspended": {
        "es": ("Tu cuenta está suspendida", "{reason}{until}"),
        "en": ("Your account is suspended", "{reason}{until}"),
    },
    "unsuspended": {
        "es": ("Tu cuenta está activa otra vez", "Ya puedes volver a usar Kuulis."),
        "en": ("Your account is active again", "You can use Kuulis again."),
    },
}


# --- Errors ------------------------------------------------------------------------------------


class ReportNotFoundError(NotFoundError):
    code = "report_not_found"
    message = "Report not found"


class NotRideParticipantError(PermissionDeniedError):
    code = "not_ride_participant"
    message = "You were not part of this ride"


class RideWithoutDriverError(ConflictError):
    code = "ride_without_driver"
    message = "This ride never had a driver"


class ReportAlreadyOpenError(ConflictError):
    code = "report_already_open"
    message = "You already have an open report about this ride"


class TooManyOpenReportsError(ConflictError):
    code = "too_many_open_reports"
    message = "You have too many open reports"


class ReportClosedError(ConflictError):
    code = "report_closed"
    message = "This report is already closed"


class ReportNotClosedError(ConflictError):
    code = "report_not_closed"
    message = "This report is still open"


class AssigneeInvalidError(AppError):
    code = "assignee_invalid"
    message = "Reports can only be assigned to staff"


class AccountSuspendedError(PermissionDeniedError):
    code = "account_suspended"
    message = "Your account is suspended"


class CannotSuspendStaffError(PermissionDeniedError):
    code = "cannot_suspend_staff"
    message = "Staff accounts cannot be suspended"


class NotSuspendedError(ConflictError):
    code = "not_suspended"
    message = "This account is not suspended"


class SuspensionUntilInvalidError(AppError):
    code = "suspension_until_invalid"
    message = "The end of the suspension must be in the future"


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    message = "User not found"


def utcnow() -> datetime:
    return datetime.now(UTC)


def brief(user: User | None) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, name=user.full_name or "", email=user.email)


async def users_by_id(session: AsyncSession, ids: Iterable[uuid.UUID | None]) -> dict:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    return {u.id: u for u in await session.scalars(select(User).where(User.id.in_(wanted)))}


# --- Suspensions -------------------------------------------------------------------------------


def _in_force(now: datetime):
    return (Suspension.lifted_at.is_(None)) & (
        Suspension.until.is_(None) | (Suspension.until > now)
    )


async def active_suspensions(
    session: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Suspension]:
    if not user_ids:
        return {}
    rows = await session.scalars(
        select(Suspension)
        .where(Suspension.user_id.in_(list(user_ids)), _in_force(utcnow()))
        .order_by(Suspension.created_at)
    )
    return {s.user_id: s for s in rows}  # the newest wins


async def active_suspension(session: AsyncSession, user_id: uuid.UUID) -> Suspension | None:
    return (await active_suspensions(session, [user_id])).get(user_id)


async def suspended_user_ids(session: AsyncSession, user_ids: Sequence[uuid.UUID]) -> set:
    return set(await active_suspensions(session, user_ids))


def suspended_filter(value: bool):
    """WHERE clause on ``User`` for ``?suspended=``."""
    clause = exists().where(Suspension.user_id == User.id, _in_force(utcnow()))
    return clause if value else ~clause


async def ensure_not_suspended(session: AsyncSession, user_id: uuid.UUID) -> None:
    suspension = await active_suspension(session, user_id)
    if suspension is not None:
        raise AccountSuspendedError(
            details={
                "until": suspension.until.isoformat() if suspension.until else None,
                "reason": suspension.reason,
            }
        )


def _until_label(until: datetime | None, locale: str) -> str:
    if until is None:
        return ""
    label = notify.date_label(until, locale)
    return f" Until {label}." if locale == "en" else f" Hasta el {label}."


async def suspend(
    session: AsyncSession,
    admin: User,
    user_id: uuid.UUID,
    reason: str,
    until: datetime | None,
    report_id: uuid.UUID | None,
) -> Suspension:
    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFoundError()
    if user.role in (Role.STAFF, Role.ADMIN):
        raise CannotSuspendStaffError()
    now = utcnow()
    if until is not None:
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        if until <= now:
            raise SuspensionUntilInvalidError()
    report = await get_report(session, report_id) if report_id else None
    # Replaces whatever was there (also expired ones that were never lifted).
    await session.execute(
        update(Suspension)
        .where(Suspension.user_id == user_id, Suspension.lifted_at.is_(None))
        .values(lifted_at=now, lifted_by_id=admin.id)
    )
    suspension = Suspension(
        user_id=user_id,
        reason=reason,
        until=until,
        created_by_id=admin.id,
        report_id=report.id if report else None,
    )
    session.add(suspension)
    if report is not None:
        until_text = until.isoformat() if until else "indefinida"
        _system_note(
            session, report, admin, NoteKind.SUSPENSION, f"{user.email} · {until_text} · {reason}"
        )
    await session.flush()
    await presence.go_offline(user_id)  # no more offers
    await notify.send(
        session,
        user_id,
        "suspended",
        kind="account",
        templates=TEMPLATES,
        data={"until": until.isoformat() if until else ""},
        localized=lambda locale: {"until": _until_label(until, locale)},
        reason=reason,
    )
    return suspension


async def unsuspend(session: AsyncSession, admin: User, user_id: uuid.UUID) -> None:
    suspension = await active_suspension(session, user_id)
    if suspension is None:
        raise NotSuspendedError()
    suspension.lifted_at = utcnow()
    suspension.lifted_by_id = admin.id
    await notify.send(session, user_id, "unsuspended", kind="account", templates=TEMPLATES)


async def suspension_history(session: AsyncSession, user_id: uuid.UUID) -> list[Suspension]:
    return list(
        await session.scalars(
            select(Suspension)
            .where(Suspension.user_id == user_id)
            .order_by(Suspension.created_at.desc())
        )
    )


def suspension_read(suspension: Suspension, users: dict) -> SuspensionRead:
    return SuspensionRead(
        reason=suspension.reason,
        suspended_at=suspension.created_at,
        until=suspension.until,
        by=brief(users.get(suspension.created_by_id)),
    )


async def suspension_reads(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, SuspensionRead]:
    active = await active_suspensions(session, user_ids)
    users = await users_by_id(session, (s.created_by_id for s in active.values()))
    return {uid: suspension_read(s, users) for uid, s in active.items()}


async def user_reads(
    session: AsyncSession, users: Sequence[User], *, staff_view: bool = False
) -> list[UserRead]:
    """UserRead with the suspension in force, if any. Who suspended is only shown to staff."""
    suspensions = await suspension_reads(session, [u.id for u in users])
    if not staff_view:
        suspensions = {k: v.model_copy(update={"by": None}) for k, v in suspensions.items()}
    return [
        UserRead.model_validate(u).model_copy(
            update={
                "suspension": suspensions.get(u.id),
                "avatar_url": storage.download_url_or_none(u.avatar_key),
            }
        )
        for u in users
    ]


async def user_read(session: AsyncSession, user: User, *, staff_view: bool = False) -> UserRead:
    return (await user_reads(session, [user], staff_view=staff_view))[0]


# --- Reports: users ----------------------------------------------------------------------------


async def create_report(
    session: AsyncSession,
    user: User,
    category: ReportCategory,
    description: str,
    ride_id: uuid.UUID | None,
) -> Report:
    reported_id = None
    role = None
    if ride_id is not None:
        ride = await session.get(Ride, ride_id)
        if ride is None or user.id not in (ride.passenger_id, ride.driver_id):
            raise NotRideParticipantError()
        if ride.driver_id is None:
            raise RideWithoutDriverError()
        if user.id == ride.passenger_id:
            role, reported_id = ReporterRole.PASSENGER, ride.driver_id
        else:
            role, reported_id = ReporterRole.DRIVER, ride.passenger_id
        existing = await session.scalar(
            select(Report.id).where(
                Report.ride_id == ride_id,
                Report.reporter_id == user.id,
                Report.status.in_(OPEN_STATUSES),
            )
        )
        if existing:
            raise ReportAlreadyOpenError(details={"report_id": str(existing)})
    open_count = await session.scalar(
        select(func.count(Report.id)).where(
            Report.reporter_id == user.id, Report.status.in_(OPEN_STATUSES)
        )
    )
    if (open_count or 0) >= MAX_OPEN_REPORTS:
        raise TooManyOpenReportsError(details={"max": MAX_OPEN_REPORTS})
    report = Report(
        reporter_id=user.id,
        reported_user_id=reported_id,
        ride_id=ride_id,
        reporter_role=role,
        category=category,
        description=description,
        status=ReportStatus.OPEN,
        priority=(
            ReportPriority.URGENT if category in URGENT_CATEGORIES else ReportPriority.NORMAL
        ),
    )
    session.add(report)
    try:
        await session.flush()
    except IntegrityError as exc:  # a double tap raced the check above
        raise ReportAlreadyOpenError() from exc
    return report


async def my_reports(
    session: AsyncSession, user_id: uuid.UUID, params: PageParams
) -> tuple[list[Report], int]:
    where = Report.reporter_id == user_id
    total = await session.scalar(select(func.count(Report.id)).where(where)) or 0
    rows = await session.scalars(
        select(Report)
        .where(where)
        .order_by(Report.created_at.desc())
        .limit(params.limit)
        .offset(params.offset)
    )
    return list(rows), total


async def my_report(session: AsyncSession, user_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    report = await session.get(Report, report_id)
    if report is None or report.reporter_id != user_id:
        raise ReportNotFoundError()
    return report


# --- Reports: admin ----------------------------------------------------------------------------


async def get_report(session: AsyncSession, report_id: uuid.UUID) -> Report:
    report = await session.get(Report, report_id)
    if report is None:
        raise ReportNotFoundError()
    return report


async def list_reports(
    session: AsyncSession,
    params: PageParams,
    *,
    status: ReportStatus | None = None,
    category: ReportCategory | None = None,
    priority: ReportPriority | None = None,
    q: str | None = None,
    user_id: uuid.UUID | None = None,
    ride_id: uuid.UUID | None = None,
) -> tuple[list[Report], int]:
    stmt = select(Report)
    if status:
        stmt = stmt.where(Report.status == status)
    if category:
        stmt = stmt.where(Report.category == category)
    if priority:
        stmt = stmt.where(Report.priority == priority)
    if user_id:
        stmt = stmt.where(or_(Report.reporter_id == user_id, Report.reported_user_id == user_id))
    if ride_id:
        stmt = stmt.where(Report.ride_id == ride_id)
    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        reporter, reported = aliased(User), aliased(User)
        stmt = (
            stmt.join(reporter, reporter.id == Report.reporter_id)
            .outerjoin(reported, reported.id == Report.reported_user_id)
            .where(
                or_(
                    func.lower(reporter.email).like(term),
                    func.lower(reporter.full_name).like(term),
                    func.lower(reported.email).like(term),
                    func.lower(reported.full_name).like(term),
                    func.lower(Report.description).like(term),
                )
            )
        )
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    urgent_open_first = case(
        (
            (Report.priority == ReportPriority.URGENT) & Report.status.in_(OPEN_STATUSES),
            0,
        ),
        else_=1,
    )
    rows = await session.scalars(
        stmt.order_by(urgent_open_first, Report.created_at.desc())
        .limit(params.limit)
        .offset(params.offset)
    )
    return list(rows), total


async def counts(session: AsyncSession) -> dict[str, int]:
    row = (
        await session.execute(
            select(
                func.count().filter(Report.status == ReportStatus.OPEN),
                func.count().filter(Report.status == ReportStatus.IN_REVIEW),
                func.count().filter(
                    Report.status.in_(OPEN_STATUSES), Report.priority == ReportPriority.URGENT
                ),
            )
        )
    ).one()
    return {"open": row[0], "in_review": row[1], "urgent_open": row[2]}


async def notes_counts(session: AsyncSession, report_ids: list[uuid.UUID]) -> dict:
    if not report_ids:
        return {}
    rows = await session.execute(
        select(ReportNote.report_id, func.count(ReportNote.id))
        .where(ReportNote.report_id.in_(report_ids))
        .group_by(ReportNote.report_id)
    )
    return dict(rows.tuples().all())


async def notes(session: AsyncSession, report_id: uuid.UUID) -> list[ReportNote]:
    return list(
        await session.scalars(
            select(ReportNote)
            .where(ReportNote.report_id == report_id)
            .order_by(ReportNote.created_at, ReportNote.id)
        )
    )


def _system_note(
    session: AsyncSession, report: Report, author: User | None, kind: NoteKind, body: str
) -> ReportNote:
    note = ReportNote(report_id=report.id, author_id=author.id if author else None, kind=kind)
    note.body = body
    session.add(note)
    report.updated_at = utcnow()
    return note


async def add_note(session: AsyncSession, admin: User, report: Report, body: str) -> ReportNote:
    note = _system_note(session, report, admin, NoteKind.NOTE, body)
    await session.flush()
    return note


async def update_report(
    session: AsyncSession,
    admin: User,
    report: Report,
    *,
    status: ReportStatus | None,
    priority: ReportPriority | None,
    assign: bool,
    assigned_to_id: uuid.UUID | None,
) -> Report:
    changes = []
    if status is not None and status != report.status:
        if report.status not in OPEN_STATUSES:
            raise ReportClosedError()
        changes.append(f"status: {report.status.value} → {status.value}")
        report.status = status
    if priority is not None and priority != report.priority:
        changes.append(f"priority: {report.priority.value} → {priority.value}")
        report.priority = priority
    if assign and assigned_to_id != report.assigned_to_id:
        assignee = None
        if assigned_to_id is not None:
            assignee = await session.get(User, assigned_to_id)
            if assignee is None or assignee.role not in (Role.STAFF, Role.ADMIN):
                raise AssigneeInvalidError()
        changes.append(f"assigned_to: {assignee.email if assignee else '—'}")
        report.assigned_to_id = assigned_to_id
    if changes:
        _system_note(session, report, admin, NoteKind.STATUS, "; ".join(changes))
        await session.flush()
    return report


async def resolve(
    session: AsyncSession, admin: User, report: Report, status: ReportStatus, resolution: str
) -> Report:
    if report.status not in OPEN_STATUSES:
        raise ReportClosedError()
    _system_note(
        session, report, admin, NoteKind.STATUS, f"status: {report.status.value} → {status.value}"
    )
    report.status = status
    report.resolution = resolution
    report.resolved_at = utcnow()
    report.resolved_by_id = admin.id
    await notify.send(
        session,
        report.reporter_id,
        "report_resolved",
        kind="report",
        templates=TEMPLATES,
        data={"report_id": str(report.id)},
        resolution=resolution,
    )
    await session.flush()
    return report


async def reopen(session: AsyncSession, admin: User, report: Report) -> Report:
    if report.status in OPEN_STATUSES:
        raise ReportNotClosedError()
    _system_note(
        session,
        report,
        admin,
        NoteKind.STATUS,
        f"status: {report.status.value} → {ReportStatus.IN_REVIEW.value}",
    )
    report.status = ReportStatus.IN_REVIEW
    report.resolved_at = None
    report.resolved_by_id = None
    await session.flush()
    return report


async def person_numbers(session: AsyncSession, user_id: uuid.UUID) -> dict:
    """Completed rides (either side), reports against and the driver profile, for summaries."""
    rides = await session.scalar(
        select(func.count(Ride.id)).where(
            Ride.status == RideStatus.COMPLETED,
            or_(Ride.passenger_id == user_id, Ride.driver_id == user_id),
        )
    )
    since = utcnow() - timedelta(days=90)
    row = (
        await session.execute(
            select(
                func.count(Report.id),
                func.count(Report.id).filter(Report.status.in_(OPEN_STATUSES)),
                func.count(Report.id).filter(Report.created_at >= since),
            ).where(Report.reported_user_id == user_id)
        )
    ).one()
    profile = await session.scalar(select(DriverProfile).where(DriverProfile.user_id == user_id))
    return {
        "rides_completed": rides or 0,
        "reports_against": {"total": row[0], "open": row[1], "last_90_days": row[2]},
        "profile": profile,
    }
