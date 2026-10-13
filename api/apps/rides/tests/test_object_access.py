"""Object-level authorization (doc 05, OWASP ASVS V4): a user can't read or act on another
person's ride, chat, report, saved place, notification or session by guessing its id."""

from apps.moderation.tests.test_moderation import _ride
from apps.notifications.models import Notification
from apps.rides.models import RideStatus
from conftest import _login, _make_user, ride_step
from kuulis.core.db import SessionLocal

from .conftest import make_driver

API = "/api/v1"


async def test_strangers_cannot_reach_someone_elses_objects(client, passenger, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    other_driver = await make_driver(client, "pedro@example.com", "Pedro Díaz")
    await _make_user("eve@example.com")
    eve = await _login(client, "eve@example.com")

    ride = await _ride(passenger.user.id, luis.user.id, RideStatus.IN_PROGRESS)
    done = await _ride(passenger.user.id, luis.user.id)
    message = await client.post(
        f"{API}/rides/{ride}/messages", json={"text": "Voy en camino"}, headers=passenger.headers
    )
    assert message.status_code == 201, message.text
    report = await client.post(
        f"{API}/reports",
        json={"ride_id": done, "category": "fare", "description": "Me cobró de más"},
        headers=passenger.headers,
    )
    assert report.status_code == 201, report.text
    place = await client.post(
        f"{API}/users/me/places",
        json={"kind": "home", "address": "Casa", "lat": 10.5, "lng": -66.84},
        headers=passenger.headers,
    )
    async with SessionLocal() as session:
        notification = Notification(user_id=passenger.user.id, title="Hola", body="", data={})
        session.add(notification)
        await session.commit()
    sessions = await client.get(f"{API}/auth/sessions", headers=passenger.headers)
    sid = sessions.json()[0]["id"]

    attempts = [
        ("get", f"/rides/{ride}", None),
        ("post", f"/rides/{ride}/cancel", {"reason": "x"}),
        ("get", f"/rides/{ride}/messages", None),
        ("post", f"/rides/{ride}/messages", {"text": "hola"}),
        ("post", f"/rides/{done}/rating", {"stars": 1}),
        ("get", f"/reports/me/{report.json()['id']}", None),
        ("patch", f"/users/me/places/{place.json()['id']}", {"address": "Mía"}),
        ("delete", f"/users/me/places/{place.json()['id']}", None),
        ("post", f"/notifications/{notification.id}/read", None),
        ("delete", f"/auth/sessions/{sid}", None),
    ]
    for actor in (eve, other_driver.headers):
        for method, path, body in attempts:
            kwargs = {"json": body} if body is not None else {}
            response = await client.request(method, f"{API}{path}", headers=actor, **kwargs)
            assert response.status_code in (403, 404), (method, path, response.status_code)

    # Another driver can't move someone else's ride along.
    for step in ("arrive", "start", "complete"):
        response = await ride_step(client, ride, step, other_driver.headers)
        assert response.status_code in (403, 404, 409), (step, response.status_code)

    # Plain users don't see other people's profiles.
    profile = await client.get(f"{API}/users/{passenger.id}", headers=eve)
    assert profile.status_code == 403

    # And nothing changed for the owner.
    assert (await client.get(f"{API}/rides/{ride}", headers=passenger.headers)).json()[
        "status"
    ] == "in_progress"
    assert len((await client.get(f"{API}/users/me/places", headers=passenger.headers)).json()) == 1
    assert len((await client.get(f"{API}/auth/sessions", headers=passenger.headers)).json()) == 1
