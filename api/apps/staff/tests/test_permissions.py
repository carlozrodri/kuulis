from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from apps.audit.tests.test_coverage import _api_routes, _calls
from apps.rides.tests.conftest import make_driver
from apps.staff.permissions import ALL_PERMISSIONS, DEFAULT_ROLES
from apps.users import tasks as user_tasks
from apps.users.models import Role, User
from conftest import PASSWORD, _login, _make_user, make_staff_role
from kuulis.asgi import app
from kuulis.core.db import SessionLocal

API = "/api/v1"
# Any staff member may confirm their own second factor and read the settings every page uses.
OPEN_TO_ALL_STAFF = {"/auth/admin/reauth", "/admin/config"}


async def _staff(client, email: str, role: str) -> dict[str, str]:
    _, permissions = DEFAULT_ROLES[role]
    staff_role = await make_staff_role(role, permissions)
    await _make_user(email, Role.STAFF, staff_role)
    return await _login(client, email)


def test_every_staff_endpoint_names_its_permission():
    missing = []
    for route in _api_routes(app.routes):
        if route.path in OPEN_TO_ALL_STAFF:
            continue
        calls = _calls(route.dependant)
        staff_open = any(Role.STAFF in getattr(c, "admin_roles", ()) for c in calls)
        if staff_open and not any(hasattr(c, "permission") for c in calls):
            missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, "Staff endpoints without Can(...):\n" + "\n".join(sorted(set(missing)))


def test_default_roles_use_known_permissions():
    for _, permissions in DEFAULT_ROLES.values():
        assert set(permissions) <= ALL_PERMISSIONS


async def test_support_cannot_adjust_balances(client):
    soporte = await _staff(client, "soporte@example.com", "soporte")
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    response = await client.post(
        f"{API}/admin/wallets/{luis.id}/adjust",
        json={"amount": "3", "reason": "x"},
        headers=soporte,
    )
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "permission_denied"
    assert error["details"] == {"permission": "wallet.adjust"}
    assert (await client.get(f"{API}/users", headers=soporte)).status_code == 200


async def test_staff_without_role_has_no_admin_access(client):
    staff = await _make_user("sinrol@example.com", Role.STAFF)
    async with SessionLocal() as session:
        await session.execute(update(User).where(User.id == staff.id).values(staff_role_id=None))
        await session.commit()
    headers = await _login(client, "sinrol@example.com")
    response = await client.get(f"{API}/users", headers=headers)
    assert response.status_code == 403
    assert (await client.get(f"{API}/users/me", headers=headers)).json()["permissions"] == []


async def test_verifier_sees_drivers_not_rides(client):
    verificador = await _staff(client, "verif@example.com", "verificador")
    assert (await client.get(f"{API}/admin/drivers", headers=verificador)).status_code == 200
    rides = await client.get(f"{API}/admin/rides", headers=verificador)
    assert rides.status_code == 403
    assert rides.json()["error"]["details"]["permission"] == "rides.view"
    me = (await client.get(f"{API}/users/me", headers=verificador)).json()
    assert me["permissions"] == sorted(DEFAULT_ROLES["verificador"][1])


async def test_support_suspends_for_seven_days_at_most(client, admin_headers):
    soporte = await _staff(client, "soporte@example.com", "soporte")
    target = await _make_user("pasajero@example.com")
    url = f"{API}/admin/users/{target.id}/suspend"
    forever = await client.post(url, json={"reason": "Abuso"}, headers=soporte)
    assert forever.status_code == 403
    assert forever.json()["error"]["details"]["permission"] == "users.suspend_long"
    month = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    long = await client.post(url, json={"reason": "Abuso", "until": month}, headers=soporte)
    assert long.status_code == 403
    week = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    ok = await client.post(url, json={"reason": "Abuso", "until": week}, headers=soporte)
    assert ok.status_code == 200, ok.text
    # An admin can suspend with no end.
    other = await _make_user("otro@example.com")
    admin_forever = await client.post(
        f"{API}/admin/users/{other.id}/suspend", json={"reason": "Fraude"}, headers=admin_headers
    )
    assert admin_forever.status_code == 200


