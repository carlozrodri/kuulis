from datetime import UTC, datetime, timedelta

import pytest

from apps.control import services
from apps.control.flags import Audience, bucket, evaluate
from apps.monitoring import stats
from apps.rides import dispatch, presence
from apps.rides.tests.conftest import (
    DROPOFF,
    NEAR,
    PICKUP,
    go_online,
    make_driver,
    request_ride,
)
from apps.users.models import Role
from conftest import _login, _make_user, make_staff_role, ride_step

API = "/api/v1"
CARACAS = {"lat": PICKUP["lat"], "lng": PICKUP["lng"]}
MESSAGE = {"es": "Volvemos pronto", "en": "Back soon"}


async def _status(client, headers, maintenance=None, pauses=()) -> dict:
    body = {
        "maintenance": maintenance or {"enabled": False},
        "area_pauses": list(pauses),
    }
    response = await client.put(f"{API}/admin/app/status", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _quote(client, actor):
    return await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=actor.headers,
    )


async def _bootstrap(client, headers=None, **params) -> dict:
    response = await client.get(f"{API}/app/bootstrap", params=params, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def updates(monkeypatch) -> list:
    sent: list = []

    async def fake_publish(event, data=None, user_ids=None):
        sent.append((event, data, user_ids))

    monkeypatch.setattr(services, "publish", fake_publish)
    monkeypatch.setattr(dispatch, "publish", fake_publish)
    return sent


async def test_maintenance_and_city_pause(client, admin_headers, passenger, updates):
    driver = await make_driver(client, "moto@example.com", "Luis")
    await go_online(client, driver, NEAR)
    ride = await request_ride(client, passenger)

    status = await _status(
        client,
        admin_headers,
        {"enabled": True, "message": MESSAGE, "eta": "2026-10-12T20:00:00Z", "areas": ["Caracas"]},
    )
    assert status["areas"] == ["Caracas"] and status["maintenance"]["enabled"] is True
    quote = await _quote(client, passenger)
    assert quote.status_code == 503
    error = quote.json()["error"]
    assert error["code"] == "service_paused"
    assert error["details"]["kind"] == "maintenance" and error["details"]["area"] == "Caracas"
    assert error["details"]["message"] == MESSAGE
    assert quote.headers["x-planned-outage"] == "1"
    assert (await stats.http_totals(2))["errors"] == 0  # planned: no 5xx alert

    # The ride already searching goes on, and the driver keeps it until it ends.
    accepted = await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    assert accepted.status_code == 200, accepted.text
    assert await presence.is_online(driver.id)
    for step in ("arrive", "start", "complete"):
        response = await ride_step(client, ride["id"], step, driver.headers)
        assert response.status_code == 200, response.text
    assert await dispatch.offline_paused() == [driver.id]
    paused = [(d, u) for e, d, u in updates if e == dispatch.PAUSED_EVENT]
    assert paused == [({**error["details"], "eta": "2026-10-12T20:00:00Z"}, [driver.id])]
    assert not await presence.is_online(driver.id)
    online = await client.post(
        f"{API}/drivers/me/online", json={"lat": NEAR[0], "lng": NEAR[1]}, headers=driver.headers
    )
    assert online.status_code == 503 and online.json()["error"]["code"] == "service_paused"

    boot = await _bootstrap(client, passenger.headers, **CARACAS)
    assert boot["area"] == "Caracas" and boot["maintenance"] is None
    assert boot["service"]["kind"] == "maintenance"
    assert [n["area"] for n in boot["paused_areas"]] == ["Caracas"]
    assert (await _bootstrap(client))["service"] is None  # unknown place: only global applies

    # A city pause instead: its own message, same block.
    await _status(client, admin_headers, pauses=[{"area": "Caracas", "message": MESSAGE}])
    error = (await _quote(client, passenger)).json()["error"]
    assert error["code"] == "service_paused" and error["details"]["kind"] == "pause"
    bad = await client.put(
        f"{API}/admin/app/status",
        json={"maintenance": {"enabled": False}, "area_pauses": [{"area": "Maracaibo"}]},
        headers=admin_headers,
    )
    assert bad.status_code == 422

    # Global maintenance: the app shows its maintenance screen everywhere.
    await _status(client, admin_headers, {"enabled": True, "message": MESSAGE})
    boot = await _bootstrap(client)
    assert boot["maintenance"]["kind"] == "maintenance" and boot["service"] is not None

    await _status(client, admin_headers)
    assert (await _quote(client, passenger)).status_code == 200
    assert (
        sum(e == services.CONFIG_UPDATED for e, *_ in updates) == 4
    )  # one config.updated per change: the apps read the bootstrap again


async def test_status_permissions(client):
    role = await make_staff_role("lector", ["app_status.view"])
    await _make_user("ops@example.com", Role.STAFF, staff_role=role)
    headers = await _login(client, "ops@example.com")
    assert (await client.get(f"{API}/admin/app/status", headers=headers)).status_code == 200
    response = await client.put(
        f"{API}/admin/app/status",
        json={"maintenance": {"enabled": True}, "area_pauses": []},
        headers=headers,
    )
    assert response.status_code == 403


def test_flag_rules():
    row = {"enabled": True, "rules": {"percent": 20}}
    ids = [f"user-{n}" for n in range(1000)]
    hits = [evaluate("chat", row, Audience(ident=i)) for i in ids]
    assert 150 < sum(hits) < 250
    assert hits == [evaluate("chat", row, Audience(ident=i)) for i in ids]  # stable
    assert evaluate("chat", row, Audience()) is False  # no id: not in a partial rollout
    assert 0 <= bucket("chat", "x") < 100

    rules = {"platforms": ["android"], "min_build": 7, "roles": ["driver"], "areas": ["Caracas"]}
    row = {"enabled": True, "rules": rules}
    assert evaluate("chat", row, Audience(platform="android", build=7, role="driver"))
    assert not evaluate("chat", row, Audience(platform="ios"))
    assert not evaluate("chat", row, Audience(build=6))
    assert not evaluate("chat", row, Audience(role="passenger"))
    assert not evaluate("chat", row, Audience(area="Valencia"))
    assert evaluate("chat", row, Audience())  # unknown facts do not exclude
    assert not evaluate("chat", {"enabled": False, "rules": {}}, Audience())
    assert evaluate("chat", None, Audience()) and evaluate("share_live_link", None, Audience())


async def test_flags(client, admin_headers, passenger):
    flags = (await client.get(f"{API}/admin/flags", headers=admin_headers)).json()
    chat = next(f for f in flags if f["key"] == "chat")
    assert chat["enabled"] is True and chat["changed"] is False
    assert (await _bootstrap(client, passenger.headers))["flags"]["chat"] is True

    response = await client.put(
        f"{API}/admin/flags/chat", json={"enabled": False}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["changed"] is True
    assert (await _bootstrap(client, passenger.headers))["flags"]["chat"] is False

    driver = await make_driver(client, "moto@example.com", "Luis")
    await go_online(client, driver, NEAR)
    ride = await request_ride(client, passenger)
    await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    message = await client.post(
        f"{API}/rides/{ride['id']}/messages", json={"text": "Hola"}, headers=passenger.headers
    )
    assert message.status_code == 403 and message.json()["error"]["code"] == "feature_disabled"

    # Only drivers on recent builds.
    rules = {"roles": ["driver"], "min_build": 10}
    await client.put(
        f"{API}/admin/flags/chat", json={"enabled": True, "rules": rules}, headers=admin_headers
    )
    boot = await _bootstrap(client, passenger.headers, mode="passenger")
    assert boot["flags"]["chat"] is False
    old = {**driver.headers, "X-App-Platform": "android", "X-App-Build": "9"}
    assert (await _bootstrap(client, old, mode="driver"))["flags"]["chat"] is False
    new = {**driver.headers, "X-App-Platform": "android", "X-App-Build": "10"}
    assert (await _bootstrap(client, new, mode="driver"))["flags"]["chat"] is True
    check = await client.get(
        f"{API}/admin/flags/chat/check", params={"email": "moto@example.com"}, headers=admin_headers
    )
    assert check.json() == {"email": "moto@example.com", "role": "driver", "enabled": True}
    check = await client.get(
        f"{API}/admin/flags/chat/check", params={"email": "ana@example.com"}, headers=admin_headers
    )
    assert check.json()["role"] == "passenger" and check.json()["enabled"] is False

    assert (
        await client.put(f"{API}/admin/flags/nope", json={"enabled": True}, headers=admin_headers)
    ).status_code == 404
    bad_area = {"enabled": True, "rules": {"areas": ["Maracaibo"]}}
    assert (
        await client.put(f"{API}/admin/flags/chat", json=bad_area, headers=admin_headers)
    ).status_code == 422

    # Promotions and transfers off: the API refuses them too.
    await client.put(
        f"{API}/admin/flags/promotions", json={"enabled": False}, headers=admin_headers
    )
    await client.put(f"{API}/admin/flags/transfers", json={"enabled": False}, headers=admin_headers)
    with_code = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto", "promo_code": "HOLA"},
        headers=passenger.headers,
    )
    assert with_code.json()["error"]["code"] == "feature_disabled"
    assert (await _quote(client, passenger)).status_code == 200
    transfer = await client.post(
        f"{API}/wallet/me/transfers",
        json={"to_user_id": passenger.id, "amount": "1.00"},
        headers=driver.headers,
    )
    assert transfer.status_code == 403 and transfer.json()["error"]["code"] == "feature_disabled"


async def test_announcements(client, admin_headers, passenger):
    now = datetime.now(UTC)
    body = {
        "title": {"es": "Lluvia en Caracas", "en": "Rain in Caracas"},
        "body": {"es": "Maneja con cuidado", "en": "Ride safe"},
        "target": {"roles": ["passenger"], "areas": ["Caracas"]},
        "cta": {"label": {"es": "Ver", "en": "See"}, "screen": "wallet"},
        "starts_at": (now + timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(hours=3)).isoformat(),
        "style": "warning",
    }
    created = await client.post(f"{API}/admin/announcements", json=body, headers=admin_headers)
    assert created.status_code == 201, created.text
    item = created.json()
    boot = await _bootstrap(client, passenger.headers, mode="passenger", **CARACAS)
    assert boot["announcements"] == []  # scheduled for later

    body["starts_at"] = (now - timedelta(minutes=1)).isoformat()
    updated = await client.put(
        f"{API}/admin/announcements/{item['id']}", json=body, headers=admin_headers
    )
    assert updated.status_code == 200, updated.text
    boot = await _bootstrap(client, passenger.headers, mode="passenger", **CARACAS)
    assert [a["id"] for a in boot["announcements"]] == [item["id"]]
    assert boot["announcements"][0]["cta"]["screen"] == "wallet"
    assert (await _bootstrap(client, passenger.headers, mode="driver", **CARACAS))[
        "announcements"
    ] == []
    assert (await _bootstrap(client, passenger.headers, mode="passenger"))["announcements"] == []

    dismissed = await client.post(
        f"{API}/app/announcements/{item['id']}/dismiss", headers=passenger.headers
    )
    assert dismissed.status_code == 204
    boot = await _bootstrap(client, passenger.headers, mode="passenger", **CARACAS)
    assert boot["announcements"] == []
    listed = (await client.get(f"{API}/admin/announcements", headers=admin_headers)).json()
    assert (listed[0]["seen"], listed[0]["dismissed"]) == (1, 1)
    assert (
        await client.post(f"{API}/app/announcements/{item['id']}/dismiss")
    ).status_code == 400  # no account and no device id

    body["ends_at"] = body["starts_at"]
    assert (
        await client.post(f"{API}/admin/announcements", json=body, headers=admin_headers)
    ).status_code == 422
    body["ends_at"] = (now + timedelta(hours=1)).isoformat()
    body["cta"] = {"label": {"es": "Ver"}, "url": "https://kuulis.app", "screen": "wallet"}
    assert (
        await client.post(f"{API}/admin/announcements", json=body, headers=admin_headers)
    ).status_code == 422

    deleted = await client.delete(f"{API}/admin/announcements/{item['id']}", headers=admin_headers)
    assert deleted.status_code == 204
    assert (await client.get(f"{API}/admin/announcements", headers=admin_headers)).json() == []


async def test_remote_settings(client, admin_headers):
    boot = await _bootstrap(client)
    assert boot["links"]["emergency_number"] == "911"
    assert boot["location_intervals"] == {"online_seconds": 10, "on_ride_seconds": 4}
    assert boot["refresh_seconds"] == services.REFRESH_SECONDS and boot["min_build"] == 0
    response = await client.patch(
        f"{API}/admin/config",
        json={"app_links": {"support_whatsapp": "+584121112233", "emergency_number": "171"}},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    links = (await _bootstrap(client))["links"]
    assert links["support_whatsapp"] == "+584121112233" and links["emergency_number"] == "171"
