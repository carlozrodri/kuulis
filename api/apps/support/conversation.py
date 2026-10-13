"""The conversation inside a ticket (doc 13): who it waits on, the response time (SLA), replies
from the user and the team, and telling the user (push, or email for the web form)."""

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.schemas import AppConfig
from apps.moderation.models import (
    OPEN_STATUSES,
    AuthorKind,
    Report,
    ReportMessage,
    ReportPriority,
    ReportStatus,
    WaitingOn,
)
from apps.users.models import Role, User
from kuulis.core import storage
from kuulis.core.exceptions import AppError, ConflictError

MAX_ATTACHMENTS = 4
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic")

Then = Literal["wait_user", "resolve", "keep"]

TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "support_reply": {
        "es": ("Te respondimos", "{text}"),
        "en": ("We answered you", "{text}"),
    },
    "report_closed_inactive": {
        "es": (
            "Cerramos tu conversación",
            "No tuvimos noticias tuyas. Si aún necesitas ayuda, respóndenos ahí mismo.",
        ),
        "en": (
            "We closed your conversation",
            "We did not hear back from you. If you still need help, just reply there.",
        ),
    },
}

INACTIVE_TEXT = {
    "es": "Cerramos la conversación porque no tuvimos respuesta. Puedes escribirnos aquí si aún "
    "necesitas ayuda.",
    "en": "We closed the conversation because we did not hear back. You can write here if you "
    "still need help.",
}


class ReportClosedError(ConflictError):
    code = "report_closed"
    message = "This report is already closed"


class AttachmentInvalidError(AppError):
    code = "attachment_invalid"
    message = "Attachments must be photos you uploaded"


def utcnow() -> datetime:
    return datetime.now(UTC)


def first_name(user: User | None) -> str:
    return ((user.full_name or "").split() or [""])[0] if user else ""


# --- State -------------------------------------------------------------------------------------


def sla_delta(report: Report, config: AppConfig) -> timedelta:
    support = config.support
    if report.priority == ReportPriority.URGENT:
        return timedelta(minutes=support.sla_urgent_minutes)
    return timedelta(hours=support.sla_normal_hours)


def wait_on_staff(report: Report, config: AppConfig, now: datetime) -> None:
    """The team owes an answer: the response time starts now."""
    report.waiting_on = WaitingOn.STAFF
    report.waiting_since = now
    report.sla_due_at = now + sla_delta(report, config)
    report.sla_alerted_at = None


def wait_on_user(report: Report, now: datetime) -> None:
    report.waiting_on = WaitingOn.USER
    report.waiting_since = now
    report.sla_due_at = None
    report.sla_alerted_at = None


def stop_waiting(report: Report) -> None:
    report.waiting_on = None
    report.waiting_since = None
    report.sla_due_at = None
    report.sla_alerted_at = None


def reprioritized(report: Report, config: AppConfig) -> None:
    """A priority change moves the deadline of a ticket that waits on the team."""
    if report.waiting_on == WaitingOn.STAFF and report.waiting_since is not None:
        report.sla_due_at = report.waiting_since + sla_delta(report, config)


def is_overdue(report: Report, now: datetime | None = None) -> bool:
    return (
        report.status in OPEN_STATUSES
        and report.waiting_on == WaitingOn.STAFF
        and report.sla_due_at is not None
        and report.sla_due_at <= (now or utcnow())
    )


def can_reply(report: Report, config: AppConfig, now: datetime | None = None) -> bool:
    """Open tickets, and resolved ones closed less than ``auto_close_days`` ago (reopened)."""
    if report.status in OPEN_STATUSES:
        return True
    if report.status != ReportStatus.RESOLVED or report.resolved_at is None:
        return False
    window = timedelta(days=config.support.auto_close_days)
    return report.resolved_at > (now or utcnow()) - window


def can_rate(report: Report) -> bool:
    return report.status == ReportStatus.RESOLVED and report.csat is None


def unread(report: Report) -> bool:
    return report.last_staff_message_at is not None and (
        report.user_seen_at is None or report.last_staff_message_at > report.user_seen_at
    )


