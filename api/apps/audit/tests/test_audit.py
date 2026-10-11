import csv
import io
import uuid
from decimal import Decimal

from sqlalchemy import select

from apps.audit.models import AuditLog
from apps.audit.services import _redact, snapshot
from apps.drivers.models import DriverProfile
from apps.rides.tests.conftest import make_driver
from apps.users.models import Role
from conftest import PASSWORD, _make_user
from kuulis.core import storage
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def _rows(action: str | None = None) -> list[AuditLog]:
    async with SessionLocal() as session:
        stmt = select(AuditLog).order_by(AuditLog.created_at)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        return list(await session.scalars(stmt))


def test_redact_hides_secrets_and_makes_values_json_safe():
    value = {
        "password": "x",
        "new_password": "y",
        "nested": {"refresh_token": "z", "items": [{"api_key": "k", "ok": 1}]},
        "amount": Decimal("3.50"),
        "id": uuid.UUID(int=1),
        "role": Role.ADMIN,
        "note": "a" * 3000,
    }
    out = _redact(value)
    assert out["password"] == out["new_password"] == "[redacted]"
    assert out["nested"] == {
        "refresh_token": "[redacted]",
        "items": [{"api_key": "[redacted]", "ok": 1}],
    }
    assert out["amount"] == "3.50" and out["id"] == str(uuid.UUID(int=1)) and out["role"] == "admin"
    assert len(out["note"]) == 2001
    assert snapshot({"a": 1, "b": 2}, ["a"]) == {"a": 1}


async def test_wallet_adjust_leaves_one_row_and_failures_none(client, admin_headers, staff_headers):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    url = f"{API}/admin/wallets/{luis.id}/adjust"
    # A business error and a missing permission write nothing.
    assert (
        await client.post(url, json={"amount": "-1", "reason": "x"}, headers=admin_headers)
    ).status_code == 409
    assert (
        await client.post(url, json={"amount": "3", "reason": "x"}, headers=staff_headers)
    ).status_code == 403
    assert await _rows("wallet.adjust") == []

    ok = await client.post(
        url,
        json={"amount": "3", "reason": "Compensación"},
        headers={**admin_headers, "User-Agent": "pytest-admin", "X-Request-ID": "req-123"},
    )
    assert ok.status_code == 201, ok.text
    [row] = await _rows("wallet.adjust")
    assert row.actor_email == "admin@example.com" and row.actor_id is not None
    assert row.entity_type == "wallet" and row.entity_id == str(luis.id)
    assert row.reason == "Compensación"
    assert row.before == {"balance": "0.00"}
    assert row.after["balance"] == "3.00" and row.after["amount"] == "3.00"
    assert row.after["entry_id"] == ok.json()["id"]
    assert row.user_agent == "pytest-admin" and row.request_id == "req-123" and row.ip


async def test_config_update_keeps_only_changed_keys(client, admin_headers):
    response = await client.patch(
        f"{API}/admin/config", json={"driver_min_age": 25}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    [row] = await _rows("config.update")
    assert row.before == {"driver_min_age": 21} and row.after == {"driver_min_age": 25}


async def test_admin_password_never_stored(client, admin_headers):
    response = await client.post(
        f"{API}/users",
        json={"email": "nuevo@example.com", "password": PASSWORD, "role": "staff"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    [row] = await _rows("user.create")
    assert row.entity_id == response.json()["id"]
    assert row.after["password"] == "[redacted]" and PASSWORD not in str(row.after)


async def test_sensitive_reads_are_audited(client, admin_headers, staff_headers):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    async with SessionLocal() as session:
        profile_id = await session.scalar(
            select(DriverProfile.id).where(DriverProfile.user_id == luis.user.id)
        )
    assert (
        await client.get(f"{API}/admin/drivers/{profile_id}", headers=staff_headers)
    ).status_code == 200
    assert (await client.get(f"{API}/users/{luis.id}", headers=staff_headers)).status_code == 200
    export = await client.get(
        f"{API}/admin/finance/entries.csv?from=2026-10-01&to=2026-10-11", headers=admin_headers
    )
    assert export.status_code == 200, export.text
    [driver_view] = await _rows("driver.view")
    assert driver_view.actor_email == "staff@example.com" and driver_view.entity_id == str(
        profile_id
    )
    assert len(await _rows("user.view")) == 1
    [csv_row] = await _rows("finance.export_entries")
    assert csv_row.after == {"from": "2026-10-01", "to": "2026-10-11"}


async def test_staff_opening_someone_elses_file_is_audited(client, admin_headers, monkeypatch):
    monkeypatch.setattr(
        storage, "presigned_download", lambda key, expires_in=None: f"https://s3.test/get/{key}"
    )
    admin = (await client.get(f"{API}/users/me", headers=admin_headers)).json()
    other = await _make_user("otra@example.com")
    own = storage.folder_prefix(f"uploads/{admin['id']}") + "a.pdf"
    foreign = storage.folder_prefix(f"drivers/{other.id}") + "cedula.jpg"
    for key in (own, foreign):
        response = await client.get(
            f"{API}/files/download", params={"key": key}, headers=admin_headers
        )
        assert response.status_code == 200, response.text
    [row] = await _rows("file.view")
    assert row.after == {"key": foreign} and row.actor_email == "admin@example.com"


async def test_list_filter_and_export(client, admin_headers, staff_headers):
    for age in (22, 23):
        await client.patch(
            f"{API}/admin/config", json={"driver_min_age": age}, headers=admin_headers
        )
    await _make_user("otro-admin@example.com", Role.ADMIN)

    assert (await client.get(f"{API}/admin/audit", headers=staff_headers)).status_code == 403
    listing = await client.get(
        f"{API}/admin/audit", params={"action": "config"}, headers=admin_headers
    )
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 2
    assert [i["after"]["driver_min_age"] for i in body["items"]] == [23, 22]  # newest first
    none = await client.get(
        f"{API}/admin/audit", params={"entity_type": "wallet"}, headers=admin_headers
    )
    assert none.json()["total"] == 0

    export = await client.get(
        f"{API}/admin/audit/export.csv", params={"action": "config"}, headers=admin_headers
    )
    assert export.status_code == 200
    rows = list(csv.reader(io.StringIO(export.text)))
    assert rows[0][:3] == ["fecha", "actor", "accion"] and len(rows) == 3
    [exported] = await _rows("audit.export")
    assert exported.after == {"action": "config"}
