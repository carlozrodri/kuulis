from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from apps.approvals.models import PendingApproval
from apps.audit.models import AuditLog
from apps.rides.tests.conftest import make_driver
from apps.staff.permissions import DEFAULT_ROLES
from apps.users.models import Role
from conftest import _login, _make_user, make_staff_role
from kuulis.core.calendar import add_months, format_month, local_now, month_start
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def _staff(client, role: str, *emails: str) -> list[dict[str, str]]:
    staff_role = await make_staff_role(role, DEFAULT_ROLES[role][1])
    for email in emails:
        await _make_user(email, Role.STAFF, staff_role)
    return [await _login(client, email) for email in emails]


async def _second_admin(client) -> dict[str, str]:
    await _make_user("admin2@example.com", Role.ADMIN)
    return await _login(client, "admin2@example.com")


async def _actions(action: str) -> list[AuditLog]:
    async with SessionLocal() as session:
        stmt = select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)
        return list(await session.scalars(stmt))


async def test_large_adjustment_waits_for_someone_else(client, admin_headers):
    [finanzas] = await _staff(client, "finanzas", "finanzas@example.com")
    [soporte] = await _staff(client, "soporte", "soporte@example.com")
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    wallet = f"{API}/admin/wallets/{luis.id}"

    small = await client.post(
        f"{wallet}/adjust", json={"amount": "20", "reason": "Compensación"}, headers=admin_headers
    )
    assert small.status_code == 201  # at the limit: applied at once

    held = await client.post(
        f"{wallet}/adjust", json={"amount": "25", "reason": "Bono"}, headers=admin_headers
    )
    assert held.status_code == 202, held.text
    body = held.json()
    assert body["status"] == "pending_approval"
    approval = body["approval"]
    assert approval["action"] == "wallet.adjust" and approval["status"] == "pending"
    assert approval["payload"]["amount"] == "25.00" and approval["reason"] == "Bono"
    assert (await client.get(wallet, headers=finanzas)).json()["balance"] == "20.00"
    [request] = await _actions("approval.request")
    assert request.entity_type == "approval" and request.entity_id == approval["id"]
    assert len(await _actions("wallet.adjust")) == 1  # only the small one

    url = f"{API}/admin/approvals/{approval['id']}"
    own = await client.post(f"{url}/approve", json={}, headers=admin_headers)
    assert own.status_code == 403
    assert own.json()["error"]["code"] == "approval_own_request"

    # Support cannot see it; finance can and decides.
    assert (await client.get(f"{API}/admin/approvals", headers=soporte)).json() == []
    assert (await client.post(f"{url}/approve", json={}, headers=soporte)).status_code == 404
    count = await client.get(f"{API}/admin/approvals/count", headers=finanzas)
    assert count.json() == {"pending": 1}
    [listed] = (await client.get(f"{API}/admin/approvals", headers=finanzas)).json()
    assert listed["can_decide"] is True

    approved = await client.post(f"{url}/approve", json={"note": " ok "}, headers=finanzas)
    assert approved.status_code == 200, approved.text
    decided = approved.json()
    assert decided["status"] == "approved" and decided["decision_note"] == "ok"
    assert decided["decided_by_email"] == "finanzas@example.com"
    assert decided["result"]["entry_id"]
    assert (await client.get(wallet, headers=finanzas)).json()["balance"] == "45.00"
    [decision] = await _actions("approval.approve")
    assert decision.after["status"] == "approved"

    again = await client.post(f"{url}/approve", json={}, headers=finanzas)
    assert again.status_code == 409 and again.json()["error"]["code"] == "approval_closed"
    count = await client.get(f"{API}/admin/approvals/count", headers=finanzas)
    assert count.json() == {"pending": 0}


async def test_rejecting_needs_a_note_and_changes_nothing(client, admin_headers):
    other = await _second_admin(client)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    held = await client.post(
        f"{API}/admin/wallets/{luis.id}/adjust",
        json={"amount": "-50", "reason": "Cobro"},
        headers=admin_headers,
    )
    assert held.status_code == 202
    url = f"{API}/admin/approvals/{held.json()['approval']['id']}/reject"
    assert (await client.post(url, json={"note": "  "}, headers=other)).status_code == 422
    rejected = await client.post(url, json={"note": "No corresponde"}, headers=other)
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    balance = (await client.get(f"{API}/admin/wallets/{luis.id}", headers=other)).json()
    assert balance["balance"] == "0.00"
    [entry] = await _actions("approval.reject")
    assert entry.reason == "No corresponde"


async def test_failed_action_keeps_the_request_pending(client, admin_headers):
    other = await _second_admin(client)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    held = await client.post(
        f"{API}/admin/wallets/{luis.id}/adjust",
        json={"amount": "-50", "reason": "Cobro"},
        headers=admin_headers,
    )
    url = f"{API}/admin/approvals/{held.json()['approval']['id']}"
    failed = await client.post(f"{url}/approve", json={}, headers=other)
    assert failed.status_code == 409  # not enough balance
    [listed] = (await client.get(f"{API}/admin/approvals", headers=other)).json()
    assert listed["status"] == "pending"


