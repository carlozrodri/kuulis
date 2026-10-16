"""Idempotency-Key on ride actions (doc 20): a retry never does the action twice."""

import asyncio

from sqlalchemy import func, select

from apps.rides.models import RideMessage
from conftest import ride_step
from kuulis.core import idempotency
from kuulis.core.db import SessionLocal

from .conftest import NEAR, go_online, make_driver, request_ride

API = "/api/v1"


def _key(headers: dict[str, str], key: str) -> dict[str, str]:
    return {**headers, "Idempotency-Key": key}


def test_applies_only_to_listed_writes():
    ride = "/api/v1/rides/0b6f7c8e-1d2a-4c3b-9e8f-112233445566"
    assert idempotency.applies("POST", "/api/v1/rides")
    assert idempotency.applies("POST", f"{ride}/complete")
    assert idempotency.applies("POST", f"{ride}/rating")
    assert idempotency.applies("POST", "/api/v1/wallet/me/transfers")
    assert not idempotency.applies("GET", f"{ride}/messages")
    assert not idempotency.applies("POST", "/api/v1/rides/quote")
    assert not idempotency.applies("POST", "/api/v1/auth/login")


async def _assigned(client, passenger) -> tuple[dict, object]:
    driver = await make_driver(client, "moto@example.com", "Luis Moto")
    await go_online(client, driver, NEAR)
    ride = await request_ride(client, passenger)
    response = await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    assert response.status_code == 200, response.text
    return ride, driver


async def test_retried_complete_is_replayed(client, passenger, recorder):
    ride, driver = await _assigned(client, passenger)
    for step in ("arrive", "start"):
        response = await ride_step(client, ride["id"], step, _key(driver.headers, f"k-{step}"))
        assert response.status_code == 200, response.text

    url = f"{API}/rides/{ride['id']}/complete"
    first = await client.post(url, headers=_key(driver.headers, "k-complete"))
    assert first.status_code == 200, first.text
    updates = len(recorder.of("ride.updated"))

    # The answer was lost: the app sends the same request again.
    again = await client.post(url, headers=_key(driver.headers, "k-complete"))
    assert again.status_code == 200
    assert again.headers["idempotent-replayed"] == "true"
    assert again.json() == first.json()
    assert len(recorder.of("ride.updated")) == updates


async def test_chat_message_is_sent_once(client, passenger):
    ride, _ = await _assigned(client, passenger)
    url = f"{API}/rides/{ride['id']}/messages"
    headers = _key(passenger.headers, "msg-1")
    responses = [
        await client.post(url, json={"text": "Voy bajando"}, headers=headers) for _ in range(3)
    ]
    assert [r.status_code for r in responses] == [201, 201, 201]
    assert len({r.json()["id"] for r in responses}) == 1
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(RideMessage))
    assert count == 1


async def test_key_reused_with_another_body(client, passenger):
    ride, _ = await _assigned(client, passenger)
    url = f"{API}/rides/{ride['id']}/messages"
    headers = _key(passenger.headers, "msg-2")
    assert (await client.post(url, json={"text": "Hola"}, headers=headers)).status_code == 201
    response = await client.post(url, json={"text": "Otro texto"}, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "idempotency_key_reused"


async def test_keys_are_per_user(client, passenger):
    ride, driver = await _assigned(client, passenger)
    url = f"{API}/rides/{ride['id']}/messages"
    a = await client.post(url, json={"text": "Hola"}, headers=_key(passenger.headers, "same"))
    b = await client.post(url, json={"text": "Hola"}, headers=_key(driver.headers, "same"))
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
    assert "idempotent-replayed" not in b.headers


async def test_errors_are_not_kept(client, passenger):
    ride, driver = await _assigned(client, passenger)
    url = f"{API}/rides/{ride['id']}/complete"
    # Completing before starting fails; once started, the same key runs for real.
    early = await client.post(url, headers=_key(driver.headers, "k"))
    assert early.status_code == 409
    for step in ("arrive", "start"):
        assert (await ride_step(client, ride["id"], step, driver.headers)).status_code == 200
    done = await client.post(url, headers=_key(driver.headers, "k"))
    assert done.status_code == 200
    assert done.json()["status"] == "completed"


async def test_same_key_while_running(client, passenger, monkeypatch):
    ride, _ = await _assigned(client, passenger)
    url = f"{API}/rides/{ride['id']}/messages"
    headers = _key(passenger.headers, "slow")
    first_request = asyncio.Event()
    release = asyncio.Event()
    inner = idempotency.IdempotencyMiddleware._run

    async def slow_run(self, scope, receive, send, redis_key, fingerprint):
        first_request.set()
        await release.wait()
        await inner(self, scope, receive, send, redis_key, fingerprint)

    monkeypatch.setattr(idempotency.IdempotencyMiddleware, "_run", slow_run)
    running = asyncio.create_task(client.post(url, json={"text": "Hola"}, headers=headers))
    await first_request.wait()
    second = await client.post(url, json={"text": "Hola"}, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_in_progress"
    release.set()
    assert (await running).status_code == 201


async def test_invalid_key(client, passenger):
    response = await client.post(
        f"{API}/rides", json={}, headers=_key(passenger.headers, "x" * 300)
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "idempotency_key_invalid"
