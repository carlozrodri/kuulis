from datetime import timedelta
from decimal import Decimal

from sqlalchemy import update

from apps.config.models import AppSetting
from apps.config.services import invalidate_cache
from apps.drivers.models import DriverProfile, VehicleType
from apps.rides import activity
from apps.rides.models import PaymentMethod, Ride, RideStatus
from apps.rides.state import utcnow
from apps.users.models import User
from conftest import _make_user
from kuulis.core.cache import cache_delete
from kuulis.core.db import SessionLocal

from .conftest import DROPOFF, PICKUP, make_driver

API = "/api/v1"
URL = f"{API}/public/rides/activity"


def _encode(points: list[tuple[float, float]]) -> str:
    """Google polyline encoding (precision 5), for the planned route of the test rides."""
    out, last = [], (0, 0)
    for lat, lng in points:
        now = (round(lat * 1e5), round(lng * 1e5))
        for value in (now[0] - last[0], now[1] - last[1]):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        last = now
    return "".join(out)


ROUTE = _encode([(PICKUP["lat"], PICKUP["lng"]), (DROPOFF["lat"], DROPOFF["lng"])])


async def _ride(passenger_id, driver_id, status, *, started_min_ago=None, completed_min_ago=None):
    now = utcnow()
    async with SessionLocal() as session:
        ride = Ride(
            passenger_id=passenger_id,
            driver_id=driver_id,
            status=status,
            vehicle_type=VehicleType.MOTO,
            pickup_lat=PICKUP["lat"],
            pickup_lng=PICKUP["lng"],
            pickup_address=PICKUP["address"],
            dropoff_lat=DROPOFF["lat"],
            dropoff_lng=DROPOFF["lng"],
            dropoff_address=DROPOFF["address"],
            distance_m=3400,
            duration_s=900,
            fare=Decimal("2.00"),
            discount=Decimal("0.20"),
            surge_multiplier=Decimal("1"),
            payment_method=PaymentMethod.CASH_USD,
            polyline=ROUTE,
            requested_at=now - timedelta(minutes=40),
            search_expires_at=now,
            started_at=now - timedelta(minutes=started_min_ago) if started_min_ago else None,
            completed_at=now - timedelta(minutes=completed_min_ago) if completed_min_ago else None,
        )
        session.add(ride)
        await session.commit()
        return ride


async def _threshold(value: int) -> None:
    async with SessionLocal() as session:
        session.add(AppSetting(key="public_activity_min_trips_per_hour", value=value))
        await session.commit()
    await invalidate_cache()


async def _get(client) -> dict:
    await cache_delete(activity.CACHE_KEY)
    response = await client.get(URL)
    assert response.status_code == 200, response.text
    return response.json()


async def test_below_threshold_is_honest(client, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _ride(passenger.user.id, luis.user.id, RideStatus.IN_PROGRESS, started_min_ago=8)

    body = await _get(client)
    assert body["live"] is False
    assert body["threshold"] == 3
    assert body["trips_last_hour"] == 1
    assert body["verified_drivers"] == 1
    assert body["in_progress"] == [] and body["recent"] == []


async def test_live_trips_are_anonymous_and_approximate(client, passenger):
    await _threshold(2)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _ride(passenger.user.id, luis.user.id, RideStatus.IN_PROGRESS, started_min_ago=8)
    await _ride(
        passenger.user.id,
        luis.user.id,
        RideStatus.COMPLETED,
        started_min_ago=30,
        completed_min_ago=12,
    )
    # Just started: still inside the 3-minute delay, so it is not on the map yet.
    eva = await make_driver(client, "eva@example.com", "Eva Díaz")
    other = await _make_user("otro@example.com")
    await _ride(other.id, eva.user.id, RideStatus.IN_PROGRESS, started_min_ago=1)

    body = await _get(client)
    assert body["live"] is True
    assert body["trips_last_hour"] == 3
    [trip] = body["in_progress"]
    assert set(trip) == {"id", "lat", "lng", "distance_m", "fare"}
    assert trip["fare"] == "1.80" and trip["distance_m"] == 3400
    # On the ~200 m grid and away from both ends of the trip.
    assert abs(trip["lat"] / activity.GRID_DEG - round(trip["lat"] / activity.GRID_DEG)) < 1e-6
    assert (trip["lat"], trip["lng"]) != (PICKUP["lat"], PICKUP["lng"])
    assert PICKUP["lat"] < trip["lat"] < DROPOFF["lat"]
    assert body["recent"] == [{"minutes_ago": 10, "distance_m": 3400, "fare": "1.80"}]
    text = str(body)
    for private in ("Luis", "Ana", PICKUP["address"], DROPOFF["address"], luis.id, passenger.id):
        assert private not in text


async def test_test_accounts_and_opted_out_drivers_are_left_out(client, passenger):
    await _threshold(1)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    eva = await make_driver(client, "eva@example.com", "Eva Díaz")
    await _ride(passenger.user.id, luis.user.id, RideStatus.IN_PROGRESS, started_min_ago=8)
    other = await _make_user("otro@example.com")
    await _ride(other.id, eva.user.id, RideStatus.IN_PROGRESS, started_min_ago=8)
    response = await client.patch(
        f"{API}/drivers/me/preferences",
        json={"hide_from_public_activity": True},
        headers=eva.headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["hide_from_public_activity"] is True

    body = await _get(client)
    assert body["trips_last_hour"] == 1
    assert len(body["in_progress"]) == 1

    async with SessionLocal() as session:
        await session.execute(
            update(User).where(User.id == luis.user.id).values(is_test_account=True)
        )
        await session.commit()
    body = await _get(client)
    assert body["live"] is False
    assert body["trips_last_hour"] == 0
    assert body["verified_drivers"] == 1  # Eva still counts: hiding trips is not leaving Kuulis


async def test_admin_can_switch_it_off(client, passenger):
    await _threshold(1)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _ride(passenger.user.id, luis.user.id, RideStatus.IN_PROGRESS, started_min_ago=8)
    async with SessionLocal() as session:
        session.add(AppSetting(key="public_activity_enabled", value=False))
        await session.commit()
    await invalidate_cache()
    assert (await _get(client))["live"] is False


def test_point_along_and_anonymous_id():
    path = [(0.0, 0.0), (0.0, 1.0), (0.0, 3.0)]
    assert activity.point_along(path, 0.5) == (0.0, 1.5)
    assert activity.point_along(path, 0) == (0.0, 0.0)
    assert activity.point_along(path, 1) == (0.0, 3.0)
    ride = Ride(id="00000000-0000-0000-0000-000000000001")
    now = utcnow()
    assert activity.anonymous_id(ride, now) == activity.anonymous_id(ride, now)
    assert activity.anonymous_id(ride, now) != activity.anonymous_id(ride, now + timedelta(hours=1))


async def test_profile_preference_default(client):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    response = await client.get(f"{API}/drivers/me", headers=luis.headers)
    assert response.json()["hide_from_public_activity"] is False
    async with SessionLocal() as session:
        profile = await session.get(DriverProfile, response.json()["id"])
        assert profile is not None and profile.hide_from_public_activity is False
