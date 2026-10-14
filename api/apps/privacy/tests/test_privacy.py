import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text, update

from apps.drivers.models import (
    DocumentKind,
    DocumentStatus,
    DriverDocument,
    DriverProfile,
    Vehicle,
)
from apps.moderation.models import Report, ReportCategory, ReportStatus
from apps.notifications.models import Notification
from apps.privacy import services
from apps.privacy.models import DataExport, ErasedEmail
from apps.rides.models import Ride, RideMessage
from apps.rides.tests.conftest import NEAR, go_online, make_driver, request_ride
from apps.subscriptions.models import Charge, ChargeStatus
from apps.users import services as users
from apps.users.models import User
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind, TopUp, TopUpMethod, TopUpStatus, Wallet
from conftest import ride_step
from kuulis.core import storage
from kuulis.core.db import SessionLocal
from kuulis.models import metadata

API = "/api/v1"


async def _age_deletion(*user_ids) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(User)
            .where(User.id.in_(user_ids))
            .values(deletion_requested_at=datetime.now(UTC) - timedelta(days=31))
        )
        await session.commit()


async def _completed_ride(client, passenger, driver) -> str:
    await go_online(client, driver, NEAR)
    ride_id = (await request_ride(client, passenger))["id"]
    accepted = await client.post(f"{API}/rides/{ride_id}/accept", headers=driver.headers)
    assert accepted.status_code == 200, accepted.text
    await client.post(
        f"{API}/rides/{ride_id}/messages",
        json={"text": "Estoy en la panadería"},
        headers=passenger.headers,
    )
    for step in ("arrive", "start", "complete"):
        response = await ride_step(client, ride_id, step, driver.headers)
        assert response.status_code == 200, response.text
    rated = await client.post(
        f"{API}/rides/{ride_id}/rating",
        json={"stars": 4, "comment": "Luis manejó muy bien por Chacao"},
        headers=passenger.headers,
    )
    assert rated.status_code == 200, rated.text
    return ride_id


async def test_deletion_waits_for_open_reports_and_fees(client, passenger, recorder):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    async with SessionLocal() as session:
        report = Report(
            reporter_id=passenger.user.id,
            reported_user_id=driver.user.id,
            category=ReportCategory.DRIVING,
            description="Iba muy rápido",
        )
        session.add(report)
        session.add(
            Charge(
                user_id=driver.user.id,
                month=date(2026, 9, 1),
                earnings=Decimal("150"),
                fee=Decimal("5"),
                status=ChargeStatus.PENDING,
                due_at=datetime.now(UTC),
            )
        )
        await session.commit()
    blocked = await client.delete(f"{API}/users/me", headers=driver.headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "account_open_reports"

    async with SessionLocal() as session:
        await session.execute(update(Report).values(status=ReportStatus.RESOLVED))
        await session.commit()
    owed = await client.delete(f"{API}/users/me", headers=driver.headers)
    assert owed.json()["error"]["code"] == "account_fee_pending"

    async with SessionLocal() as session:
        await session.execute(update(Charge).values(status=ChargeStatus.PAID))
        await session.commit()
    assert (await client.delete(f"{API}/users/me", headers=driver.headers)).status_code == 200


async def test_an_erased_account_leaves_no_personal_data(client, passenger, recorder, monkeypatch):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _completed_ride(client, passenger, driver)
    contact = await client.post(
        f"{API}/users/me/trusted-contacts",
        json={"name": "Mamá Carmen", "phone": "+584149876543"},
        headers=passenger.headers,
    )
    assert contact.status_code == 201, contact.text
    await client.post(
        f"{API}/users/me/places",
        json={"kind": "home", "address": "Calle Los Mangos 12", "lat": 10.5, "lng": -66.8},
        headers=passenger.headers,
    )
    await client.put(
        f"{API}/users/me/consents",
        json={"kind": "background_location", "granted": True},
        headers=driver.headers,
    )
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.user.id)
        )
        plate = await session.scalar(select(Vehicle.plate).where(Vehicle.driver_id == profile.id))
        session.add(
            DriverDocument(
                driver_id=profile.id,
                kind=DocumentKind.ID_CARD,
                key="test/drivers/cedula.jpg",
                content_type="image/jpeg",
            )
        )
        session.add(
            TopUp(
                user_id=driver.user.id,
                status=TopUpStatus.COMPLETED,
                method=TopUpMethod.BINANCE_PAY,
                amount=Decimal("10"),
                transaction_id="tx-1",
                payer_binance_id="987654321",
                payer_name="Luis Alberto Gómez",
            )
        )
        await wallet.post_entry(
            session,
            driver.user.id,
            EntryKind.TRANSFER_IN,
            Decimal("5"),
            counterpart_user_id=passenger.user.id,
            details={"counterpart_name": "Ana P.", "note": None},
        )
        await session.execute(
            update(Wallet)
            .where(Wallet.user_id == driver.user.id)
            .values(binance_pay_id="123456789")
        )
        session.add(
            DataExport(user_id=passenger.user.id, status="ready", file_key="test/exports/a.json")
        )
        national_id = profile.national_id
        await session.commit()

    deleted: list[str] = []
    monkeypatch.setattr(storage, "delete_objects", lambda keys: deleted.extend(keys) or True)
    for who in (passenger, driver):
        assert (await client.delete(f"{API}/users/me", headers=who.headers)).status_code == 200
    await _age_deletion(passenger.user.id, driver.user.id)
    async with SessionLocal() as session:
        assert await users.erase_due(session) == 2

    personal = [
        "ana@example.com",
        "luis@example.com",
        "Ana Pérez",
        "Luis Gómez",
        "Ana P.",
        "Mamá Carmen",
        "+584149876543",
        "+584121234567",
        national_id,
        plate,
        "Plaza Altamira",
        "Los Dos Caminos",
        "Calle Los Mangos",
        "panadería",
        "Chacao",
        "Luis Alberto",
        "987654321",
        "123456789",
    ]
    async with SessionLocal() as session:
        for table in metadata.sorted_tables:
            query = f"SELECT row_to_json(t)::text FROM {table.name} t"  # noqa: S608 (model tables)
            rows = await session.scalars(text(query))
            dump = "\n".join(rows)
            for needle in personal:
                assert needle.lower() not in dump.lower(), f"{needle!r} left in {table.name}"
        erased = list(await session.scalars(select(ErasedEmail.email_hash)))
    assert services.email_hash("ANA@example.com ") in erased
    assert set(deleted) >= {"test/drivers/cedula.jpg", "test/exports/a.json"}
    # The ride is still counted (amounts and dates), without its addresses.
    async with SessionLocal() as session:
        fares = await session.scalar(text("SELECT count(*) FROM rides WHERE status = 'completed'"))
    assert fares == 1


