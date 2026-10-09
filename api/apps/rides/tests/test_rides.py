import asyncio
import time
import uuid
from decimal import Decimal

from sqlalchemy import select

from apps.config.schemas import AppConfig
from apps.drivers.models import DriverProfile, DriverStatus
from apps.geo.clients import estimate_route
from apps.rides import dispatch, presence
from apps.rides.models import OfferStatus, Ride, RideOffer, RideStatus
from apps.rides.pricing import CARACAS_TZ, compute_fare
from apps.rides.state import utcnow
from apps.users.models import User
from conftest import _login, _make_user
from kuulis.core.db import SessionLocal

from .conftest import (
    DROPOFF,
    FAR,
    MID,
    NEAR,
    PICKUP,
    Actor,
    age_location,
    expire_offers,
    go_online,
    make_driver,
    request_ride,
)

API = "/api/v1"


async def _offers(ride_id: str) -> list[RideOffer]:
    async with SessionLocal() as session:
        rows = await session.scalars(
            select(RideOffer)
            .where(RideOffer.ride_id == uuid.UUID(ride_id))
            .order_by(RideOffer.created_at)
        )
        return list(rows)


async def _ride(ride_id: str) -> Ride:
    async with SessionLocal() as session:
        ride = await session.get(Ride, uuid.UUID(ride_id))
        assert ride is not None
        return ride


async def _assigned_ride(client, passenger, driver) -> dict:
    await go_online(client, driver, NEAR)
    ride = await request_ride(client, passenger)
    response = await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _completed_ride(client, passenger, driver) -> dict:
    ride = await _assigned_ride(client, passenger, driver)
    for step in ("arrive", "start", "complete"):
        response = await client.post(f"{API}/rides/{ride['id']}/{step}", headers=driver.headers)
        assert response.status_code == 200, response.text
    return response.json()


# --- Quote -------------------------------------------------------------------------------------


async def test_quote(client, passenger):
    response = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    route = estimate_route(PICKUP["lat"], PICKUP["lng"], DROPOFF["lat"], DROPOFF["lng"])
    assert (body["distance_m"], body["duration_s"]) == (route.distance_m, route.duration_s)
    expected = compute_fare(
        AppConfig().fares["moto"], route.distance_m, route.duration_s, Decimal(1), Decimal("0.1")
    )
    assert body["fare"] == f"{expected:.2f}"
    assert body["surge_multiplier"] == "1.00"
    assert body["polyline"] is None and body["quote_id"]


async def test_quote_errors(client, passenger):
    outside = {"lat": 10.65, "lng": -71.61, "address": "Maracaibo"}
    response = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": outside, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "outside_service_area"
    response = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "car"},
        headers=passenger.headers,
    )
    assert response.json()["error"]["code"] == "vehicle_type_not_enabled"


async def test_request_errors(client, passenger, user_headers):
    quote = (
        await client.post(
            f"{API}/rides/quote",
            json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
            headers=passenger.headers,
        )
    ).json()
    bad_method = await client.post(
        f"{API}/rides",
        json={"quote_id": quote["quote_id"], "payment_method": "bitcoin"},
        headers=passenger.headers,
    )
    assert bad_method.status_code == 400
    assert bad_method.json()["error"]["code"] == "payment_method_invalid"
    # A quote is bound to the user who asked for it.
    stolen = await client.post(
        f"{API}/rides",
        json={"quote_id": quote["quote_id"], "payment_method": "cash_usd"},
        headers=user_headers,
    )
    assert stolen.status_code == 400 and stolen.json()["error"]["code"] == "quote_expired"
    unknown = await client.post(
        f"{API}/rides",
        json={"quote_id": "nope", "payment_method": "cash_usd"},
        headers=passenger.headers,
    )
    assert unknown.json()["error"]["code"] == "quote_expired"

    first = await client.post(
        f"{API}/rides",
        json={"quote_id": quote["quote_id"], "payment_method": "cash_usd"},
        headers=passenger.headers,
    )
    assert first.status_code == 201
    assert first.json()["status"] == "searching"
    reused = await client.post(
        f"{API}/rides",
        json={"quote_id": quote["quote_id"], "payment_method": "cash_usd"},
        headers=passenger.headers,
    )
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "ride_already_active"
    assert reused.json()["error"]["details"]["ride_id"] == first.json()["id"]


# --- Happy path --------------------------------------------------------------------------------


