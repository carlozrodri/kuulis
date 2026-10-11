"""Email jobs for the users/auth flows, and the account erasure loop (deleted accounts whose
grace period ended, see ``services.erase_due``), started with each worker process."""

import asyncio
import contextlib
import html
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
    "login_locked": {
        "es": (
            "Intentos fallidos de entrar a tu cuenta",
            "Hola {name}, hubo varios intentos fallidos de entrar a tu cuenta de Kuulis y la "
            "bloqueamos unos minutos. Si no fuiste tú, cambia tu contraseña desde la app "
            "(Olvidé mi contraseña).",
        ),
        "en": (
            "Failed sign-in attempts on your account",
            "Hi {name}, there were several failed attempts to sign in to your Kuulis account, so "
            "we locked it for a few minutes. If it was not you, change your password in the app "
            "(Forgot password).",
        ),
    },
}


@broker.task(task_name="users.send_templated_email", retry_on_error=True, max_retries=3)
async def send_templated_email(to: str, template: str, locale: str, name: str, link: str) -> bool:
    subject, body = TEMPLATES[template].get(locale, TEMPLATES[template]["es"])
    # The name is user input and the email is HTML: escape it so nobody can inject links.
    safe = body.format(name=html.escape(name or to), link=html.escape(link, quote=True))
    return await send_email(to, subject, safe)


async def erase_loop() -> None:
    from apps.monitoring import stats
    from apps.users import services
    from kuulis.core.db import SessionLocal

    while True:
        try:
            async with SessionLocal() as session:
                erased = await services.erase_due(session)
            if erased:
                logger.info("Erased %s deleted accounts", erased)
            await stats.beat("account_erasure")
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
