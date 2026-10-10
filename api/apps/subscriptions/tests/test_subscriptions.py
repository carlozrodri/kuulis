from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from apps.drivers.models import DriverProfile, VehicleType
from apps.notifications.models import Notification
from apps.rides.models import PaymentMethod, Ride, RideStatus
from apps.rides.tests.conftest import make_driver
from apps.subscriptions import services
from apps.subscriptions.models import Charge, ChargeStatus
from apps.subscriptions.schemas import Tier
from apps.wallet import services as wallet
from conftest import _make_user
from kuulis.core.calendar import add_months, format_month, local_now, month_bounds, month_start
from kuulis.core.db import SessionLocal

API = "/api/v1"


def _month(offset: int):
    return add_months(month_start(local_now()), offset)


async def _ride(driver, fare: str, month_offset: int, day: int = 10) -> None:
    """A completed ride in the given (relative) month."""
    start, _ = month_bounds(_month(month_offset))
    when = start + timedelta(days=day - 1, hours=12)
    passenger = await _make_user(f"p{datetime.now(UTC).timestamp()}@example.com")
    async with SessionLocal() as session:
        session.add(
            Ride(
                passenger_id=passenger.id,
                driver_id=driver.user.id,
                status=RideStatus.COMPLETED,
                vehicle_type=VehicleType.MOTO,
                pickup_lat=10.49,
                pickup_lng=-66.88,
                dropoff_lat=10.50,
                dropoff_lng=-66.85,
                distance_m=3000,
                duration_s=600,
                fare=Decimal(fare),
                surge_multiplier=Decimal("1"),
                payment_method=PaymentMethod.CASH_USD,
                requested_at=when,
                search_expires_at=when,
                completed_at=when,
            )
        )
        await session.commit()


async def _first_trip(driver, month_offset: int) -> None:
    start, _ = month_bounds(_month(month_offset))
    async with SessionLocal() as session:
        await session.execute(
            update(DriverProfile)
            .where(DriverProfile.user_id == driver.user.id)
            .values(first_trip_completed_at=start + timedelta(hours=1))
        )
        await session.commit()


async def _credit(driver, amount: str) -> None:
    async with SessionLocal() as session:
        await wallet.credit(session, driver.user.id, wallet.EntryKind.ADJUSTMENT, Decimal(amount))
        await session.commit()


async def _charges(driver) -> list[Charge]:
    async with SessionLocal() as session:
        return list(
            await session.scalars(
                select(Charge).where(Charge.user_id == driver.user.id).order_by(Charge.month)
            )
        )


async def _balance(client, driver) -> str:
    return (await client.get(f"{API}/wallet/me", headers=driver.headers)).json()["balance"]


@pytest.mark.parametrize(
    ("earned", "fee"),
    [("0", "0"), ("100", "0"), ("100.01", "5"), ("250", "10"), ("600", "25"), ("5000", "30")],
)
def test_fee_for(earned, fee):
    assert services.fee_for(services.DEFAULT_TIERS, Decimal(earned)) == Decimal(fee)