async def test_full_ride_flow(client, passenger, recorder):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    far_driver = await make_driver(client, "pedro@example.com", "Pedro Díaz")
    await go_online(client, driver, NEAR)
    await go_online(client, far_driver, FAR)

    ride = await request_ride(client, passenger)
    ride_id = ride["id"]
    assert ride["passenger"]["first_name"] == "Ana" and ride["driver"] is None

    # The nearest driver gets the offer (realtime + push), only them.
    offers = recorder.of("ride.offer")
    assert len(offers) == 1 and recorder.of("ride.offer", driver.id) == offers
    offer = offers[0]
    assert offer["ride_id"] == ride_id and offer["fare"] == ride["fare"]
    assert offer["passenger"] == {"first_name": "Ana", "rating": None}
    assert 0 < offer["pickup_distance_m"] < 300
    assert recorder.pushed("offer", driver.id)

    state = (await client.get(f"{API}/drivers/me/state", headers=driver.headers)).json()
    assert state["online"] is True and state["active_ride_id"] is None
    assert state["current_offer"]["ride_id"] == ride_id

    # Only participants see the ride.
    hidden = await client.get(f"{API}/rides/{ride_id}", headers=far_driver.headers)
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "ride_not_found"

    accepted = await client.post(f"{API}/rides/{ride_id}/accept", headers=driver.headers)
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "driver_assigned" and body["assigned_at"]
    assert body["driver"]["first_name"] == "Luis"
    assert body["driver"]["vehicle"] == {
        "brand": "Yamaha",
        "model": "YBR 125",
        "color": "Negra",
        "plate": body["driver"]["vehicle"]["plate"],
    }
    assert body["driver_location"]["lat"] == NEAR[0]
    assert recorder.pushed("assigned", passenger.id)
    updates = recorder.of("ride.updated", passenger.id)
    assert updates[-1]["status"] == "driver_assigned"
    assert recorder.of("ride.updated", driver.id)[-1]["status"] == "driver_assigned"

    for who in (passenger, driver):
        active = (await client.get(f"{API}/rides/active", headers=who.headers)).json()
        assert active["id"] == ride_id

    # Live location is forwarded to the passenger, throttled (one forward per 2 s).
    for lat in (10.4905, 10.4904):
        await age_location(driver, 3)
        await presence.handle_location(
            driver.id, {"type": "location", "lat": lat, "lng": -66.88, "heading": 90}
        )
    forwarded = recorder.of("ride.driver_location", passenger.id)
    assert forwarded == [{"ride_id": ride_id, "lat": 10.4905, "lng": -66.88, "heading": 90.0}]
    assert (await presence.get_location(driver.id)).lat == 10.4904  # still stored
    await presence.handle_location(driver.id, {"type": "location", "lat": "x", "lng": 1})  # ignored

    # Chat while the ride is active.
    message = await client.post(
        f"{API}/rides/{ride_id}/messages", json={"text": " Ya voy "}, headers=passenger.headers
    )
    assert message.status_code == 201 and message.json()["text"] == "Ya voy"
    assert recorder.of("ride.message", driver.id)[0]["sender_id"] == passenger.id
    assert recorder.pushed("message", driver.id)
    listed = (await client.get(f"{API}/rides/{ride_id}/messages", headers=driver.headers)).json()
    assert [m["text"] for m in listed] == ["Ya voy"]

    # Wrong order is rejected; the driver can't go offline mid ride.
    early = await client.post(f"{API}/rides/{ride_id}/complete", headers=driver.headers)
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "ride_invalid_transition"
    offline = await client.post(f"{API}/drivers/me/offline", headers=driver.headers)
    assert offline.status_code == 409 and offline.json()["error"]["code"] == "ride_active"
    other = await client.post(f"{API}/rides/{ride_id}/arrive", headers=far_driver.headers)
    assert other.status_code == 404

    for step, status in (
        ("arrive", "driver_arrived"),
        ("start", "in_progress"),
        ("complete", "completed"),
    ):
        response = await client.post(f"{API}/rides/{ride_id}/{step}", headers=driver.headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status
    again = await client.post(f"{API}/rides/{ride_id}/complete", headers=driver.headers)
    assert again.status_code == 200  # idempotent retry
    assert recorder.pushed("arrived", passenger.id) and recorder.pushed("completed", passenger.id)
    done = again.json()
    assert done["completed_at"] and done["started_at"] and done["arrived_at"]
    assert done["driver_location"] is None

    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.user.id)
        )
        assert profile.first_trip_completed_at is not None

    closed = await client.post(
        f"{API}/rides/{ride_id}/messages", json={"text": "gracias"}, headers=passenger.headers
    )
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "chat_closed"

    # Ratings are mandatory: the passenger can't ask for another ride before rating.
    pending = (await client.get(f"{API}/rides/pending-rating", headers=passenger.headers)).json()
    assert pending["id"] == ride_id
    quote = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=passenger.headers,
    )
    blocked = await client.post(
        f"{API}/rides",
        json={"quote_id": quote.json()["quote_id"], "payment_method": "cash_usd"},
        headers=passenger.headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"] == {
        "code": "rating_required",
        "message": blocked.json()["error"]["message"],
        "details": {"ride_id": ride_id},
    }

    rated = await client.post(
        f"{API}/rides/{ride_id}/rating",
        json={"stars": 5, "tags": ["safe_driving", "On_Time"], "comment": " Excelente "},
        headers=passenger.headers,
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["my_rating"]["stars"] == 5
    assert rated.json()["my_rating"]["tags"] == ["safe_driving", "on_time"]
    twice = await client.post(
        f"{API}/rides/{ride_id}/rating", json={"stars": 1}, headers=passenger.headers
    )
    assert twice.status_code == 409
    assert twice.json()["error"]["code"] == "rating_already_submitted"
    assert (
        await client.get(f"{API}/rides/pending-rating", headers=passenger.headers)
    ).json() is None

    # The driver rates the passenger too.
    assert (await client.get(f"{API}/rides/pending-rating", headers=driver.headers)).json()[
        "id"
    ] == ride_id
    response = await client.post(
        f"{API}/rides/{ride_id}/rating", json={"stars": 4, "tags": []}, headers=driver.headers
    )
    assert response.status_code == 200
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.user.id)
        )
        user = await session.get(User, passenger.user.id)
        assert (profile.rating_count, float(profile.rating_avg)) == (1, 5.0)
        assert (user.rating_count, float(user.rating_avg)) == (1, 4.0)

    me = (await client.get(f"{API}/drivers/me", headers=driver.headers)).json()
    assert me["rating_avg"] == 5.0 and me["rating_count"] == 1
    history = (await client.get(f"{API}/rides?role=driver", headers=driver.headers)).json()
    assert history["total"] == 1 and history["items"][0]["my_rating"]["stars"] == 4
    assert (await client.get(f"{API}/rides?role=passenger", headers=driver.headers)).json()[
        "total"
    ] == 0


