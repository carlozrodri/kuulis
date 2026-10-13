import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from apps.config.schemas import SafetySettings
from apps.rides import presence
from apps.rides.models import Ride
from apps.rides.tests.conftest import NEAR, go_online, make_driver, request_ride
from apps.safety import services, tasks, track
from apps.safety.models import AlertKind, AlertStatus, RideTrack, SafetyAlert
from conftest import ride_step, set_config
from kuulis.core.db import SessionLocal

API = "/api/v1"


@pytest.fixture(autouse=True)
def team(monkeypatch) -> list[str]:
    """Telegram messages to the team, and realtime events of the safety module."""
    sent: list[str] = []

    async def fake_notify(text: str) -> None:
        sent.append(text)

    async def fake_publish(event, data=None, user_ids=None):
        sent.append(f"publish:{event}:{','.join(user_ids or [])}")

    from apps.monitoring import alerts

    monkeypatch.setattr(alerts, "notify", fake_notify)
    monkeypatch.setattr(services, "publish", fake_publish)
    return sent


async def _assigned(client, passenger, driver) -> dict:
    await go_online(client, driver, NEAR)
    ride = await request_ride(client, passenger)
    response = await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _in_progress(client, passenger, driver) -> str:
    ride_id = (await _assigned(client, passenger, driver))["id"]
    for step in ("arrive", "start"):
        response = await ride_step(client, ride_id, step, driver.headers)
        assert response.status_code == 200, response.text
    return ride_id


# --- Start PIN ---------------------------------------------------------------------------------


async def test_start_pin(client, passenger):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride = await _assigned(client, passenger, driver)
    ride_id = ride["id"]
    assert ride["pin_required"] is True and ride["start_pin"] is None  # the driver's view

    mine = (await client.get(f"{API}/rides/{ride_id}", headers=passenger.headers)).json()
    pin = mine["start_pin"]
    assert mine["pin_required"] and len(pin) == 4 and pin.isdigit()
    wrong = "0000" if pin != "0000" else "1111"

    await client.post(f"{API}/rides/{ride_id}/arrive", headers=driver.headers)
    missing = await client.post(f"{API}/rides/{ride_id}/start", headers=driver.headers)
    assert missing.status_code == 400
    assert missing.json()["error"] == {
        "code": "pin_invalid",
        "message": "The PIN is not correct",
        "details": {"attempts_left": 2},
    }
    bad = await client.post(
        f"{API}/rides/{ride_id}/start", json={"pin": wrong}, headers=driver.headers
    )
    assert bad.status_code == 400 and bad.json()["error"]["details"] == {"attempts_left": 1}
    last = await client.post(
        f"{API}/rides/{ride_id}/start", json={"pin": wrong}, headers=driver.headers
    )
    assert last.status_code == 429 and last.json()["error"]["code"] == "pin_attempts_exceeded"
    locked = await client.post(
        f"{API}/rides/{ride_id}/start", json={"pin": pin}, headers=driver.headers
    )
    assert locked.status_code == 429  # even the right code: call support or cancel

    detail = await client.get(f"{API}/admin/rides/{ride_id}", headers=await _admin(client))
    assert detail.json()["pin_failures"] == 3 and detail.json()["status"] == "driver_arrived"

    # The driver can still cancel the ride.
    cancel = await client.post(f"{API}/rides/{ride_id}/cancel", headers=driver.headers)
    assert cancel.status_code == 200


async def test_right_pin_starts_and_is_hidden_afterwards(client, passenger, recorder):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _in_progress(client, passenger, driver)
    started = (await client.get(f"{API}/rides/{ride_id}", headers=passenger.headers)).json()
    assert started["status"] == "in_progress" and started["start_pin"] is None
    # The driver never receives the code over the socket either.
    for data in recorder.of("ride.updated", driver.id):
        assert data["start_pin"] is None


async def test_no_pin_outside_pin_cities(client, passenger):
    await set_config(safety=SafetySettings(pin_areas=[]).model_dump())
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = (await _assigned(client, passenger, driver))["id"]
    mine = (await client.get(f"{API}/rides/{ride_id}", headers=passenger.headers)).json()
    assert mine["pin_required"] is False and mine["start_pin"] is None
    await client.post(f"{API}/rides/{ride_id}/arrive", headers=driver.headers)
    started = await client.post(f"{API}/rides/{ride_id}/start", headers=driver.headers)
    assert started.status_code == 200