async def test_charge_month_paid_pending_waived(client, recorder):
    rich = await make_driver(client, "rich@example.com", "Rico Pérez")
    poor = await make_driver(client, "poor@example.com", "Pedro Pobre")
    small = await make_driver(client, "small@example.com", "Sara Poco")
    for driver in (rich, poor, small):
        await _first_trip(driver, -6)  # free period over
    await _ride(rich, "150", -1)
    await _ride(rich, "60", -1, day=12)  # 210 -> $10
    await _ride(poor, "120", -1)  # $5
    await _ride(small, "40", -1)  # below the first tier
    await _ride(rich, "500", 0)  # current month: not charged
    await _credit(rich, "12")

    async with SessionLocal() as session:
        result = await services.charge_month(session, _month(-1))
    assert (result.created, result.paid, result.pending, result.waived) == (3, 1, 1, 1)

    paid = (await _charges(rich))[0]
    assert paid.status == ChargeStatus.PAID and paid.fee == Decimal("10.00")
    assert paid.earnings == Decimal("210.00") and paid.entry_id is not None
    assert await _balance(client, rich) == "2.00"
    pending = (await _charges(poor))[0]
    assert pending.status == ChargeStatus.PENDING and pending.fee == Decimal("5.00")
    waived = (await _charges(small))[0]
    assert waived.status == ChargeStatus.WAIVED and waived.waived_reason == "below_minimum"

    async with SessionLocal() as session:  # idempotent
        again = await services.charge_month(session, _month(-1))
    assert again.created == 0

    entries = (await client.get(f"{API}/wallet/me/entries", headers=rich.headers)).json()
    assert entries["items"][0]["kind"] == "subscription_fee"
    assert entries["items"][0]["amount"] == "-10.00"
    assert entries["items"][0]["details"] == {"month": format_month(_month(-1))}


async def test_free_period(client, recorder):
    new = await make_driver(client, "new@example.com", "Nuevo Ruiz")
    await _first_trip(new, -1)  # free until three months later
    await _ride(new, "400", -1)
    async with SessionLocal() as session:
        await services.charge_month(session, _month(-1))
    charge = (await _charges(new))[0]
    assert charge.status == ChargeStatus.WAIVED and charge.free_period
    assert charge.waived_reason == "free_period" and charge.earnings == Decimal("0.00")

    summary = (await client.get(f"{API}/wallet/me/subscription", headers=new.headers)).json()
    assert summary["in_free_period"] is True and summary["blocked"] is False
    assert summary["estimated_fee"] == "0.00" and len(summary["tiers"]) == 7

    # Rides inside the free period don't count for the fee but still show as earned this month.
    await _ride(new, "25", 0, day=1)
    summary = (await client.get(f"{API}/wallet/me/subscription", headers=new.headers)).json()
    assert summary["earnings"] == "0.00" and summary["earned"] == "25.00"
    assert summary["trips"] == 1


async def test_month_not_closed(client, admin_headers, staff_headers):
    url = f"{API}/admin/subscriptions/run"
    current = format_month(_month(0))
    response = await client.post(url, json={"month": current}, headers=admin_headers)
    assert response.status_code == 400 and response.json()["error"]["code"] == "month_not_closed"
    forbidden = await client.post(
        url, json={"month": format_month(_month(-1))}, headers=staff_headers
    )
    assert forbidden.status_code == 403
    ok = await client.post(url, json={"month": format_month(_month(-1))}, headers=admin_headers)
    assert ok.status_code == 200 and ok.json() == {
        "created": 0,
        "paid": 0,
        "pending": 0,
        "waived": 0,
    }