# --- Messages ----------------------------------------------------------------------------------


def check_attachments(user: User, keys: Sequence[str]) -> list[str]:
    """Photos the user uploaded with ``/files/presign-upload`` (folder ``uploads``)."""
    keys = list(dict.fromkeys(keys))
    if len(keys) > MAX_ATTACHMENTS:
        raise AttachmentInvalidError(details={"max": MAX_ATTACHMENTS})
    for key in keys:
        if not storage.key_in_folder(key, f"uploads/{user.id}") or not key.lower().endswith(
            IMAGE_EXTENSIONS
        ):
            raise AttachmentInvalidError(details={"key": key})
    return keys


def add_message(
    session: AsyncSession,
    report: Report,
    kind: AuthorKind,
    body: str,
    *,
    author: User | None = None,
    attachments: Sequence[str] = (),
    now: datetime | None = None,
) -> ReportMessage:
    now = now or utcnow()
    message = ReportMessage(
        report_id=report.id,
        author_id=author.id if author else None,
        author_kind=kind,
        body=body,
        attachments=list(attachments),
        created_at=now,
        updated_at=now,
    )
    session.add(message)
    report.last_message_at = now
    report.updated_at = now
    if kind != AuthorKind.USER:
        report.last_staff_message_at = now
    return message


async def messages(session: AsyncSession, report_id: uuid.UUID) -> list[ReportMessage]:
    return list(
        await session.scalars(
            select(ReportMessage)
            .where(ReportMessage.report_id == report_id)
            .order_by(ReportMessage.created_at, ReportMessage.id)
        )
    )


async def messages_counts(session: AsyncSession, report_ids: list[uuid.UUID]) -> dict:
    if not report_ids:
        return {}
    rows = await session.execute(
        select(ReportMessage.report_id, func.count(ReportMessage.id))
        .where(ReportMessage.report_id.in_(report_ids))
        .group_by(ReportMessage.report_id)
    )
    return dict(rows.all())


def attachment_urls(keys: Sequence[str]) -> list[dict[str, str | None]]:
    return [{"key": key, "url": storage.download_url_or_none(key)} for key in keys]


# --- Opening, replies and closing --------------------------------------------------------------


async def _assignee(session: AsyncSession) -> uuid.UUID | None:
    """The active staff member with the support permission and the fewest open tickets."""
    from apps.moderation.models import Report as R
    from apps.staff.models import StaffRole

    staff = list(
        await session.scalars(
            select(User.id)
            .join(StaffRole, StaffRole.id == User.staff_role_id)
            .where(
                User.role == Role.STAFF,
                User.is_active.is_(True),
                StaffRole.permissions.any("reports.manage"),  # type: ignore[arg-type]
            )
        )
    )
    if not staff:
        return None
    loads = dict(
        (
            await session.execute(
                select(R.assigned_to_id, func.count(R.id))
                .where(R.assigned_to_id.in_(staff), R.status.in_(OPEN_STATUSES))
                .group_by(R.assigned_to_id)
            )
        ).all()
    )
    return min(staff, key=lambda uid: (loads.get(uid, 0), str(uid)))


async def opened(
    session: AsyncSession,
    report: Report,
    config: AppConfig,
    *,
    author: User | None,
    attachments: Sequence[str] = (),
) -> None:
    """A new ticket: its description is the first message and it waits on the team."""
    now = report.created_at or utcnow()
    add_message(
        session,
        report,
        AuthorKind.USER,
        report.description,
        author=author,
        attachments=attachments,
        now=now,
    )
    report.last_staff_message_at = None
    wait_on_staff(report, config, now)
    if config.support.auto_assign and report.assigned_to_id is None:
        report.assigned_to_id = await _assignee(session)