# --- Trusted contacts --------------------------------------------------------------------------


async def test_trusted_contacts(client, passenger):
    url = f"{API}/users/me/trusted-contacts"
    first = await client.post(
        url,
        json={
            "name": " Mamá ",
            "phone": "+584141234567",
            "auto_share": True,
            "auto_share_from": "20:00",
            "auto_share_to": "06:00",
        },
        headers=passenger.headers,
    )
    assert first.status_code == 201, first.text
    assert first.json()["name"] == "Mamá" and first.json()["auto_share_to"] == "06:00"

    half = await client.post(
        url,
        json={"name": "Papá", "phone": "+584141234568", "auto_share_from": "20:00"},
        headers=passenger.headers,
    )
    assert half.status_code == 422
    bad_phone = await client.post(
        url, json={"name": "Papá", "phone": "04141234568"}, headers=passenger.headers
    )
    assert bad_phone.status_code == 422

    for n in range(4):
        response = await client.post(
            url, json={"name": f"Amigo {n}", "phone": f"+58414000000{n}"}, headers=passenger.headers
        )
        assert response.status_code == 201
    sixth = await client.post(
        url, json={"name": "Sexto", "phone": "+584140000009"}, headers=passenger.headers
    )
    assert sixth.status_code == 409 and sixth.json()["error"]["code"] == "too_many_contacts"

    contact_id = first.json()["id"]
    edited = await client.put(
        f"{url}/{contact_id}",
        json={"name": "Mamá Carmen", "phone": "+584141234567", "auto_share": False},
        headers=passenger.headers,
    )
    assert edited.json()["auto_share_from"] is None and edited.json()["name"] == "Mamá Carmen"
    other = await make_driver(client, "luis@example.com", "Luis Gómez")
    assert (await client.delete(f"{url}/{contact_id}", headers=other.headers)).status_code == 404
    assert (
        await client.delete(f"{url}/{contact_id}", headers=passenger.headers)
    ).status_code == 204
    listed = (await client.get(url, headers=passenger.headers)).json()
    assert [c["name"] for c in listed] == [f"Amigo {n}" for n in range(4)]


# --- Live share link and track -----------------------------------------------------------------


async def test_share_link_follows_the_ride_and_expires(client, passenger):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = (await _assigned(client, passenger, driver))["id"]
    shared = await client.post(f"{API}/rides/{ride_id}/share", headers=passenger.headers)
    assert shared.status_code == 200, shared.text
    token = shared.json()["token"]
    assert shared.json()["url"].endswith(f"/v/{token}")
    # The driver can share too.
    assert (
        await client.post(f"{API}/rides/{ride_id}/share", headers=driver.headers)
    ).status_code == 200

    public = await client.get(f"{API}/public/rides/shared/{token}")  # no login
    assert public.status_code == 200, public.text
    body = public.json()
    assert body["status"] == "driver_assigned"
    assert body["driver"]["first_name"] == "Luis" and body["passenger"]["first_name"] == "Ana"
    assert body["vehicle"]["brand"] == "Yamaha" and body["driver_location"] is not None
    assert "id" not in body and "fare" not in body and body["sos"] is False

    await ride_step(client, ride_id, "arrive", driver.headers)
    await ride_step(client, ride_id, "start", driver.headers)
    for lat in (10.4920, 10.4940, 10.4960):
        await _skip_throttle(ride_id)
        await presence.handle_location(driver.id, {"lat": lat, "lng": -66.875})
    moving = (await client.get(f"{API}/public/rides/shared/{token}")).json()
    assert moving["status"] == "in_progress" and moving["eta"] is not None
    assert moving["driver_location"]["lat"] == 10.4960

    await ride_step(client, ride_id, "complete", driver.headers)
    gone = await client.get(f"{API}/public/rides/shared/{token}")
    assert gone.status_code == 410 and gone.json()["error"]["code"] == "share_expired"
    missing = await client.get(f"{API}/public/rides/shared/nope")
    assert missing.status_code == 404
    closed = await client.post(f"{API}/rides/{ride_id}/share", headers=passenger.headers)
    assert closed.status_code == 409

    # The real path was stored when the ride ended, and the admin sees it.
    async with SessionLocal() as session:
        stored = await session.scalar(select(RideTrack).where(RideTrack.ride_id == ride_id))
    assert stored is not None and [p[0] for p in stored.points] == [10.492, 10.494, 10.496]
    detail = await client.get(f"{API}/admin/rides/{ride_id}", headers=await _admin(client))
    assert len(detail.json()["track"]) == 3


