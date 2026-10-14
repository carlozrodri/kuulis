"""Doc 16: anti-fraud rules, held money, banned identifiers and the admin's Risk inbox."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from apps.drivers.models import DriverProfile
from apps.notifications.models import Notification
from apps.promotions.tests.test_promotions import _complete, _create, _quote, _request
from apps.rides import presence
from apps.rides.models import Rating
from apps.rides.state import utcnow
from apps.rides.tests.conftest import NEAR, age_location, go_online, make_driver
from apps.risk import gps
from apps.risk import services as risk
from apps.risk.models import HoldStatus, RiskHold, RiskSignal
from apps.users.models import User
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind
from conftest import PASSWORD, _make_user, set_config
from kuulis.core.db import SessionLocal

API = "/api/v1"
PHONE = "android:0123456789abcdef"


@pytest.fixture(autouse=True)
def gps_events(monkeypatch, recorder):
    async def fake_publish(event, data=None, user_ids=None):
        recorder.events.append((event, data, user_ids))

    monkeypatch.setattr(gps, "publish", fake_publish)
    return recorder


async def _login_on(client, email: str, device: str, **headers: str) -> dict[str, str]:
    response = await client.post(
        f"{API}/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"X-Device-Id": device, "X-Client-Platform": "android", **headers},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _signals(**where) -> list[RiskSignal]:
    async with SessionLocal() as session:
        stmt = select(RiskSignal).order_by(RiskSignal.created_at)
        for name, value in where.items():
            stmt = stmt.where(getattr(RiskSignal, name) == value)
        return list(await session.scalars(stmt))


async def _score(user_id) -> int:
    async with SessionLocal() as session:
        return (await session.get(User, user_id)).risk_score


# --- Rides -------------------------------------------------------------------------------------


async def test_ride_on_one_phone_holds_the_promotion_credit(client, admin_headers, passenger):
    await _create(client, admin_headers)
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    # Both accounts sign in on the same phone: a ride with oneself.
    await _login_on(client, "ana@example.com", PHONE, **{"X-Device-Model": "Redmi Note 12"})
    await _login_on(client, "luis@example.com", PHONE)
    await go_online(client, driver, NEAR)
    quote = (await _quote(client, passenger)).json()
    ride = (await _request(client, passenger, quote)).json()
    await _complete(client, driver, ride["id"])

    [signal] = await _signals(kind="suspicious_ride")
    assert "same_device" in signal.reasons and str(signal.ride_id) == ride["id"]
    assert str(signal.user_id) == driver.id and str(signal.related_user_id) == passenger.id
    assert await _score(driver.user.id) >= 60 and await _score(passenger.user.id) >= 60

    # No credit yet: it waits for a review, and the driver is told.
    me = (await client.get(f"{API}/wallet/me", headers=driver.headers)).json()
    assert me["balance"] == "0.00"
    async with SessionLocal() as session:
        hold = await session.scalar(select(RiskHold))
        titles = list(
            await session.scalars(
                select(Notification.title).where(Notification.user_id == driver.user.id)
            )
        )
    assert hold.status == HoldStatus.HELD and hold.amount == Decimal(quote["discount"])
    assert any("revisión" in t for t in titles)

    summary = (await client.get(f"{API}/admin/risk/summary", headers=admin_headers)).json()
    assert summary["holds"] == 1 and summary["held_amount"] == quote["discount"]
    assert {c["kind"]: c["open"] for c in summary["open"]}["suspicious_ride"] == 1

    detail = (
        await client.get(f"{API}/admin/risk/signals/{signal.id}", headers=admin_headers)
    ).json()
    assert detail["ride"]["id"] == ride["id"] and detail["holds"][0]["id"] == str(hold.id)
    assert {a["id"] for a in detail["accounts"]} == {driver.id, passenger.id}

    user = (await client.get(f"{API}/admin/risk/users/{driver.id}", headers=admin_headers)).json()
    [device] = user["devices"]
    assert device["platform"] == "android" and device["other_accounts"][0]["id"] == passenger.id
    assert user["frozen"] is True

    released = await client.post(
        f"{API}/admin/risk/holds/{hold.id}/release", json={"note": "Ok"}, headers=admin_headers
    )
    assert released.status_code == 200 and released.json()["status"] == "released"
    me = (await client.get(f"{API}/wallet/me", headers=driver.headers)).json()
    assert me["balance"] == quote["discount"]
    again = await client.post(
        f"{API}/admin/risk/holds/{hold.id}/void", json={}, headers=admin_headers
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "risk_hold_not_held"

    # Ratings of a flagged ride do not move the averages.
    rated = await client.post(
        f"{API}/rides/{ride['id']}/rating", json={"stars": 1}, headers=passenger.headers
    )
    assert rated.status_code in (200, 201), rated.text
    async with SessionLocal() as session:
        rating = await session.scalar(select(Rating))
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.user.id)
        )
    assert rating.ignored is True and profile.rating_count == 0

    # Dismissing the alert stops it counting.
    dismissed = await client.post(
        f"{API}/admin/risk/signals/{signal.id}/dismiss",
        json={"note": "Familia"},
        headers=admin_headers,
    )
    assert dismissed.status_code == 200 and dismissed.json()["status"] == "dismissed"
    assert dismissed.json()["reviewed_by_name"]
    assert await _score(driver.user.id) == 0


async def test_shared_device_alert(client, passenger):
    await set_config(risk={"max_accounts_per_device": 2})
    for email in ("a@example.com", "b@example.com"):
        await _make_user(email)
        await _login_on(client, email, PHONE)
    assert await _signals(kind="shared_device") == []
    await _login_on(client, "ana@example.com", PHONE)  # a third account on the phone
    [signal] = await _signals(kind="shared_device")
    assert signal.evidence["count"] == 3 and str(signal.user_id) == passenger.id
    await _login_on(client, "ana@example.com", PHONE)  # again: no new alert
    assert len(await _signals(kind="shared_device")) == 1


# --- Fake GPS ----------------------------------------------------------------------------------


async def test_mock_location_takes_the_driver_offline(client, recorder):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)
    await age_location(driver, 5)
    body = {"lat": NEAR[0], "lng": NEAR[1], "mocked": True}
    sent = await client.post(f"{API}/drivers/me/location", json=body, headers=driver.headers)
    assert sent.status_code == 204
    assert await presence.is_online(driver.id) is False
    assert recorder.of(gps.MOCK_EVENT, driver.id) == [{"online": False}]
    [signal] = await _signals(kind="fake_gps")
    assert signal.reasons == ["mocked"]

    refused = await client.post(f"{API}/drivers/me/online", json=body, headers=driver.headers)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "mock_location"
    assert len(await _signals(kind="fake_gps")) == 1  # one alert per hour
    await go_online(client, driver, NEAR)  # with the real location again


async def test_impossible_jumps(client):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await go_online(client, driver, NEAR)
    far = {"lat": NEAR[0] + 0.2, "lng": NEAR[1]}  # ~22 km away
    for point in (far, {"lat": NEAR[0], "lng": NEAR[1]}, far):
        await age_location(driver, 2)
        response = await client.post(
            f"{API}/drivers/me/location", json=point, headers=driver.headers
        )
        assert response.status_code == 204
    [signal] = await _signals(kind="fake_gps")
    assert signal.reasons == ["jumps"] and signal.evidence["jumps"] == 3
    assert await presence.is_online(driver.id) is True  # glitches happen: only an alert


# --- Transfers ---------------------------------------------------------------------------------


async def _fund(user_id, amount: str) -> None:
    async with SessionLocal() as session:
        await wallet.credit(session, user_id, EntryKind.ADJUSTMENT, Decimal(amount))
        await session.commit()


async def test_first_transfer_waits_and_suspicious_ones_need_review(client, admin_headers):
    await set_config(risk={"new_account_days": 0})
    ana = await make_driver(client, "ana@example.com", "Ana Ruiz")
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _fund(ana.user.id, "50")
    url = f"{API}/wallet/me/transfers"

    async def send(sender, to, amount: str):
        return await client.post(
            url, json={"to_user_id": to.id, "amount": amount}, headers=sender.headers
        )

    first = await client.post(
        url, json={"to_user_id": luis.id, "amount": "10"}, headers=ana.headers
    )
    assert first.status_code == 201, first.text
    assert first.json()["details"]["held"] is True and first.json()["details"]["held_until"]
    luis_wallet = (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()
    assert luis_wallet["balance"] == "0.00"

    # The second one goes straight through.
    second = await client.post(
        url, json={"to_user_id": luis.id, "amount": "5"}, headers=ana.headers
    )
    assert "held" not in second.json()["details"]
    luis_wallet = (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()
    assert luis_wallet["balance"] == "5.00"

    # When the 24 h end, the worker pays it.
    async with SessionLocal() as session:
        await session.execute(update(RiskHold).values(release_at=utcnow() - timedelta(minutes=1)))
        await session.commit()
        assert await risk.release_due(session) == 1
    luis_wallet = (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()
    assert luis_wallet["balance"] == "15.00"

    # Passing on money just received from someone else: held with no end, an alert on Luis.
    pedro = await make_driver(client, "pedro@example.com", "Pedro Díaz")
    await _fund(luis.user.id, "20")
    await client.post(url, json={"to_user_id": pedro.id, "amount": "1"}, headers=luis.headers)
    chain = await client.post(
        url, json={"to_user_id": pedro.id, "amount": "12"}, headers=luis.headers
    )
    assert chain.json()["details"] == {
        "counterpart_name": "Pedro D.",
        "note": None,
        "held": True,
        "held_until": None,
    }
    # Both transfers pass on what Ana sent minutes ago (the first one is also Luis' first).
    signals = await _signals(kind="transfers")
    assert len(signals) == 2
    assert all(s.reasons == ["chain"] and str(s.user_id) == luis.id for s in signals)
    holds = (await client.get(f"{API}/admin/risk/holds", headers=admin_headers)).json()
    held = next(h for h in holds["items"] if h["amount"] == "12.00")
    assert held["reasons"] == ["chain"] and held["sender"]["id"] == luis.id

    voided = await client.post(
        f"{API}/admin/risk/holds/{held['id']}/void", json={}, headers=admin_headers
    )
    assert voided.status_code == 200 and voided.json()["status"] == "voided"
    luis_wallet = (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()
    assert luis_wallet["balance"] == "34.00"  # 15 + 20 - 1 (first, held) - 12 + 12 back
    transfers = (await client.get(f"{API}/admin/transfers", headers=admin_headers)).json()
    assert any(t["returned"] for t in transfers["items"])

    # A high-risk account cannot send.
    async with SessionLocal() as session:
        await session.execute(update(User).where(User.id == ana.user.id).values(risk_score=80))
        await session.commit()
    frozen = await client.post(
        url, json={"to_user_id": luis.id, "amount": "1"}, headers=ana.headers
    )
    assert frozen.status_code == 403 and frozen.json()["error"]["code"] == "transfers_frozen"


# --- Banned accounts ---------------------------------------------------------------------------


async def test_ban_blocks_new_accounts(client, admin_headers):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _login_on(client, "luis@example.com", PHONE)
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.user.id)
        )
        from apps.drivers import verification

        await verification.record_profile_marks(session, profile)
        await session.commit()
        national_id = profile.national_id

    banned = await client.post(
        f"{API}/admin/risk/users/{driver.id}/ban",
        json={"reason": "Viajes falsos"},
        headers=admin_headers,
    )
    assert banned.status_code == 200, banned.text
    body = banned.json()
    assert body["suspended"] is True
    assert {b["kind"] for b in body["blocked"]} >= {"email", "national_id", "phone", "device"}

    # Same email, same phone or same cédula: no new account.
    taken = await client.post(
        f"{API}/auth/register",
        json={"email": "otra@example.com", "password": PASSWORD, "full_name": "Otra"},
        headers={"X-Device-Id": PHONE},
    )
    assert taken.status_code == 403 and taken.json()["error"]["code"] == "registration_blocked"
    await _make_user("nuevo@example.com")
    login = await client.post(
        f"{API}/auth/login", json={"email": "nuevo@example.com", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    profile = await client.put(
        f"{API}/drivers/me",
        json={
            "birth_date": "1990-01-01",
            "national_id": national_id,
            "rif": "V999999999",
            "phone": "+584149999999",
        },
        headers=headers,
    )
    assert profile.status_code == 403, profile.text
    assert profile.json()["error"]["code"] == "registration_blocked"

    listing = (await client.get(f"{API}/admin/risk/blocked", headers=admin_headers)).json()
    assert listing["total"] == len(body["blocked"])
    removed = await client.delete(
        f"{API}/admin/risk/blocked/{listing['items'][0]['id']}", headers=admin_headers
    )
    assert removed.status_code == 204

    staff = await _make_user("jefa@example.com")
    async with SessionLocal() as session:
        from apps.users.models import Role

        await session.execute(update(User).where(User.id == staff.id).values(role=Role.STAFF))
        await session.commit()
    refused = await client.post(
        f"{API}/admin/risk/users/{staff.id}/ban", json={"reason": "Prueba"}, headers=admin_headers
    )
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "cannot_ban_staff"
    missing = await client.get(f"{API}/admin/risk/users/{uuid.uuid4()}", headers=admin_headers)
    assert missing.status_code == 404


async def test_risk_pages_need_permission(client, user_headers):
    for path in ("summary", "signals", "holds", "blocked"):
        response = await client.get(f"{API}/admin/risk/{path}", headers=user_headers)
        assert response.status_code == 403
