from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from apps.audit.models import AuditLog
from apps.staff.models import StaffRole, StaffServiceToken
from apps.users.models import Role
from conftest import _make_user, make_staff_role
from kuulis.core.db import SessionLocal

API = "/api/v1"
MARKETING = ("marketing.view", "marketing.manage", "marketing.publish")


async def _agent_account(name: str = "agentes"):
    role = await make_staff_role(f"rol_{name}", MARKETING)
    user = await _make_user(f"{name}@example.com", Role.STAFF, role)
    return user, role


async def _create(client, admin_headers, user_id, permissions, **extra) -> dict:
    response = await client.post(
        f"{API}/admin/service-tokens",
        json={"name": "Agentes de marketing", "user_id": str(user_id), "permissions": permissions}
        | extra,
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_token_opens_only_its_permissions(client, admin_headers):
    user, _ = await _agent_account()
    created = await _create(client, admin_headers, user.id, ["marketing.view", "marketing.manage"])
    assert created["token"].startswith("kst_")
    assert created["prefix"] == created["token"][:12]
    headers = _bearer(created["token"])

    listed = await client.get(f"{API}/admin/marketing/contents", headers=headers)
    assert listed.status_code == 200, listed.text

    # A write is audited as the token's staff account.
    made = await client.post(
        f"{API}/admin/marketing/contents",
        json={"title": "Prueba"},
        headers=headers,
    )
    assert made.status_code == 201, made.text
    async with SessionLocal() as session:
        logged = await session.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.actor_id == user.id)
        )
    assert logged == 1

    # The role has marketing.publish, but the token does not.
    queue = await client.get(f"{API}/admin/marketing/queue", headers=headers)
    assert queue.status_code == 403
    assert queue.json()["error"]["code"] == "service_token_forbidden"

    # Routes without a named permission never take a service token.
    me = await client.get(f"{API}/users/me", headers=headers)
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "service_token_not_allowed"
    team = await client.get(f"{API}/admin/staff", headers=headers)
    assert team.status_code == 401

    # The list never shows the key.
    tokens = (await client.get(f"{API}/admin/service-tokens", headers=admin_headers)).json()
    assert len(tokens) == 1 and "token" not in tokens[0]
    assert tokens[0]["last_used_at"] is not None


async def test_revoked_expired_and_unknown_tokens_fail(client, admin_headers):
    user, _ = await _agent_account()
    created = await _create(client, admin_headers, user.id, ["marketing.view"])
    headers = _bearer(created["token"])
    revoked = await client.post(
        f"{API}/admin/service-tokens/{created['id']}/revoke", headers=admin_headers
    )
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]
    response = await client.get(f"{API}/admin/marketing/contents", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "service_token_invalid"

    later = await _create(client, admin_headers, user.id, ["marketing.view"])
    async with SessionLocal() as session:
        await session.execute(
            update(StaffServiceToken)
            .where(StaffServiceToken.id == later["id"])
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    expired = await client.get(f"{API}/admin/marketing/contents", headers=_bearer(later["token"]))
    assert expired.status_code == 401

    unknown = await client.get(f"{API}/admin/marketing/contents", headers=_bearer("kst_nope"))
    assert unknown.json()["error"]["code"] == "service_token_invalid"


async def test_token_follows_the_role(client, admin_headers):
    user, role = await _agent_account()
    created = await _create(client, admin_headers, user.id, ["marketing.view"])
    async with SessionLocal() as session:
        await session.execute(
            update(StaffRole).where(StaffRole.id == role.id).values(permissions=["users.view"])
        )
        await session.commit()
    response = await client.get(
        f"{API}/admin/marketing/contents", headers=_bearer(created["token"])
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


async def test_create_checks_account_and_permissions(client, admin_headers, user_headers):
    user, _ = await _agent_account()
    beyond = await client.post(
        f"{API}/admin/service-tokens",
        json={"name": "x" * 3, "user_id": str(user.id), "permissions": ["wallet.adjust"]},
        headers=admin_headers,
    )
    assert beyond.status_code == 400
    assert beyond.json()["error"]["code"] == "service_token_permissions"
    assert beyond.json()["error"]["details"] == {"missing": ["wallet.adjust"]}

    admin = await _make_user("otro-admin@example.com", Role.ADMIN)
    as_admin = await client.post(
        f"{API}/admin/service-tokens",
        json={"name": "Admin", "user_id": str(admin.id), "permissions": ["marketing.view"]},
        headers=admin_headers,
    )
    assert as_admin.json()["error"]["code"] == "service_token_account"

    # Staff can't manage tokens.
    response = await client.get(f"{API}/admin/service-tokens", headers=user_headers)
    assert response.status_code == 403