async def user_reply(
    session: AsyncSession,
    user: User,
    report: Report,
    config: AppConfig,
    body: str,
    attachments: Sequence[str],
) -> ReportMessage:
    from apps.moderation import services as moderation

    now = utcnow()
    if not can_reply(report, config, now):
        raise ReportClosedError()
    keys = check_attachments(user, attachments)
    if report.status not in OPEN_STATUSES:  # resolved a few days ago: back to the team
        moderation.status_note(
            session, report, None, f"status: {report.status.value} → in_review (user replied)"
        )
        report.status = ReportStatus.IN_REVIEW
        report.resolved_at = None
        report.resolved_by_id = None
    message = add_message(session, report, AuthorKind.USER, body, author=user, attachments=keys)
    wait_on_staff(report, config, now)
    report.user_seen_at = now
    await session.flush()
    return message


_VARIABLES = re.compile(r"\{(nombre|name|viaje|ride)\}")


async def render(session: AsyncSession, report: Report, body: str) -> str:
    """Fills ``{nombre}`` and ``{viaje}`` in a saved reply."""
    if not _VARIABLES.search(body):
        return body
    from apps.rides.models import Ride

    reporter = await session.get(User, report.reporter_id) if report.reporter_id else None
    name = first_name(reporter) or (report.contact_name or "").split(" ")[0]
    ride_label = ""
    if report.ride_id:
        ride = await session.get(Ride, report.ride_id)
        if ride is not None:
            when = ride.completed_at or ride.requested_at
            ride_label = (
                f"{when:%d/%m/%Y} (#{str(ride.id)[:8]})" if when else f"#{str(ride.id)[:8]}"
            )
    values = {"nombre": name, "name": name, "viaje": ride_label, "ride": ride_label}
    return _VARIABLES.sub(lambda m: values[m.group(1)], body)


async def tell_user(session: AsyncSession, report: Report, event: str, text: str = "") -> None:
    """Push and inbox for app users; email for web tickets without an account."""
    from apps.support import tasks
    from apps.wallet import notify

    if report.reporter_id is not None:
        if event == "report_resolved":
            from apps.moderation.services import TEMPLATES as MODERATION

            templates = MODERATION
            values = {"resolution": text[:300]}
        else:
            templates = TEMPLATES
            values = {"text": text[:140]}
        await notify.send(
            session,
            report.reporter_id,
            event,
            kind="support",
            templates=templates,
            data={"report_id": str(report.id)},
            **values,
        )
    elif report.contact_email:
        await tasks.send_ticket_email.kiq(
            report.contact_email, report.locale, str(report.id), event, text
        )


async def staff_reply(
    session: AsyncSession,
    admin: User,
    report: Report,
    config: AppConfig,
    body: str,
    attachments: Sequence[str],
    then: Then = "wait_user",
    add_tags: Sequence[str] = (),
) -> None:
    from apps.moderation import services as moderation

    if report.status not in OPEN_STATUSES:
        raise ReportClosedError()
    keys = check_attachments(admin, attachments)
    body = await render(session, report, body)
    if add_tags:
        report.tags = sorted(set(report.tags or []) | {t.strip().lower() for t in add_tags if t})
    now = utcnow()
    report.first_response_at = report.first_response_at or now
    if report.status == ReportStatus.OPEN:
        report.status = ReportStatus.IN_REVIEW
    if then == "resolve":
        await moderation.resolve(
            session, admin, report, ReportStatus.RESOLVED, body, attachments=keys
        )
        return
    add_message(session, report, AuthorKind.STAFF, body, author=admin, attachments=keys, now=now)
    if then == "wait_user":
        wait_on_user(report, now)
    else:  # keep: still the team's turn, with a new deadline
        wait_on_staff(report, config, now)
    await session.flush()
    await tell_user(session, report, "support_reply", body)


async def close_inactive(session: AsyncSession, report: Report) -> None:
    """Waited on the user for ``auto_close_days``: resolved, the user can still reply."""
    from apps.moderation import services as moderation

    now = utcnow()
    text = INACTIVE_TEXT.get(report.locale, INACTIVE_TEXT["es"])
    add_message(session, report, AuthorKind.SYSTEM, text, now=now)
    moderation.status_note(
        session, report, None, f"status: {report.status.value} → resolved (no answer)"
    )
    report.status = ReportStatus.RESOLVED
    report.resolution = report.resolution or text
    report.resolved_at = now
    stop_waiting(report)
    await session.flush()
    await tell_user(session, report, "report_closed_inactive", text)
