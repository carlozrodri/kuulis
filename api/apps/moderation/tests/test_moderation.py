from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from apps.drivers.models import VehicleType
from apps.moderation.models import Suspension
from apps.notifications.models import Notification
from apps.rides import presence
from apps.rides.models import PaymentMethod, Ride, RideStatus
from apps.rides.tests.conftest import DROPOFF, PICKUP, make_driver
from conftest import _login, _make_user
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def _ride(passenger_id, driver_id, status=RideStatus.COMPLETED) -> str:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        ride = Ride(
            passenger_id=passenger_id,
            driver_id=driver_id,
            status=status,
            vehicle_type=VehicleType.MOTO,
            pickup_lat=PICKUP["lat"],
            pickup_lng=PICKUP["lng"],
            dropoff_lat=DROPOFF["lat"],
            dropoff_lng=DROPOFF["lng"],
            distance_m=3000,
            duration_s=600,
            fare=Decimal("2.50"),
            surge_multiplier=Decimal("1"),
            payment_method=PaymentMethod.CASH_USD,
            requested_at=now,
            search_expires_at=now,
            completed_at=now if status == RideStatus.COMPLETED else None,
        )
        session.add(ride)
        await session.commit()
        return str(ride.id)


async def _titles(user_id) -> list[str]:
    async with SessionLocal() as session:
        return list(
            await session.scalars(select(Notification.title).where(Notification.user_id == user_id))
        )