async def test_download_my_data(client, passenger, recorder, monkeypatch):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _completed_ride(client, passenger, driver)
    uploads, emails = {}, []
    monkeypatch.setattr(storage, "put_object", lambda key, body, ct: uploads.update({key: body}))
    monkeypatch.setattr(
        storage, "presigned_download", lambda key, ttl=None: f"https://s3/{key}?ttl={ttl}"
    )

    async def send(to, subject, html, text=None):
        emails.append((to, subject, html))
        return True

    monkeypatch.setattr("apps.privacy.tasks.send_email", send)

    assert (await client.get(f"{API}/users/me/export", headers=passenger.headers)).json() is None
    response = await client.post(f"{API}/users/me/export", headers=passenger.headers)
    assert response.status_code == 202, response.text
    export = response.json()
    assert export["status"] == "ready" and export["expires_at"] and export["next_at"]

    [(key, body)] = uploads.items()
    assert f"/exports/{passenger.user.id.hex}/" in key
    data = json.loads(body)
    assert data["account"]["email"] == "ana@example.com"
    assert [r["pickup"]["address"] for r in data["rides"]] == ["Plaza Altamira"]
    assert data["ratings_given"][0]["comment"].startswith("Luis manejó")
    assert "driver" not in data
    [(to, _subject, html)] = emails
    assert to == "ana@example.com" and "ttl=86400" in html

    again = await client.post(f"{API}/users/me/export", headers=passenger.headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "export_too_soon"

    # The driver gets the received rating without its author.
    driver_data = await _export_data(driver.user.id)
    assert driver_data["ratings_received"][0]["stars"] == 4
    assert "rater" not in json.dumps(driver_data["ratings_received"])
    assert driver_data["driver"]["vehicle"]["brand"] == "Yamaha"


async def _export_data(user_id) -> dict:
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        return json.loads(services.export_json(await services.export_data(session, user)))


async def test_failed_export_can_be_retried(client, user_headers):
    # Storage is not configured in tests: the export fails and the user may try again.
    response = await client.post(f"{API}/users/me/export", headers=user_headers)
    assert response.json()["status"] == "failed"
    assert response.json()["next_at"] is None
    retry = await client.post(f"{API}/users/me/export", headers=user_headers)
    assert retry.status_code == 202


async def test_retention(client, passenger, recorder, monkeypatch):
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _completed_ride(client, passenger, driver)
    deleted: list[str] = []
    monkeypatch.setattr(storage, "delete_objects", lambda keys: deleted.extend(keys) or True)
    old = datetime.now(UTC) - timedelta(days=200)
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == driver.user.id)
        )
        session.add(
            DriverDocument(
                driver_id=profile.id,
                kind=DocumentKind.ID_CARD,
                key="test/old-rejected.jpg",
                content_type="image/jpeg",
                status=DocumentStatus.REJECTED,
                reviewed_at=old,
            )
        )
        session.add(
            DriverDocument(
                driver_id=profile.id,
                kind=DocumentKind.DRIVERS_LICENSE,
                key="test/approved.jpg",
                content_type="image/jpeg",
                status=DocumentStatus.APPROVED,
                reviewed_at=old,
            )
        )
        session.add(Notification(user_id=passenger.user.id, title="Vieja", created_at=old))
        session.add(Notification(user_id=passenger.user.id, title="Nueva"))
        session.add(
            DataExport(
                user_id=passenger.user.id,
                status="ready",
                file_key="test/export.json",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.execute(update(RideMessage).values(created_at=old))
        await session.execute(
            update(Ride)
            .where(Ride.id == uuid.UUID(ride_id))
            .values(requested_at=old, polyline="abc")
        )
        await session.commit()

    async with SessionLocal() as session:
        result = await services.apply_retention(session)
    assert result == {
        "chat_messages": 1,
        "routes": 1,
        "tracks": 0,
        "rejected_documents": 1,
        "notifications": 1,
        "exports": 1,
    }
    assert sorted(deleted) == ["test/export.json", "test/old-rejected.jpg"]
    async with SessionLocal() as session:
        titles = list(await session.scalars(select(Notification.title)))
        export = await session.scalar(select(DataExport))
    assert "Vieja" not in titles and export.status == "expired" and export.file_key is None

    # A reported ride keeps its chat.
    await client.post(
        f"{API}/rides/{ride_id}/messages", json={"text": "hola"}, headers=passenger.headers
    )
    async with SessionLocal() as session:
        await session.execute(update(RideMessage).values(created_at=old))
        session.add(
            Report(
                reporter_id=passenger.user.id,
                reported_user_id=driver.user.id,
                ride_id=ride_id,
                category=ReportCategory.DRIVING,
                description="x",
            )
        )
        await session.commit()
        assert (await services.apply_retention(session))["chat_messages"] == 0


async def test_consents(client, user_headers):
    me = (await client.get(f"{API}/users/me", headers=user_headers)).json()
    # Anonymous usage data is on until the user opts out (doc 19); the rest needs a yes.
    assert me["consents"] == ["usage_data"]
    url = f"{API}/users/me/consents"
    body = {"kind": "background_location", "granted": True}
    assert (await client.put(url, json=body, headers=user_headers)).json() == [
        "background_location",
        "usage_data",
    ]
    withdrawn = await client.put(url, json=body | {"granted": False}, headers=user_headers)
    assert withdrawn.json() == ["usage_data"]
    bad = await client.put(url, json={"kind": "camera", "granted": True}, headers=user_headers)
    assert bad.status_code == 422


async def test_admin_lists(client, user_headers, staff_headers):
    me = (await client.get(f"{API}/users/me", headers=user_headers)).json()
    await client.post(f"{API}/users/me/export", headers=user_headers)
    forbidden = await client.get(f"{API}/admin/privacy/exports", headers=user_headers)
    assert forbidden.status_code == 403
    await client.delete(f"{API}/users/me", headers=user_headers)

    deletions = await client.get(f"{API}/admin/privacy/deletions", headers=staff_headers)
    assert deletions.status_code == 200, deletions.text
    [row] = deletions.json()["items"]
    assert row["email"] == me["email"] and row["erased_at"] is None
    erased = await client.get(f"{API}/admin/privacy/deletions?state=erased", headers=staff_headers)
    assert erased.json()["total"] == 0
    exports = (await client.get(f"{API}/admin/privacy/exports", headers=staff_headers)).json()
    assert exports["items"][0]["email"] == me["email"]
    assert exports["items"][0]["error"] == "storage_disabled"
    detail = await client.get(f"{API}/users/{me['id']}", headers=staff_headers)
    assert detail.json()["deletion_requested_at"] is not None
