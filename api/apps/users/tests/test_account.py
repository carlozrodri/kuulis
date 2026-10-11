from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from apps.places.models import SavedPlace
from apps.users import services
from apps.users.models import User
from conftest import PASSWORD
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def test_trusted_contact(client, user_headers):
    response = await client.patch(
        f"{API}/users/me",
        json={"trusted_contact_name": " Mamá ", "trusted_contact_phone": "+584141234567"},
        headers=user_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["trusted_contact_name"] == "Mamá"

    half = await client.patch(
        f"{API}/users/me", json={"trusted_contact_name": ""}, headers=user_headers
    )
    assert half.json()["error"]["code"] == "trusted_contact_incomplete"
    bad = await client.patch(
        f"{API}/users/me", json={"trusted_contact_phone": "04141234567"}, headers=user_headers
    )
    assert bad.status_code == 422

    cleared = await client.patch(
        f"{API}/users/me",
        json={"trusted_contact_name": None, "trusted_contact_phone": None},
        headers=user_headers,
    )
    assert cleared.json()["trusted_contact_phone"] is None


async def test_delete_restore_and_erase(client, user_headers):
    me = (await client.get(f"{API}/users/me", headers=user_headers)).json()
    await client.post(
        f"{API}/users/me/places",
        json={"kind": "home", "address": "Casa", "lat": 10.5, "lng": -66.8},
        headers=user_headers,
    )

    response = await client.delete(f"{API}/users/me", headers=user_headers)
    assert response.status_code == 200, response.text
    erase_at = datetime.fromisoformat(response.json()["erase_at"])
    assert timedelta(days=29) < erase_at - datetime.now(UTC) <= timedelta(days=30)
    assert (await client.get(f"{API}/users/me", headers=user_headers)).status_code == 401

    # Signing in during the grace period restores the account.
    login = await client.post(
        f"{API}/auth/login", json={"email": me["email"], "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.delete(f"{API}/users/me", headers=headers)).status_code == 200

    async with SessionLocal() as session:
        # Not due yet.
        assert await services.erase_due(session) == 0
        await session.execute(
            update(User)
            .where(User.email == me["email"])
            .values(deletion_requested_at=datetime.now(UTC) - timedelta(days=31))
        )
        await session.commit()
        assert await services.erase_due(session) == 1

    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.full_name == "", User.deleted_at.is_not(None))
        )
        assert user is not None and user.email.endswith("@deleted.invalid")
        assert user.hashed_password is None
        assert await session.scalar(select(SavedPlace).where(SavedPlace.user_id == user.id)) is None

    gone = await client.post(f"{API}/auth/login", json={"email": me["email"], "password": PASSWORD})
    assert gone.status_code == 401