async def test_roles_matrix_is_admin_only_and_audited(client, admin_headers, staff_headers):
    assert (await client.get(f"{API}/admin/roles", headers=staff_headers)).status_code == 403
    finanzas = await make_staff_role("finanzas", DEFAULT_ROLES["finanzas"][1])
    overview = (await client.get(f"{API}/admin/roles", headers=admin_headers)).json()
    assert {g["group"] for g in overview["catalog"]} >= {"wallet", "users"}
    assert "finanzas" in {r["name"] for r in overview["roles"]}

    bad = await client.put(
        f"{API}/admin/roles/{finanzas.id}",
        json={"permissions": ["config.edit"]},
        headers=admin_headers,
    )
    assert bad.status_code == 422  # admin-only areas cannot be granted
    updated = await client.put(
        f"{API}/admin/roles/{finanzas.id}",
        json={"permissions": ["finance.view", "wallet.view"]},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["permissions"] == ["finance.view", "wallet.view"]
    audit = (
        await client.get(f"{API}/admin/audit", params={"action": "role."}, headers=admin_headers)
    ).json()
    [entry] = audit["items"]
    assert entry["before"]["permissions"] == sorted(DEFAULT_ROLES["finanzas"][1])
    assert entry["after"]["permissions"] == ["finance.view", "wallet.view"]

    created = await client.post(
        f"{API}/admin/roles",
        json={"name": "auditor", "label": "Auditor", "permissions": ["finance.view"]},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text


async def test_invite_accept_and_manage_team(client, admin_headers, monkeypatch):
    sent = []

    async def fake_kiq(*args):
        sent.append(args)

    monkeypatch.setattr(user_tasks.send_templated_email, "kiq", fake_kiq)
    soporte = await make_staff_role("soporte", DEFAULT_ROLES["soporte"][1])
    invited = await client.post(
        f"{API}/admin/staff/invite",
        json={
            "email": "Nueva@Example.com",
            "full_name": "Nueva Persona",
            "staff_role_id": str(soporte.id),
        },
        headers=admin_headers,
    )
    assert invited.status_code == 201, invited.text
    member = invited.json()
    assert member["invite_pending"] is True and member["staff_role_label"] == "Soporte"
    [(to, template, _, _, link)] = sent
    assert to == "nueva@example.com" and template == "invite" and "/accept-invite?token=" in link
    token = link.split("token=")[1]

    # Not usable before accepting; the token works once.
    login = {"email": "nueva@example.com", "password": PASSWORD}
    assert (await client.post(f"{API}/auth/login", json=login)).status_code == 401
    accept = await client.post(
        f"{API}/auth/invite/accept", json={"token": token, "password": PASSWORD}
    )
    assert accept.status_code == 204, accept.text
    again = await client.post(
        f"{API}/auth/invite/accept", json={"token": token, "password": PASSWORD}
    )
    assert again.status_code == 401
    headers = await _login(client, "nueva@example.com")
    assert (await client.get(f"{API}/admin/reports", headers=headers)).status_code == 200

    # An existing account cannot be invited.
    await _make_user("cliente@example.com")
    taken = await client.post(
        f"{API}/admin/staff/invite",
        json={
            "email": "cliente@example.com",
            "full_name": "Cliente",
            "staff_role_id": str(soporte.id),
        },
        headers=admin_headers,
    )
    assert taken.status_code == 409

    team = (await client.get(f"{API}/admin/staff", headers=admin_headers)).json()
    assert {m["email"] for m in team} == {"admin@example.com", "nueva@example.com"}
    assert all(m["email"] != "cliente@example.com" for m in team)

    deactivated = await client.patch(
        f"{API}/admin/staff/{member['id']}", json={"is_active": False}, headers=admin_headers
    )
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False
    assert (await client.get(f"{API}/admin/reports", headers=headers)).status_code == 401

    admin = (await client.get(f"{API}/users/me", headers=admin_headers)).json()
    myself = await client.patch(
        f"{API}/admin/staff/{admin['id']}", json={"role": "staff"}, headers=admin_headers
    )
    assert myself.status_code == 403 and myself.json()["error"]["code"] == "self_demotion"
