from datetime import UTC, datetime, timedelta
from decimal import Decimal

from apps.drivers.models import VehicleType
from apps.rides.models import PaymentMethod, Rating, RatingRole, Ride, RideStatus
from apps.rides.tests.conftest import DROPOFF, PICKUP, make_driver
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind, TopUp, TopUpMethod, TopUpStatus
from conftest import _make_user
from kuulis.core.calendar import local_now
from kuulis.core.db import SessionLocal

API = "/api/v1"
VALENCIA = (39.47, -0.37)


async def _ride(passenger_id, driver_id, status, fare="2.00", where=None, minutes=5) -> Ride:
    now = datetime.now(UTC) - timedelta(minutes=minutes)
    lat, lng = where or (PICKUP["lat"], PICKUP["lng"])
    async with SessionLocal() as session:
        ride = Ride(
            passenger_id=passenger_id,
            driver_id=driver_id,
            status=status,
            vehicle_type=VehicleType.MOTO,
            pickup_lat=lat,
            pickup_lng=lng,
            dropoff_lat=DROPOFF["lat"],
            dropoff_lng=DROPOFF["lng"],
            distance_m=3000,
            duration_s=600,
            fare=Decimal(fare),
            discount=Decimal("0.50") if status == RideStatus.COMPLETED else Decimal("0"),
            surge_multiplier=Decimal("1"),
            payment_method=PaymentMethod.CASH_USD,
            requested_at=now,
            search_expires_at=now,
            assigned_at=now + timedelta(seconds=30) if driver_id else None,
            arrived_at=now + timedelta(seconds=150) if driver_id else None,
            started_at=now + timedelta(seconds=200) if driver_id else None,
            completed_at=now + timedelta(seconds=800) if status == RideStatus.COMPLETED else None,
        )
        session.add(ride)
        await session.commit()
        return ride