async def test_share_is_a_feature_flag(client, passenger, admin_headers):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = (await _assigned(client, passenger, driver))["id"]
    off = await client.put(
        f"{API}/admin/flags/share_live_link",
        json={"enabled": False, "rules": {}},
        headers=admin_headers,
    )
    assert off.status_code == 200, off.text
    refused = await client.post(f"{API}/rides/{ride_id}/share", headers=passenger.headers)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "feature_disabled"


def test_track_thinning():
    now = time.time()
    points = [(10.49, -66.88, now), (10.49001, -66.88, now + 5), (10.4910, -66.88, now + 10)]
    assert track.thin(points) == [[10.49, -66.88, int(now)], [10.491, -66.88, int(now + 10)]]
    assert track.thin([]) == []


# --- SOS ---------------------------------------------------------------------------------------


async def test_sos_reaches_the_team(client, passenger, team):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _in_progress(client, passenger, driver)
    response = await client.post(
        f"{API}/rides/{ride_id}/sos", json={"lat": 10.49, "lng": -66.87}, headers=passenger.headers
    )
    assert response.status_code == 200, response.text
    sos = response.json()
    assert sos["kind"] == "sos" and sos["status"] == "open" and sos["location_seconds"] == 5
    assert "/v/" in sos["share_url"]
    telegram = [t for t in team if t.startswith("🆘")]
    assert len(telegram) == 1 and "Ana Pérez" in telegram[0] and "maps.google.com" in telegram[0]
    again = await client.post(f"{API}/rides/{ride_id}/sos", json={}, headers=passenger.headers)
    assert again.json()["id"] == sos["id"]  # one SOS, no second Telegram
    assert len([t for t in team if t.startswith("🆘")]) == 1

    moved = await client.post(
        f"{API}/safety/location", json={"lat": 10.5, "lng": -66.86}, headers=passenger.headers
    )
    assert moved.status_code == 204
    nothing = await client.post(
        f"{API}/safety/location", json={"lat": 10.5, "lng": -66.86}, headers=driver.headers
    )
    assert nothing.status_code == 404 and nothing.json()["error"]["code"] == "no_active_sos"
    active = (await client.get(f"{API}/safety/alerts/active", headers=passenger.headers)).json()
    assert [a["id"] for a in active] == [sos["id"]]

    # The link keeps working after the ride ends while the SOS is open.
    token = sos["share_url"].rsplit("/", 1)[1]
    await ride_step(client, ride_id, "complete", driver.headers)
    public = (await client.get(f"{API}/public/rides/shared/{token}")).json()
    assert public["sos"] is True and public["sos_location"]["lat"] == 10.5

    # Safety center: badge, list, acknowledge, resolve.
    admin = await _admin(client)
    summary = (await client.get(f"{API}/admin/safety/summary", headers=admin)).json()
    assert summary == {"open": 1, "acknowledged": 0, "latest_id": sos["id"]}
    listed = (await client.get(f"{API}/admin/safety/alerts", headers=admin)).json()
    item = listed["items"][0]
    assert item["raised_by"]["name"] == "Ana Pérez" and item["driver"]["phone"] == "+584121234567"
    assert item["lat"] == 10.5 and item["vehicle"]["plate"]
    ack = await client.post(f"{API}/admin/safety/alerts/{sos['id']}/acknowledge", headers=admin)
    assert ack.json()["status"] == "acknowledged" and ack.json()["handled_by_name"] is not None
    done = await client.post(
        f"{API}/admin/safety/alerts/{sos['id']}/resolve",
        json={"outcome": "false_alarm", "notes": "Llamamos a Ana, todo bien"},
        headers=admin,
    )
    assert done.json()["status"] == "resolved" and done.json()["notes"].startswith("Llamamos")
    assert (await client.get(f"{API}/public/rides/shared/{token}")).status_code == 410
    audit = await client.get(
        f"{API}/admin/audit", params={"action": "safety.resolve"}, headers=admin
    )
    assert audit.json()["total"] == 1