async def test_rating_average(client, passenger):
    driver = await make_driver(client, "luis@example.com", "Luis")
    for stars in (5, 4, 4):
        ride = await _completed_ride(client, passenger, driver)
        for who, value in ((passenger, stars), (driver, 5)):
            response = await client.post(
                f"{API}/rides/{ride['id']}/rating", json={"stars": value}, headers=who.headers
            )
            assert response.status_code == 200, response.text
    accepted = await client.post(
        f"{API}/rides/{ride['id']}/rating", json={"stars": 6}, headers=passenger.headers
    )
    assert accepted.status_code == 422
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.user.id)
        )
        assert profile.rating_count == 3 and str(profile.rating_avg) == "4.33"


async def test_rating_requires_completed(client, passenger):
    driver = await make_driver(client, "luis@example.com", "Luis")
    ride = await _assigned_ride(client, passenger, driver)
    response = await client.post(
        f"{API}/rides/{ride['id']}/rating", json={"stars": 5}, headers=passenger.headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ride_not_completed"


# --- Matching ----------------------------------------------------------------------------------


async def test_decline_and_timeout_move_to_next_driver(client, passenger, recorder):
    first = await make_driver(client, "a@example.com", "A")
    second = await make_driver(client, "b@example.com", "B")
    third = await make_driver(client, "c@example.com", "C")
    await go_online(client, first, NEAR)
    await go_online(client, second, MID)
    await go_online(client, third, FAR)

    ride = await request_ride(client, passenger)
    assert [str(o.driver_id) for o in await _offers(ride["id"])] == [first.id]

    declined = await client.post(f"{API}/rides/{ride['id']}/decline", headers=first.headers)
    assert declined.status_code == 204
    offers = await _offers(ride["id"])
    assert [(str(o.driver_id), o.status) for o in offers] == [
        (first.id, OfferStatus.DECLINED),
        (second.id, OfferStatus.PENDING),
    ]
    late = await client.post(f"{API}/rides/{ride['id']}/accept", headers=first.headers)
    assert late.status_code == 409 and late.json()["error"]["code"] == "offer_expired"

    # Timeout: the dispatcher loop picks the due step and offers the ride to the third driver.
    await expire_offers(ride["id"])
    assert await dispatch.run_due(now=time.time() + 3600) == 1
    offers = await _offers(ride["id"])
    assert [o.status for o in offers] == [
        OfferStatus.DECLINED,
        OfferStatus.EXPIRED,
        OfferStatus.PENDING,
    ]
    assert str(offers[-1].driver_id) == third.id
    assert recorder.of("ride.offer_cancelled", second.id) == [{"ride_id": ride["id"]}]
    expired = await client.post(f"{API}/rides/{ride['id']}/accept", headers=second.headers)
    assert expired.json()["error"]["code"] == "offer_expired"

    # Nobody left; once the search deadline passes the ride ends with no_drivers.
    await expire_offers(ride["id"])
    await dispatch.advance(uuid.UUID(ride["id"]))
    assert (await _ride(ride["id"])).status == RideStatus.SEARCHING  # still within deadline
    async with SessionLocal() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        row.search_expires_at = utcnow()
        await session.commit()
    await dispatch.advance(uuid.UUID(ride["id"]))
    assert (await _ride(ride["id"])).status == RideStatus.NO_DRIVERS
    assert recorder.pushed("no_drivers", passenger.id)
    assert recorder.of("ride.updated", passenger.id)[-1]["status"] == "no_drivers"
    # A step on a finished ride is a no-op (idempotent).
    await dispatch.advance(uuid.UUID(ride["id"]))
    assert len(await _offers(ride["id"])) == 3


async def test_offer_waits_for_driver_coming_online(client, passenger):
    ride = await request_ride(client, passenger)
    assert await _offers(ride["id"]) == []
    driver = await make_driver(client, "a@example.com", "A")
    await go_online(client, driver, MID)
    await dispatch.run_due(now=time.time() + 60)
    assert [str(o.driver_id) for o in await _offers(ride["id"])] == [driver.id]


async def test_ineligible_drivers_are_skipped(client, passenger):
    stale = await make_driver(client, "stale@example.com", "Stale")
    unrated = await make_driver(client, "unrated@example.com", "Unrated")
    pending = await make_driver(client, "pending@example.com", "Pending", DriverStatus.SUSPENDED)
    ok = await make_driver(client, "ok@example.com", "Ok")

    # "unrated" finishes a ride with another passenger and does not rate it.
    await _make_user("bob@example.com")
    bob = Actor(await _user("bob@example.com"), await _login(client, "bob@example.com"))
    await _completed_ride(client, bob, unrated)

    await go_online(client, stale, NEAR)
    await age_location(stale, 120)
    assert (
        await client.post(
            f"{API}/drivers/me/online",
            json={"lat": NEAR[0], "lng": NEAR[1]},
            headers=pending.headers,
        )
    ).json()["error"]["code"] == "driver_not_approved"
    await go_online(client, ok, FAR)

    ride = await request_ride(client, passenger)
    assert [str(o.driver_id) for o in await _offers(ride["id"])] == [ok.id]


async def _user(email: str) -> User:
    async with SessionLocal() as session:
        return await session.scalar(select(User).where(User.email == email))


async def test_busy_driver_with_open_offer_is_not_double_booked(client, passenger):
    driver = await make_driver(client, "a@example.com", "A")
    await go_online(client, driver, NEAR)
    ride = await request_ride(client, passenger)
    await _make_user("bob@example.com")
    bob = Actor(await _user("bob@example.com"), await _login(client, "bob@example.com"))
    second = await request_ride(client, bob)
    assert len(await _offers(ride["id"])) == 1
    assert await _offers(second["id"]) == []  # the only driver holds the first offer


async def test_concurrent_accept_only_one_wins(client, passenger):
    first = await make_driver(client, "a@example.com", "A")
    second = await make_driver(client, "b@example.com", "B")
    await go_online(client, first, NEAR)
    ride = await request_ride(client, passenger)
    # Simulate a race: both drivers hold a live offer for the same ride.
    async with SessionLocal() as session:
        session.add(
            RideOffer(
                ride_id=uuid.UUID(ride["id"]),
                driver_id=second.user.id,
                status=OfferStatus.PENDING,
                pickup_distance_m=500,
                pickup_eta_s=60,
                expires_at=utcnow().replace(year=2099),
            )
        )
        await session.commit()
    responses = await asyncio.gather(
        client.post(f"{API}/rides/{ride['id']}/accept", headers=first.headers),
        client.post(f"{API}/rides/{ride['id']}/accept", headers=second.headers),
    )
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 409]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["error"]["code"] == "ride_taken"
    winner = next(r for r in responses if r.status_code == 200).json()
    assert (await _ride(ride["id"])).driver_id == uuid.UUID(winner["driver"]["id"])


