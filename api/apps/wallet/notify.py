"""Wallet and subscription notices: inbox row + push, in the user's language.

The push task only reads device tokens, so it can be queued before the caller commits.
"""

import uuid
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.notifications import services as notifications
from apps.notifications import tasks as notification_tasks
from apps.users.models import User
from kuulis.core.calendar import CARACAS_TZ

# event -> locale -> (title, body)
TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "top_up_credited": {
        "es": ("Recarga acreditada", "Sumamos {amount} USDT a tu billetera."),
        "en": ("Top-up credited", "We added {amount} USDT to your wallet."),
    },
    "top_up_rejected": {
        "es": ("Recarga rechazada", "No pudimos confirmar tu recarga: {reason}"),
        "en": ("Top-up rejected", "We could not confirm your top-up: {reason}"),
    },
    "transfer_received": {
        "es": ("Recibiste saldo", "{name} te transfirió {amount} USDT."),
        "en": ("You received balance", "{name} sent you {amount} USDT."),
    },
    "adjustment": {
        "es": ("Ajuste de saldo", "Kuulis ajustó tu saldo en {amount} USDT: {reason}"),
        "en": ("Balance adjustment", "Kuulis adjusted your balance by {amount} USDT: {reason}"),
    },
    "fee_paid": {
        "es": ("Cuota pagada", "Pagaste {fee} USDT por {month}. ¡Gracias!"),
        "en": ("Fee paid", "You paid {fee} USDT for {month}. Thank you!"),
    },
    "fee_pending": {
        "es": (
            "Tu cuota de {month}",
            "Te toca pagar {fee} USDT. Recarga tu billetera antes del {due}.",
        ),
        "en": ("Your {month} fee", "You owe {fee} USDT. Top up your wallet before {due}."),
    },
    "fee_due_soon": {
        "es": ("Tu cuota vence mañana", "Recarga {fee} USDT para seguir recibiendo viajes."),
        "en": ("Your fee is due tomorrow", "Top up {fee} USDT to keep receiving rides."),
    },
    "fee_overdue": {
        "es": (
            "No puedes recibir viajes",
            "Tu cuota de {fee} USDT venció. Recarga tu billetera para volver a conectarte.",
        ),
        "en": (
            "You can't receive rides",
            "Your {fee} USDT fee is overdue. Top up your wallet to go online again.",
        ),
    },
    "fee_waived": {
        "es": ("Cuota condonada", "Kuulis condonó tu cuota de {month}."),
        "en": ("Fee waived", "Kuulis waived your {month} fee."),
    },
}


_MONTHS = {
    "es": [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ],
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
}


def month_label(value: date, locale: str) -> str:
    names = _MONTHS["en" if locale == "en" else "es"]
    return f"{names[value.month - 1]} {value.year}"


def date_label(value: datetime, locale: str) -> str:
    local = value.astimezone(CARACAS_TZ)
    names = _MONTHS["en" if locale == "en" else "es"]
    if locale == "en":
        return f"{names[local.month - 1]} {local.day}"
    return f"{local.day} de {names[local.month - 1]}"


def render(
    event: str,
    locale: str,
    templates: dict[str, dict[str, tuple[str, str]]] | None = None,
    **values: Any,
) -> tuple[str, str]:
    locale = locale if locale in ("es", "en") else "es"
    title, body = (templates or TEMPLATES)[event][locale]
    return title.format(**values), body.format(**values)


async def send(
    session: AsyncSession,
    user_id: uuid.UUID,
    event: str,
    kind: str = "wallet",
    localized: Callable[[str], dict[str, Any]] | None = None,
    templates: dict[str, dict[str, tuple[str, str]]] | None = None,
    data: dict[str, Any] | None = None,
    **values: Any,
) -> None:
    """``localized(locale)`` returns extra values that depend on the language (dates, months).
    ``templates`` lets other apps reuse this with their own texts; ``data`` goes in the push."""
    user = await session.get(User, user_id)
    if user is None:
        return
    if localized is not None:
        values |= localized(user.locale)
    title, body = render(event, user.locale, templates, **values)
    payload = {"type": kind, "event": event} | (data or {})
    await notifications.create_notifications(session, [user.id], title, body, payload)
    await notification_tasks.send_push.kiq([str(user.id)], title, body, payload)
