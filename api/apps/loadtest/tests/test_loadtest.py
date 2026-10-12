from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from sqlalchemy import func, select

from apps.loadtest import services
from apps.notifications.models import Notification
from apps.rides.models import Ride
from apps.users.models import User
from conftest import _make_user
from kuulis.core.db import SessionLocal
from kuulis.settings import settings

API = "/api/v1"
PASSWORD = "loadtest-password-for-tests"


async def _count(model, *where) -> int:
    async with SessionLocal() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def _seed(**kw) -> dict[str, int]:
    async with SessionLocal() as session:
        return await services.seed(
            session, PASSWORD, **{"passengers": 4, "drivers": 2, "admins": 2, "rides": 30, **kw}
        )


async def test_seeded_accounts_sign_in_and_ride(client) -> None:
    assert await _seed() == {"passengers": 4, "drivers": 2, "admins": 2, "rides": 30}

    login = await client.post(
        f"{API}/auth/login",
        json={"email": services.email_for("d", 1), "password": PASSWORD},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    online = await client.post(
        f"{API}/drivers/me/online", json={"lat": 10.49, "lng": -66.88}, headers=headers
    )
    assert online.status_code == 200, online.text
    rider = await client.post(
        f"{API}/auth/login", json={"email": services.email_for("p", 1), "password": PASSWORD}
    )
    pending = await client.get(
        f"{API}/rides/pending-rating",
        headers={"Authorization": f"Bearer {rider.json()['access_token']}"},
    )
    assert pending.json() is None  # history never blocks the next request


async def test_admin_totp_secret_matches_the_runner_derivation(client, monkeypatch) -> None:
    await _seed()
    monkeypatch.setattr(settings, "ADMIN_TOTP_REQUIRED", True)
    step = await client.post(
        f"{API}/auth/admin/login",
        json={"email": services.email_for("a", 1), "password": PASSWORD},
    )
    code = pyotp.TOTP(services.admin_totp_secret(PASSWORD, 1)).now()
    done = await client.post(
        f"{API}/auth/admin/totp", json={"challenge": step.json()["challenge"], "code": code}
    )
    assert done.status_code == 200, done.text


async def test_seed_refuses_twice_and_in_production(monkeypatch) -> None:
    await _seed()
    with pytest.raises(services.LoadTestRefusedError):
        await _seed()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    async with SessionLocal() as session:
        with pytest.raises(services.LoadTestRefusedError):
            await services.clean(session)


async def test_report_and_clean() -> None:
    real = await _make_user("real@example.com")
    await _seed()
    async with SessionLocal() as session:
        session.add(Notification(user_id=real.id, title=services.CAMPAIGN_TITLE, body=""))
        session.add(Notification(user_id=real.id, title="Otra", body=""))
        await session.commit()
        report = await services.report(session, datetime.now(UTC) - timedelta(days=365))
    assert report["rides"] == 30

    async with SessionLocal() as session:
        result = await services.clean(session)
    assert result == {"users": 4 + 2 + 2, "rides": 30, "campaign_notifications": 1}
    assert await _count(User, User.email.like(f"%@{services.LOADTEST_DOMAIN}")) == 0
    assert await _count(Ride) == 0
    assert await _count(User) == 1
    assert await _count(Notification) == 1


async def test_pg_stats_snapshot() -> None:
    async with SessionLocal() as session:
        stats = await services.pg_stats(session, samples=2, every=0)
    assert "max_connections" in stats["settings"]
    assert len(stats["snapshots"]) == 2