# --- Cancellation ------------------------------------------------------------------------------


async def test_passenger_cancels_while_searching(client, passenger, recorder):
    driver = await make_driver(client, "a@example.com", "A")
    await go_online(client, driver, NEAR)
    ride = await request_ride(client, passenger)
    response = await client.post(
        f"{API}/rides/{ride['id']}/cancel",
        json={"reason": "cambié de idea"},
        headers=passenger.headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled_by_passenger" and body["cancel_reason"] == "cambié de idea"
    assert recorder.of("ride.offer_cancelled", driver.id) == [{"ride_id": ride["id"]}]
    assert (await _offers(ride["id"]))[0].status == OfferStatus.CANCELLED
    accept = await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    assert accept.json()["error"]["code"] == "ride_taken"
    # The driver is free again and the passenger can ask for another ride.
    assert (await client.get(f"{API}/rides/active", headers=passenger.headers)).json() is None
    again = await request_ride(client, passenger)
    assert [str(o.driver_id) for o in await _offers(again["id"])] == [driver.id]


async def test_cancellation_rules(client, passenger, recorder, admin_headers):
    driver = await make_driver(client, "a@example.com", "A")
    ride = await _assigned_ride(client, passenger, driver)
    response = await client.post(f"{API}/rides/{ride['id']}/cancel", headers=driver.headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled_by_driver"
    assert recorder.pushed("cancelled_by_driver", passenger.id)
    assert (await client.get(f"{API}/drivers/me/state", headers=driver.headers)).json()[
        "active_ride_id"
    ] is None

    ride = await _assigned_ride(client, passenger, driver)
    for step in ("arrive", "start"):
        await client.post(f"{API}/rides/{ride['id']}/{step}", headers=driver.headers)
    for who in (passenger, driver):
        response = await client.post(f"{API}/rides/{ride['id']}/cancel", headers=who.headers)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ride_invalid_transition"

    # Staff can cancel at any active status, with a reason.
    missing = await client.post(
        f"{API}/admin/rides/{ride['id']}/cancel", json={"reason": " "}, headers=admin_headers
    )
    assert missing.status_code == 422
    response = await client.post(
        f"{API}/admin/rides/{ride['id']}/cancel",
        json={"reason": "accidente"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled_by_admin"
    assert recorder.pushed("cancelled_by_admin", passenger.id)
    assert recorder.pushed("cancelled_by_admin", driver.id)
    again = await client.post(
        f"{API}/admin/rides/{ride['id']}/cancel", json={"reason": "x"}, headers=admin_headers
    )
    assert again.json()["error"]["code"] == "ride_invalid_transition"


# --- Presence ----------------------------------------------------------------------------------


async def test_driver_presence(client, user_headers):
    response = await client.post(
        f"{API}/drivers/me/online", json={"lat": 10.5, "lng": -66.9}, headers=user_headers
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "driver_not_approved"

    driver = await make_driver(client, "a@example.com", "A")
    await go_online(client, driver, NEAR)
    assert await presence.is_online(driver.id)
    await presence.handle_location(driver.id, {"type": "location", "lat": 10.6, "lng": -66.9})
    loc = await presence.get_location(driver.id)
    assert loc.lat == NEAR[0]  # faster than 1 update per second: ignored
    await age_location(driver, 5)
    await presence.handle_location(driver.id, {"type": "location", "lat": 10.6, "lng": -66.9})
    assert (await presence.get_location(driver.id)).lat == 10.6

    response = await client.post(f"{API}/drivers/me/offline", headers=driver.headers)
    assert response.status_code == 200 and response.json()["online"] is False
    # Offline drivers' locations are ignored.
    await presence.handle_location(driver.id, {"type": "location", "lat": 10.5, "lng": -66.9})
    assert await presence.get_location(driver.id) is None


async def test_offline_declines_open_offer(client, passenger):
    first = await make_driver(client, "a@example.com", "A")
    second = await make_driver(client, "b@example.com", "B")
    await go_online(client, first, NEAR)
    await go_online(client, second, MID)
    ride = await request_ride(client, passenger)
    await client.post(f"{API}/drivers/me/offline", headers=first.headers)
    offers = await _offers(ride["id"])
    assert [(str(o.driver_id), o.status) for o in offers] == [
        (first.id, OfferStatus.DECLINED),
        (second.id, OfferStatus.PENDING),
    ]


async def test_stale_drivers_cleanup(client):
    driver = await make_driver(client, "a@example.com", "A")
    await go_online(client, driver, NEAR)
    await age_location(driver, 3600)
    assert await presence.cleanup_stale(1800) == [driver.id]
    assert not await presence.is_online(driver.id)


async def test_reconcile_reschedules_lost_rides(client, passenger):
    ride = await request_ride(client, passenger)
    await dispatch.unschedule(uuid.UUID(ride["id"]))
    assert await dispatch.reconcile() == 1
    assert await dispatch.reconcile() == 0


# --- Admin -------------------------------------------------------------------------------------


async def test_admin_endpoints(client, passenger, staff_headers, user_headers):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride = await _completed_ride(client, passenger, driver)
    await client.post(
        f"{API}/rides/{ride['id']}/rating", json={"stars": 5}, headers=passenger.headers
    )

    assert (await client.get(f"{API}/admin/rides", headers=user_headers)).status_code == 403
    listing = await client.get(f"{API}/admin/rides?q=luis&status=completed", headers=staff_headers)
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["passenger_name"] == "Ana Pérez" and item["driver_name"] == "Luis Gómez"
    assert item["driver"]["profile_id"] == item["driver_profile_id"]
    plate = item["driver"]["vehicle"]["plate"]
    assert (await client.get(f"{API}/admin/rides?q={plate.lower()}", headers=staff_headers)).json()[
        "total"
    ] == 1
    assert (await client.get(f"{API}/admin/rides?q=nadie", headers=staff_headers)).json()[
        "total"
    ] == 0
    assert (await client.get(f"{API}/admin/rides?q={ride['id']}", headers=staff_headers)).json()[
        "total"
    ] == 1
    today = utcnow().astimezone(CARACAS_TZ).date()
    in_range = await client.get(
        f"{API}/admin/rides?date_from={today}&date_to={today}", headers=staff_headers
    )
    assert in_range.json()["total"] == 1
    future = await client.get(f"{API}/admin/rides?date_from=2099-01-01", headers=staff_headers)
    assert future.json()["total"] == 0

    detail = (await client.get(f"{API}/admin/rides/{ride['id']}", headers=staff_headers)).json()
    assert detail["offers"][0]["status"] == "accepted"
    assert detail["offers"][0]["driver_name"] == "Luis Gómez" and detail["offers"][0]["sent_at"]
    assert detail["ratings"][0]["rater_role"] == "passenger"
    assert detail["messages"] == []
    assert (
        await client.get(f"{API}/admin/rides/{uuid.uuid4()}", headers=staff_headers)
    ).status_code == 404

    await go_online(client, driver, NEAR)
    online = (await client.get(f"{API}/admin/drivers/online", headers=staff_headers)).json()
    assert len(online) == 1
    assert online[0]["name"] == "Luis Gómez" and online[0]["lat"] == NEAR[0]
    assert online[0]["driver_id"] == online[0]["driver_profile_id"] == item["driver_profile_id"]
    assert online[0]["active_ride_id"] is None

    live = (await client.get(f"{API}/admin/rides/live", headers=staff_headers)).json()
    assert live == []


async def test_websocket_location_message(client):
    from apps.realtime.tests.test_realtime import _ws_session

    driver = await make_driver(client, "a@example.com", "A")
    await go_online(client, driver, NEAR)
    await age_location(driver, 5)
    token = driver.headers["Authorization"].split()[1]
    sent = await _ws_session(
        [
            {"type": "websocket.receive", "text": f'{{"type": "auth", "token": "{token}"}}'},
            {
                "type": "websocket.receive",
                "text": '{"type": "location", "lat": 10.52, "lng": -66.9, "heading": 180}',
            },
            {"type": "websocket.receive", "text": '{"type": "location", "lat": "bad"}'},
            {"type": "websocket.receive", "text": '{"type": "ping"}'},
        ]
    )
    texts = [m.get("text", "") for m in sent if m["type"] == "websocket.send"]
    assert '"pong"' in texts[-1]  # the socket survived the bad message
    loc = await presence.get_location(driver.id)
    assert (loc.lat, loc.lng, loc.heading) == (10.52, -66.9, 180.0)
