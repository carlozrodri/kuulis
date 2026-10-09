from datetime import date

import pytest
from sqlalchemy import select

from apps.drivers import services
from apps.notifications.models import Notification
from kuulis.core import storage
from kuulis.core.db import SessionLocal

PROFILE = {
    "birth_date": "1995-04-12",
    "national_id": "v-12.345.678",
    "rif": "V123456789",
    "phone": "+58 412 123 4567",
}
VEHICLE = {
    "type": "moto",
    "brand": "Yamaha",
    "model": "YBR 125",
    "year": 2019,
    "plate": "ab2-c34 d",
    "color": "Negra",
}
REQUIRED = [
    "id_card",
    "rif",
    "drivers_license",
    "medical_certificate",
    "vehicle_registration",
    "selfie",
]


@pytest.fixture(autouse=True)
def fake_storage(monkeypatch):
    """Presign returns fake URLs and every key "exists" in S3 as a JPEG."""
    monkeypatch.setattr(storage, "presigned_upload", lambda key, ct: f"https://s3.test/{key}")
    monkeypatch.setattr(storage, "presigned_download", lambda key: f"https://s3.test/get/{key}")
    monkeypatch.setattr(
        storage, "head_object", lambda key: {"ContentType": "image/jpeg", "ContentLength": 1000}
    )


