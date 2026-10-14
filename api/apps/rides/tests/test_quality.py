"""Doc 15: cancellation reasons, waiting and no-shows, reassignment, pauses and quality rates."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from apps.config.services import get_app_config
from apps.moderation.models import Report, ReportCategory
from apps.notifications.models import Notification
from apps.quality import services as quality
from apps.quality.models import QualityLevel, QualityPause, QualityRole, QualityStats
from apps.rides.models import CancelReason, OfferStatus, Ride, RideCancellation, RideOffer
from apps.rides.state import utcnow
from conftest import ride_step
from kuulis.core.db import SessionLocal

from .conftest import MID, NEAR, go_online, make_driver, request_ride

API = "/api/v1"


@pytest.fixture(autouse=True)
def quality_events(monkeypatch, recorder):
    async def fake_publish(event, data=None, user_ids=None):
        recorder.events.append((event, data, user_ids))

    monkeypatch.setattr(quality, "publish", fake_publish)
    return recorder


async def _assigned(client, passenger, driver, point=NEAR) -> dict:
    await go_online(client, driver, point)
    ride = await request_ride(client, passenger)
    response = await client.post(f"{API}/rides/{ride['id']}/accept", headers=driver.headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _shift(ride_id: str, **fields: timedelta) -> None:
    """Moves ride timestamps into the past (``assigned_at=timedelta(minutes=3)``)."""
    async with SessionLocal() as session:
        ride = await session.get(Ride, uuid.UUID(ride_id))
        for name, delta in fields.items():
            setattr(ride, name, getattr(ride, name) - delta)
        await session.commit()


async def _cancellations(ride_id: str) -> list[RideCancellation]:
    async with SessionLocal() as session:
        rows = await session.scalars(
            select(RideCancellation)
            .where(RideCancellation.ride_id == uuid.UUID(ride_id))
            .order_by(RideCancellation.created_at)
        )
        return list(rows)


async def _cancel(client, ride_id: str, who, code: str | None = None, reason: str | None = None):
    body = {"reason_code": code, "reason": reason}
    return await client.post(f"{API}/rides/{ride_id}/cancel", json=body, headers=who.headers)


# --- Passenger cancellations -------------------------------------------------------------------


async def test_passenger_grace_and_reasons(client, passenger):
    driver = await make_driver(client, "a@example.com", "A")
    ride = await _assigned(client, passenger, driver)
    assert ride["cancel_free_until"] is not None

    wrong = await _cancel(client, ride["id"], passenger, "no_show")
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "cancel_reason_invalid"

    # Inside the grace period: logged, not counted.
    response = await _cancel(client, ride["id"], passenger, "changed_plans")
    assert response.status_code == 200
    assert response.json()["cancel_reason_code"] == "changed_plans"
    [log] = await _cancellations(ride["id"])
    assert (log.side, log.counted, log.stage.value) == ("passenger", False, "driver_assigned")

    # After it: counted.
    ride = await _assigned(client, passenger, driver)
    await _shift(ride["id"], assigned_at=timedelta(minutes=3))
    await _cancel(client, ride["id"], passenger, "driver_late", "Tardó demasiado")
    [log] = await _cancellations(ride["id"])
    assert log.counted is True and log.reason == "Tardó demasiado"

    # Old apps send no code: still works.
    ride = await request_ride(client, passenger)
    old = await client.post(f"{API}/rides/{ride['id']}/cancel", headers=passenger.headers)
    assert old.status_code == 200
    [log] = await _cancellations(ride["id"])
    assert log.reason_code is None and log.counted is False  # no driver yet


async def test_vehicle_mismatch_opens_a_report(client, passenger):
    driver = await make_driver(client, "a@example.com", "A")
    ride = await _assigned(client, passenger, driver)
    await _shift(ride["id"], assigned_at=timedelta(minutes=5))
    response = await _cancel(client, ride["id"], passenger, "vehicle_mismatch")
    assert response.status_code == 200
    [log] = await _cancellations(ride["id"])
    assert log.counted is False  # never against the passenger
    async with SessionLocal() as session:
        report = await session.scalar(select(Report).where(Report.ride_id == uuid.UUID(ride["id"])))
    assert report is not None
    assert report.category == ReportCategory.VEHICLE_MISMATCH
    assert str(report.reported_user_id) == driver.id


# --- No-show -----------------------------------------------------------------------------------


async def test_no_show_after_the_wait(client, passenger, recorder):
    driver = await make_driver(client, "a@example.com", "A")
    ride = await _assigned(client, passenger, driver)
    early = await _cancel(client, ride["id"], driver, "no_show")
    assert early.status_code == 409 and early.json()["error"]["code"] == "no_show_too_early"

    arrived = (await ride_step(client, ride["id"], "arrive", driver.headers)).json()
    assert arrived["no_show_at"] is not None
    early = await _cancel(client, ride["id"], driver, "no_show")
    assert early.json()["error"]["code"] == "no_show_too_early"
    assert early.json()["error"]["details"]["available_at"]

    await _shift(ride["id"], arrived_at=timedelta(minutes=5, seconds=1))
    response = await _cancel(client, ride["id"], driver, "no_show")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "cancelled_by_driver" and body["cancel_reason_code"] == "no_show"
    assert recorder.pushed("no_show", passenger.id)
    [log] = await _cancellations(ride["id"])
    assert log.counted is False and log.reason_code == CancelReason.NO_SHOW


async def test_no_shows_pause_the_passenger(client, passenger):
    driver = await make_driver(client, "a@example.com", "A")
    for _ in range(3):
        ride = await _assigned(client, passenger, driver)
        await ride_step(client, ride["id"], "arrive", driver.headers)
        await _shift(ride["id"], arrived_at=timedelta(minutes=6))
        assert (await _cancel(client, ride["id"], driver, "no_show")).status_code == 200

    quote = await client.post(
        f"{API}/rides/quote",
        json={
            "pickup": {"lat": 10.49, "lng": -66.88, "address": "A"},
            "dropoff": {"lat": 10.50, "lng": -66.85, "address": "B"},
            "vehicle_type": "moto",
        },
        headers=passenger.headers,
    )
    assert quote.status_code == 403
    error = quote.json()["error"]
    assert error["code"] == "temporarily_paused" and error["details"]["reason"] == "no_shows"
    async with SessionLocal() as session:
        inbox = await session.scalar(
            select(Notification).where(Notification.user_id == passenger.user.id)
        )
    assert inbox is not None and inbox.title == "Tu cuenta está en pausa"


# --- Driver cancellation and reassignment ------------------------------------------------------


async def test_driver_cancel_reassigns_the_ride(client, passenger, recorder):
    first = await make_driver(client, "a@example.com", "A")
    second = await make_driver(client, "b@example.com", "B")
    await go_online(client, second, MID)
    ride = await _assigned(client, passenger, first)
    sent = await client.post(
        f"{API}/rides/{ride['id']}/messages", json={"text": "voy"}, headers=first.headers
    )
    assert sent.status_code == 201

    wrong = await _cancel(client, ride["id"], first, "driver_late")
    assert wrong.json()["error"]["code"] == "cancel_reason_invalid"
    response = await _cancel(client, ride["id"], first, "wrong_address")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled_by_driver"
    assert recorder.pushed("reassigning", passenger.id)
    assert recorder.of("ride.updated", first.id)[-1]["status"] == "cancelled_by_driver"
    # A retry from the first driver is harmless.
    again = await _cancel(client, ride["id"], first, "wrong_address")
    assert again.status_code == 200 and again.json()["status"] == "cancelled_by_driver"
    assert len(await _cancellations(ride["id"])) == 1

    async with SessionLocal() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        offers = list(
            await session.scalars(
                select(RideOffer).where(RideOffer.ride_id == row.id).order_by(RideOffer.created_at)
            )
        )
    assert row.status.value == "searching" and row.reassign_count == 1
    assert str(row.reassigned_from_driver_id) == first.id and row.driver_id is None
    assert [str(o.driver_id) for o in offers] == [first.id, second.id]
    assert offers[-1].status == OfferStatus.PENDING

    accepted = await client.post(f"{API}/rides/{ride['id']}/accept", headers=second.headers)
    assert accepted.status_code == 200
    assert accepted.json()["reassign_count"] == 1
    messages = await client.get(f"{API}/rides/{ride['id']}/messages", headers=second.headers)
    assert messages.json() == []  # the new driver does not read the first conversation
    [log] = await _cancellations(ride["id"])
    assert log.reassigned is True and log.counted is True

    # Once the ride started it cannot be cancelled by the driver, as before.
    for step in ("arrive", "start"):
        await ride_step(client, ride["id"], step, second.headers)
    late = await _cancel(client, ride["id"], second, "other")
    assert late.json()["error"]["code"] == "ride_invalid_transition"


async def test_cancel_burst_pauses_the_driver(client, passenger, recorder):
    driver = await make_driver(client, "a@example.com", "A")
    for i in range(3):
        ride = await _assigned(client, passenger, driver)
        assert (await _cancel(client, ride["id"], driver, "vehicle_problem")).status_code == 200
        assert (await _cancel(client, ride["id"], passenger, "other")).status_code == 200
        paused = recorder.of("quality.paused", driver.id)
        assert bool(paused) == (i == 2)

    response = await client.post(
        f"{API}/drivers/me/online", json={"lat": NEAR[0], "lng": NEAR[1]}, headers=driver.headers
    )
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "temporarily_paused" and error["details"]["reason"] == "cancel_burst"
    state = (await client.get(f"{API}/drivers/me/state", headers=driver.headers)).json()
    assert state["online"] is False
    mine = (await client.get(f"{API}/drivers/me/quality", headers=driver.headers)).json()
    assert mine["paused_until"] and mine["pause_reason"] == "cancel_burst"


async def test_decline_streak_pauses_and_admin_lifts(client, passenger, admin_headers):
    driver = await make_driver(client, "a@example.com", "A")
    await go_online(client, driver, NEAR)
    for _ in range(5):
        ride = await request_ride(client, passenger)
        declined = await client.post(f"{API}/rides/{ride['id']}/decline", headers=driver.headers)
        assert declined.status_code == 204
        await _cancel(client, ride["id"], passenger)
    async with SessionLocal() as session:
        pause = await session.scalar(
            select(QualityPause).where(QualityPause.user_id == driver.user.id)
        )
    assert pause is not None and pause.reason.value == "decline_streak"
    assert pause.until - utcnow() > timedelta(minutes=14)

    response = await client.post(
        f"{API}/admin/quality/pauses/{pause.id}/lift", headers=admin_headers
    )
    assert response.status_code == 200 and response.json()["lifted_at"]
    await go_online(client, driver, NEAR)
    twice = await client.post(f"{API}/admin/quality/pauses/{pause.id}/lift", headers=admin_headers)
    assert twice.json()["error"]["code"] == "pause_not_active"
    # The offers before the pause do not count again: one more decline is not a new streak.
    ride = await request_ride(client, passenger)
    await client.post(f"{API}/rides/{ride['id']}/decline", headers=driver.headers)
    async with SessionLocal() as session:
        count = len(
            list(
                await session.scalars(
                    select(QualityPause).where(QualityPause.user_id == driver.user.id)
                )
            )
        )
    assert count == 1


# --- Rates, levels and dispatch ----------------------------------------------------------------


@pytest.mark.usefixtures("relaxed_risk")
async def test_rates_match_a_manual_count(client, passenger, admin_headers):
    driver = await make_driver(client, "a@example.com", "A")
    # 4 accepted: 1 completed, 2 cancelled by the driver (one a safety concern), 1 no-show.
    completed = await _assigned(client, passenger, driver)
    for step in ("arrive", "start", "complete"):
        await ride_step(client, completed["id"], step, driver.headers)
    await client.post(
        f"{API}/rides/{completed['id']}/rating", json={"stars": 5}, headers=driver.headers
    )
    await client.post(
        f"{API}/rides/{completed['id']}/rating", json={"stars": 4}, headers=passenger.headers
    )
    for code in ("vehicle_problem", "safety_concern"):
        ride = await _assigned(client, passenger, driver)
        await _cancel(client, ride["id"], driver, code)
        await _cancel(client, ride["id"], passenger, "other")
    ride = await _assigned(client, passenger, driver)
    await ride_step(client, ride["id"], "arrive", driver.headers)
    await _shift(ride["id"], arrived_at=timedelta(minutes=6))
    await _cancel(client, ride["id"], driver, "no_show")
    # 1 declined offer.
    ride = await request_ride(client, passenger)
    await client.post(f"{API}/rides/{ride['id']}/decline", headers=driver.headers)
    await _cancel(client, ride["id"], passenger)

    mine = (await client.get(f"{API}/drivers/me/quality", headers=driver.headers)).json()
    assert (mine["offers"], mine["accepted"], mine["cancels"], mine["completed"]) == (5, 4, 1, 1)
    assert mine["acceptance_rate"] == 0.8 and mine["cancel_rate"] == 0.25
    assert mine["rating_avg"] == 4.0 and mine["thresholds"]["pickup_wait_minutes"] == 5

    detail = await client.get(f"{API}/admin/quality/users/{passenger.id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    p = detail.json()["passenger"]
    # 4 rides got a driver (the declined one never did); the passenger's own cancellations
    # came after the driver left (searching), so none counts.
    assert (p["rides"], p["cancels"], p["no_shows"], p["completed"]) == (4, 0, 1, 1)
    assert detail.json()["driver"] is None
    assert sum(w["no_shows"] for w in detail.json()["weeks"]) == 1

    by_reason = (
        await client.get(f"{API}/admin/quality/cancellations", headers=admin_headers)
    ).json()
    driver_rows = {r["reason_code"]: r for r in by_reason if r["side"] == "driver"}
    assert driver_rows["vehicle_problem"] == {
        "side": "driver",
        "reason_code": "vehicle_problem",
        "total": 1,
        "counted": 1,
        "reassigned": 1,
    }
    assert driver_rows["safety_concern"]["counted"] == 0
    assert driver_rows["no_show"]["reassigned"] == 0


async def test_refresh_levels_warnings_and_admin_list(client, passenger, admin_headers):
    driver = await make_driver(client, "a@example.com", "A")
    async with SessionLocal() as session:
        config = await get_app_config(session)
    q = config.quality.model_copy(update={"min_rides": 2, "driver_cancel_burst": 0})
    config = config.model_copy(update={"quality": q})
    for _ in range(2):
        ride = await _assigned(client, passenger, driver)
        await _cancel(client, ride["id"], driver, "other")
        await _cancel(client, ride["id"], passenger, "other")
    async with SessionLocal() as session:
        values = await quality.compute(session, QualityRole.DRIVER, q, [driver.user.id])
        assert values[driver.user.id].cancel_rate == 1.0
        assert values[driver.user.id].level == QualityLevel.REVIEW
        assert await quality.refresh(session, config) >= 2
        row = await session.scalar(
            select(QualityStats).where(
                QualityStats.user_id == driver.user.id, QualityStats.role == QualityRole.DRIVER
            )
        )
        assert row.level == QualityLevel.REVIEW and row.reasons == ["cancel_rate"]
        assert row.warned_level == QualityLevel.REVIEW
        factors = await quality.dispatch_factors(session, [driver.user.id], q)
        assert factors[driver.user.id] >= 1.5

    listed = await client.get(
        f"{API}/admin/quality/users", params={"role": "driver"}, headers=admin_headers
    )
    assert listed.status_code == 200, listed.text
    [item] = listed.json()["items"]
    assert item["user_id"] == driver.id and item["level"] == "review"
    assert item["driver_profile_id"]
    passengers = await client.get(
        f"{API}/admin/quality/users", params={"role": "passenger"}, headers=admin_headers
    )
    assert passengers.json()["items"] == []


async def test_dispatch_prefers_reliable_drivers_at_similar_distance(client, passenger):
    unreliable = await make_driver(client, "a@example.com", "A")
    reliable = await make_driver(client, "b@example.com", "B")
    await go_online(client, unreliable, NEAR)  # ~110 m
    await go_online(client, reliable, (10.49135, -66.8800))  # ~150 m
    async with SessionLocal() as session:
        session.add(
            QualityStats(
                user_id=unreliable.user.id,
                role=QualityRole.DRIVER,
                offers=20,
                accepted=10,
                rides=10,
                cancels=3,
                acceptance_rate=0.5,
                cancel_rate=0.3,
                level=QualityLevel.LOW_PRIORITY,
                reasons=["cancel_rate"],
                warned_level=QualityLevel.LOW_PRIORITY,
                computed_at=utcnow(),
            )
        )
        await session.commit()
    ride = await request_ride(client, passenger)
    async with SessionLocal() as session:
        offer = await session.scalar(
            select(RideOffer).where(RideOffer.ride_id == uuid.UUID(ride["id"]))
        )
    assert str(offer.driver_id) == reliable.id

    # Far apart, distance still wins: the penalty only reorders similar distances.
    await client.post(f"{API}/rides/{ride['id']}/cancel", headers=passenger.headers)
    await go_online(client, reliable, MID)  # ~1.7 km
    ride = await request_ride(client, passenger)
    async with SessionLocal() as session:
        offer = await session.scalar(
            select(RideOffer).where(RideOffer.ride_id == uuid.UUID(ride["id"]))
        )
    assert str(offer.driver_id) == unreliable.id
