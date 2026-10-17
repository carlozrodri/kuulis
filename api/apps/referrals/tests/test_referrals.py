from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update

from apps.audit.models import AuditLog
from apps.config.services import get_app_config
from apps.drivers.models import DriverProfile, DriverStatus, MarkKind
from apps.drivers.verification import record_marks
from apps.notifications.models import Notification
from apps.referrals import services
from apps.referrals.models import Referral, ReferralStatus
from apps.rides.tests.conftest import Actor, make_driver
from apps.rides.tests.test_rides import _completed_ride
from apps.risk.models import RiskKind, RiskSignal
from apps.subscriptions import services as subscriptions
from apps.subscriptions.models import Charge, ChargeStatus
from apps.subscriptions.tests.test_subscriptions import _first_trip, _month, _ride
from apps.users.models import Role, User
from apps.wallet.models import EntryKind, Wallet, WalletEntry
from conftest import _login, _make_user, make_staff_role, set_config
from kuulis.core.db import SessionLocal

API = "/api/v1/referrals"
ADMIN = "/api/v1/admin/referrals"


async def _free_months(user_id) -> int:
    async with SessionLocal() as session:
        return await session.scalar(
            select(DriverProfile.free_months_credit).where(DriverProfile.user_id == user_id)
        )


async def _bonuses(user_id) -> list[Decimal]:
    async with SessionLocal() as session:
        return list(
            await session.scalars(
                select(WalletEntry.amount)
                .join(Wallet, Wallet.id == WalletEntry.wallet_id)
                .where(Wallet.user_id == user_id, WalletEntry.kind == EntryKind.REFERRAL_BONUS)
            )
        )


async def _titles(user_id) -> list[str]:
    async with SessionLocal() as session:
        return list(
            await session.scalars(select(Notification.title).where(Notification.user_id == user_id))
        )


async def _referral(referred_id) -> Referral:
    async with SessionLocal() as session:
        return await session.scalar(select(Referral).where(Referral.referred_id == referred_id))


async def _approve(driver: Actor, days_ago: int = 0) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(DriverProfile)
            .where(DriverProfile.user_id == driver.user.id)
            .values(
                status=DriverStatus.APPROVED,
                approved_at=datetime.now(UTC) - timedelta(days=days_ago),
            )
        )
        await session.commit()


async def _invite(client, inviter: Actor, email: str, name: str) -> Actor:
    """A new driver (pending review) who enters ``inviter``'s code, then is approved."""
    code = (await client.get(f"{API}/me", headers=inviter.headers)).json()["code"]
    new = await make_driver(client, email, name, DriverStatus.PENDING_REVIEW)
    response = await client.post(f"{API}/redeem", json={"code": code}, headers=new.headers)
    assert response.status_code == 200, response.text
    await _approve(new)
    return new


async def _trip(client, passenger: Actor, driver: Actor) -> None:
    """A completed ride, rated by both (the next request needs it); the driver goes offline so
    the next ride can go to another one."""
    ride = await _completed_ride(client, passenger, driver)
    for actor in (passenger, driver):
        response = await client.post(
            f"/api/v1/rides/{ride['id']}/rating", json={"stars": 5}, headers=actor.headers
        )
        assert response.status_code in (200, 201), response.text
    await client.post("/api/v1/drivers/me/offline", headers=driver.headers)


async def _program(**values) -> None:
    await set_config(referral_program={"required_trips": 2} | values)


async def _sweep() -> dict[str, int]:
    async with SessionLocal() as session:
        return await services.sweep(session, await get_app_config(session))


