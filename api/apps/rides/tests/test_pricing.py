from datetime import datetime
from decimal import Decimal

from apps.config.schemas import AppConfig, FareConfig, SurgeRule
from apps.drivers.models import VehicleType
from apps.rides import pricing
from apps.rides.pricing import CARACAS_TZ, compute_fare, quote_price, round_up, surge_multiplier

MOTO = FareConfig(
    base=Decimal("0.80"),
    per_km=Decimal("0.35"),
    per_minute=Decimal("0.05"),
    minimum=Decimal("1.50"),
)
ONE = Decimal("1.00")


def caracas(year, month, day, hour, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=CARACAS_TZ)


def test_round_up():
    assert round_up(Decimal("2.31"), Decimal("0.10")) == Decimal("2.40")
    assert round_up(Decimal("2.30"), Decimal("0.10")) == Decimal("2.30")
    assert round_up(Decimal("2.3000001"), Decimal("0.10")) == Decimal("2.30")  # noise ignored
    assert round_up(Decimal("2.01"), Decimal("0.25")) == Decimal("2.25")
    assert round_up(Decimal("2.01"), Decimal("1.00")) == Decimal("3.00")
    assert str(round_up(Decimal("3"), Decimal("0.10"))) == "3.00"


def test_compute_fare_formula():
    # 0.80 + 0.35 * 5.2 + 0.05 * 12.5 = 3.245 -> 3.30
    assert compute_fare(MOTO, 5200, 750, ONE, Decimal("0.10")) == Decimal("3.30")
    # Short ride: 0.80 + 0.35 * 0.5 + 0.05 * 2 = 1.075 -> minimum 1.50
    assert compute_fare(MOTO, 500, 120, ONE, Decimal("0.10")) == Decimal("1.50")
    # Surge applies after the minimum and before rounding: 1.50 * 1.25 = 1.875 -> 1.90
    assert compute_fare(MOTO, 500, 120, Decimal("1.25"), Decimal("0.10")) == Decimal("1.90")
    assert compute_fare(MOTO, 5200, 750, Decimal("1.50"), Decimal("0.01")) == Decimal("4.87")


def test_surge_rules_and_manual():
    rules = [
        SurgeRule(days=[0, 1, 2, 3, 4], start="07:00", end="09:00", multiplier=Decimal("1.30")),
        SurgeRule(days=[4], start="22:00", end="02:00", multiplier=Decimal("1.50")),
    ]
    config = AppConfig(surge_rules=rules)
    # 2026-10-05 is a Monday.
    assert surge_multiplier(config, caracas(2026, 10, 5, 7, 30)) == Decimal("1.30")
    assert surge_multiplier(config, caracas(2026, 10, 5, 9, 0)) == ONE  # end is exclusive
    assert surge_multiplier(config, caracas(2026, 10, 10, 8, 0)) == ONE  # Saturday
    # Friday 22:00 -> Saturday 02:00 belongs to Friday.
    assert surge_multiplier(config, caracas(2026, 10, 9, 23, 0)) == Decimal("1.50")
    assert surge_multiplier(config, caracas(2026, 10, 10, 1, 59)) == Decimal("1.50")
    assert surge_multiplier(config, caracas(2026, 10, 10, 2, 0)) == ONE
    assert surge_multiplier(config, caracas(2026, 10, 8, 23, 0)) == ONE  # Thursday night
    # UTC input is converted to Caracas (UTC-4): 11:30 UTC Monday = 07:30 Caracas.
    utc = datetime.fromisoformat("2026-10-05T11:30:00+00:00")
    assert surge_multiplier(config, utc) == Decimal("1.30")
    # The highest of rule and manual wins.
    manual = AppConfig(surge_rules=rules, surge_manual_multiplier=Decimal("1.40"))
    assert surge_multiplier(manual, caracas(2026, 10, 5, 7, 30)) == Decimal("1.40")
    assert surge_multiplier(manual, caracas(2026, 10, 9, 23, 0)) == Decimal("1.50")


def test_quote_price_uses_config(monkeypatch):
    config = AppConfig(fare_rounding=Decimal("0.50"), surge_manual_multiplier=Decimal("1.10"))
    fare, surge = quote_price(config, VehicleType.MOTO, 5200, 750, caracas(2026, 10, 5, 12))
    assert surge == Decimal("1.10")
    assert fare == Decimal("4.00")  # 3.245 * 1.1 = 3.5695 -> 4.00
    assert Decimal("0.01") == pricing.CENT
