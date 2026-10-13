"""Ongoing driver verification (doc 12)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, update

from apps.drivers import tasks, verification
from apps.drivers.models import (
    CheckKind,
    CheckStatus,
    DocumentKind,
    DocumentStatus,
    DriverCheck,
    DriverDocument,
    DriverProfile,
    DriverStatus,
    MarkKind,
    Vehicle,
    VehicleStatus,
)
from apps.moderation.models import Report, ReportCategory
from apps.notifications.models import Notification
from apps.rides.tests.conftest import Actor, make_driver
from conftest import set_config
from kuulis.core import storage
from kuulis.core.db import SessionLocal
from kuulis.core.redis import redis_client

API = "/api/v1"
POINT = {"lat": 10.4910, "lng": -66.8800}


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    monkeypatch.setattr(storage, "presigned_upload", lambda key, ct: f"https://s3.test/{key}")
    monkeypatch.setattr(
        storage, "presigned_download", lambda key, expires_in=None: f"https://s3.test/get/{key}"
    )
    monkeypatch.setattr(
        storage, "head_object", lambda key: {"ContentType": "image/jpeg", "ContentLength": 1000}
    )


def _today() -> date:
    return datetime.now(UTC).date()


async def _driver(client, email="luis@example.com", **documents) -> Actor:
    """An approved driver whose license expires on ``documents['license']`` (default in a year)."""
    actor = await make_driver(client, email, "Luis Gómez")
    async with SessionLocal() as session:
        profile = await session.scalar(
            select(DriverProfile).where(DriverProfile.user_id == actor.user.id)
        )
        profile.selfie_due_at = datetime.now(UTC) + timedelta(days=7)
        expiry = {
            DocumentKind.DRIVERS_LICENSE: documents.get("license", _today() + timedelta(days=365)),
            DocumentKind.MEDICAL_CERTIFICATE: _today() + timedelta(days=365),
            DocumentKind.VEHICLE_REGISTRATION: _today() + timedelta(days=365),
        }
        for kind in (
            DocumentKind.ID_CARD,
            DocumentKind.SELFIE,
            DocumentKind.VEHICLE_PHOTO,
            *expiry,
        ):
            session.add(
                DriverDocument(
                    driver_id=profile.id,
                    kind=kind,
                    key=f"drivers/{actor.id}/{kind.value}/old.jpg",
                    content_type="image/jpeg",
                    status=DocumentStatus.APPROVED,
                    expires_on=expiry.get(kind),
                    expiry_confirmed=kind in expiry,
                )
            )
        await session.commit()
    actor.profile_id = str(profile.id)
    return actor


async def _online(client, driver: Actor, device: str | None = None):
    headers = driver.headers | ({"X-Device-Id": device} if device else {})
    return await client.post(f"{API}/drivers/me/online", json=POINT, headers=headers)


async def _presign(client, headers, kind: str, *, checks: bool = False) -> str:
    path = "checks/presign" if checks else "documents/presign"
    response = await client.post(
        f"{API}/drivers/me/{path}",
        json={"kind": kind, "filename": f"{kind}.jpg", "content_type": "image/jpeg", "size": 900},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["key"]


async def _queue(client, headers, **query) -> list[dict]:
    response = await client.get(f"{API}/admin/drivers/checks", params=query, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def _review(client, headers, check_id: str, **body):
    return await client.post(
        f"{API}/admin/drivers/checks/{check_id}/review", json=body, headers=headers
    )


async def test_expired_license_blocks_until_the_renewal_is_approved(client, staff_headers):
    driver = await _driver(client, license=_today() - timedelta(days=1))
    me = (await client.get(f"{API}/drivers/me", headers=driver.headers)).json()
    assert me["verification"]["expired"] == ["drivers_license"]
    assert me["verification"]["can_go_online"] is False

    response = await _online(client, driver)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "document_expired"
    assert response.json()["error"]["details"]["kinds"] == ["drivers_license"]

    # Renewal: the date is required, and the old file stays in use until approved.
    key = await _presign(client, driver.headers, "drivers_license")
    body = {"kind": "drivers_license", "key": key}
    missing = await client.post(f"{API}/drivers/me/documents", json=body, headers=driver.headers)
    assert missing.json()["error"]["code"] == "expiry_required"
    new_expiry = (_today() + timedelta(days=700)).isoformat()
    response = await client.post(
        f"{API}/drivers/me/documents",
        json=body | {"expires_on": new_expiry},
        headers=driver.headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["verification"]["expiring"][0]["renewal_pending"] is True
    assert (await _online(client, driver)).status_code == 403

    (check,) = await _queue(client, staff_headers)
    assert check["kind"] == "document_renewal"
    assert check["driver"]["full_name"] == "Luis Gómez"
    detail = (
        await client.get(f"{API}/admin/drivers/checks/{check['id']}", headers=staff_headers)
    ).json()
    assert detail["document"]["expires_on"] == new_expiry
    assert {r["kind"] for r in detail["references"]} == {"selfie", "id_card", "drivers_license"}

    approved = await _review(client, staff_headers, check["id"], status="approved")
    assert approved.status_code == 200, approved.text
    assert (await _online(client, driver)).status_code == 200

    me = (await client.get(f"{API}/drivers/me", headers=driver.headers)).json()
    licenses = [d for d in me["documents"] if d["kind"] == "drivers_license"]
    assert len(licenses) == 1  # the old one is history now
    assert licenses[0]["expires_on"] == new_expiry and licenses[0]["expiry_confirmed"]
    admin = (
        await client.get(f"{API}/admin/drivers/{driver.profile_id}", headers=staff_headers)
    ).json()
    assert sum(1 for d in admin["documents"] if d["kind"] == "drivers_license") == 2
    async with SessionLocal() as session:
        events = list(await session.scalars(select(Notification.data)))
    assert any(e.get("event") == "document_renewed" for e in events)


async def test_rejected_renewal_keeps_the_old_document(client, staff_headers):
    driver = await _driver(client)
    key = await _presign(client, driver.headers, "drivers_license")
    await client.post(
        f"{API}/drivers/me/documents",
        json={"kind": "drivers_license", "key": key, "expires_on": "2031-01-01"},
        headers=driver.headers,
    )
    (check,) = await _queue(client, staff_headers)
    assert (await _review(client, staff_headers, check["id"], status="rejected")).status_code == 422
    response = await _review(
        client, staff_headers, check["id"], status="rejected", reason="Borrosa"
    )
    assert response.status_code == 200
    me = (await client.get(f"{API}/drivers/me", headers=driver.headers)).json()
    statuses = sorted(d["status"] for d in me["documents"] if d["kind"] == "drivers_license")
    assert statuses == ["approved", "rejected"]
    assert (await _online(client, driver)).status_code == 200


async def test_expiry_notices_go_once_per_step(client):
    driver = await _driver(client, license=_today() + timedelta(days=6))
    async with SessionLocal() as session:
        from apps.config.services import get_app_config

        config = await get_app_config(session)
        notices = await verification.expiry_notices(session, config, _today())
        assert [(n.document.kind, n.days_left) for n in notices] == [
            (DocumentKind.DRIVERS_LICENSE, 6)
        ]
        assert notices[0].document.expiry_notice_days == 7
        await session.commit()
        # Same step the next day: nothing new; the 1-day step and the expiry each notify once.
        later = _today() + timedelta(days=1)
        assert await verification.expiry_notices(session, config, later) == []
        assert (
            len(await verification.expiry_notices(session, config, _today() + timedelta(days=5)))
            == 1
        )
        assert (
            len(await verification.expiry_notices(session, config, _today() + timedelta(days=7)))
            == 1
        )
        assert (
            await verification.expiry_notices(session, config, _today() + timedelta(days=8)) == []
        )

    # The daily job sends them as notifications, once a day.
    async with SessionLocal() as session:
        await session.execute(update(DriverDocument).values(expiry_notice_days=None))
        await session.commit()
    assert await tasks.run_expirations_once(force=True) == 1
    assert await tasks.run_expirations_once(force=True) is None
    async with SessionLocal() as session:
        titles = list(
            await session.scalars(
                select(Notification.body).where(Notification.user_id == driver.user.id)
            )
        )
    assert any("Licencia de conducir vence el" in t for t in titles)
    await redis_client.flushdb()


async def test_random_selfie_rejected_suspends_and_opens_a_report(client, staff_headers):
    driver = await _driver(client)
    async with SessionLocal() as session:
        await session.execute(
            update(DriverProfile).values(selfie_due_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    response = await _online(client, driver)
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "selfie_required" and error["details"]["kind"] == "selfie"
    check_id = error["details"]["check_id"]
    assert (await _online(client, driver)).json()["error"]["details"]["check_id"] == check_id

    # Requested checks are not in the verifier's queue yet.
    assert await _queue(client, staff_headers) == []
    key = await _presign(client, driver.headers, "selfie", checks=True)
    wrong = await client.post(
        f"{API}/drivers/me/checks/{check_id}/submit",
        json={"files": [{"kind": "vehicle_photo", "key": key}]},
        headers=driver.headers,
    )
    assert wrong.json()["error"]["code"] == "check_files_invalid"
    sent = await client.post(
        f"{API}/drivers/me/checks/{check_id}/submit",
        json={"files": [{"kind": "selfie", "key": key}]},
        headers=driver.headers,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "pending"
    # Works while the selfie waits for review.
    assert (await _online(client, driver)).status_code == 200

    (check,) = await _queue(client, staff_headers)
    taken = await client.post(
        f"{API}/admin/drivers/checks/{check_id}/assign",
        json={"user_id": check["driver"]["user_id"]},
        headers=staff_headers,
    )
    assert taken.json()["error"]["code"] == "not_staff"
    rejected = await _review(
        client, staff_headers, check_id, status="rejected", reason="No es la misma persona"
    )
    assert rejected.status_code == 200, rejected.text
    async with SessionLocal() as session:
        profile = await session.get(DriverProfile, driver.profile_id)
        report = await session.scalar(select(Report))
    assert profile.status == DriverStatus.SUSPENDED
    assert report.reported_user_id == driver.user.id and report.category == ReportCategory.SAFETY
    assert (await _online(client, driver)).status_code == 403


async def test_mismatch_reports_ask_for_a_reverification(client, staff_headers):
    driver = await _driver(client)
    async with SessionLocal() as session:
        for _ in range(2):
            session.add(
                Report(
                    reporter_id=driver.user.id,
                    reported_user_id=driver.user.id,
                    category=ReportCategory.VEHICLE_MISMATCH,
                    description="Otra moto",
                )
            )
        await session.commit()
        assert await verification.on_mismatch_report(session, driver.user.id) is True
        await session.commit()
        assert await verification.on_mismatch_report(session, driver.user.id) is False

    response = await _online(client, driver)
    assert response.json()["error"]["details"]["kind"] == "reverification"
    check_id = response.json()["error"]["details"]["check_id"]
    selfie = await _presign(client, driver.headers, "selfie", checks=True)
    photo = await _presign(client, driver.headers, "vehicle_photo", checks=True)
    short = await client.post(
        f"{API}/drivers/me/checks/{check_id}/submit",
        json={
            "files": [{"kind": "selfie", "key": selfie}, {"kind": "vehicle_photo", "key": photo}]
        },
        headers=driver.headers,
    )
    assert short.json()["error"]["code"] == "check_files_missing"
    photo2 = await _presign(client, driver.headers, "vehicle_photo", checks=True)
    files = [
        {"kind": "selfie", "key": selfie},
        {"kind": "vehicle_photo", "key": photo},
        {"kind": "vehicle_photo", "key": photo2},
    ]
    sent = await client.post(
        f"{API}/drivers/me/checks/{check_id}/submit", json={"files": files}, headers=driver.headers
    )
    assert sent.status_code == 200, sent.text
    assert (await _review(client, staff_headers, check_id, status="approved")).status_code == 200
    me = (await client.get(f"{API}/drivers/me", headers=driver.headers)).json()
    photos = [d for d in me["documents"] if d["kind"] == "vehicle_photo"]
    assert len(photos) == 2  # the new ones replace the old photo


async def test_vehicle_change(client, staff_headers):
    driver = await _driver(client)
    other = await make_driver(client, "otro@example.com", "Otro")
    registration = await _presign(client, driver.headers, "vehicle_registration", checks=True)
    photos = [await _presign(client, driver.headers, "vehicle_photo", checks=True) for _ in "ab"]
    body = {
        "vehicle": {
            "type": "moto",
            "brand": "Bera",
            "model": "SBR",
            "year": 2022,
            "plate": "AC1 23BD",
            "color": "Roja",
        },
        "registration_key": registration,
        "registration_expires_on": (_today() + timedelta(days=900)).isoformat(),
        "photo_keys": photos,
    }
    async with SessionLocal() as session:
        other_plate = await session.scalar(
            select(Vehicle.plate).join(DriverProfile).where(DriverProfile.user_id == other.user.id)
        )
    taken = await client.post(
        f"{API}/drivers/me/vehicles",
        json=body | {"vehicle": body["vehicle"] | {"plate": other_plate}},
        headers=driver.headers,
    )
    assert taken.json()["error"]["code"] == "plate_taken"
    response = await client.post(f"{API}/drivers/me/vehicles", json=body, headers=driver.headers)
    assert response.status_code == 201, response.text
    me = response.json()
    assert me["pending_vehicle"]["plate"] == "AC123BD"
    assert me["vehicle"]["plate"] != "AC123BD"
    again = await client.post(f"{API}/drivers/me/vehicles", json=body, headers=driver.headers)
    assert again.json()["error"]["code"] == "vehicle_change_pending"
    assert (await _online(client, driver)).status_code == 200  # keeps working meanwhile

    (check,) = await _queue(client, staff_headers, kind="vehicle_change")
    detail = (
        await client.get(f"{API}/admin/drivers/checks/{check['id']}", headers=staff_headers)
    ).json()
    assert (
        detail["vehicle"]["plate"] == "AC123BD"
        and detail["expires_on"] == body["registration_expires_on"]
    )
    assert (await _review(client, staff_headers, check["id"], status="approved")).status_code == 200
    me = (await client.get(f"{API}/drivers/me", headers=driver.headers)).json()
    assert me["vehicle"]["plate"] == "AC123BD" and me["pending_vehicle"] is None
    registrations = [d for d in me["documents"] if d["kind"] == "vehicle_registration"]
    assert [d["expires_on"] for d in registrations] == [body["registration_expires_on"]]
    async with SessionLocal() as session:
        statuses = sorted(
            v.status
            for v in await session.scalars(
                select(Vehicle).where(Vehicle.driver_id == driver.profile_id)
            )
        )
    assert statuses == [VehicleStatus.ACTIVE, VehicleStatus.RETIRED]


async def test_vehicle_change_can_be_cancelled(client):
    driver = await _driver(client)
    registration = await _presign(client, driver.headers, "vehicle_registration", checks=True)
    photos = [await _presign(client, driver.headers, "vehicle_photo", checks=True) for _ in "ab"]
    body = {
        "vehicle": {
            "type": "moto",
            "brand": "Bera",
            "model": "SBR",
            "year": 2022,
            "plate": "AC123BD",
            "color": "Roja",
        },
        "registration_key": registration,
        "registration_expires_on": "2030-01-01",
        "photo_keys": photos,
    }
    await client.post(f"{API}/drivers/me/vehicles", json=body, headers=driver.headers)
    response = await client.delete(f"{API}/drivers/me/vehicles/pending", headers=driver.headers)
    assert response.status_code == 200 and response.json()["pending_vehicle"] is None
    async with SessionLocal() as session:
        check = await session.scalar(select(DriverCheck))
    assert check.status == CheckStatus.CANCELLED and check.kind == CheckKind.VEHICLE_CHANGE


async def test_duplicates_show_on_both_accounts(client, staff_headers):
    first = await _driver(client, "a@example.com")
    second = await _driver(client, "b@example.com")
    # Same phone (make_driver uses one for everybody) and, after going online, same device.
    async with SessionLocal() as session:
        for actor in (first, second):
            profile = await session.get(DriverProfile, actor.profile_id)
            await verification.record_profile_marks(session, profile)
        await session.commit()
    assert (await _online(client, first, device="android-123")).status_code == 200
    assert (await _online(client, second, device="android-123")).status_code == 200
    for actor, other in ((first, second), (second, first)):
        page = (
            await client.get(f"{API}/admin/drivers/{actor.profile_id}", headers=staff_headers)
        ).json()
        kinds = {(d["kind"], d["user_id"]) for d in page["duplicates"]}
        assert kinds == {("phone", other.id), ("device", other.id)}

    # An erased account still counts (only the hash is kept).
    async with SessionLocal() as session:
        await verification.record_marks(session, first.user.id, {MarkKind.NATIONAL_ID: "V999"})
        await verification.record_marks(session, second.user.id, {MarkKind.NATIONAL_ID: "v 999"})
        await session.execute(
            update(type(first.user))
            .where(type(first.user).id == first.user.id)
            .values(deleted_at=datetime.now(UTC))
        )
        await session.commit()
    page = (
        await client.get(f"{API}/admin/drivers/{second.profile_id}", headers=staff_headers)
    ).json()
    erased = [d for d in page["duplicates"] if d["kind"] == "national_id"]
    assert erased == [
        {
            "kind": "national_id",
            "user_id": first.id,
            "name": "Luis Gómez",
            "email": None,
            "driver_id": first.profile_id,
            "driver_status": "approved",
            "deleted": True,
            "suspended": False,
        }
    ]


async def test_missing_expiry_is_typed_by_the_driver(client, staff_headers):
    driver = await _driver(client)
    async with SessionLocal() as session:
        await session.execute(
            update(DriverDocument)
            .where(DriverDocument.kind == DocumentKind.MEDICAL_CERTIFICATE)
            .values(expires_on=None, expiry_confirmed=False)
        )
        await session.commit()
    me = (await client.get(f"{API}/drivers/me", headers=driver.headers)).json()
    assert me["verification"]["missing_expiry"] == ["medical_certificate"]
    assert me["verification"]["can_go_online"] is True
    medical = next(d for d in me["documents"] if d["kind"] == "medical_certificate")
    response = await client.patch(
        f"{API}/drivers/me/documents/{medical['id']}",
        json={"expires_on": "2030-05-01"},
        headers=driver.headers,
    )
    assert response.status_code == 200
    assert response.json()["verification"]["missing_expiry"] == []
    license_ = next(d for d in me["documents"] if d["kind"] == "drivers_license")
    confirmed = await client.patch(
        f"{API}/drivers/me/documents/{license_['id']}",
        json={"expires_on": "2030-05-01"},
        headers=driver.headers,
    )
    assert confirmed.json()["error"]["code"] == "expiry_confirmed"

    # The verifier confirms it in the document review.
    review = await client.post(
        f"{API}/admin/drivers/{driver.profile_id}/documents/{medical['id']}/review",
        json={"status": "approved", "expires_on": "2030-06-01"},
        headers=staff_headers,
    )
    document = next(d for d in review.json()["documents"] if d["id"] == medical["id"])
    assert document["expires_on"] == "2030-06-01" and document["expiry_confirmed"] is True


async def test_induction_and_reverify_from_the_admin(client, staff_headers):
    await set_config(verification={"induction_required": True})
    pending = await make_driver(
        client, "nuevo@example.com", "Nuevo", status=DriverStatus.PENDING_REVIEW
    )
    async with SessionLocal() as session:
        profile_id = await session.scalar(
            select(DriverProfile.id).where(DriverProfile.user_id == pending.user.id)
        )
    url = f"{API}/admin/drivers/{profile_id}"
    refused = await client.post(f"{url}/approve", headers=staff_headers)
    assert refused.json()["error"]["code"] == "induction_required"
    marked = await client.post(f"{url}/induction", json={"done": True}, headers=staff_headers)
    assert marked.json()["induction_completed_at"] is not None
    approved = await client.post(f"{url}/approve", headers=staff_headers)
    assert approved.status_code == 200, approved.text

    asked = await client.post(f"{url}/reverify", headers=staff_headers)
    assert asked.status_code == 200
    assert asked.json()["checks"][0]["kind"] == "reverification"
    assert (await _online(client, pending)).json()["error"]["code"] == "selfie_required"


async def test_overview_counts(client, admin_headers):
    driver = await _driver(client, license=_today() + timedelta(days=3))
    key = await _presign(client, driver.headers, "medical_certificate")
    await client.post(
        f"{API}/drivers/me/documents",
        json={"kind": "medical_certificate", "key": key, "expires_on": "2031-01-01"},
        headers=driver.headers,
    )
    overview = (await client.get(f"{API}/admin/overview", headers=admin_headers)).json()
    assert overview["pending_reverifications"] == 1
    assert overview["documents_expiring_week"] == 1
