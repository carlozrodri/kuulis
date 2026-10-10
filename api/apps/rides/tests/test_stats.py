from datetime import timedelta
from decimal import Decimal

from apps.drivers.models import VehicleType
from apps.rides.models import PaymentMethod, Ride, RideStatus
from apps.rides.state import utcnow
from kuulis.core.calendar import local_now
from kuulis.core.db import SessionLocal

from .conftest import DROPOFF, PICKUP, make_driver

API = "/api/v1"


async def _ride(
    passenger_id,
    driver_id,
    fare,
    discount="0",
    days_ago=0,
    status=RideStatus.COMPLETED,
    dropoff=DROPOFF,
):
    when = utcnow() - timedelta(days=days_ago, minutes=1)
    async with SessionLocal() as session:
        session.add(
            Ride(
                passenger_id=passenger_id,
                driver_id=driver_id,
                status=status,
                vehicle_type=VehicleType.MOTO,
                pickup_lat=PICKUP["lat"],
                pickup_lng=PICKUP["lng"],
                dropoff_lat=dropoff["lat"],
                dropoff_lng=dropoff["lng"],
                dropoff_address=dropoff["address"],
                distance_m=3000,
                duration_s=600,
                fare=Decimal(fare),
                discount=Decimal(discount),
                surge_multiplier=Decimal("1"),
                payment_method=PaymentMethod.CASH_USD,
                requested_at=when,
                search_expires_at=when,
                completed_at=when if status == RideStatus.COMPLETED else None,
            )
        )
        await session.commit()


async def test_driver_stats(client, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _ride(passenger.user.id, luis.user.id, "3.00", discount="0.50")
    await _ride(passenger.user.id, luis.user.id, "2.00")
    await _ride(passenger.user.id, luis.user.id, "4.00", days_ago=1)
    await _ride(passenger.user.id, luis.user.id, "9.00", status=RideStatus.CANCELLED_BY_DRIVER)

    response = await client.get(f"{API}/drivers/me/stats", headers=luis.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["today"] == {"rides": 2, "earnings": "4.50"}
    assert body["yesterday"] == {"rides": 1, "earnings": "4.00"}
    today = local_now().date()
    in_week = today.weekday() > 0
    in_month = today.day > 1
    assert body["week"] == {"rides": 3 if in_week else 2, "earnings": "8.50" if in_week else "4.50"}
    assert body["month"]["rides"] == (3 if in_month else 2)
    assert len(body["by_day"]) == 7 and body["by_day"][-1]["date"] == str(today)
    assert body["by_day"][-1]["earnings"] == "4.50" and body["by_day"][-2]["rides"] == 1
    assert body["total_rides"] == 3 and body["rating"] is None

    empty = (await client.get(f"{API}/drivers/me/stats", headers=passenger.headers)).json()
    assert empty["today"] == {"rides": 0, "earnings": "0.00"} and empty["total_rides"] == 0


async def test_passenger_stats(client, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    office = {"lat": 10.4806, "lng": -66.9036, "address": "Torre Británica"}
    await _ride(passenger.user.id, luis.user.id, "3.00", discount="0.50")
    await _ride(passenger.user.id, luis.user.id, "2.00", days_ago=3)
    await _ride(passenger.user.id, luis.user.id, "4.00", days_ago=1, dropoff=office)
    await _ride(passenger.user.id, luis.user.id, "9.00", status=RideStatus.CANCELLED_BY_DRIVER)

    response = await client.get(f"{API}/rides/me/stats", headers=passenger.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rides"] == 3 and body["distance_m"] == 9000 and body["spent"] == "8.50"
    assert [(p["address"], p["rides"]) for p in body["frequent_places"]] == [
        (DROPOFF["address"], 2),
        (office["address"], 1),
    ]
    assert body["frequent_places"][1]["lat"] == office["lat"]

    # The driver's own rides as a driver don't count as a passenger.
    empty = (await client.get(f"{API}/rides/me/stats", headers=luis.headers)).json()
    assert empty == {"rides": 0, "distance_m": 0, "spent": "0.00", "frequent_places": []}
