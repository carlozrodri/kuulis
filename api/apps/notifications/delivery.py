"""How a notification is delivered (doc 14): its category, the Android channel of its push and
the quiet hours of marketing."""

from collections.abc import Iterable
from datetime import datetime, time
from typing import Any

from apps.notifications.models import Category
from kuulis.core.calendar import CARACAS_TZ

# Android channels the app creates (mobile/src/lib/notificationChannels.ts). The app reports
# the ones it has when it registers the phone; older apps only have "default".
DEFAULT_CHANNEL = "default"
# Wanted channel -> fallbacks, best first. ``ride_offer_sound`` comes with the APK that ships the
# offer sound; until then offers use ``ride_offer``.
CHANNEL_FALLBACKS: dict[str, tuple[str, ...]] = {
    "ride_offer": ("ride_offer_sound", "ride_offer"),
    "ride_updates": ("ride_updates",),
    "safety": ("safety",),
    "support": ("account",),
    "account": ("account",),
    "marketing": ("marketing",),
}

SUPPORT_TYPES = frozenset({"support", "report", "lost_item"})


def payload_type(data: dict[str, Any] | None) -> str:
    return str((data or {}).get("type") or "")


def category_of(data: dict[str, Any] | None) -> Category:
    kind = payload_type(data)
    if kind == "safety":
        return Category.SAFETY
    if kind in SUPPORT_TYPES:
        return Category.SUPPORT
    if kind == "campaign":
        return Category.MARKETING
    return Category.TRANSACTIONAL


def wanted_channel(data: dict[str, Any] | None) -> str:
    kind = payload_type(data)
    if kind == "ride":
        return "ride_offer" if (data or {}).get("event") == "offer" else "ride_updates"
    if kind == "safety":
        return "safety"
    if kind == "campaign":
        return "marketing"
    if kind in SUPPORT_TYPES:
        return "support"
    return "account"


def pick_channel(wanted: str, available: Iterable[str] | None) -> str:
    """The best channel this phone has for ``wanted``; ``default`` exists on every app version."""
    have = set(available or ())
    for channel in CHANNEL_FALLBACKS.get(wanted, (wanted,)):
        if channel in have:
            return channel
    return DEFAULT_CHANNEL


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def in_quiet_hours(now: datetime, start: str, end: str) -> bool:
    """Whether ``now`` falls in [start, end) Caracas time; the window may cross midnight.
    Equal start and end means no quiet hours."""
    if start == end:
        return False
    local = now.astimezone(CARACAS_TZ).time().replace(second=0, microsecond=0)
    begin, finish = parse_hhmm(start), parse_hhmm(end)
    if begin < finish:
        return begin <= local < finish
    return local >= begin or local < finish
