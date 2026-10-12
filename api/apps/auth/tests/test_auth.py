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
    second = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert second.status_code == 200
    # The first token again, after the client already moved on: treated as stolen.
    reused = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401
    # Reuse revokes every session, including the rotated one.
    rotated = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second.json()["refresh_token"]}
    )
    assert rotated.status_code == 401


async def test_retried_refresh_gets_the_same_tokens(client):
    """A refresh whose answer was lost and is sent again does not log the user out."""
    tokens = (await client.post("/api/v1/auth/register", json=REGISTER)).json()
    body = {"refresh_token": tokens["refresh_token"]}
    first = await client.post("/api/v1/auth/refresh", json=body)
    retry = await client.post("/api/v1/auth/refresh", json=body)
    assert retry.status_code == 200
    assert retry.json()["refresh_token"] == first.json()["refresh_token"]
    following = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": retry.json()["refresh_token"]}
    )
    assert following.status_code == 200


async def test_retried_refresh_after_grace_is_reuse(client):
    from apps.auth import services

    tokens = (await client.post("/api/v1/auth/register", json=REGISTER)).json()
    body = {"refresh_token": tokens["refresh_token"]}
    first = await client.post("/api/v1/auth/refresh", json=body)
    jti = services.decode_token(tokens["refresh_token"], "refresh")["jti"]
    await services.redis_client.delete(services._rotated_key(jti))  # the grace period is over
    assert (await client.post("/api/v1/auth/refresh", json=body)).status_code == 401
    rotated = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert rotated.status_code == 401


async def test_retried_refresh_of_logged_out_session_fails(client):
    tokens = (await client.post("/api/v1/auth/register", json=REGISTER)).json()
    body = {"refresh_token": tokens["refresh_token"]}
    first = await client.post("/api/v1/auth/refresh", json=body)
    await client.post("/api/v1/auth/logout", json={"refresh_token": first.json()["refresh_token"]})
    response = await client.post("/api/v1/auth/refresh", json=body)
    assert response.status_code == 401


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


async def test_login_upgrades_hashes_made_with_older_argon2_settings(client, user_headers):
    from pwdlib import PasswordHash
    from sqlalchemy import select, update

    from apps.users.models import User
    from conftest import PASSWORD
    from kuulis.core.db import SessionLocal

    old = PasswordHash.recommended().hash(PASSWORD)  # 64 MiB, 3 passes, 4 lanes
    async with SessionLocal() as session:
        await session.execute(
            update(User).where(User.email == "user@example.com").values(hashed_password=old)
        )
        await session.commit()

    response = await client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    async with SessionLocal() as session:
        stored = await session.scalar(
            select(User.hashed_password).where(User.email == "user@example.com")
        )
    assert stored.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
