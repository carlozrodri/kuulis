import time
from datetime import date, timedelta
from typing import Any

import orjson
import pytest
from sqlalchemy import update

from apps.drivers.models import DriverProfile, DriverStatus, Vehicle, VehicleType
from apps.rides import events, notify, presence
from apps.rides.models import RideOffer
from conftest import _login, _make_user
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client
from kuulis.settings import settings

PICKUP = {"lat": 10.4900, "lng": -66.8800, "address": "Plaza Altamira"}
DROPOFF = {"lat": 10.5000, "lng": -66.8500, "address": "Los Dos Caminos"}
NEAR = (10.4910, -66.8800)  # ~110 m from the pickup
MID = (10.5050, -66.8800)  # ~1.7 km
FAR = (10.5250, -66.8800)  # ~3.9 km (second radius)


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any, list[str] | None]] = []
        self.pushes: list[tuple[str, str, str]] = []  # (user_id, locale, event)

    def of(self, event: str, user_id: str | None = None) -> list[Any]:
        return [
            data
            for name, data, users in self.events
            if name == event and (user_id is None or (users and user_id in users))
        ]

    def pushed(self, event: str, user_id: str | None = None) -> bool:
        return any(e == event and (user_id is None or u == user_id) for u, _, e in self.pushes)


@pytest.fixture(autouse=True)
def recorder(monkeypatch) -> Recorder:
    rec = Recorder()

    async def fake_publish(event, data=None, user_ids=None):
        rec.events.append((event, data, user_ids))

    async def fake_push(user_id, locale, event, ride_id, options=None, **values):
        notify.render(event, locale, **values)  # templates must format
        rec.pushes.append((str(user_id), locale, event))

    monkeypatch.setattr(events, "publish", fake_publish)
    monkeypatch.setattr(presence, "publish", fake_publish)
    monkeypatch.setattr(notify, "push", fake_push)
    monkeypatch.setattr(settings, "OSRM_URL", "")
    monkeypatch.setattr(settings, "PHOTON_URL", "")
    return rec


class Actor:
    def __init__(self, user, headers: dict[str, str]) -> None:
        self.user = user
        self.id = str(user.id)
        self.headers = headers


@pytest.fixture
async def passenger(client) -> Actor:
    user = await _make_user("ana@example.com")
    async with SessionLocal() as session:
        await session.execute(
            update(type(user)).where(type(user).id == user.id).values(full_name="Ana Pérez")
        )
        await session.commit()
    return Actor(user, await _login(client, "ana@example.com"))


_plates = iter(range(100, 999))


async def make_driver(
    client, email: str, name: str, status: DriverStatus = DriverStatus.APPROVED
) -> Actor:
    user = await _make_user(email)
    async with SessionLocal() as session:
        await session.execute(
            update(type(user)).where(type(user).id == user.id).values(full_name=name)
        )
        number = next(_plates)
        profile = DriverProfile(
            user_id=user.id,
            status=status,
            birth_date=date(1990, 1, 1),
            national_id=f"V{10000000 + number}",
            rif=f"V{100000000 + number}",
            phone="+584121234567",
        )
        session.add(profile)
        await session.flush()
        session.add(
            Vehicle(
                driver_id=profile.id,
                type=VehicleType.MOTO,
                brand="Yamaha",
                model="YBR 125",
                year=2019,
                plate=f"AB{number}CD",
                color="Negra",
            )
        )
        await session.commit()
    return Actor(user, await _login(client, email))


async def go_online(client, driver: Actor, point: tuple[float, float]) -> None:
    response = await client.post(
        "/api/v1/drivers/me/online",
        json={"lat": point[0], "lng": point[1]},
        headers=driver.headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["online"] is True


async def request_ride(client, passenger: Actor, payment: str = "cash_usd") -> dict:
    quote = await client.post(
        "/api/v1/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    assert quote.status_code == 200, quote.text
    response = await client.post(
        "/api/v1/rides",
        json={"quote_id": quote.json()["quote_id"], "payment_method": payment},
        headers=passenger.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def expire_offers(ride_id: str) -> None:
    """Moves every open offer of the ride into the past (as if the timeout passed)."""
    async with SessionLocal() as session:
        await session.execute(
            update(RideOffer)
            .where(RideOffer.ride_id == ride_id)
            .values(expires_at=RideOffer.expires_at - timedelta(minutes=5))
        )
        await session.commit()


async def age_location(driver: Actor, seconds: int) -> None:
    loc = await presence.get_location(driver.id)
    assert loc is not None
    await redis_client.hset(
        presence.LOC_KEY,
        driver.id,
        orjson.dumps(
            {
                "lat": loc.lat,
                "lng": loc.lng,
                "heading": None,
                "speed": None,
                "ts": time.time() - seconds,
            }
        ).decode(),
    )