async def test_report_about_a_ride(client, staff_headers, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _ride(passenger.user.id, luis.user.id)
    body = {"category": "fare", "description": "  Me cobró 5 dólares en vez de 2.50  "}

    created = await client.post(
        f"{API}/reports", json={**body, "ride_id": ride_id}, headers=passenger.headers
    )
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["status"] == "open" and report["priority"] == "normal"
    assert report["reporter_role"] == "passenger"
    assert report["description"] == "Me cobró 5 dólares en vez de 2.50"

    again = await client.post(
        f"{API}/reports", json={**body, "ride_id": ride_id}, headers=passenger.headers
    )
    assert again.status_code == 409
    assert again.json()["error"]["details"] == {"report_id": report["id"]}

    other = await _make_user("otra@example.com")
    stranger = await client.post(
        f"{API}/reports",
        json={**body, "ride_id": ride_id},
        headers=await _login(client, other.email),
    )
    assert stranger.status_code == 403
    assert stranger.json()["error"]["code"] == "not_ride_participant"

    # The driver reports the passenger: urgent.
    urgent = await client.post(
        f"{API}/reports",
        json={
            "category": "harassment",
            "description": "Me insultó todo el viaje",
            "ride_id": ride_id,
        },
        headers=luis.headers,
    )
    assert urgent.json()["priority"] == "urgent" and urgent.json()["reporter_role"] == "driver"

    listing = (await client.get(f"{API}/admin/reports", headers=staff_headers)).json()
    assert listing["total"] == 2 and listing["counts"] == {
        "open": 2,
        "in_review": 0,
        "urgent_open": 1,
    }
    assert listing["items"][0]["id"] == urgent.json()["id"]  # urgent first
    assert listing["items"][1]["reported"]["email"] == "luis@example.com"
    by_user = await client.get(
        f"{API}/admin/reports", params={"user_id": luis.id, "q": "cobró"}, headers=staff_headers
    )
    assert by_user.json()["total"] == 1

    detail = (await client.get(f"{API}/admin/reports/{report['id']}", headers=staff_headers)).json()
    assert detail["ride"]["id"] == ride_id
    assert detail["reported_summary"]["role_in_ride"] == "driver"
    assert detail["reported_summary"]["phone"] == "+584121234567"
    assert detail["reported_summary"]["reports_against"] == {
        "total": 1,
        "open": 1,
        "last_90_days": 1,
    }
    assert detail["reporter_summary"]["rides_completed"] == 1


async def test_general_reports_and_limits(client, passenger):
    url = f"{API}/reports"
    needs_ride = await client.post(
        url,
        json={"category": "safety", "description": "Algo pasó en la calle"},
        headers=passenger.headers,
    )
    assert needs_ride.status_code == 422
    short = await client.post(
        url, json={"category": "app_issue", "description": "falla"}, headers=passenger.headers
    )
    assert short.status_code == 422
    for i in range(5):
        ok = await client.post(
            url,
            json={"category": "app_issue", "description": f"La app se cierra sola {i}"},
            headers=passenger.headers,
        )
        assert ok.status_code == 201 and ok.json()["reporter_role"] is None
    too_many = await client.post(
        url,
        json={"category": "other", "description": "Otro problema más"},
        headers=passenger.headers,
    )
    assert too_many.json()["error"]["code"] == "too_many_open_reports"
    mine = (await client.get(f"{API}/reports/me?limit=2", headers=passenger.headers)).json()
    assert mine["total"] == 5 and len(mine["items"]) == 2
    one = await client.get(f"{API}/reports/me/{mine['items'][0]['id']}", headers=passenger.headers)
    assert one.status_code == 200

    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    no_driver = await _ride(passenger.user.id, None, RideStatus.NO_DRIVERS)
    assert (
        await client.get(f"{API}/reports/me/{one.json()['id']}", headers=luis.headers)
    ).status_code == 404
    response = await client.post(
        url,
        json={"category": "other", "description": "Nadie llegó nunca", "ride_id": no_driver},
        headers=passenger.headers,
    )
    assert response.json()["error"]["code"] == "ride_without_driver"


async def test_staff_workflow(client, staff_headers, admin_headers, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _ride(passenger.user.id, luis.user.id)
    report = (
        await client.post(
            f"{API}/reports",
            json={"category": "driving", "description": "Iba muy rápido", "ride_id": ride_id},
            headers=passenger.headers,
        )
    ).json()
    url = f"{API}/admin/reports/{report['id']}"
    staff = (await client.get(f"{API}/users/me", headers=staff_headers)).json()

    patched = await client.patch(
        url,
        json={"status": "in_review", "priority": "urgent", "assigned_to_id": staff["id"]},
        headers=staff_headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["assigned_to"]["id"] == staff["id"]
    bad_assignee = await client.patch(
        url, json={"assigned_to_id": str(passenger.user.id)}, headers=staff_headers
    )
    assert bad_assignee.json()["error"]["code"] == "assignee_invalid"
    note = await client.post(
        f"{url}/notes", json={"body": "Llamé al motorizado"}, headers=staff_headers
    )
    assert note.status_code == 201 and note.json()["kind"] == "note"

    resolved = await client.post(
        f"{url}/resolve",
        json={"status": "resolved", "resolution": "Hablamos con el motorizado y lo advertimos."},
        headers=staff_headers,
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "resolved" and body["resolved_at"]
    assert [n["kind"] for n in body["notes"]] == ["status", "note", "status"]
    assert (
        await client.post(
            f"{url}/resolve",
            json={"status": "dismissed", "resolution": "x x x"},
            headers=staff_headers,
        )
    ).status_code == 409
    assert "Revisamos tu reporte" in await _titles(passenger.user.id)
    mine = (await client.get(f"{API}/reports/me/{report['id']}", headers=passenger.headers)).json()
    assert mine["resolution"] == "Hablamos con el motorizado y lo advertimos."

    reopened = await client.post(f"{url}/reopen", headers=staff_headers)
    assert reopened.json()["status"] == "in_review" and reopened.json()["resolved_at"] is None
    assert (await client.post(f"{url}/reopen", headers=staff_headers)).status_code == 409


async def test_suspension_blocks_rides(client, staff_headers, passenger, monkeypatch):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _ride(passenger.user.id, luis.user.id)
    report = (
        await client.post(
            f"{API}/reports",
            json={"category": "safety", "description": "Manejó borracho", "ride_id": ride_id},
            headers=passenger.headers,
        )
    ).json()
    online = f"{API}/drivers/me/online"
    point = {"lat": PICKUP["lat"], "lng": PICKUP["lng"]}
    assert (await client.post(online, json=point, headers=luis.headers)).status_code == 200

    until = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    url = f"{API}/admin/users/{luis.id}"
    past = await client.post(
        f"{url}/suspend",
        json={"reason": "Investigación", "until": "2020-01-01T00:00:00Z"},
        headers=staff_headers,
    )
    assert past.json()["error"]["code"] == "suspension_until_invalid"
    suspended = await client.post(
        f"{url}/suspend",
        json={"reason": "Reporte de seguridad", "until": until, "report_id": report["id"]},
        headers=staff_headers,
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["by"]["email"] and suspended.json()["until"]
    assert not await presence.is_online(luis.user.id)

    blocked = await client.post(online, json=point, headers=luis.headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "account_suspended"
    assert blocked.json()["error"]["details"]["reason"] == "Reporte de seguridad"
    # As a passenger too.
    quote = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=luis.headers,
    )
    assert quote.status_code == 403
    me = (await client.get(f"{API}/users/me", headers=luis.headers)).json()
    assert me["suspension"]["reason"] == "Reporte de seguridad"
    assert "Tu cuenta está suspendida" in await _titles(luis.user.id)

    listing = await client.get(f"{API}/users?suspended=true", headers=staff_headers)
    assert [u["id"] for u in listing.json()["items"]] == [luis.id]
    assert listing.json()["items"][0]["suspension"]["until"]
    detail = (await client.get(f"{API}/admin/reports/{report['id']}", headers=staff_headers)).json()
    assert detail["notes"][-1]["kind"] == "suspension"
    assert detail["reported_summary"]["suspension"]["reason"] == "Reporte de seguridad"

    lifted = await client.post(f"{url}/unsuspend", headers=staff_headers)
    assert lifted.status_code == 204
    assert (await client.post(f"{url}/unsuspend", headers=staff_headers)).status_code == 409
    assert (await client.post(online, json=point, headers=luis.headers)).status_code == 200
    history = (await client.get(f"{url}/suspensions", headers=staff_headers)).json()
    assert len(history) == 1 and history[0]["lifted_at"] and history[0]["report_id"] == report["id"]


async def test_expired_suspension_and_staff(client, staff_headers, admin_headers, passenger):
    async with SessionLocal() as session:
        session.add(
            Suspension(
                user_id=passenger.user.id,
                reason="Vieja",
                until=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.commit()
    me = (await client.get(f"{API}/users/me", headers=passenger.headers)).json()
    assert me["suspension"] is None
    quote = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    assert quote.status_code == 200, quote.text

    indefinite = await client.post(
        f"{API}/admin/users/{passenger.id}/suspend",
        json={"reason": "Fraude"},
        headers=staff_headers,
    )
    assert indefinite.json()["until"] is None
    assert (await client.get(f"{API}/users/me", headers=passenger.headers)).json()["suspension"]
    staff = (await client.get(f"{API}/users/me", headers=staff_headers)).json()
    cannot = await client.post(
        f"{API}/admin/users/{staff['id']}/suspend", json={"reason": "Prueba"}, headers=admin_headers
    )
    assert cannot.json()["error"]["code"] == "cannot_suspend_staff"
    forbidden = await client.post(
        f"{API}/admin/users/{passenger.id}/unsuspend", headers=passenger.headers
    )
    assert forbidden.status_code == 403
