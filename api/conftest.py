import os

os.environ["APP_ENV"] = "test"

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from apps.staff.models import StaffRole
from apps.staff.permissions import ALL_PERMISSIONS
from apps.users.models import Role
from apps.users.schemas import UserCreate
from kuulis.asgi import app
from kuulis.core.db import SessionLocal, engine
from kuulis.core.redis import redis_client
from kuulis.models import metadata
from kuulis.tasks import broker

PASSWORD = "Sup3r-secret!"


@pytest.fixture(scope="session", autouse=True)
async def _database() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    await broker.startup()
    yield
    await broker.shutdown()
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean() -> AsyncIterator[None]:
    yield
    tables = ", ".join(t.name for t in metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await redis_client.flushdb()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# What plain staff could do before roles (doc 06): everything but the admin-only writes.
LEGACY_STAFF = ALL_PERMISSIONS - {
    "promotions.manage",
    "rates.manage",
    "top_ups.manage",
    "wallet.adjust",
    "subscriptions.manage",
}


async def make_staff_role(name: str, permissions) -> StaffRole:
    async with SessionLocal() as session:
        role = StaffRole(name=name, label=name.title(), permissions=sorted(permissions))
        session.add(role)
        await session.commit()
        return role


async def _make_user(email: str, role: Role = Role.USER, staff_role: StaffRole | None = None):
    from apps.users import services

    if role == Role.STAFF and staff_role is None:
        staff_role = await make_staff_role(f"legacy_{email.split('@')[0]}", LEGACY_STAFF)
    async with SessionLocal() as session:
        user = await services.create_user(
            session, UserCreate(email=email, password=PASSWORD), role=role, is_verified=True
        )
        user.staff_role_id = staff_role.id if staff_role else None
        await session.commit()
        return user


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def user_headers(client: AsyncClient) -> dict[str, str]:
    await _make_user("user@example.com")
    return await _login(client, "user@example.com")


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    await _make_user("admin@example.com", Role.ADMIN)
    return await _login(client, "admin@example.com")


@pytest.fixture
async def staff_headers(client: AsyncClient) -> dict[str, str]:
    await _make_user("staff@example.com", Role.STAFF)
    return await _login(client, "staff@example.com")
