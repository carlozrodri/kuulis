from datetime import timedelta

from kuulis.core.security import create_token

REGISTER = {"email": "New@Example.com", "password": "Sup3r-secret!", "full_name": "New"}


async def test_register_returns_tokens_and_normalizes_email(client):
    response = await client.post("/api/v1/auth/register", json=REGISTER)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["role"] == "user"
    assert body["access_token"] and body["refresh_token"]


async def test_register_duplicate_email(client):
    await client.post("/api/v1/auth/register", json=REGISTER)
    response = await client.post("/api/v1/auth/register", json=REGISTER)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_login_wrong_password(client, user_headers):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "wrong-pass"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_refresh_rotation_and_reuse_detection(client):
    tokens = (await client.post("/api/v1/auth/register", json=REGISTER)).json()
    first = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert first.status_code == 200
    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401
    # Reuse revokes every session, including the rotated one.
    rotated = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert rotated.status_code == 401


async def test_logout_revokes_refresh_token(client):
    tokens = (await client.post("/api/v1/auth/register", json=REGISTER)).json()
    await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


async def test_admin_login_requires_staff_role(client, user_headers):
    response = await client.post(
        "/api/v1/auth/admin/login", json={"email": "user@example.com", "password": "Sup3r-secret!"}
    )
    assert response.status_code == 403


async def test_password_reset_token_is_single_use(client):
    body = (await client.post("/api/v1/auth/register", json=REGISTER)).json()
    token, _, _ = create_token(body["user"]["id"], "password_reset", timedelta(minutes=5))
    payload = {"token": token, "new_password": "An0ther-secret!"}
    assert (
        await client.post("/api/v1/auth/password-reset/confirm", json=payload)
    ).status_code == 204
    assert (
        await client.post("/api/v1/auth/password-reset/confirm", json=payload)
    ).status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"email": REGISTER["email"], "password": "An0ther-secret!"}
    )
    assert login.status_code == 200


async def test_verify_email(client):
    body = (await client.post("/api/v1/auth/register", json=REGISTER)).json()
    token, _, _ = create_token(body["user"]["id"], "email_verification", timedelta(hours=1))
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert response.json()["is_verified"] is True


async def test_password_reset_request_does_not_leak_emails(client):
    response = await client.post(
        "/api/v1/auth/password-reset", json={"email": "nobody@example.com"}
    )
    assert response.status_code == 202


async def test_access_token_cannot_be_used_as_refresh(client, user_headers):
    access = user_headers["Authorization"].split()[1]
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert response.status_code == 401
