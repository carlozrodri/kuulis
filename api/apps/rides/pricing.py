"""Fare calculation (all Decimal, never float).

fare = max(minimum, base + per_km * km + per_minute * min) * surge, rounded UP to ``fare_rounding``.
surge = the highest of the active time rule(s) (Caracas time) and the manual multiplier.
"""

from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from apps.config.schemas import AppConfig, FareConfig, SurgeRule
from apps.drivers.models import VehicleType

CARACAS_TZ = ZoneInfo("America/Caracas")
CENT = Decimal("0.01")
_PRECISION = Decimal("0.0001")  # intermediate precision before rounding up


def rule_active(rule: SurgeRule, local: datetime) -> bool:
    """``local`` must be in Caracas time. Windows crossing midnight belong to their start day."""
    now, weekday = local.time().replace(second=0, microsecond=0), local.weekday()
    start, end = rule.start_time, rule.end_time
    if start < end:
        return weekday in rule.days and start <= now < end
    previous_day = (weekday - 1) % 7
    return (weekday in rule.days and now >= start) or (previous_day in rule.days and now < end)


def surge_multiplier(config: AppConfig, at: datetime | None = None) -> Decimal:
    local = (at or datetime.now(UTC)).astimezone(CARACAS_TZ)
    active = [r.multiplier for r in config.surge_rules if rule_active(r, local)]
    return max([config.surge_manual_multiplier, *active]).quantize(CENT)


def round_up(amount: Decimal, step: Decimal) -> Decimal:
    amount = amount.quantize(_PRECISION, rounding=ROUND_HALF_UP)
    return ((amount / step).to_integral_value(rounding=ROUND_CEILING) * step).quantize(CENT)


def compute_fare(
    fare: FareConfig, distance_m: int, duration_s: int, surge: Decimal, rounding: Decimal
) -> Decimal:
    km = Decimal(distance_m) / 1000
    minutes = Decimal(duration_s) / 60
    raw = fare.base + fare.per_km * km + fare.per_minute * minutes
    return round_up(max(fare.minimum, raw) * surge, rounding)


def quote_price(
    config: AppConfig,
    vehicle_type: VehicleType,
    distance_m: int,
    duration_s: int,
    at: datetime | None = None,
) -> tuple[Decimal, Decimal]:
    """Returns (fare, surge_multiplier)."""
    surge = surge_multiplier(config, at)
    fare = compute_fare(
        config.fares[vehicle_type], distance_m, duration_s, surge, config.fare_rounding
    )
    return fare, surge
