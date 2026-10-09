"""Email jobs for the users/auth flows."""

from kuulis.core.email import send_email
from kuulis.tasks import broker

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
