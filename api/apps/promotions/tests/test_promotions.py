from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from apps.notifications.models import Notification
from apps.rates import services as rates
from apps.rates.models import RateSource
from apps.rides.tests.conftest import (
    DROPOFF,
    NEAR,
    PICKUP,
    go_online,
    make_driver,
)
from conftest import _login, _make_user
from kuulis.core.db import SessionLocal

API = "/api/v1"


def _promo(**overrides) -> dict:
    now = datetime.now(UTC)
    body = {
        "name": "Bienvenida",
        "code": None,
        "discount_type": "percent",
        "discount_value": "25",
        "max_discount": "1.00",
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(days=7)).isoformat(),
        "budget": "10.00",
        "max_uses_per_passenger": 5,
    }
    return body | overrides


async def _create(client, admin_headers, **overrides) -> dict:
    response = await client.post(
        f"{API}/admin/promotions", json=_promo(**overrides), headers=admin_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _quote(client, actor, code: str | None = None):
    body = {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"}
    if code is not None:
        body["promo_code"] = code
    return await client.post(f"{API}/rides/quote", json=body, headers=actor.headers)


async def _request(client, actor, quote: dict):
    return await client.post(
        f"{API}/rides",
        json={"quote_id": quote["quote_id"], "payment_method": "cash_usd"},
        headers=actor.headers,
    )


async def _complete(client, driver, ride_id: str) -> dict:
    response = await client.post(f"{API}/rides/{ride_id}/accept", headers=driver.headers)
    assert response.status_code == 200, response.text
    for step in ("arrive", "start", "complete"):
        response = await client.post(f"{API}/rides/{ride_id}/{step}", headers=driver.headers)
        assert response.status_code == 200, response.text
    return response.json()


async def _rate(client, actor, ride_id: str) -> None:
    response = await client.post(
        f"{API}/rides/{ride_id}/rating", json={"stars": 5}, headers=actor.headers
    )
    assert response.status_code in (200, 201), response.text


# --- Admin -------------------------------------------------------------------------------------


async def test_admin_promotion_validation(client, admin_headers, staff_headers):
    assert (
        await client.post(f"{API}/admin/promotions", json=_promo(), headers=staff_headers)
    ).status_code == 403
    for overrides in (
        {"discount_value": "120"},
        {"discount_type": "fixed", "discount_value": "0"},
        {"ends_at": "2020-01-01T00:00:00Z"},
        {"budget": "0"},
        {"code": "a!"},
        {"service_areas": ["Narnia"]},
        {"max_uses_per_passenger": 0},
    ):
        response = await client.post(
            f"{API}/admin/promotions", json=_promo(**overrides), headers=admin_headers
        )
        assert response.status_code == 422, (overrides, response.text)

    created = await _create(client, admin_headers, code=" hola 10 ", service_areas=["Caracas"])
    assert created["code"] == "HOLA10" and created["status"] == "active"
    assert created["stats"] == {
        "uses": 0,
        "completed": 0,
        "credited": "0.00",
        "reserved": "0.00",
        "remaining": "10.00",
    }
    taken = await client.post(
        f"{API}/admin/promotions", json=_promo(code="hola10"), headers=admin_headers
    )
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "promotion_code_taken"

    fixed = await _create(client, admin_headers, discount_type="fixed", discount_value="0.5")
    assert fixed["max_discount"] is None
    response = await client.patch(
        f"{API}/admin/promotions/{fixed['id']}", json={"is_active": False}, headers=admin_headers
    )
    assert response.status_code == 200 and response.json()["status"] == "inactive"
    scheduled = await _create(
        client,
        admin_headers,
        starts_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
        ends_at=(datetime.now(UTC) + timedelta(days=2)).isoformat(),
    )
    listing = await client.get(f"{API}/admin/promotions?status=scheduled", headers=staff_headers)
    assert [p["id"] for p in listing.json()["items"]] == [scheduled["id"]]
    search = await client.get(f"{API}/admin/promotions?q=hola", headers=staff_headers)
    assert search.json()["total"] == 1


# --- Applying ----------------------------------------------------------------------------------


async def test_automatic_promotion_quote_ride_and_credit(
    client, admin_headers, passenger, recorder
):
    async with SessionLocal() as session:
        await rates.record_auto(session, RateSource.BCV, Decimal("800"), datetime.now(UTC))
    await _create(client, admin_headers, name="Pequeña", discount_value="10")
    best = await _create(client, admin_headers, name="Grande")  # 25 % capped at $1.00
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)

    quote = (await _quote(client, passenger)).json()
    fare = Decimal(quote["fare"])
    discount = min(Decimal("1.00"), (fare * Decimal("0.25")).quantize(Decimal("0.01")))
    assert quote["promotion"]["name"] == "Grande"
    assert Decimal(quote["discount"]) == discount
    assert Decimal(quote["total"]) == fare - discount
    assert Decimal(quote["total_ves"]["bcv"]) == (fare - discount) * 800
    assert quote["total_ves"]["binance"] is None

    ride = (await _request(client, passenger, quote)).json()
    assert ride["promotion"]["id"] == best["id"]
    assert ride["rates"] == {"bcv": "800.00", "binance": None}
    detail = await client.get(f"{API}/admin/promotions/{best['id']}", headers=admin_headers)
    assert detail.json()["stats"]["reserved"] == quote["discount"]

    offer = recorder.of("ride.offer", driver.id)[-1]
    assert offer["total"] == quote["total"] and offer["discount"] == quote["discount"]

    done = await _complete(client, driver, ride["id"])
    assert done["total"] == quote["total"]
    wallet = (await client.get(f"{API}/wallet/me", headers=driver.headers)).json()
    assert wallet == {"balance": quote["discount"], "currency": "USDT"}
    entries = (await client.get(f"{API}/wallet/me/entries", headers=driver.headers)).json()
    assert entries["total"] == 1
    entry = entries["items"][0]
    assert entry["kind"] == "promo_credit" and entry["amount"] == quote["discount"]
    assert entry["description"] == "Grande" and entry["details"] == {"passenger_name": "Ana P."}
    async with SessionLocal() as session:
        notice = await session.scalar(
            select(Notification).where(Notification.user_id == driver.user.id)
        )
        assert notice is not None and quote["discount"] in notice.title

    stats = (await client.get(f"{API}/admin/promotions/{best['id']}", headers=admin_headers)).json()
    assert stats["stats"]["credited"] == quote["discount"] and stats["stats"]["reserved"] == "0.00"
    assert stats["stats"]["completed"] == 1
    rides = await client.get(f"{API}/admin/promotions/{best['id']}/rides", headers=admin_headers)
    assert rides.json()["items"][0]["passenger_name"] == "Ana Pérez"


async def test_code_reasons(client, admin_headers, passenger):
    response = await _quote(client, passenger, "NOPE")
    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "promotion_invalid",
        "message": "The promotion code cannot be used",
        "details": {"reason": "not_found"},
    }
    await _create(
        client,
        admin_headers,
        code="LUEGO",
        starts_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
        ends_at=(datetime.now(UTC) + timedelta(days=2)).isoformat(),
    )
    await _create(client, admin_headers, code="CARRO", vehicle_types=["car"])
    await _create(client, admin_headers, code="CARO", min_fare="50")
    for code, reason in (
        ("luego", "not_started"),
        ("CARRO", "not_eligible"),
        ("caro", "not_eligible"),
    ):
        response = await _quote(client, passenger, code)
        assert response.json()["error"]["details"]["reason"] == reason, code

    await _create(client, admin_headers, code="HOLA", discount_type="fixed", discount_value="0.5")
    quote = await _quote(client, passenger, " hola ")
    assert quote.status_code == 200 and quote.json()["discount"] == "0.50"