async def test_requests_expire(client, admin_headers):
    other = await _second_admin(client)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    held = await client.post(
        f"{API}/admin/wallets/{luis.id}/adjust",
        json={"amount": "30", "reason": "Bono"},
        headers=admin_headers,
    )
    approval_id = held.json()["approval"]["id"]
    async with SessionLocal() as session:
        await session.execute(
            update(PendingApproval).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    [listed] = (await client.get(f"{API}/admin/approvals", headers=other)).json()
    assert listed["status"] == "expired" and listed["can_decide"] is False
    pending = await client.get(f"{API}/admin/approvals?status=pending", headers=other)
    assert pending.json() == []
    late = await client.post(f"{API}/admin/approvals/{approval_id}/approve", json={}, headers=other)
    assert late.status_code == 409


async def test_fee_schedule_needs_a_second_admin(client, admin_headers):
    [finanzas] = await _staff(client, "finanzas", "finanzas@example.com")
    other = await _second_admin(client)
    url = f"{API}/admin/subscriptions/schedules"
    tiers = [{"above": "0", "fee": "0"}, {"above": "150", "fee": "8"}]

    # Invalid requests are refused before they are held.
    current = format_month(month_start(local_now()))
    past = await client.post(
        url, json={"effective_month": current, "tiers": tiers}, headers=admin_headers
    )
    assert past.status_code == 400

    month = format_month(add_months(month_start(local_now()), 1))
    held = await client.post(
        url, json={"effective_month": month, "tiers": tiers}, headers=admin_headers
    )
    assert held.status_code == 202, held.text
    approval_id = held.json()["approval"]["id"]
    assert len((await client.get(url, headers=other)).json()) == 1  # nothing created yet

    # Finance has subscriptions.manage, but fee schedules are admin-only: it does not even see it.
    denied = await client.post(
        f"{API}/admin/approvals/{approval_id}/approve", json={}, headers=finanzas
    )
    assert denied.status_code == 404

    approved = await client.post(
        f"{API}/admin/approvals/{approval_id}/approve", json={}, headers=other
    )
    assert approved.status_code == 200, approved.text
    schedules = (await client.get(url, headers=other)).json()
    assert len(schedules) == 2
    assert {s["created_by"]["email"] for s in schedules if s["id"]} == {"admin@example.com"}


async def test_fare_changes_wait_but_other_settings_do_not(client, admin_headers):
    other = await _second_admin(client)
    config = (await client.get(f"{API}/admin/config", headers=admin_headers)).json()

    # The panel sends the whole object; unchanged fares do not trigger an approval.
    plain = await client.patch(
        f"{API}/admin/config", json=config | {"driver_min_age": 22}, headers=admin_headers
    )
    assert plain.status_code == 200 and plain.json()["driver_min_age"] == 22

    fares = config["fares"] | {"moto": config["fares"]["moto"] | {"base": "1.00"}}
    held = await client.patch(
        f"{API}/admin/config",
        json=config | {"driver_min_age": 22, "fares": fares},
        headers=admin_headers,
    )
    assert held.status_code == 202, held.text
    assert set(held.json()["approval"]["payload"]) == {"fares"}
    public = (await client.get(f"{API}/config/public")).json()
    assert public["fares"]["moto"]["base"] == "0.80"

    # A later edit is not undone when the request is approved.
    await client.patch(f"{API}/admin/config", json={"driver_min_age": 25}, headers=admin_headers)
    approval_id = held.json()["approval"]["id"]
    approved = await client.post(
        f"{API}/admin/approvals/{approval_id}/approve", json={}, headers=other
    )
    assert approved.status_code == 200, approved.text
    public = (await client.get(f"{API}/config/public")).json()
    assert public["fares"]["moto"]["base"] == "1.00" and public["driver_min_age"] == 25


async def test_broadcast_waits_and_direct_messages_do_not(client, user_headers):
    operaciones, ops2 = await _staff(client, "operaciones", "ops@example.com", "ops2@example.com")
    me = (await client.get(f"{API}/users/me", headers=user_headers)).json()
    direct = await client.post(
        f"{API}/notifications/send",
        json={"title": "Hola", "user_id": me["id"]},
        headers=operaciones,
    )
    assert direct.json() == {"queued": 1}

    held = await client.post(
        f"{API}/notifications/send", json={"title": "Aviso"}, headers=operaciones
    )
    assert held.status_code == 202 and held.json()["status"] == "pending_approval"
    inbox = (await client.get(f"{API}/notifications", headers=user_headers)).json()
    assert inbox["total"] == 1

    approval_id = held.json()["approval"]["id"]
    approved = await client.post(
        f"{API}/admin/approvals/{approval_id}/approve", json={}, headers=ops2
    )
    assert approved.status_code == 200, approved.text
    inbox = (await client.get(f"{API}/notifications", headers=user_headers)).json()
    assert inbox["total"] == 2