async def test_overdue_blocks_until_top_up(client, admin_headers, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _first_trip(luis, -6)
    await _ride(luis, "350", -1)  # $15
    async with SessionLocal() as session:
        await services.charge_month(session, _month(-1))
    charge = (await _charges(luis))[0]
    assert charge.status == ChargeStatus.PENDING

    online = f"{API}/drivers/me/online"
    point = {"lat": 10.49, "lng": -66.88}
    assert (await client.post(online, json=point, headers=luis.headers)).status_code == 200
    await client.post(f"{API}/drivers/me/offline", headers=luis.headers)

    async with SessionLocal() as session:  # grace period over
        await session.execute(
            update(Charge)
            .where(Charge.id == charge.id)
            .values(due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    blocked = await client.post(online, json=point, headers=luis.headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "subscription_overdue"
    summary = (await client.get(f"{API}/wallet/me/subscription", headers=luis.headers)).json()
    assert summary["blocked"] is True and summary["pending"][0]["overdue"] is True

    async with SessionLocal() as session:
        assert await services.send_reminders(session) == 1
    async with SessionLocal() as session:
        assert await services.send_reminders(session) == 0  # only once

    await _credit(luis, "10")  # not enough: stays pending
    assert (await _charges(luis))[0].status == ChargeStatus.PENDING
    await _credit(luis, "7")
    assert (await _charges(luis))[0].status == ChargeStatus.PAID
    assert await _balance(client, luis) == "2.00"
    assert (await client.post(online, json=point, headers=luis.headers)).status_code == 200

    async with SessionLocal() as session:
        titles = list(
            await session.scalars(
                select(Notification.title).where(Notification.user_id == luis.user.id)
            )
        )
    assert len(titles) == 3  # pending, overdue, paid

    history = (await client.get(f"{API}/wallet/me/charges", headers=luis.headers)).json()
    assert history["total"] == 1 and history["items"][0]["status"] == "paid"


async def test_waive_and_admin_listing(client, admin_headers, staff_headers, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ana = await make_driver(client, "ana2@example.com", "Ana Ruiz")
    for driver in (luis, ana):
        await _first_trip(driver, -6)
    await _ride(luis, "150", -1)
    await _ride(ana, "250", -1)
    await _credit(ana, "20")
    async with SessionLocal() as session:
        await services.charge_month(session, _month(-1))

    month = format_month(_month(-1))
    listing = await client.get(
        f"{API}/admin/subscriptions/charges?month={month}", headers=staff_headers
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 2
    assert body["totals"]["paid"] == "10.00" and body["totals"]["pending"] == "5.00"
    bad = await client.get(
        f"{API}/admin/subscriptions/charges?month=2026-13", headers=staff_headers
    )
    assert bad.status_code == 400

    charge = (await _charges(luis))[0]
    url = f"{API}/admin/subscriptions/charges/{charge.id}/waive"
    reason = {"reason": "Moto en el taller"}
    assert (await client.post(url, json=reason, headers=staff_headers)).status_code == 403
    waived = await client.post(url, json=reason, headers=admin_headers)
    assert waived.status_code == 200, waived.text
    assert waived.json()["status"] == "waived"
    assert waived.json()["waived_reason"] == "Moto en el taller"
    assert (await client.post(url, json=reason, headers=admin_headers)).status_code == 409


async def test_schedules(client, admin_headers, staff_headers):
    url = f"{API}/admin/subscriptions/schedules"
    initial = (await client.get(url, headers=staff_headers)).json()
    assert len(initial) == 1 and initial[0]["current"] is True and initial[0]["id"] is None

    tiers = [{"above": "0", "fee": "0"}, {"above": "150", "fee": "8"}]
    now = format_month(_month(0))
    past = await client.post(
        url, json={"effective_month": now, "tiers": tiers}, headers=admin_headers
    )
    assert past.status_code == 400
    assert past.json()["error"]["code"] == "schedule_month_invalid"
    unordered = [
        {"above": "0", "fee": "0"},
        {"above": "150", "fee": "8"},
        {"above": "100", "fee": "9"},
    ]
    invalid = await client.post(
        url,
        json={"effective_month": format_month(_month(1)), "tiers": unordered},
        headers=admin_headers,
    )
    assert invalid.status_code == 422

    body = {"effective_month": format_month(_month(1)), "tiers": tiers}
    assert (await client.post(url, json=body, headers=staff_headers)).status_code == 403
    created = await client.post(url, json=body, headers=admin_headers)
    assert created.status_code == 201, created.text
    assert created.json()["created_by"]["email"]
    assert (await client.post(url, json=body, headers=admin_headers)).status_code == 409

    listing = (await client.get(url, headers=staff_headers)).json()
    assert [s["effective_month"] for s in listing] == [
        format_month(services.DEFAULT_EFFECTIVE),
        format_month(_month(1)),
    ]
    async with SessionLocal() as session:
        schedule = await services.schedule_for(session, _month(1))
    assert schedule.tiers == [
        Tier(above=Decimal("0"), fee=Decimal("0")),
        Tier(above=Decimal("150"), fee=Decimal("8")),
    ]
