import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.rides import dispatch
from apps.rides.models import Ride, RideStatus
from apps.rides.state import utcnow
from apps.rides.tests.conftest import (
    DROPOFF,
    NEAR,
    PICKUP,
    go_online,
    make_driver,
)
from apps.zones import demand, geometry, tasks
from conftest import make_staff_role, set_config
from kuulis.core.db import SessionLocal

API = "/api/v1"


def box(lat: float, lng: float, half: float = 0.003) -> list[list[float]]:
    """A small square around a point (~330 m each side of it)."""
    return [
        [lat - half, lng - half],
        [lat - half, lng + half],
        [lat + half, lng + half],
        [lat + half, lng - half],
    ]


async def quote(client, actor, pickup=PICKUP, dropoff=DROPOFF):
    return await client.post(
        f"{API}/rides/quote",
        json={"pickup": pickup, "dropoff": dropoff, "vehicle_type": "moto"},
        headers=actor.headers,
    )


async def create_zone(client, headers, **body):
    payload = {"city": "Caracas", "rules": {}} | body
    response = await client.post(f"{API}/admin/zones", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Geometry ------------------------------------------------------------------------------------


def test_point_in_polygon_and_validation():
    triangle = [(0.0, 0.0), (0.0, 10.0), (10.0, 0.0)]
    assert geometry.contains(triangle, 1, 1)
    assert geometry.contains(triangle, 0, 5)  # on the border
    assert not geometry.contains(triangle, 6, 6)
    assert geometry.problem(triangle) is None
    assert (
        geometry.problem([(0, 0), (1, 1), (0, 1), (1, 0)]) == "the polygon edges cross each other"
    )
    assert geometry.problem([(0, 0), (0, 1), (0, 0)]) is not None
    assert geometry.ring([[1, 2], [3, 4], [5, 6], [1, 2]]) == [(1, 2), (3, 4), (5, 6)]


# --- Cities as polygons --------------------------------------------------------------------------


async def test_city_polygon_rejects_origins_inside_the_old_box(client, admin_headers, passenger):
    assert (await quote(client, passenger)).status_code == 200
    # A polygon that covers the dropoff but leaves the pickup out (both inside the old box).
    polygon = [[10.45, -66.87], [10.45, -66.80], [10.55, -66.80], [10.55, -66.87]]
    response = await client.put(
        f"{API}/admin/zones/cities/Caracas", json={"polygon": polygon}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    city = response.json()
    assert city["polygon"] == polygon
    assert (city["min_lat"], city["max_lng"]) == (10.45, -66.80)

    refused = await quote(client, passenger)
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "outside_service_area"

    # Back to the box: the old rectangle is the polygon's, so widen it again via the settings.
    reset = await client.put(
        f"{API}/admin/zones/cities/Caracas", json={"polygon": None}, headers=admin_headers
    )
    assert reset.json()["polygon"] is None
    unknown = await client.put(
        f"{API}/admin/zones/cities/Madrid", json={"polygon": polygon}, headers=admin_headers
    )
    assert unknown.json()["error"]["code"] == "city_not_found"


async def test_crossing_polygon_is_refused(client, admin_headers):
    response = await client.post(
        f"{API}/admin/zones",
        json={
            "kind": "restricted",
            "name": "Mal dibujada",
            "city": "Caracas",
            "polygon": [[10.40, -66.90], [10.45, -66.85], [10.40, -66.85], [10.45, -66.90]],
        },
        headers=admin_headers,
    )
    assert response.status_code == 422
    unknown_city = await client.post(
        f"{API}/admin/zones",
        json={"kind": "restricted", "name": "X", "city": "Madrid", "polygon": box(10.49, -66.88)},
        headers=admin_headers,
    )
    assert unknown_city.json()["error"]["code"] == "zone_invalid"


async def test_trips_between_cities_follow_the_pairs(client, passenger):
    valencia = {
        "name": "Valencia",
        "min_lat": 10.10,
        "max_lat": 10.25,
        "min_lng": -68.10,
        "max_lng": -67.90,
    }
    caracas = {
        "name": "Caracas",
        "min_lat": 10.35,
        "max_lat": 10.56,
        "min_lng": -67.10,
        "max_lng": -66.70,
    }
    await set_config(service_areas=[caracas, valencia])
    to_valencia = {"lat": 10.16, "lng": -68.00, "address": "Valencia"}
    refused = await quote(client, passenger, dropoff=to_valencia)
    assert refused.json()["error"]["code"] == "outside_service_area"

    await set_config(intercity_pairs=[{"a": "Valencia", "b": "Caracas"}])
    assert (await quote(client, passenger, dropoff=to_valencia)).status_code == 200


# --- Zone rules in the quote ---------------------------------------------------------------------


async def test_surge_zone_raises_the_fare_and_explains_it(client, admin_headers, passenger):
    plain = (await quote(client, passenger)).json()
    assert plain["surge_reason"] is None

    zone = await create_zone(
        client,
        admin_headers,
        kind="surge",
        name="Altamira",
        polygon=box(PICKUP["lat"], PICKUP["lng"]),
        rules={"multiplier": "1.20"},
    )
    surged = (await quote(client, passenger)).json()
    assert surged["surge_multiplier"] == "1.20"
    assert (surged["surge_reason"], surged["surge_zone"]) == ("zone", "Altamira")
    assert Decimal(surged["fare"]) > Decimal(plain["fare"])

    # A higher manual multiplier wins and the reason changes.
    await set_config(surge_manual_multiplier="1.50")
    manual = (await quote(client, passenger)).json()
    assert (manual["surge_multiplier"], manual["surge_reason"]) == ("1.50", "manual")
    await set_config(surge_manual_multiplier="1.00")

    # Out of force: inactive, or its validity already over.
    await client.patch(
        f"{API}/admin/zones/{zone['id']}", json={"active": False}, headers=admin_headers
    )
    assert (await quote(client, passenger)).json()["surge_reason"] is None
    ended = (utcnow() - timedelta(hours=1)).isoformat()
    started = (utcnow() - timedelta(hours=2)).isoformat()
    response = await client.patch(
        f"{API}/admin/zones/{zone['id']}",
        json={"active": True, "starts_at": started, "ends_at": ended},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert (await quote(client, passenger)).json()["surge_reason"] is None


async def test_restricted_pickup_suggests_a_point(client, admin_headers, passenger):
    exit_point = {"name": "Salida Plaza Altamira", "lat": 10.4935, "lng": -66.8800}
    await create_zone(
        client,
        admin_headers,
        kind="restricted",
        name="Zona cerrada",
        polygon=box(PICKUP["lat"], PICKUP["lng"]),
        rules={
            "pickup": True,
            "dropoff": False,
            "points": [exit_point],
            "message": {"es": "No se recoge aquí", "en": "No pickups here"},
        },
    )
    refused = await quote(client, passenger)
    assert refused.status_code == 422
    error = refused.json()["error"]
    assert error["code"] == "pickup_restricted"
    assert error["details"]["zone"] == "Zona cerrada"
    assert error["details"]["suggestion"]["name"] == "Salida Plaza Altamira"

    check = await client.get(
        f"{API}/zones/check",
        params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
        headers=passenger.headers,
    )
    body = check.json()
    assert body["city"] == "Caracas"
    assert body["restricted"] == {
        "zone": "Zona cerrada",
        "message": {"es": "No se recoge aquí", "en": "No pickups here"},
    }
    assert body["suggestion"]["name"] == "Salida Plaza Altamira"
    assert 300 < body["suggestion"]["distance_m"] < 450

    # The suggested point itself is outside the zone, so the ride can start there.
    moved = {"lat": exit_point["lat"], "lng": exit_point["lng"], "address": "Salida"}
    assert (await quote(client, passenger, pickup=moved)).status_code == 200


async def test_restricted_dropoff(client, admin_headers, passenger):
    await create_zone(
        client,
        admin_headers,
        kind="restricted",
        name="Aeropuerto",
        polygon=box(DROPOFF["lat"], DROPOFF["lng"]),
        rules={"pickup": False, "dropoff": True},
    )
    refused = await quote(client, passenger)
    assert refused.json()["error"]["code"] == "dropoff_restricted"
    assert refused.json()["error"]["details"]["zone"] == "Aeropuerto"


async def test_pickup_zone_suggests_the_closest_point(client, admin_headers, passenger):
    points = [
        {"name": "Metro Altamira", "lat": 10.4915, "lng": -66.8800},
        {"name": "Centro Comercial", "lat": 10.4880, "lng": -66.8790},
    ]
    await create_zone(
        client,
        admin_headers,
        kind="pickup",
        name="Altamira",
        polygon=box(PICKUP["lat"], PICKUP["lng"]),
        rules={"points": points},
    )
    check = await client.get(
        f"{API}/zones/check", params={"lat": 10.4905, "lng": -66.8800}, headers=passenger.headers
    )
    assert check.json()["suggestion"]["name"] == "Metro Altamira"
    assert check.json()["restricted"] is None
    # Already standing on the point: nothing to suggest.
    there = await client.get(
        f"{API}/zones/check", params={"lat": 10.4915, "lng": -66.8800}, headers=passenger.headers
    )
    assert there.json()["suggestion"] is None
    outside = await client.get(
        f"{API}/zones/check", params={"lat": 1.0, "lng": 1.0}, headers=passenger.headers
    )
    assert outside.json() == {"city": None, "restricted": None, "suggestion": None, "surge": None}


# --- Admin ---------------------------------------------------------------------------------------


async def test_admin_crud_export_and_import(client, admin_headers):
    zone = await create_zone(
        client,
        admin_headers,
        kind="pickup",
        name="Metro",
        polygon=box(10.49, -66.88),
        rules={"points": [{"name": "Salida 1", "lat": 10.49, "lng": -66.88}]},
    )
    listed = await client.get(f"{API}/admin/zones?kind=pickup", headers=admin_headers)
    assert [z["id"] for z in listed.json()] == [zone["id"]]

    exported = (await client.get(f"{API}/admin/zones/export", headers=admin_headers)).json()
    kinds = [f["properties"]["kind"] for f in exported["features"]]
    assert kinds == ["city", "pickup"]
    ring = exported["features"][1]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1] and ring[0] == [-66.883, 10.487]  # [lng, lat], closed

    await client.delete(f"{API}/admin/zones/{zone['id']}", headers=admin_headers)
    assert (await client.get(f"{API}/admin/zones", headers=admin_headers)).json() == []

    exported["features"].append({"type": "Feature", "geometry": None, "properties": {}})
    imported = await client.post(
        f"{API}/admin/zones/import", json={"geojson": exported}, headers=admin_headers
    )
    assert imported.status_code == 200, imported.text
    result = imported.json()
    assert (result["cities"], result["created"], result["updated"]) == (1, 1, 0)
    assert [s["index"] for s in result["skipped"]] == [2]
    again = await client.get(f"{API}/admin/zones", headers=admin_headers)
    assert [z["name"] for z in again.json()] == ["Metro"]

    bad = await client.post(
        f"{API}/admin/zones/import", json={"geojson": {"type": "Point"}}, headers=admin_headers
    )
    assert bad.json()["error"]["code"] == "geojson_invalid"


async def test_zone_permissions(client):
    from apps.users.models import Role
    from conftest import _login, _make_user

    role = await make_staff_role("mirada", {"zones.view"})
    await _make_user("mira@example.com", Role.STAFF, role)
    headers = await _login(client, "mira@example.com")
    assert (await client.get(f"{API}/admin/zones", headers=headers)).status_code == 200
    denied = await client.post(
        f"{API}/admin/zones",
        json={"kind": "restricted", "name": "X", "city": "Caracas", "polygon": box(10.49, -66.88)},
        headers=headers,
    )
    assert denied.status_code == 403


# --- Demand --------------------------------------------------------------------------------------


@pytest.fixture
def pushes(monkeypatch) -> list[tuple[list[str], str, str, dict]]:
    from apps.notifications import tasks as notification_tasks

    sent: list[tuple[list[str], str, str, dict]] = []

    class FakeTask:
        async def kiq(self, user_ids, title, body, data=None, options=None):
            sent.append((user_ids, title, body, data))

    monkeypatch.setattr(notification_tasks, "send_push", FakeTask())
    return sent


@pytest.fixture
def published(monkeypatch) -> list[tuple[str, dict, list[str] | None]]:
    events: list[tuple[str, dict, list[str] | None]] = []

    async def fake_publish(event, data=None, user_ids=None):
        events.append((event, data, user_ids))

    monkeypatch.setattr(tasks, "publish", fake_publish)
    return events


async def _fail_search(ride_id: str) -> None:
    async with SessionLocal() as session:
        row = await session.get(Ride, uuid.UUID(ride_id))
        row.search_expires_at = utcnow()
        await session.commit()
    await dispatch.advance(uuid.UUID(ride_id))


async def test_demand_map_reflects_a_spike(client, admin_headers, passenger, pushes, published):
    await set_config(demand={"hot_requests": 3})
    # A real request that ends without a driver (nobody online yet), then a spike in its cell.
    response = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    created = await client.post(
        f"{API}/rides",
        json={"quote_id": response.json()["quote_id"], "payment_method": "cash_usd"},
        headers=passenger.headers,
    )
    ride_id = created.json()["id"]
    await _fail_search(ride_id)
    async with SessionLocal() as session:
        assert (await session.get(Ride, uuid.UUID(ride_id))).status == RideStatus.NO_DRIVERS
    driver = await make_driver(client, "moto@example.com", "Luis Moto")
    await go_online(client, driver, NEAR)
    away = await make_driver(client, "lejos@example.com", "Pedro Lejos")
    await go_online(client, away, (10.40, -67.05))  # ~19 km away

    empty = await client.get(
        f"{API}/drivers/me/demand", params={"lat": NEAR[0], "lng": NEAR[1]}, headers=driver.headers
    )
    assert empty.status_code == 200
    assert [c["level"] for c in empty.json()["cells"]] == [1]
    await tasks.run_once()  # stores the map before the spike

    await demand.record(demand.REQUESTS, PICKUP["lat"], PICKUP["lng"], 3)

    await tasks.redis_client.delete(tasks.LOCK)
    after = await tasks.run_once()
    assert after is not None
    [cell] = after["cells"]
    assert (cell["requests"], cell["unmatched"], cell["level"]) == (4, 1, 3)
    # Online drivers hear about the new map and the nearby free one gets one push.
    [(event, _, users)] = published[-1:]
    assert event == tasks.UPDATED_EVENT and set(users or []) == {driver.id, away.id}
    assert len(pushes) == 1 and pushes[0][0] == [driver.id]
    assert pushes[0][3]["type"] == "demand"

    shown = await client.get(
        f"{API}/drivers/me/demand", params={"lat": NEAR[0], "lng": NEAR[1]}, headers=driver.headers
    )
    body = shown.json()
    [mine] = body["cells"]
    assert mine["level"] == 3 and mine["drivers"] is None and len(mine["boundary"]) == 6
    far = await client.get(
        f"{API}/drivers/me/demand", params={"lat": 10.40, "lng": -67.05}, headers=away.headers
    )
    assert far.json()["cells"] == []

    admin = await client.get(f"{API}/admin/zones/demand", headers=admin_headers)
    assert admin.json()["cells"][0]["drivers"] == 1

    # Still hot a minute later: no second push (rate limit and not "new").
    await tasks.redis_client.delete(tasks.LOCK)
    await demand.record(demand.REQUESTS, PICKUP["lat"], PICKUP["lng"], 1)
    await tasks.run_once()
    assert len(pushes) == 1


async def test_demand_needs_an_approved_driver_and_respects_settings(client, passenger, pushes):
    denied = await client.get(
        f"{API}/drivers/me/demand",
        params={"lat": NEAR[0], "lng": NEAR[1]},
        headers=passenger.headers,
    )
    assert denied.json()["error"]["code"] == "driver_not_approved"

    driver = await make_driver(client, "moto@example.com", "Luis Moto")
    await go_online(client, driver, NEAR)
    muted = await client.put(
        f"{API}/notifications/preferences", json={"demand_alerts": False}, headers=driver.headers
    )
    assert muted.json()["demand_alerts"] is False
    await demand.record(demand.REQUESTS, PICKUP["lat"], PICKUP["lng"], 5)
    await demand.record(demand.UNMATCHED, PICKUP["lat"], PICKUP["lng"], 2)
    assert (await tasks.run_once())["cells"][0]["level"] == 3
    assert pushes == []

    await set_config(demand={"enabled": False})
    off = await client.get(
        f"{API}/drivers/me/demand", params={"lat": NEAR[0], "lng": NEAR[1]}, headers=driver.headers
    )
    assert off.json()["enabled"] is False and off.json()["cells"] == []


async def test_simulate_spike(client, admin_headers):
    response = await client.post(
        f"{API}/admin/zones/demand/simulate",
        json={"lat": 10.49, "lng": -66.88, "requests": 6, "unmatched": 2},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    [cell] = response.json()["cells"]
    assert (cell["requests"], cell["unmatched"], cell["level"]) == (6, 2, 3)