async def test_sos_needs_a_recent_ride_and_can_be_cancelled(client, passenger, team):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _in_progress(client, passenger, driver)
    await ride_step(client, ride_id, "complete", driver.headers)
    sos = await client.post(f"{API}/rides/{ride_id}/sos", headers=driver.headers)
    assert sos.status_code == 200  # within 30 min of the end
    cancelled = await client.post(
        f"{API}/safety/alerts/{sos.json()['id']}/cancel", headers=driver.headers
    )
    assert cancelled.json()["status"] == "resolved"
    assert any("cancelado" in t for t in team)

    async with SessionLocal() as session:
        await session.execute(
            update(Ride)
            .where(Ride.id == ride_id)
            .values(completed_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()
    late = await client.post(f"{API}/rides/{ride_id}/sos", headers=passenger.headers)
    assert late.status_code == 409 and late.json()["error"]["code"] == "sos_closed"
    stranger = await make_driver(client, "eva@example.com", "Eva Ruiz")
    assert (
        await client.post(f"{API}/rides/{ride_id}/sos", headers=stranger.headers)
    ).status_code == 404


async def test_safety_center_permissions(client, user_headers, staff_headers):
    assert (
        await client.get(f"{API}/admin/safety/summary", headers=user_headers)
    ).status_code == 403
    # Plain staff (legacy role in tests) have every permission.
    assert (
        await client.get(f"{API}/admin/safety/summary", headers=staff_headers)
    ).status_code == 200


# --- Anomalies ---------------------------------------------------------------------------------

POLYLINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"  # Google's sample: (38.5,-120.2) ... (43.252,-126.453)


def _ride(**values) -> Ride:
    base = {
        "id": uuid.uuid4(),
        "started_at": datetime.now(UTC) - timedelta(minutes=12),
        "duration_s": 1800,
        "dropoff_lat": 10.50,
        "dropoff_lng": -66.85,
        "polyline": None,
    }
    return Ride(**(base | values))


def test_detect_rules():
    rules = SafetySettings()
    now = time.time()
    stopped = [(10.49, -66.88, now - s) for s in range(660, -1, -5)]
    assert set(services.detect(_ride(), stopped, rules, now)) == {AlertKind.STOP}
    # Stopped at the destination is fine; a short stop is fine.
    at_dropoff = [(10.50, -66.85, t) for _, _, t in stopped]
    assert services.detect(_ride(), at_dropoff, rules, now) == {}
    assert services.detect(_ride(), stopped[-60:], rules, now) == {}

    overtime = _ride(started_at=datetime.now(UTC) - timedelta(minutes=65))
    assert AlertKind.OVERTIME in services.detect(overtime, [], rules, now)
    short = _ride(duration_s=60, started_at=datetime.now(UTC) - timedelta(minutes=4))
    assert services.detect(short, [], rules, now) == {}  # under estimate + 5 min

    on_route = [(38.5 + i * 0.0001, -120.2, now - 200 + i * 5) for i in range(41)]
    off_route = [(38.4, -120.2 - i * 0.0001, now - 200 + i * 5) for i in range(41)]
    with_route = _ride(polyline=POLYLINE, dropoff_lat=43.25, dropoff_lng=-126.45)
    assert AlertKind.DEVIATION not in services.detect(with_route, on_route, rules, now)
    found = services.detect(with_route, off_route, rules, now)
    assert found[AlertKind.DEVIATION]["distance_m"] > 600


async def _stop_ride(ride_id: str, minutes: int) -> None:
    now = time.time()
    from kuulis.core.redis import redis_client

    key = track.track_key(ride_id)
    await redis_client.delete(key)
    for s in range(minutes * 60, -1, -5):
        await redis_client.rpush(key, f"10.4900,-66.8800,{now - s:.0f}")


async def test_stop_asks_and_escalates_without_answer(client, passenger, team, recorder):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _in_progress(client, passenger, driver)
    await _stop_ride(ride_id, 11)

    assert await tasks.run_once() is True
    assert await tasks.run_once() is False  # another process holds this round
    async with SessionLocal() as session:
        alert = await session.scalar(select(SafetyAlert).where(SafetyAlert.ride_id == ride_id))
    assert alert.kind == AlertKind.STOP and alert.status == AlertStatus.CHECKING
    assert f"publish:safety.check_in:{passenger.id}" in team
    assert f"publish:safety.check_in:{driver.id}" in team
    for who in (passenger, driver):
        pending = (await client.get(f"{API}/safety/alerts/active", headers=who.headers)).json()
        assert [a["id"] for a in pending] == [str(alert.id)]
    assert not [t for t in team if t.startswith("⚠️")]  # the team is not bothered yet

    # The driver answering "ok" is not enough; the deadline passes.
    ok = await client.post(f"{API}/safety/alerts/{alert.id}/ok", headers=driver.headers)
    assert ok.json()["status"] == "checking"
    async with SessionLocal() as session:
        await session.execute(
            update(SafetyAlert)
            .where(SafetyAlert.id == alert.id)
            .values(check_in_deadline=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
        escalated = await services.escalate_due(session)
    assert [a.id for a in escalated] == [alert.id]
    warning = [t for t in team if t.startswith("⚠️")]
    assert len(warning) == 1 and "nadie respondió" in warning[0]
    # Only one anomaly of each kind per ride.
    async with SessionLocal() as session:
        assert await services.check_rides(session) == []


async def test_check_in_answers(client, passenger, team):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _in_progress(client, passenger, driver)
    await _stop_ride(ride_id, 11)
    async with SessionLocal() as session:
        [alert] = await services.check_rides(session)

    stranger = await make_driver(client, "eva@example.com", "Eva Ruiz")
    assert (
        await client.post(f"{API}/safety/alerts/{alert.id}/ok", headers=stranger.headers)
    ).status_code == 404
    ok = await client.post(f"{API}/safety/alerts/{alert.id}/ok", headers=passenger.headers)
    assert ok.json()["status"] == "dismissed"
    again = await client.post(f"{API}/safety/alerts/{alert.id}/help", headers=passenger.headers)
    assert again.status_code == 409

    # "Necesito ayuda" goes to the team at once.
    async with SessionLocal() as session:
        await session.execute(
            update(Ride)
            .where(Ride.id == ride_id)
            .values(started_at=datetime.now(UTC) - timedelta(hours=2))
        )
        await session.commit()
        created = await services.check_rides(session)
    assert [a.kind for a in created] == [AlertKind.OVERTIME]
    help_ = await client.post(
        f"{API}/safety/alerts/{created[0].id}/answer",
        json={"answer": "help"},
        headers=driver.headers,
    )
    assert help_.json()["status"] == "open"
    assert any("pidió ayuda" in t for t in team)


async def _skip_throttle(ride_id: str) -> None:
    from kuulis.core.redis import redis_client

    await redis_client.delete(f"{track.PREFIX}:track_thr:{ride_id}")
    stale = time.time() - presence.MIN_LOCATION_INTERVAL - 1
    await redis_client.hset(
        presence.LOC_KEY,
        str(await _driver_of(ride_id)),
        f'{{"lat": 0, "lng": 0, "heading": null, "speed": null, "ts": {stale}}}',
    )


async def _driver_of(ride_id: str) -> uuid.UUID:
    async with SessionLocal() as session:
        return await session.scalar(select(Ride.driver_id).where(Ride.id == ride_id))


async def _admin(client) -> dict[str, str]:
    from apps.users.models import Role
    from conftest import _login, _make_user

    email = f"admin-{uuid.uuid4().hex[:6]}@example.com"
    await _make_user(email, Role.ADMIN)
    return await _login(client, email)


async def test_privacy_export_lists_contacts(client, passenger):
    await client.post(
        f"{API}/users/me/trusted-contacts",
        json={"name": "Mamá", "phone": "+584141234567"},
        headers=passenger.headers,
    )
    from apps.privacy import services as privacy
    from apps.users.models import User

    async with SessionLocal() as session:
        user = await session.get(User, passenger.user.id)
        data = await privacy.export_data(session, user)
    assert data["trusted_contacts"] == [
        {"name": "Mamá", "phone": "+584141234567", "auto_share": False}
    ]