async def test_redeem_rules(client, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    me = (await client.get(f"{API}/me", headers=luis.headers)).json()
    code = me["code"]
    assert len(code) == 6 and me["invited"] == 0 and me["earned_usd"] == "0.00"
    assert me["share_url"].endswith(f"/i/{code}")
    assert me["program"] == {
        "active": True,
        "reward_usd": "5.00",
        "required_trips": 20,
        "window_days": 30,
        "referred_free_month": False,
        "ends_at": None,
    }

    # Not approved yet: no code of their own, but they can enter one.
    new = await make_driver(client, "new@example.com", "Nuevo Ruiz", DriverStatus.PENDING_REVIEW)
    summary = (await client.get(f"{API}/me", headers=new.headers)).json()
    assert summary["code"] is None and summary["can_redeem"] is True

    bad = await client.post(f"{API}/redeem", json={"code": "ZZZZZZ"}, headers=new.headers)
    assert bad.json()["error"]["code"] == "referral_code_invalid"
    own = await client.post(f"{API}/redeem", json={"code": code}, headers=luis.headers)
    assert own.json()["error"]["code"] == "referral_own_code"
    as_passenger = await client.post(
        f"{API}/redeem", json={"code": code}, headers=passenger.headers
    )
    assert as_passenger.json()["error"]["code"] == "referral_driver_only"

    # The program off: no new codes.
    await _program(enabled=False)
    closed = await client.post(f"{API}/redeem", json={"code": code}, headers=new.headers)
    assert closed.json()["error"]["code"] == "referral_program_closed"
    assert (await client.get(f"{API}/me", headers=new.headers)).json()["can_redeem"] is False
    await _program()

    redeemed = await client.post(
        f"{API}/redeem", json={"code": code.lower()[:3] + "-" + code[3:]}, headers=new.headers
    )
    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["referred_by"] == "Luis G." and redeemed.json()["can_redeem"] is False
    twice = await client.post(f"{API}/redeem", json={"code": code}, headers=new.headers)
    assert twice.json()["error"]["code"] == "referral_already_used"

    # The inviter sees the invitee waiting for approval.
    invitees = (await client.get(f"{API}/me", headers=luis.headers)).json()["invitees"]
    assert invitees == [
        {
            "name": "Nuevo R.",
            "joined_at": invitees[0]["joined_at"],
            "approved": False,
            "status": "pending",
            "trips": 0,
            "required_trips": 2,
            "deadline_at": None,
            "reward_usd": None,
            "reward_kind": None,
        }
    ]

    # The public page of the code (no account).
    public = await client.get(f"{API}/codes/{code.lower()}")
    assert public.status_code == 200 and public.json()["name"] == "Luis"
    missing = await client.get(f"{API}/codes/ZZZZZZ")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "referral_code_invalid"


async def test_reward_after_required_trips(client, passenger, recorder, relaxed_risk):
    await _program(referred_free_month=True)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    new = await _invite(client, luis, "new@example.com", "Nuevo Ruiz")

    await _trip(client, passenger, new)
    referral = await _referral(new.user.id)
    assert referral.status == ReferralStatus.PENDING and referral.trips == 1
    assert referral.deadline_at is not None
    assert await _bonuses(luis.user.id) == []

    await _trip(client, passenger, new)
    referral = await _referral(new.user.id)
    assert referral.status == ReferralStatus.REWARDED and referral.trips == 2
    assert await _bonuses(luis.user.id) == [Decimal("5.00")]
    assert "¡Ganaste 5.00 USDT!" in await _titles(luis.user.id)
    # The invitee's own free month (referred_free_month).
    assert await _free_months(new.user.id) == 1
    assert "¡Ganaste un mes gratis!" in await _titles(new.user.id)

    # Only once.
    await _trip(client, passenger, new)
    assert await _bonuses(luis.user.id) == [Decimal("5.00")]
    assert await _free_months(new.user.id) == 1

    me = (await client.get(f"{API}/me", headers=luis.headers)).json()
    assert (me["invited"], me["rewarded"], me["earned_usd"]) == (1, 1, "5.00")
    assert me["invitees"][0]["status"] == "rewarded"
    assert me["invitees"][0]["reward_usd"] == "5.00"

    # The bonus shows in the statement and is not part of the month's earnings.
    statement = (await client.get("/api/v1/wallet/me/statements", headers=luis.headers)).json()
    assert statement["movements"]["referral_bonuses"] == "5.00"


async def test_trips_with_the_inviter_do_not_count(client, recorder, relaxed_risk):
    await _program()
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    new = await _invite(client, luis, "new@example.com", "Nuevo Ruiz")
    await _trip(client, luis, new)  # Luis rides with his own invitee
    await _trip(client, luis, new)
    referral = await _referral(new.user.id)
    assert referral.status == ReferralStatus.PENDING and referral.trips == 0


async def test_shared_identity_is_rejected_and_alerted(
    client, passenger, recorder, relaxed_risk, admin_headers
):
    await _program()
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    new = await _invite(client, luis, "new@example.com", "Nuevo Ruiz")
    async with SessionLocal() as session:
        for user in (luis.user, new.user):
            await record_marks(session, user.id, {MarkKind.DEVICE: "same-phone"})
        await session.commit()

    await _trip(client, passenger, new)
    referral = await _referral(new.user.id)
    assert referral.status == ReferralStatus.REJECTED
    assert referral.reason == "shared_identity" and referral.details["shared"] == ["device"]
    await _trip(client, passenger, new)
    assert await _bonuses(luis.user.id) == []
    async with SessionLocal() as session:
        signal = await session.scalar(
            select(RiskSignal).where(RiskSignal.kind == RiskKind.REFERRAL)
        )
    assert signal.user_id == new.user.id and signal.related_user_id == luis.user.id

    # In the admin alerts; the inviter only sees "not eligible".
    alerts = (await client.get(ADMIN, params={"alerts": True}, headers=admin_headers)).json()
    assert alerts["total"] == 1 and alerts["items"][0]["reason"] == "shared_identity"
    overview = (await client.get(f"{ADMIN}/overview", headers=admin_headers)).json()
    assert overview["alerts"] == 1
    invitee = (await client.get(f"{API}/me", headers=luis.headers)).json()["invitees"][0]
    assert invitee["status"] == "not_eligible"

    # Relatives sharing a phone: the admin reopens it and it is paid without the check.
    reopened = await client.post(
        f"{ADMIN}/{referral.id}/reopen", json={"note": "Hermanos"}, headers=admin_headers
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "rewarded"
    assert await _bonuses(luis.user.id) == [Decimal("5.00")]
    alerts = (await client.get(ADMIN, params={"alerts": True}, headers=admin_headers)).json()
    assert alerts["total"] == 0


async def test_expired_window(client, passenger, recorder, relaxed_risk):
    await _program(window_days=30)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    new = await _invite(client, luis, "new@example.com", "Nuevo Ruiz")
    await _approve(new, days_ago=31)
    await _trip(client, passenger, new)
    referral = await _referral(new.user.id)
    assert referral.status == ReferralStatus.REJECTED and referral.reason == "expired"
    invitee = (await client.get(f"{API}/me", headers=luis.headers)).json()["invitees"][0]
    assert invitee["status"] == "expired"

    # The sweep expires the ones that never drove.
    other = await _invite(client, luis, "other@example.com", "Otro Díaz")
    await _approve(other, days_ago=40)
    assert await _sweep() == {"rejected": 1}
    assert (await _referral(other.user.id)).reason == "expired"


async def test_budget_and_monthly_cap(client, passenger, recorder, relaxed_risk, admin_headers):
    await _program(budget_usd="5.00", monthly_cap=0)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    first = await _invite(client, luis, "a@example.com", "Ana Uno")
    second = await _invite(client, luis, "b@example.com", "Beto Dos")
    for driver in (first, second):
        for _ in range(2):
            await _trip(client, passenger, driver)
    assert await _bonuses(luis.user.id) == [Decimal("5.00")]
    waiting = await _referral(second.user.id)
    assert waiting.status == ReferralStatus.QUALIFIED and waiting.reason == "budget"
    overview = (await client.get(f"{ADMIN}/overview", headers=admin_headers)).json()
    assert overview["paid_usd"] == "5.00" and overview["budget_left_usd"] == "0.00"
    assert overview["waiting"] == {"budget": 1}
    # Paying by hand still respects the budget.
    forced = await client.post(f"{ADMIN}/{waiting.id}/release", json={}, headers=admin_headers)
    assert forced.json()["error"]["code"] == "referral_budget_exhausted"

    # A bigger budget but one reward per month: still waiting, now for the cap.
    await _program(budget_usd="100.00", monthly_cap=1)
    assert await _sweep() == {}
    assert (await _referral(second.user.id)).reason == "monthly_cap"
    # The admin can pay it anyway (the budget has room).
    paid = await client.post(f"{ADMIN}/{waiting.id}/release", json={}, headers=admin_headers)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "rewarded"
    assert await _bonuses(luis.user.id) == [Decimal("5.00"), Decimal("5.00")]

    ranking = (await client.get(f"{ADMIN}/ranking", headers=admin_headers)).json()
    assert ranking[0]["user"]["email"] == "luis@example.com"
    assert (ranking[0]["invited"], ranking[0]["rewarded"], ranking[0]["earned_usd"]) == (
        2,
        2,
        "10.00",
    )


async def test_high_risk_holds_the_reward(client, passenger, recorder, relaxed_risk, admin_headers):
    await _program()
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    new = await _invite(client, luis, "new@example.com", "Nuevo Ruiz")
    other = await _invite(client, luis, "other@example.com", "Otro Díaz")
    async with SessionLocal() as session:
        await session.execute(update(User).where(User.id == luis.user.id).values(risk_score=80))
        await session.commit()
    for driver in (new, other):
        for _ in range(2):
            await _trip(client, passenger, driver)
    held = await _referral(new.user.id)
    assert held.status == ReferralStatus.HELD and held.reason == "risk_score"
    assert held.reward_amount == Decimal("5.00")
    assert await _bonuses(luis.user.id) == []
    assert "Tu premio está en revisión" in await _titles(luis.user.id)
    overview = (await client.get(f"{ADMIN}/overview", headers=admin_headers)).json()
    assert overview["held_usd"] == "10.00" and overview["alerts"] == 2

    released = await client.post(
        f"{ADMIN}/{held.id}/release", json={"note": "Revisado"}, headers=admin_headers
    )
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "rewarded" and released.json()["note"] == "Revisado"
    assert await _bonuses(luis.user.id) == [Decimal("5.00")]

    rejected_id = (await _referral(other.user.id)).id
    rejected = await client.post(f"{ADMIN}/{rejected_id}/reject", json={}, headers=admin_headers)
    assert rejected.json()["status"] == "rejected" and rejected.json()["reason"] == "staff"
    assert "Premio por invitación no acreditado" in await _titles(luis.user.id)
    again = await client.post(f"{ADMIN}/{rejected_id}/reject", json={}, headers=admin_headers)
    assert again.json()["error"]["code"] == "referral_invalid_status"
    async with SessionLocal() as session:
        actions = set(await session.scalars(select(AuditLog.action)))
    assert {"referrals.release", "referrals.reject"} <= actions


async def test_program_settings(client, admin_headers):
    # Finanzas-like staff can look but not change the program.
    role = await make_staff_role("mirar", {"referrals.view"})
    await _make_user("mira@example.com", Role.STAFF, role)
    viewer = await _login(client, "mira@example.com")
    assert (await client.get(f"{ADMIN}/overview", headers=viewer)).status_code == 200
    denied = await client.put(f"{ADMIN}/program", json={}, headers=viewer)
    assert denied.status_code == 403
    response = await client.put(
        f"{ADMIN}/program",
        json={
            "enabled": True,
            "reward_usd": "3.00",
            "required_trips": 15,
            "window_days": 20,
            "referred_free_month": True,
            "monthly_cap": 5,
            "budget_usd": "250.00",
            "starts_at": None,
            "ends_at": None,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["reward_usd"] == "3.00"
    overview = (await client.get(f"{ADMIN}/overview", headers=admin_headers)).json()
    assert overview["program"]["required_trips"] == 15
    assert overview["budget_left_usd"] == "250.00"
    bad = await client.put(
        f"{ADMIN}/program",
        json={"starts_at": "2026-11-02T00:00:00Z", "ends_at": "2026-11-01T00:00:00Z"},
        headers=admin_headers,
    )
    assert bad.status_code == 422
    async with SessionLocal() as session:
        actions = set(await session.scalars(select(AuditLog.action)))
    assert "referrals.program_update" in actions


async def test_free_month_waives_next_fee(client, recorder):
    """Months earned before doc 22 (and the invitee's own month) still waive a fee."""
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
    assert await _free_months(luis.user.id) == 0
