"""Push notifications for ride events, in each user's language.

Ride pushes are not stored in the inbox (they are transient); the app reacts to the realtime
events and uses the push only to wake up / inform while in the background.
"""

import uuid
from typing import Any

from apps.notifications import tasks as notification_tasks

# event -> locale -> (title, body)
TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "offer": {
        "es": ("Nuevo viaje", "Recogida: {pickup}. Tarifa: ${fare}."),
        "en": ("New ride", "Pickup: {pickup}. Fare: ${fare}."),
    },
    "assigned": {
        "es": ("Tu motorizado va en camino", "{name} aceptó tu viaje."),
        "en": ("Your driver is on the way", "{name} accepted your ride."),
    },
    "arrived": {
        "es": ("Tu motorizado llegó", "{name} te espera en el punto de recogida."),
        "en": ("Your driver has arrived", "{name} is waiting at the pickup point."),
    },
    "completed": {
        "es": ("Viaje completado", "Califica tu viaje con {name}."),
        "en": ("Ride completed", "Rate your ride with {name}."),
    },
    "cancelled_by_passenger": {
        "es": ("Viaje cancelado", "El pasajero canceló el viaje."),
        "en": ("Ride cancelled", "The passenger cancelled the ride."),
    },
    "cancelled_by_driver": {
        "es": ("Viaje cancelado", "El motorizado canceló el viaje. Puedes pedir otro."),
        "en": ("Ride cancelled", "The driver cancelled the ride. You can request another one."),
    },
    "cancelled_by_admin": {
        "es": ("Viaje cancelado", "Kuulis canceló el viaje."),
        "en": ("Ride cancelled", "Kuulis cancelled the ride."),
    },
    "no_drivers": {
        "es": (
            "No encontramos motorizado",
            "No hay motorizados disponibles cerca. Intenta de nuevo en unos minutos.",
        ),
        "en": (
            "No drivers found",
            "There are no drivers available nearby. Please try again in a few minutes.",
        ),
    },
    "promo_credit": {
        "es": ("Kuulis te acreditó ${amount}", "Es el descuento de la promoción del último viaje."),
        "en": ("Kuulis credited you ${amount}", "It is the promotion discount of your last ride."),
    },
    "message": {
        "es": ("{name}", "{text}"),
        "en": ("{name}", "{text}"),
    },
}


def render(event: str, locale: str, **values: Any) -> tuple[str, str]:
    locale = locale if locale in ("es", "en") else "es"
    title, body = TEMPLATES[event][locale]
    return title.format(**values), body.format(**values)


async def push(
    user_id: uuid.UUID,
    locale: str,
    event: str,
    ride_id: uuid.UUID,
    options: dict[str, Any] | None = None,
    **values: Any,
) -> None:
    title, body = render(event, locale, **values)
    data = {"type": "ride", "event": event, "ride_id": str(ride_id)}
    await notification_tasks.send_push.kiq([str(user_id)], title, body, data, options)
