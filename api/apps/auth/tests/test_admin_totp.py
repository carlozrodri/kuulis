"""Doc 05 (part 2): admin second factor and visible sessions."""

import time

import pyotp
import pytest

from apps.auth import totp
from conftest import PASSWORD, _make_user
from kuulis.settings import settings

ADMIN = {"email": "admin@example.com", "password": PASSWORD}


@pytest.fixture
def totp_required(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOTP_REQUIRED", True)


def _code(secret: str, offset: int = 0) -> str:
    """The code of the current time step (``offset`` steps ahead: a code not used yet)."""
    generator = pyotp.TOTP(secret)
    return generator.at(int(time.time()) + offset * generator.interval)


async def _enroll(client) -> tuple[dict, str, list[str]]:
    """Admin login with the setup step; returns headers, secret and recovery codes."""
    step = (await client.post("/api/v1/auth/admin/login", json=ADMIN)).json()
    assert step["status"] == "totp_setup"
    secret = step["setup"]["secret"]
    assert step["setup"]["otpauth_uri"].startswith("otpauth://totp/")
    assert step["setup"]["qr_data_uri"].startswith("data:image/svg+xml")
    done = await client.post(
        "/api/v1/auth/admin/totp", json={"challenge": step["challenge"], "code": _code(secret)}
    )
    assert done.status_code == 200, done.text
    body = done.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, secret, body["recovery_codes"]


async def test_admin_login_needs_the_second_factor(client, totp_required):
    from apps.users.models import Role

    await _make_user("admin@example.com", Role.ADMIN)
    headers, secret, codes = await _enroll(client)
    assert len(codes) == totp.RECOVERY_CODES
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 200

    # Next sign-in asks for a code; the one already used is refused (no replay).
    step = (await client.post("/api/v1/auth/admin/login", json=ADMIN)).json()
    assert step["status"] == "totp_required" and step["setup"] is None
    bad = await client.post(
        "/api/v1/auth/admin/totp", json={"challenge": step["challenge"], "code": _code(secret)}
    )
    assert bad.json()["error"]["code"] == "totp_invalid"
    # A recovery code works once.
    ok = await client.post(
        "/api/v1/auth/admin/totp", json={"challenge": step["challenge"], "code": codes[0]}
    )
    assert ok.status_code == 200 and ok.json()["recovery_codes"] is None
    step = (await client.post("/api/v1/auth/admin/login", json=ADMIN)).json()
    again = await client.post(
        "/api/v1/auth/admin/totp", json={"challenge": step["challenge"], "code": codes[0]}
    )
    assert again.json()["error"]["code"] == "totp_invalid"


async def test_challenge_dies_after_too_many_codes(client, totp_required):
    from apps.users.models import Role

    await _make_user("admin@example.com", Role.ADMIN)
    step = (await client.post("/api/v1/auth/admin/login", json=ADMIN)).json()
    for _ in range(totp.MAX_ATTEMPTS):
        await client.post(
            "/api/v1/auth/admin/totp", json={"challenge": step["challenge"], "code": "000000"}
        )
    last = await client.post(
        "/api/v1/auth/admin/totp", json={"challenge": step["challenge"], "code": "000000"}
    )
    assert last.json()["error"]["code"] == "totp_challenge_expired"


async def test_staff_signed_in_from_the_app_has_no_admin_powers(client, totp_required):
    from apps.users.models import Role

    await _make_user("staff@example.com", Role.STAFF)
    app_login = await client.post(
        "/api/v1/auth/login", json={"email": "staff@example.com", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {app_login.json()['access_token']}"}
    denied = await client.get("/api/v1/users", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "admin_mfa_required"
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 200


async def test_sensitive_actions_ask_for_a_fresh_code(client, totp_required):
    from apps.users.models import Role

    await _make_user("admin@example.com", Role.ADMIN)
    target = await _make_user("someone@example.com")
    headers, secret, _ = await _enroll(client)
    change = {"role": "staff"}
    asked = await client.patch(f"/api/v1/users/{target.id}", headers=headers, json=change)
    assert asked.json()["error"]["code"] == "reauth_required"
    # Renaming does not need it.
    rename = await client.patch(
        f"/api/v1/users/{target.id}", headers=headers, json={"full_name": "Someone"}
    )
    assert rename.status_code == 200

    reauth = await client.post(
        "/api/v1/auth/admin/reauth", headers=headers, json={"code": _code(secret, 1)}
    )
    assert reauth.status_code == 204, reauth.text
    done = await client.patch(f"/api/v1/users/{target.id}", headers=headers, json=change)
    assert done.status_code == 200 and done.json()["role"] == "staff"


async def test_admin_resets_a_staff_authenticator(client, totp_required):
    from apps.users.models import Role

    await _make_user("admin@example.com", Role.ADMIN)
    staff = await _make_user("staff@example.com", Role.STAFF)
    staff_login = {"email": "staff@example.com", "password": PASSWORD}
    step = (await client.post("/api/v1/auth/admin/login", json=staff_login)).json()
    staff_secret = step["setup"]["secret"]
    staff_code = {"challenge": step["challenge"], "code": _code(staff_secret)}
    await client.post("/api/v1/auth/admin/totp", json=staff_code)
    headers, secret, _ = await _enroll(client)
    await client.post("/api/v1/auth/admin/reauth", headers=headers, json={"code": _code(secret, 1)})
    reset = await client.post(f"/api/v1/users/{staff.id}/totp/reset", headers=headers)
    assert reset.status_code == 204
    step = (await client.post("/api/v1/auth/admin/login", json=staff_login)).json()
    assert step["status"] == "totp_setup"


async def test_sessions_are_listed_and_closed_one_by_one(client):
    await _make_user("user@example.com")
    login = {"email": "user@example.com", "password": PASSWORD}
    phone = (
        await client.post(
            "/api/v1/auth/login",
            json=login,
            headers={"User-Agent": "okhttp/4.12.0", "X-Client-Platform": "android"},
        )
    ).json()
    laptop = (
        await client.post(
            "/api/v1/auth/login",
            json=login,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36"},
        )
    ).json()
    phone_headers = {"Authorization": f"Bearer {phone['access_token']}"}
    laptop_headers = {"Authorization": f"Bearer {laptop['access_token']}"}

    listed = (await client.get("/api/v1/auth/sessions", headers=phone_headers)).json()
    assert len(listed) == 2
    current = next(s for s in listed if s["current"])
    other = next(s for s in listed if not s["current"])
    assert current["platform"] == "android" and current["device"] == "Kuulis · Android"
    assert other["device"] == "Chrome · Windows"

    # Closing the laptop session stops its access token and its refresh token at once.
    closed = await client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=phone_headers)
    assert closed.status_code == 204
    assert (await client.get("/api/v1/users/me", headers=laptop_headers)).status_code == 401
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": laptop["refresh_token"]}
    )
    assert refresh.json()["error"]["code"] == "token_revoked"
    # ...without signing the phone out (it is not treated as token reuse).
    assert (await client.get("/api/v1/users/me", headers=phone_headers)).status_code == 200
    rotated = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": phone["refresh_token"]}
    )
    assert rotated.status_code == 200
    after = (await client.get("/api/v1/auth/sessions", headers=phone_headers)).json()
    assert [s["id"] for s in after] == [current["id"]]  # same session after the refresh