async def _upload(client, headers, kind: str) -> dict:
    presign = await client.post(
        "/api/v1/drivers/me/documents/presign",
        json={"kind": kind, "filename": f"{kind}.jpg", "content_type": "image/jpeg", "size": 1000},
        headers=headers,
    )
    assert presign.status_code == 200, presign.text
    response = await client.post(
        "/api/v1/drivers/me/documents",
        json={"kind": kind, "key": presign.json()["key"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _complete_driver(client, headers) -> dict:
    await client.put("/api/v1/drivers/me", json=PROFILE, headers=headers)
    await client.put("/api/v1/drivers/me/vehicle", json=VEHICLE, headers=headers)
    for kind in [*REQUIRED, "vehicle_photo", "vehicle_photo"]:
        body = await _upload(client, headers, kind)
    return body


async def _submitted_driver_id(client, headers) -> str:
    await _complete_driver(client, headers)
    response = await client.post("/api/v1/drivers/me/submit", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_age_on():
    assert services.age_on(date(2000, 5, 10), date(2021, 5, 9)) == 20
    assert services.age_on(date(2000, 5, 10), date(2021, 5, 10)) == 21


async def test_profile_create_and_normalize(client, user_headers):
    assert (await client.get("/api/v1/drivers/me", headers=user_headers)).status_code == 404
    response = await client.put("/api/v1/drivers/me", json=PROFILE, headers=user_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["national_id"] == "V12345678"
    assert body["phone"] == "+584121234567"
    assert body["city"] == "caracas"
    assert body["vehicle"] is None
    assert body["requirements"]["age_ok"] is True
    assert body["requirements"]["can_submit"] is False


async def test_national_id_unique(client, user_headers, staff_headers):
    await client.put("/api/v1/drivers/me", json=PROFILE, headers=user_headers)
    response = await client.put("/api/v1/drivers/me", json=PROFILE, headers=staff_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "national_id_taken"


async def test_underage_driver_cannot_submit(client, user_headers):
    young = PROFILE | {"birth_date": date.today().replace(year=date.today().year - 18).isoformat()}
    response = await client.put("/api/v1/drivers/me", json=young, headers=user_headers)
    assert response.json()["requirements"]["age_ok"] is False


async def test_vehicle_validation(client, user_headers, staff_headers):
    await client.put("/api/v1/drivers/me", json=PROFILE, headers=user_headers)
    old = await client.put(
        "/api/v1/drivers/me/vehicle", json=VEHICLE | {"year": 2010}, headers=user_headers
    )
    assert old.json()["error"]["code"] == "vehicle_too_old"
    car = await client.put(
        "/api/v1/drivers/me/vehicle", json=VEHICLE | {"type": "car"}, headers=user_headers
    )
    assert car.json()["error"]["code"] == "vehicle_type_not_enabled"
    ok = await client.put("/api/v1/drivers/me/vehicle", json=VEHICLE, headers=user_headers)
    assert ok.status_code == 200
    assert ok.json()["vehicle"]["plate"] == "AB2C34D"
    assert ok.json()["requirements"]["vehicle_ok"] is True

    other = PROFILE | {"national_id": "V87654321"}
    await client.put("/api/v1/drivers/me", json=other, headers=staff_headers)
    taken = await client.put(
        "/api/v1/drivers/me/vehicle", json=VEHICLE | {"plate": "AB2C34D"}, headers=staff_headers
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "plate_taken"


async def test_document_register_and_replace(client, user_headers):
    await client.put("/api/v1/drivers/me", json=PROFILE, headers=user_headers)
    presign = await client.post(
        "/api/v1/drivers/me/documents/presign",
        json={
            "kind": "selfie",
            "filename": "x.exe",
            "content_type": "application/x-exe",
            "size": 9,
        },
        headers=user_headers,
    )
    assert presign.json()["error"]["code"] == "file_type_not_allowed"

    first = await _upload(client, user_headers, "selfie")
    second = await _upload(client, user_headers, "selfie")
    selfies = [d for d in second["documents"] if d["kind"] == "selfie"]
    assert len(selfies) == 1 and selfies[0]["id"] != first["documents"][0]["id"]

    await _upload(client, user_headers, "vehicle_photo")
    body = await _upload(client, user_headers, "vehicle_photo")
    assert body["requirements"]["vehicle_photos"] == 2

    doc_id = body["documents"][-1]["id"]
    deleted = await client.delete(f"/api/v1/drivers/me/documents/{doc_id}", headers=user_headers)
    assert deleted.json()["requirements"]["vehicle_photos"] == 1


async def test_document_key_must_belong_to_user(client, user_headers):
    await client.put("/api/v1/drivers/me", json=PROFILE, headers=user_headers)
    for key in (
        "test/drivers/00000000-0000-0000-0000-000000000000/selfie/abc-x.jpg",
        "test/avatars/abc-x.jpg",
    ):
        response = await client.post(
            "/api/v1/drivers/me/documents",
            json={"kind": "selfie", "key": key},
            headers=user_headers,
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "document_key_invalid"
    # A key presigned for one kind cannot be registered as another.
    presign = await client.post(
        "/api/v1/drivers/me/documents/presign",
        json={"kind": "selfie", "filename": "s.jpg", "content_type": "image/jpeg", "size": 10},
        headers=user_headers,
    )
    response = await client.post(
        "/api/v1/drivers/me/documents",
        json={"kind": "id_card", "key": presign.json()["key"]},
        headers=user_headers,
    )
    assert response.json()["error"]["code"] == "document_key_invalid"


async def test_submit_missing_requirements(client, user_headers):
    await client.put("/api/v1/drivers/me", json=PROFILE, headers=user_headers)
    await _upload(client, user_headers, "vehicle_photo")
    response = await client.post("/api/v1/drivers/me/submit", headers=user_headers)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "driver_requirements_missing"
    assert error["details"]["missing_documents"] == REQUIRED
    assert error["details"]["vehicle_photos"] == 1
    assert error["details"]["vehicle_photos_required"] == 2
    assert error["details"]["vehicle_ok"] is False


async def test_submit_and_admin_approve(client, user_headers, staff_headers):
    driver_id = await _submitted_driver_id(client, user_headers)
    me = (await client.get("/api/v1/drivers/me", headers=user_headers)).json()
    assert me["status"] == "pending_review" and me["submitted_at"]
    # Not editable while under review.
    edit = await client.put("/api/v1/drivers/me", json=PROFILE, headers=user_headers)
    assert edit.json()["error"]["code"] == "driver_not_editable"

    listing = await client.get(
        "/api/v1/admin/drivers?status=pending_review&q=ab2c", headers=staff_headers
    )
    assert listing.status_code == 200
    page = listing.json()
    assert page["total"] == 1 and page["limit"] == 20 and page["offset"] == 0
    assert page["items"][0]["user"]["email"] == "user@example.com"
    assert page["items"][0]["vehicle"]["plate"] == "AB2C34D"

    detail = (await client.get(f"/api/v1/admin/drivers/{driver_id}", headers=staff_headers)).json()
    assert all(d["download_url"].startswith("https://s3.test/get/") for d in detail["documents"])

    approved = await client.post(
        f"/api/v1/admin/drivers/{driver_id}/approve", headers=staff_headers
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved" and body["approved_at"]
    assert {d["status"] for d in body["documents"]} == {"approved"}

    again = await client.post(f"/api/v1/admin/drivers/{driver_id}/approve", headers=staff_headers)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "driver_invalid_transition"

    async with SessionLocal() as session:
        titles = list(
            await session.scalars(select(Notification.title).order_by(Notification.created_at))
        )
    assert titles == ["Recibimos tu solicitud", "¡Fuiste aprobado!"]


async def test_reject_resubmit_and_document_review(client, user_headers, staff_headers):
    await client.patch("/api/v1/users/me", json={"locale": "en"}, headers=user_headers)
    driver_id = await _submitted_driver_id(client, user_headers)
    detail = (await client.get(f"/api/v1/admin/drivers/{driver_id}", headers=staff_headers)).json()
    selfie = next(d for d in detail["documents"] if d["kind"] == "selfie")

    no_reason = await client.post(
        f"/api/v1/admin/drivers/{driver_id}/documents/{selfie['id']}/review",
        json={"status": "rejected", "reason": None},
        headers=staff_headers,
    )
    assert no_reason.status_code == 422
    reviewed = await client.post(
        f"/api/v1/admin/drivers/{driver_id}/documents/{selfie['id']}/review",
        json={"status": "rejected", "reason": "Blurry"},
        headers=staff_headers,
    )
    assert reviewed.status_code == 200

    blocked = await client.post(f"/api/v1/admin/drivers/{driver_id}/approve", headers=staff_headers)
    assert blocked.json()["error"]["code"] == "driver_documents_rejected"

    missing_reason = await client.post(
        f"/api/v1/admin/drivers/{driver_id}/reject", json={}, headers=staff_headers
    )
    assert missing_reason.status_code == 422
    rejected = await client.post(
        f"/api/v1/admin/drivers/{driver_id}/reject",
        json={"reason": "Selfie unreadable"},
        headers=staff_headers,
    )
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Selfie unreadable"

    me = (await client.get("/api/v1/drivers/me", headers=user_headers)).json()
    assert me["requirements"]["missing_documents"] == ["selfie"]
    await _upload(client, user_headers, "selfie")
    resubmit = await client.post("/api/v1/drivers/me/submit", headers=user_headers)
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "pending_review"
    assert resubmit.json()["rejection_reason"] is None

    async with SessionLocal() as session:
        titles = set(await session.scalars(select(Notification.title)))
    assert {"Document rejected", "Your application needs changes"} <= titles


async def test_suspend_and_reinstate(client, user_headers, staff_headers):
    driver_id = await _submitted_driver_id(client, user_headers)
    url = f"/api/v1/admin/drivers/{driver_id}"
    cannot = await client.post(f"{url}/suspend", json={"reason": "x"}, headers=staff_headers)
    assert cannot.status_code == 409
    await client.post(f"{url}/approve", headers=staff_headers)
    suspended = await client.post(
        f"{url}/suspend", json={"reason": "Complaints"}, headers=staff_headers
    )
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["rejection_reason"] == "Complaints"
    reinstated = await client.post(f"{url}/reinstate", headers=staff_headers)
    assert reinstated.json()["status"] == "approved"
    assert reinstated.json()["rejection_reason"] is None


async def test_regular_user_cannot_use_admin_endpoints(client, user_headers):
    assert (await client.get("/api/v1/admin/drivers", headers=user_headers)).status_code == 403