async def test_uses_first_ride_and_cancel_release(client, admin_headers, passenger):
    promo = await _create(
        client, admin_headers, code="UNA", max_uses_per_passenger=1, first_ride_only=True
    )
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)

    ride = (
        await _request(client, passenger, (await _quote(client, passenger, "UNA")).json())
    ).json()
    used = await _quote(client, passenger, "UNA")  # the ride in flight counts as a use
    assert used.json()["error"]["details"]["reason"] == "max_uses"
    cancel = await client.post(
        f"{API}/rides/{ride['id']}/cancel", json={}, headers=passenger.headers
    )
    assert cancel.status_code == 200
    detail = (
        await client.get(f"{API}/admin/promotions/{promo['id']}", headers=admin_headers)
    ).json()
    assert detail["stats"]["uses"] == 0 and detail["stats"]["reserved"] == "0.00"

    ride = (
        await _request(client, passenger, (await _quote(client, passenger, "UNA")).json())
    ).json()
    await _complete(client, driver, ride["id"])
    await _rate(client, passenger, ride["id"])
    response = await _quote(client, passenger, "UNA")
    assert response.json()["error"]["details"]["reason"] == "first_ride_only"


async def test_budget_runs_out_between_quote_and_request(client, admin_headers, passenger):
    promo = await _create(
        client,
        admin_headers,
        code="POCO",
        discount_type="fixed",
        discount_value="0.5",
        budget="0.5",
    )
    other = await _make_user("bea@example.com")
    bea_headers = await _login(client, "bea@example.com")

    class Bea:
        headers = bea_headers
        id = str(other.id)

    first = (await _quote(client, passenger, "POCO")).json()
    second = (await _quote(client, Bea, "POCO")).json()
    assert (await _request(client, passenger, first)).status_code == 201
    response = await _request(client, Bea, second)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "promotion_unavailable"
    exhausted = await _quote(client, Bea, "POCO")
    assert exhausted.json()["error"]["details"]["reason"] == "exhausted"

    lower = await client.patch(
        f"{API}/admin/promotions/{promo['id']}", json={"budget": "0.2"}, headers=admin_headers
    )
    assert lower.status_code == 409 and lower.json()["error"]["code"] == "budget_below_committed"
    listing = await client.get(f"{API}/admin/promotions?status=exhausted", headers=admin_headers)
    assert listing.json()["total"] == 1


async def test_pair_alerts(client, admin_headers, passenger):
    await client.patch(
        f"{API}/admin/config", json={"promo_pair_alert_threshold": 2}, headers=admin_headers
    )
    await _create(client, admin_headers, discount_type="fixed", discount_value="0.3")
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)
    for _ in range(2):
        ride = (await _request(client, passenger, (await _quote(client, passenger)).json())).json()
        await _complete(client, driver, ride["id"])
        await _rate(client, passenger, ride["id"])
        await _rate(client, driver, ride["id"])
    alerts = await client.get(f"{API}/admin/promotions/alerts", headers=admin_headers)
    assert alerts.status_code == 200, alerts.text
    [alert] = alerts.json()
    assert alert["rides"] == 2 and alert["discount_total"] == "0.60"
    assert alert["passenger"]["email"] == "ana@example.com"
    assert alert["driver"]["profile_id"]
    wallet = (await client.get(f"{API}/wallet/me", headers=driver.headers)).json()
    assert wallet["balance"] == "0.60"