async def _seed(client, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ana = await make_driver(client, "ana2@example.com", "Ana Ruiz")
    first = await _ride(passenger.user.id, luis.user.id, RideStatus.COMPLETED, "3.00")
    await _ride(passenger.user.id, luis.user.id, RideStatus.COMPLETED, "2.00")
    await _ride(passenger.user.id, ana.user.id, RideStatus.COMPLETED, "4.00", where=VALENCIA)
    await _ride(passenger.user.id, None, RideStatus.NO_DRIVERS)
    await _ride(passenger.user.id, luis.user.id, RideStatus.CANCELLED_BY_DRIVER)
    await _ride(passenger.user.id, None, RideStatus.SEARCHING, minutes=0)
    async with SessionLocal() as session:
        session.add(
            Rating(
                ride_id=first.id,
                rater_id=passenger.user.id,
                ratee_id=luis.user.id,
                rater_role=RatingRole.PASSENGER,
                stars=4,
                tags=[],
            )
        )
        await session.commit()
    return luis, ana


async def test_metrics(client, staff_headers, admin_headers, passenger):
    luis, _ = await _seed(client, passenger)
    await client.patch(
        f"{API}/admin/config",
        json={
            "service_areas": [
                {
                    "name": "Caracas",
                    "min_lat": 10.3,
                    "max_lat": 10.6,
                    "min_lng": -67.1,
                    "max_lng": -66.7,
                },
                {
                    "name": "Valencia",
                    "min_lat": 39.40,
                    "max_lat": 39.55,
                    "min_lng": -0.45,
                    "max_lng": -0.30,
                },
            ]
        },
        headers=admin_headers,
    )
    response = await client.get(f"{API}/admin/metrics", headers=staff_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    today = str(local_now().date())
    assert body["to"] == today and body["area"] is None
    totals = body["totals"]
    assert totals["rides_requested"] == 6 and totals["rides_completed"] == 3
    assert totals["rides_no_drivers"] == 1 and totals["rides_cancelled_driver"] == 1
    assert totals["completion_rate"] == 0.6  # 3 of 5 finished (one still searching)
    assert (
        totals["gmv"] == "9.00" and totals["discounts"] == "1.50" and totals["avg_fare"] == "3.00"
    )
    assert (
        totals["avg_assign_s"] == 30
        and totals["avg_pickup_s"] == 120
        and totals["avg_trip_s"] == 600
    )
    assert totals["active_drivers"] == 2 and totals["active_passengers"] == 1
    assert totals["avg_rating_drivers"] == 4.0 and totals["avg_rating_passengers"] is None
    day = next(d for d in body["by_day"] if d["date"] == today)
    assert day["requested"] == 6 and day["gmv"] == "9.00" and day["cancelled"] == 1
    assert len(body["by_hour"]) == 24 and sum(h["requested"] for h in body["by_hour"]) == 6
    assert body["top_drivers"][0] == {
        "user_id": luis.id,
        "name": "Luis G.",
        "rides": 2,
        "earnings": "5.00",
        "rating_avg": None,
    }

    valencia = (
        await client.get(f"{API}/admin/metrics?area=valencia", headers=staff_headers)
    ).json()
    assert valencia["area"] == "Valencia" and valencia["totals"]["rides_requested"] == 1
    unknown = await client.get(f"{API}/admin/metrics?area=Madrid", headers=staff_headers)
    assert unknown.json()["error"]["code"] == "area_not_found"
    bad = await client.get(
        f"{API}/admin/metrics",
        params={"from": "2026-10-09", "to": "2026-01-01"},
        headers=staff_headers,
    )
    assert bad.status_code == 422
    assert (await client.get(f"{API}/admin/metrics", headers=passenger.headers)).status_code == 403


async def test_finance_and_csv(client, staff_headers, admin_headers, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    staff = await _make_user("caja@example.com")
    async with SessionLocal() as session:
        entry = await wallet.credit(session, luis.user.id, EntryKind.TOP_UP, Decimal("20"))
        now = datetime.now(UTC)
        session.add_all(
            [
                TopUp(
                    user_id=luis.user.id,
                    status=TopUpStatus.COMPLETED,
                    method=TopUpMethod.BINANCE_PAY,
                    amount=Decimal("20"),
                    transaction_id="T-1",
                    payer_name="Luis",
                    entry_id=entry.id,
                    completed_at=now,
                ),
                TopUp(
                    user_id=None,
                    status=TopUpStatus.UNMATCHED,
                    method=TopUpMethod.BINANCE_PAY,
                    amount=Decimal("7"),
                    transaction_id="T-2",
                    payer_name="Desconocido, S.A.",
                ),
                TopUp(
                    user_id=luis.user.id,
                    status=TopUpStatus.COMPLETED,
                    method=TopUpMethod.BINANCE_PAY,
                    amount=Decimal("5"),
                    reviewed_by_id=staff.id,
                    completed_at=now,
                ),
            ]
        )
        await wallet.credit(session, luis.user.id, EntryKind.TOP_UP, Decimal("5"))
        await session.commit()
    await client.post(
        f"{API}/admin/wallets/{luis.id}/adjust",
        json={"amount": "-2", "reason": "Corrección"},
        headers=admin_headers,
    )

    summary = (await client.get(f"{API}/admin/finance/summary", headers=staff_headers)).json()
    assert summary["top_ups"]["completed"] == {"count": 2, "amount": "25.00"}
    assert summary["top_ups"]["completed_auto"] == {"count": 1, "amount": "20.00"}
    assert summary["top_ups"]["completed_manual"] == {"count": 1, "amount": "5.00"}
    assert summary["top_ups"]["unmatched"] == {"count": 1, "amount": "7.00"}
    assert summary["adjustments"] == {"credit": "0.00", "debit": "2.00"}
    assert summary["wallet_balances"] == "23.00"
    assert summary["fees"] == {"collected": "0.00", "pending": "0.00", "waived_count": 0}
    today = next(d for d in summary["by_day"] if d["date"] == str(local_now().date()))
    assert today["top_ups"] == "25.00"

    entries = await client.get(f"{API}/admin/finance/entries.csv", headers=staff_headers)
    assert entries.status_code == 200
    assert entries.headers["content-type"].startswith("text/csv")
    assert "kuulis-movimientos-" in entries.headers["content-disposition"]
    lines = entries.content.decode("utf-8-sig").strip().splitlines()
    assert lines[0].startswith("fecha,usuario,email,tipo,monto")
    assert len(lines) == 4 and "T-1" in lines[1] and "reason: Corrección" in lines[3]
    only_adjust = await client.get(
        f"{API}/admin/finance/entries.csv?kind=adjustment", headers=staff_headers
    )
    assert len(only_adjust.content.decode("utf-8-sig").strip().splitlines()) == 2

    top_ups = await client.get(f"{API}/admin/finance/top-ups.csv", headers=staff_headers)
    rows = top_ups.content.decode("utf-8-sig").strip().splitlines()
    assert len(rows) == 4 and '"Desconocido, S.A."' in rows[2]
    assert ",auto," in rows[1] and ",manual," in rows[3]


async def test_overview(client, staff_headers, passenger):
    await _seed(client, passenger)
    body = (await client.get(f"{API}/admin/overview", headers=staff_headers)).json()
    assert body["rides_today"] == 6 and body["completed_today"] == 3
    assert body["gmv_today"] == "9.00" and body["rides_in_progress"] == 1
    assert body["online_drivers"] == 0 and body["open_reports"] == 0
    assert isinstance(body["stale_rates"], list)
