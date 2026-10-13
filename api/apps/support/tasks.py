"""Support jobs (doc 13): emails for web tickets, and a loop started with each worker that
alerts the team about urgent tickets past their response time and closes tickets that waited on
the user for ``support.auto_close_days``."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from kuulis.core.email import send_email
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 60
_task: asyncio.Task | None = None

# Ticket events -> email templates (apps/notifications/emails.py).
EMAIL_TEMPLATES = {
    "received": "support_received",
    "support_reply": "support_reply",
    "report_resolved": "support_reply",
    "report_closed_inactive": "support_closed",
}


def ticket_email(locale: str, event: str, text: str) -> tuple[str, str, str]:
    """Subject, HTML and plain text. The text is user or staff input: the template escapes it."""
    from apps.notifications import emails

    return emails.render(EMAIL_TEMPLATES[event], locale, {"text": text})


@broker.task(task_name="support.send_ticket_email", retry_on_error=True, max_retries=3)
async def send_ticket_email(to: str, locale: str, report_id: str, event: str, text: str) -> bool:
    from apps.config.services import get_app_config
    from kuulis.core.db import SessionLocal

    async with SessionLocal() as session:
        reply_to = (await get_app_config(session)).app_links.support_email or None
    subject, body, plain = ticket_email(locale, event, text)
    return await send_email(to, f"{subject} · #{report_id[:8]}", body, plain, reply_to=reply_to)


async def run_once() -> tuple[int, int]:
    """(urgent tickets alerted, tickets closed for inactivity)."""
    from apps.config.services import get_app_config
    from apps.monitoring import alerts
    from apps.support import conversation, services
    from kuulis.core.db import SessionLocal

    now = conversation.utcnow()
    async with SessionLocal() as session:
        config = await get_app_config(session)
        overdue = await services.overdue_to_alert(session, now)
        lines = [
            f"#{str(r.id)[:8]} {r.category.value} · {late} min"
            for r in overdue
            if r.sla_due_at is not None
            for late in [int((now - r.sla_due_at).total_seconds() // 60)]
        ]
        await session.commit()
    if lines:
        await alerts.notify(
            "⏰ Tickets urgentes sin respuesta a tiempo:\n"
            + "\n".join(lines)
            + f"\n{settings.admin_url}/reports"
        )
    closed = 0
    async with SessionLocal() as session:
        for report in await services.stale_waiting_on_user(session, config, now):
            await conversation.close_inactive(session, report)
            closed += 1
        await session.commit()
    return len(lines), closed


async def loop() -> None:
    from apps.monitoring import stats

    while True:
        try:
            alerted, closed = await run_once()
            if alerted or closed:
                logger.info("Support: %s overdue alerts, %s closed", alerted, closed)
            await stats.beat("support_sla")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Support loop failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(loop(), name="support-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
