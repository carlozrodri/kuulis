"""Social login with locally signed ID tokens; the JWKS download is replaced (no network)."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.auth import social
from kuulis.settings import settings

GOOGLE_CLIENT = "web-client.apps.googleusercontent.com"
APPLE_CLIENT = "com.kuulis.app"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks() -> dict:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_private_key.public_key(), as_dict=True)
    return {"keys": [jwk | {"kid": "k1", "alg": "RS256", "use": "sig"}]}


def _token(key=_private_key, kid: str = "k1", **claims) -> str:
    now = int(time.time())
    payload = {"iat": now, "exp": now + 600} | claims
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


def _google(**claims) -> str:
    base = {
        "iss": "https://accounts.google.com",
        "aud": GOOGLE_CLIENT,
        "sub": "google-123",
        "email": "Rider@Gmail.com",
        "email_verified": True,
        "name": "Rider Uno",
    }
    return _token(**(base | claims))


def _apple(**claims) -> str:
    base = {
        "iss": "https://appleid.apple.com",
        "aud": APPLE_CLIENT,
        "sub": "apple-001",
        "email": "abc@privaterelay.appleid.com",
        "email_verified": "true",
    }
    return _token(**(base | claims))


@pytest.fixture(autouse=True)
def _providers(monkeypatch):
    calls = {"n": 0}

    async def fake_fetch(provider):
        calls["n"] += 1
        return _jwks()

    monkeypatch.setattr(social, "fetch_jwks", fake_fetch)
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_IDS", [GOOGLE_CLIENT])
    monkeypatch.setattr(settings, "APPLE_CLIENT_IDS", [APPLE_CLIENT])
    return calls


async def test_google_creates_verified_user_and_reuses_account(client, _providers):
    response = await client.post("/api/v1/auth/social/google", json={"id_token": _google()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "rider@gmail.com"
    assert body["user"]["is_verified"] is True
    assert body["user"]["full_name"] == "Rider Uno"
    assert body["access_token"] and body["refresh_token"]

    # Same Google subject, new email: still the same user (lookup by provider + sub first).
    again = await client.post(
        "/api/v1/auth/social/google", json={"id_token": _google(email="new@gmail.com")}
    )
    assert again.json()["user"]["id"] == body["user"]["id"]
    assert _providers["n"] == 1  # JWKS cached in Redis


async def test_google_links_existing_email_user(client, user_headers):
    me = (await client.get("/api/v1/users/me", headers=user_headers)).json()
    token = _google(sub="google-999", email="user@example.com")
    response = await client.post("/api/v1/auth/social/google", json={"id_token": token})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == me["id"]


async def test_google_rejects_bad_tokens(client):
    cases = [
        _google(aud="someone-else"),
        _google(iss="https://evil.example.com"),
        _google(email_verified=False),
        _google(exp=int(time.time()) - 3600),
        _token(_other_key, **{"iss": "accounts.google.com", "aud": GOOGLE_CLIENT, "sub": "x"}),
        _google()[:-5] + "abcde",
        "not-a-jwt",
    ]
    for token in cases:
        response = await client.post("/api/v1/auth/social/google", json={"id_token": token})
        assert response.status_code == 401, token
        assert response.json()["error"]["code"] == "social_token_invalid"


async def test_unknown_kid_refetches_once(client, _providers):
    response = await client.post("/api/v1/auth/social/google", json={"id_token": _google(kid="k9")})
    assert response.status_code == 401
    assert _providers["n"] == 2


async def test_provider_disabled_without_client_ids(client, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_IDS", [])
    response = await client.post("/api/v1/auth/social/google", json={"id_token": _google()})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "social_provider_disabled"


async def test_apple_first_login_uses_full_name_then_works_without_email(client):
    first = await client.post(
        "/api/v1/auth/social/apple", json={"id_token": _apple(), "full_name": "Ana Pérez"}
    )
    assert first.status_code == 200, first.text
    assert first.json()["user"]["full_name"] == "Ana Pérez"
    claims = {"email": None, "email_verified": None}
    again = await client.post("/api/v1/auth/social/apple", json={"id_token": _apple(**claims)})
    assert again.status_code == 200
    assert again.json()["user"]["id"] == first.json()["user"]["id"]


async def test_apple_without_email_and_no_account_is_rejected(client):
    token = _apple(sub="apple-new", email=None)
    response = await client.post("/api/v1/auth/social/apple", json={"id_token": token})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "social_token_invalid"


async def test_inactive_user_cannot_social_login(client, admin_headers):
    first = await client.post("/api/v1/auth/social/google", json={"id_token": _google()})
    user_id = first.json()["user"]["id"]
    await client.patch(f"/api/v1/users/{user_id}", json={"is_active": False}, headers=admin_headers)
    response = await client.post("/api/v1/auth/social/google", json={"id_token": _google()})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "user_inactive"
