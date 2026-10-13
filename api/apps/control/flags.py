"""Feature flags (doc 10): the known keys, their defaults and how a flag is evaluated.

A flag is on for someone when its row is enabled (or, with no row, its default) and every rule
that narrows it matches. Rules about something the server does not know (the platform of a call
without app headers, the city of a user without location) do not exclude anyone; the percentage
uses a stable hash of the flag and the account (or device), so the same person keeps the same
answer at every start.
"""

import hashlib
from dataclasses import dataclass

from apps.control.schemas import FlagRules


@dataclass(frozen=True)
class Flag:
    default: bool
    description: str


# Adding a key here shows it in the admin. The app hides what is off; the API refuses it too.
FLAGS: dict[str, Flag] = {
    "chat": Flag(True, "Chat entre pasajero y motorizado durante el viaje"),
    "promotions": Flag(True, "Promociones y códigos de descuento al cotizar"),
    "transfers": Flag(True, "Transferencias de saldo entre usuarios"),
    "binance_auto": Flag(True, "Acreditación automática de recargas por Binance Pay"),
    "share_live_link": Flag(True, "Compartir el viaje en vivo con un enlace"),
}


@dataclass(frozen=True)
class Audience:
    """Who is asking. ``ident`` is the account id (or the device id before login)."""

    ident: str | None = None
    role: str | None = None
    platform: str | None = None
    build: int | None = None
    area: str | None = None


def bucket(key: str, ident: str) -> int:
    """0-99, stable for the same flag and person (different flags split people differently)."""
    digest = hashlib.sha256(f"{key}:{ident}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100


def evaluate(key: str, row: dict | None, who: Audience) -> bool:
    if row is None:
        flag = FLAGS.get(key)
        return bool(flag and flag.default)
    if not row.get("enabled"):
        return False
    rules = FlagRules.model_validate(row.get("rules") or {})
    if rules.platforms and who.platform and who.platform not in rules.platforms:
        return False
    if rules.min_build and who.build is not None and who.build < rules.min_build:
        return False
    if rules.areas and who.area and who.area not in rules.areas:
        return False
    if rules.roles and who.role and who.role not in rules.roles:
        return False
    if rules.percent < 100:
        return who.ident is not None and bucket(key, who.ident) < rules.percent
    return True
