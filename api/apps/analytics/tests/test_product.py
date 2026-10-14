"""Product analytics (doc 19): app events, opting out, the supply sampler and the admin reports."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text

from apps.analytics import events, maintenance, product
from apps.analytics.models import AnalyticsEvent, DriverOnlineSession, SupplyHour
from apps.config.services import get_app_config
from apps.drivers.models import VehicleType
from apps.promotions.models import DiscountType, Promotion
from apps.rides.models import PaymentMethod, Ride, RideStatus
from apps.rides.tests.conftest import DROPOFF, PICKUP, go_online, make_driver
from apps.subscriptions.models import Charge, ChargeStatus
from apps.users.models import Role
from conftest import _login, _make_user, make_staff_role
from kuulis.core.calendar import local_now
from kuulis.core.db import SessionLocal

API = "/api/v1"
CARACAS_CELL = events.cell_of(PICKUP["lat"], PICKUP["lng"])


def _batch(*items, anon="install-1234"):
    now = datetime.now(UTC).isoformat()
    return {
        "anon_id": anon,
        "platform": "android",
        "app_version": "1.0.0 (12)",
        "events": [{"occurred_at": now, **item} for item in items],
    }


async def _events() -> list[AnalyticsEvent]:
    async with SessionLocal() as session:
        return list(await session.scalars(select(AnalyticsEvent).order_by(AnalyticsEvent.event)))


async def _ride(passenger_id, driver_id, status, at, *, promotion=None, discount="0"):
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
            fare=Decimal("3.00"),
            discount=Decimal(discount),
            promotion_id=promotion,
            surge_multiplier=Decimal("1"),
            payment_method=PaymentMethod.CASH_USD,
            requested_at=at,
            search_expires_at=at,
            assigned_at=at + timedelta(minutes=1) if driver_id else None,
            completed_at=at + timedelta(minutes=21) if status == RideStatus.COMPLETED else None,
        )
        session.add(ride)
        await session.commit()
        return ride


def now_minus(minutes: int) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=minutes)


# --- Events ------------------------------------------------------------------------------------


def test_event_catalogue_has_no_personal_data():
    for name, spec in events.EVENTS.items():
        assert not set(spec) & events.FORBIDDEN_KEYS, name
    props = events.clean_props(
        "report_created",
        {"category": "ana@example.com", "email": "ana@example.com", "lat": 10.49, "lng": -66.88},
    )
    assert props == {}
    assert events.clean_props("screen_view", {"screen": "Llámame al +58 412 123 4567"}) == {}
    assert events.clean_props(
        "screen_view", {"screen": "/reports/0b5f7c3e-6a0f-4e8e-9d2a-1c3b4d5e6f70"}
    ) == {"screen": "/reports/:id"}
    assert events.clean_props("rating_submitted", {"stars": "5", "role": "passenger"}) == {
        "role": "passenger"
    }
    assert events.cell_of(10.49, -66.88) == "1049:-6688"
    assert events.cell_center("1049:-6688") == (10.495, -66.875)


async def test_post_events(client, user_headers):
    old = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    response = await client.post(
        f"{API}/analytics/events",
        json=_batch(
            {"event": "app_open", "props": {"mode": "passenger", "cold": True, "phone": "1"}},
            {"event": "quote_shown", "cell": CARACAS_CELL, "props": {"fare": 2.456}},
            {"event": "made_up_event"},
            {"event": "search_opened", "occurred_at": old},
            {"event": "search_opened", "occurred_at": future},
        ),
    )
    assert response.status_code == 202, response.text
    assert response.json() == {"accepted": 3, "dropped": 2}
    rows = await _events()
    by_event = {r.event: r for r in rows}
    assert by_event["app_open"].props == {"mode": "passenger", "cold": True}
    assert by_event["app_open"].user_id is None and by_event["app_open"].platform == "android"
    quote = by_event["quote_shown"]
    assert quote.props == {"fare": 2.46} and quote.area == "Caracas"
    # A clock in the future is brought back to now.
    assert by_event["search_opened"].occurred_at <= datetime.now(UTC)

    signed_in = await client.post(
        f"{API}/analytics/events",
        json=_batch({"event": "search_opened"}),
        headers=user_headers,
    )
    assert signed_in.json()["accepted"] == 1
    assert sum(1 for r in await _events() if r.user_id is not None) == 1

    too_many = _batch(*[{"event": "app_open"}] * 101)
    assert (await client.post(f"{API}/analytics/events", json=too_many)).status_code == 422
    bad_cell = _batch({"event": "quote_shown", "cell": "10.4912,-66.8812"})
    assert (await client.post(f"{API}/analytics/events", json=bad_cell)).status_code == 422


async def test_opting_out_stops_events(client, user_headers):
    me = (await client.get(f"{API}/users/me", headers=user_headers)).json()
    assert "usage_data" in me["consents"]  # on by default (doc 19, question 1)

    assert (
        await client.post(
            f"{API}/analytics/events", json=_batch({"event": "app_open"}), headers=user_headers
        )
    ).json()["accepted"] == 1
    consent = await client.put(
        f"{API}/users/me/consents",
        json={"kind": "usage_data", "granted": False},
        headers=user_headers,
    )
    assert consent.status_code == 200 and "usage_data" not in consent.json()
    response = await client.post(
        f"{API}/analytics/events", json=_batch({"event": "app_open"}), headers=user_headers
    )
    assert response.json() == {"accepted": 0, "dropped": 1}
    assert len(await _events()) == 1

    await client.put(
        f"{API}/users/me/consents",
        json={"kind": "usage_data", "granted": True},
        headers=user_headers,
    )
    response = await client.post(
        f"{API}/analytics/events", json=_batch({"event": "app_open"}), headers=user_headers
    )
    assert response.json()["accepted"] == 1


# --- Supply sampler and drivers ----------------------------------------------------------------


async def test_sampler_tracks_online_sessions_and_supply(client, admin_headers):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, (PICKUP["lat"], PICKUP["lng"]))
    async with SessionLocal() as session:
        config = await get_app_config(session)
        first = await maintenance.sample_supply(session, config)
        await maintenance.sample_supply(session, config)
    assert first == {"online": 1, "opened": 1, "closed": 0, "cells": 1}
    async with SessionLocal() as session:
        open_session = await session.scalar(select(DriverOnlineSession))
        supply = await session.scalar(select(SupplyHour))
    assert open_session.ended_at is None and open_session.area == "Caracas"
    assert supply.cell == CARACAS_CELL and supply.driver_minutes == 2

    off = await client.post(f"{API}/drivers/me/offline", headers=driver.headers)
    assert off.status_code == 200
    async with SessionLocal() as session:
        closed = await maintenance.sample_supply(session, config)
        assert closed["closed"] == 1
        # Online for two hours, one ride of 20 minutes in them.
        row = await session.scalar(select(DriverOnlineSession))
        row.started_at = datetime.now(UTC) - timedelta(hours=2)
        await session.commit()
    ana = await _make_user("ana@example.com")
    await _ride(ana.id, driver.user.id, RideStatus.COMPLETED, now_minus(30))

    response = await client.get(f"{API}/admin/analytics/drivers", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["drivers"] == 1 and body["total_earnings"] == "3.00"
    assert body["online_drivers"] == 1 and body["online_hours"] == 2.0
    assert body["ride_hours"] == 0.3 and body["utilization"] == 16.7
    assert body["earnings"][0] == {"min": 0, "max": 10, "count": 1}
    assert sum(b["count"] for b in body["utilization_spread"]) == 1
    assert sum(t["drivers"] for t in body["tiers"]) == 1


# --- Funnels, retention, supply and demand, promotions -----------------------------------------


async def test_funnels_and_retention(client, admin_headers):
    now = datetime.now(UTC)
    ana = await _make_user("ana@example.com")
    await _make_user("leo@example.com")  # signed up, never asked for a ride
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    async with SessionLocal() as session:
        session.add(
            Charge(
                user_id=driver.user.id,
                month=date.today().replace(day=1),
                earnings=Decimal("120"),
                fee=Decimal("5"),
                status=ChargeStatus.PAID,
                due_at=now,
            )
        )
        await session.commit()
    # Ana: first ride 4 weeks ago, again in her week 1 and her week 2 (not in week 4 yet).
    four_weeks = now - timedelta(days=28)
    for days in (0, 8, 15):
        await _ride(ana.id, driver.user.id, RideStatus.COMPLETED, four_weeks + timedelta(days=days))
    await _ride(ana.id, None, RideStatus.NO_DRIVERS, now - timedelta(hours=1))
    await client.post(
        f"{API}/analytics/events",
        json=_batch(
            {"event": "quote_shown", "cell": CARACAS_CELL},
            {"event": "quote_shown", "cell": CARACAS_CELL},
            {"event": "driver_onboarding_step", "props": {"step": "personal"}},
            {"event": "driver_onboarding_step", "props": {"step": "vehicle"}},
        ),
    )

    async with SessionLocal() as session:
        config = await get_app_config(session)
        result = await product.refresh_cohorts(session, config)
    assert result["passenger_funnel"] and result["driver_funnel"]

    response = await client.get(
        f"{API}/admin/analytics/funnels",
        params={"from": str(local_now().date() - timedelta(days=60))},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    passenger = {s["step"]: s["users"] for s in body["passenger"]}
    # Every account signs up (the driver too); Ana is the only one who asked for and took a ride.
    assert passenger == {"signup": 3, "first_request": 1, "first_ride": 1}
    driver_steps = {s["step"]: s["users"] for s in body["driver"]}
    assert driver_steps["application"] == 1 and driver_steps["vehicle"] == 1
    # The fixture skips the dates of the application: a fee paid implies every earlier step.
    assert driver_steps["submitted"] == 1 and driver_steps["approved"] == 1
    assert driver_steps["first_fee"] == 1 and driver_steps["first_ride"] == 1
    rides = {s["step"]: s["users"] for s in body["rides"]}
    assert rides == {"quote": 2, "request": 4, "matched": 3, "completed": 3}
    screens = {s["step"]: s["users"] for s in body["onboarding_screens"]}
    assert screens["personal"] == 1 and screens["vehicle"] == 1 and screens["review"] == 0
    assert body["computed_at"] is not None
    assert (
        await client.get(
            f"{API}/admin/analytics/funnels", params={"area": "Madrid"}, headers=admin_headers
        )
    ).json()["error"]["code"] == "area_not_found"

    response = await client.get(
        f"{API}/admin/analytics/retention",
        params={"from": str(local_now().date() - timedelta(days=60))},
        headers=admin_headers,
    )
    body = response.json()
    rows = body["passenger"]["rows"]
    assert len(rows) == 1 and rows[0]["users"] == 1
    weeks = rows[0]["weeks"]
    assert weeks["8"] is None and weeks["4"] is None
    assert weeks["1"] == 1
    assert body["passenger"]["average"]["1"] == 100.0
    assert body["driver"]["rows"][0]["users"] == 1


async def test_supply_demand_and_csv(client, admin_headers):
    ana = await _make_user("ana@example.com")
    now = datetime.now(UTC)
    await _ride(ana.id, None, RideStatus.NO_DRIVERS, now - timedelta(minutes=10))
    await _ride(ana.id, None, RideStatus.NO_DRIVERS, now - timedelta(minutes=5))
    await client.post(
        f"{API}/analytics/events", json=_batch({"event": "quote_shown", "cell": CARACAS_CELL})
    )
    response = await client.get(f"{API}/admin/analytics/supply-demand", headers=admin_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    cell = body["cells"][0]
    assert cell["cell"] == CARACAS_CELL and cell["requests"] == 2 and cell["no_drivers"] == 2
    assert cell["quotes"] == 1 and cell["driver_hours"] == 0
    assert len(body["hours"]) == 24 and sum(h["no_drivers"] for h in body["hours"]) == 2
    other_hour = (local_now().hour + 12) % 24
    empty = await client.get(
        f"{API}/admin/analytics/supply-demand", params={"hour": other_hour}, headers=admin_headers
    )
    assert empty.json()["cells"] == []

    csv = await client.get(f"{API}/admin/analytics/supply-demand.csv", headers=admin_headers)
    assert csv.status_code == 200 and csv.text.splitlines()[0].startswith("celda,lat,lng")
    assert CARACAS_CELL in csv.text and "ana@example.com" not in csv.text
    for report in ("funnels", "retention", "promotions", "drivers"):
        assert (
            await client.get(f"{API}/admin/analytics/{report}.csv", headers=admin_headers)
        ).status_code == 200
    # A role without the analytics permissions (e.g. Soporte) cannot see them.
    support = await make_staff_role("support_only", {"dashboard.view", "reports.manage"})
    await _make_user("soporte@example.com", Role.STAFF, support)
    headers = await _login(client, "soporte@example.com")
    assert (await client.get(f"{API}/admin/analytics/funnels", headers=headers)).status_code == 403


async def test_promotions_report(client, admin_headers):
    now = datetime.now(UTC)
    ana = await _make_user("ana@example.com")
    leo = await _make_user("leo@example.com")
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    async with SessionLocal() as session:
        promo = Promotion(
            name="Bienvenida",
            code="HOLA",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("1.00"),
            starts_at=now - timedelta(days=60),
            ends_at=now + timedelta(days=60),
            budget=Decimal("100"),
        )
        session.add(promo)
        await session.commit()
    # Ana came with the promo 40 days ago and rode again; Leo came with it today.
    start = now - timedelta(days=40)
    await _ride(
        ana.id, driver.user.id, RideStatus.COMPLETED, start, promotion=promo.id, discount="1"
    )
    await _ride(ana.id, driver.user.id, RideStatus.COMPLETED, start + timedelta(days=3))
    await _ride(
        leo.id,
        driver.user.id,
        RideStatus.COMPLETED,
        now - timedelta(hours=1),
        promotion=promo.id,
        discount="1",
    )
    response = await client.get(
        f"{API}/admin/analytics/promotions",
        params={"from": str(local_now().date() - timedelta(days=60))},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    [row] = response.json()
    assert row["name"] == "Bienvenida" and row["rides"] == 2 and row["cost"] == "2.00"
    assert row["cost_per_ride"] == "1.00" and row["new_passengers"] == 2
    assert row["returned_30d"] == 1 and row["eligible_30d"] == 1 and row["retention_30d"] == 50.0


# --- Partitions and retention ------------------------------------------------------------------


async def test_partitions_and_retention():
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        created = await maintenance.ensure_partitions(session, now)
        names = await maintenance.partitions(session)
        month = now.date().replace(day=1)
        assert maintenance.partition_name(month) in names
        assert all(name in names for name in created)
        # Running again creates nothing.
        assert await maintenance.ensure_partitions(session, now) == []

        await session.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics_events_y2020m01 PARTITION OF "
                "analytics_events FOR VALUES FROM ('2020-01-01') TO ('2020-02-01')"
            )
        )
        await session.commit()
        removed = await maintenance.apply_retention(session, now)
        assert removed["partitions"] >= 1
        assert "analytics_events_y2020m01" not in await maintenance.partitions(session)
        # Events still land in the monthly table.
        session.add(
            AnalyticsEvent(occurred_at=now, anon_id="install-1234", event="app_open", props={})
        )
        await session.commit()
        stored = await session.scalar(
            text(f"SELECT count(*) FROM {maintenance.partition_name(month)}")  # noqa: S608
        )
        assert stored == 1
        assert await session.scalar(select(func.count()).select_from(AnalyticsEvent)) == 1


async def test_erasing_an_account_deletes_its_events(client, user_headers):
    from apps.privacy import services as privacy
    from apps.users.models import User

    await client.post(
        f"{API}/analytics/events", json=_batch({"event": "app_open"}), headers=user_headers
    )
    await client.post(f"{API}/analytics/events", json=_batch({"event": "app_open"}))
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == "user@example.com"))
        exported = await privacy.export_data(session, user)
        assert [e["event"] for e in exported["usage_events"]] == ["app_open"]
        await privacy.scrub(session, user, was_suspended=False)
        await session.commit()
    rows = await _events()
    assert len(rows) == 1 and rows[0].user_id is None  # the anonymous one stays
