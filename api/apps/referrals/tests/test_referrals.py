from sqlalchemy import select

from apps.drivers.models import DriverProfile, DriverStatus
from apps.notifications.models import Notification
from apps.rides.tests.conftest import make_driver
from apps.rides.tests.test_rides import _completed_ride
from apps.subscriptions import services as subscriptions
from apps.subscriptions.models import Charge, ChargeStatus
from apps.subscriptions.tests.test_subscriptions import _first_trip, _month, _ride
from kuulis.core.db import SessionLocal

API = "/api/v1/referrals"


async def _credit(user_id) -> int:
    async with SessionLocal() as session:
        return await session.scalar(
            select(DriverProfile.free_months_credit).where(DriverProfile.user_id == user_id)
        )


async def test_invite_reward_on_first_trip(client, passenger, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    me = (await client.get(f"{API}/me", headers=luis.headers)).json()
    code = me["code"]
    assert len(code) == 6 and me["invited"] == 0 and me["free_months"] == 0

    # Not approved yet: no code of their own, but they can enter one.
    new = await make_driver(client, "new@example.com", "Nuevo Ruiz", DriverStatus.PENDING_REVIEW)
    summary = (await client.get(f"{API}/me", headers=new.headers)).json()
    assert summary["code"] is None and summary["can_redeem"] is True

    for bad, error in (("ZZZZZZ", "referral_code_invalid"),):
        response = await client.post(f"{API}/redeem", json={"code": bad}, headers=new.headers)
        assert response.json()["error"]["code"] == error
    own = await client.post(f"{API}/redeem", json={"code": code}, headers=luis.headers)
    assert own.json()["error"]["code"] == "referral_own_code"
    as_passenger = await client.post(
        f"{API}/redeem", json={"code": code}, headers=passenger.headers
    )
    assert as_passenger.json()["error"]["code"] == "referral_driver_only"

    redeemed = await client.post(
        f"{API}/redeem", json={"code": code.lower()[:3] + "-" + code[3:]}, headers=new.headers
    )
    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["referred_by"] == "Luis G." and redeemed.json()["can_redeem"] is False
    twice = await client.post(f"{API}/redeem", json={"code": code}, headers=new.headers)
    assert twice.json()["error"]["code"] == "referral_already_used"

    # Approved and completes the first ride: Luis earns one free month, once.
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == new.user.id)
        )
        profile.status = DriverStatus.APPROVED
        await session.commit()
    await _completed_ride(client, passenger, new)
    assert await _credit(luis.user.id) == 1
    me = (await client.get(f"{API}/me", headers=luis.headers)).json()
    assert (me["invited"], me["rewarded"], me["free_months"]) == (1, 1, 1)
    async with SessionLocal() as session:
        titles = list(
            await session.scalars(
                select(Notification.title).where(Notification.user_id == luis.user.id)
            )
        )
    assert "¡Ganaste un mes gratis!" in titles

    late = await client.post(f"{API}/redeem", json={"code": code}, headers=new.headers)
    assert late.json()["error"]["code"] in ("referral_already_used", "referral_closed")


async def test_free_month_waives_next_fee(client, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _first_trip(luis, -6)
    await _ride(luis, "250", -1)  # $10 fee
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == luis.user.id)
        )
        profile.free_months_credit = 1
        await session.commit()
        await subscriptions.charge_month(session, _month(-1))
        charge = await session.scalar(select(Charge).where(Charge.user_id == luis.user.id))
    assert charge.status == ChargeStatus.WAIVED and charge.waived_reason == "referral"
    assert await _credit(luis.user.id) == 0
