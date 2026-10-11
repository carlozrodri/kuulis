"""Doc 05 (part 1): rate limit keys, login lockout, common passwords, security headers."""

from datetime import timedelta

from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from apps.auth import lockout
from apps.users import passwords
from kuulis.core import rate_limit
from kuulis.core.security import create_token

TRUSTED = "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"  # docker/entrypoint.sh default


async def _client_after_proxies(forwarded_for: str, peer: str = "172.18.0.4") -> str:
    """What request.client becomes behind uvicorn's proxy middleware with our trusted networks."""
    seen: dict = {}

    async def app(scope, receive, send):
        seen["client"] = scope["client"]

    scope = {
        "type": "http",
        "client": (peer, 5000),
        "headers": [(b"x-forwarded-for", forwarded_for.encode())],
    }
    await ProxyHeadersMiddleware(app, trusted_hosts=TRUSTED)(scope, None, None)
    return seen["client"][0]


async def test_spoofed_forwarded_for_does_not_change_the_client_ip():
    # NPM appends the real address; Traefik appends NPM's private one.
    assert await _client_after_proxies("190.6.1.20, 192.168.1.10") == "190.6.1.20"
    assert await _client_after_proxies("1.2.3.4, 190.6.1.20, 192.168.1.10") == "190.6.1.20"


def _request(headers: dict[str, str] | None = None, ip: str = "190.6.1.20") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "client": (ip, 1), "headers": raw})


def test_signed_in_requests_are_limited_per_user_not_per_ip():
    token, _, _ = create_token("user-1", "access", timedelta(minutes=5))
    same_ip_other_user, _, _ = create_token("user-2", "access", timedelta(minutes=5))
    assert rate_limit.rate_key(_request({"Authorization": f"Bearer {token}"})) == "user:user-1"
    assert (
        rate_limit.rate_key(_request({"Authorization": f"Bearer {same_ip_other_user}"}))
        == "user:user-2"
    )
    assert rate_limit.rate_key(_request({"Authorization": "Bearer nope"})) == "ip:190.6.1.20"
    assert rate_limit.rate_key(_request()) == "ip:190.6.1.20"


async def test_rate_limit_answers_with_the_error_envelope(client, monkeypatch):
    monkeypatch.setattr(rate_limit.limiter, "enabled", True)
    try:
        for _ in range(5):
            await client.post("/api/v1/auth/password-reset", json={"email": "a@example.com"})
        response = await client.post("/api/v1/auth/password-reset", json={"email": "a@example.com"})
    finally:
        rate_limit.limiter.reset()
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response.headers["retry-after"]) > 0


async def test_login_locks_progressively_per_email(client, user_headers):
    wrong = {"email": "user@example.com", "password": "wrong-pass"}
    for _ in range(lockout.LOCK_AFTER - 1):
        assert (await client.post("/api/v1/auth/login", json=wrong)).status_code == 401
    locked = await client.post("/api/v1/auth/login", json=wrong)
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "login_locked"
    assert locked.json()["error"]["details"]["retry_after"] == 60

    # Even the right password waits until the lock ends.
    from conftest import PASSWORD

    right = {"email": "user@example.com", "password": PASSWORD}
    assert (await client.post("/api/v1/auth/login", json=right)).status_code == 429

    # The next lock in the same day is longer.
    from kuulis.core.redis import redis_client

    _, lock_key, _ = lockout._keys("user@example.com")
    await redis_client.delete(lock_key)
    for _ in range(lockout.LOCK_AFTER - 1):
        await client.post("/api/v1/auth/login", json=wrong)
    again = await client.post("/api/v1/auth/login", json=wrong)
    assert again.json()["error"]["details"]["retry_after"] == 5 * 60


async def test_unknown_emails_lock_the_same_way(client):
    wrong = {"email": "nobody@example.com", "password": "wrong-pass"}
    codes = [(await client.post("/api/v1/auth/login", json=wrong)).status_code for _ in range(6)]
    assert codes == [401, 401, 401, 401, 429, 429]


async def test_common_passwords_are_rejected(client, user_headers):
    assert passwords.is_common("Password123") and passwords.is_common("venezuela123")
    assert not passwords.is_common("Sup3r-secret!")
    response = await client.post(
        "/api/v1/auth/register", json={"email": "new@example.com", "password": "password123"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "password_too_common"
    from conftest import PASSWORD

    change = await client.post(
        "/api/v1/users/me/password",
        headers=user_headers,
        json={"current_password": PASSWORD, "new_password": "qwertyuiop"},
    )
    assert change.json()["error"]["code"] == "password_too_common"


async def test_api_sends_security_headers(client):
    response = await client.get("/api/health/live")
    assert "max-age" in response.headers["strict-transport-security"]
    assert response.headers["content-security-policy"].startswith("default-src 'none'")
    assert "camera=()" in response.headers["permissions-policy"]
