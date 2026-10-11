"""Email jobs for the users/auth flows, and the account erasure loop (deleted accounts whose
grace period ended, see ``services.erase_due``), started with each worker process."""

import asyncio
import contextlib
import logging

from taskiq import TaskiqEvents, TaskiqState

from kuulis.core.email import send_email
from kuulis.settings import settings
from kuulis.tasks import broker

logger = logging.getLogger(__name__)

ERASE_EVERY_SECONDS = 3600
_task: asyncio.Task | None = None

TEMPLATES = {
    "verify": {
        "es": (
            "Confirma tu correo",
            "Hola {name}, confirma tu correo aquí: <a href='{link}'>{link}</a>",
        ),
        "en": (
            "Confirm your email",
            "Hi {name}, confirm your email here: <a href='{link}'>{link}</a>",
        ),
    },
    "reset": {
        "es": (
            "Restablece tu contraseña",
            "Hola {name}, restablece tu contraseña aquí: <a href='{link}'>{link}</a>",
        ),
        "en": (
            "Reset your password",
            "Hi {name}, reset your password here: <a href='{link}'>{link}</a>",
        ),
    },
}


@broker.task(task_name="users.send_templated_email", retry_on_error=True, max_retries=3)
async def send_templated_email(to: str, template: str, locale: str, name: str, link: str) -> bool:
    subject, body = TEMPLATES[template].get(locale, TEMPLATES[template]["es"])
    return await send_email(to, subject, body.format(name=name or to, link=link))


async def erase_loop() -> None:
    from apps.users import services
    from kuulis.core.db import SessionLocal

    while True:
        try:
            async with SessionLocal() as session:
                erased = await services.erase_due(session)
            if erased:
                logger.info("Erased %s deleted accounts", erased)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Account erasure failed")
        await asyncio.sleep(ERASE_EVERY_SECONDS)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def _start(_: TaskiqState) -> None:
    global _task
    if settings.APP_ENV != "test" and _task is None:
        _task = asyncio.create_task(erase_loop(), name="account-erasure-loop")


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _stop(_: TaskiqState) -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
