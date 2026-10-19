from datetime import UTC, date, datetime, timedelta

import pytest

from apps.marketing import storage
from apps.marketing.services import next_code
from apps.users.models import Role
from conftest import _login, _make_user, make_staff_role
from kuulis.core.calendar import CARACAS_TZ
from kuulis.core.db import SessionLocal
from kuulis.settings import settings

API = "/api/v1/admin/marketing"


@pytest.fixture
def bucket(monkeypatch) -> set[str]:
    """A fake marketing bucket: keys land in the set once "uploaded"."""
    uploaded: set[str] = set()
    monkeypatch.setattr(storage, "presigned_upload", lambda key, ct: f"https://s3.test/put/{key}")
    monkeypatch.setattr(
        storage,
        "head_object",
        lambda key: {"ContentLength": 1234} if key in uploaded else None,
    )
    monkeypatch.setattr(
        storage,
        "download_url_or_none",
        lambda key, filename=None: f"https://s3.test/get/{key}?name={filename}" if key else None,
    )
    return uploaded


async def _role_headers(client, email: str, role: str, permissions) -> dict[str, str]:
    staff_role = await make_staff_role(role, permissions)
    await _make_user(email, Role.STAFF, staff_role)
    return await _login(client, email)


async def _upload(client, headers, bucket, content_id, name="video.mp4", ct="video/mp4") -> dict:
    response = await client.post(
        f"{API}/contents/{content_id}/assets",
        json={"filename": name, "content_type": ct, "size": 1000, "source": "remotion"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["upload_url"].startswith("https://s3.test/put/marketing/test/")
    asset = body["asset"]
    bucket.add(asset["s3_key"])
    confirmed = await client.post(
        f"{API}/contents/{content_id}/assets/{asset['id']}/confirm", headers=headers
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def _today_at(hour: int) -> str:
    now = datetime.now(UTC).astimezone(CARACAS_TZ)
    return now.replace(hour=hour, minute=30, second=0, microsecond=0).isoformat()


async def test_piece_goes_through_the_whole_cycle(client, admin_headers, bucket) -> None:
    team = await _role_headers(
        client, "mk@example.com", "mk", ["marketing.view", "marketing.manage"]
    )
    poster = await _role_headers(client, "pub@example.com", "pub", ["marketing.publish"])

    created = await client.post(
        f"{API}/contents",
        json={
            "title": "Cuota justa",
            "pillar": "dinero",
            "format": "subtitulos",
            "status": "guion",
        },
        headers=team,
    )
    assert created.status_code == 201, created.text
    content = created.json()
    assert content["code"].startswith("K-")
    assert content["allowed_statuses"] == ["descartado", "idea", "revisado"]
    cid = content["id"]

    for status in ("revisado", "producido"):
        moved = await client.post(
            f"{API}/contents/{cid}/status", json={"status": status}, headers=team
        )
        assert moved.status_code == 200, moved.text
    # Approval is not a plain status change.
    refused = await client.post(
        f"{API}/contents/{cid}/status", json={"status": "aprobado"}, headers=team
    )
    assert refused.json()["error"]["code"] == "marketing_invalid_transition"

    video = await _upload(client, team, bucket, cid)
    assert video["size"] == 1234 and video["kind"] == "video" and video["uploaded_at"]
    cover = await _upload(client, team, bucket, cid, "portada.jpg", "image/jpeg")

    variant = await client.post(
        f"{API}/contents/{cid}/variants",
        json={
            "platform": "tiktok",
            "account": "@kuulis",
            "caption": "Lo que cobras es tuyo",
            "hashtags": ["#Caracas", "motorizados", "caracas"],
            "asset_id": video["id"],
            "cover_asset_id": cover["id"],
        },
        headers=team,
    )
    assert variant.status_code == 201, variant.text
    [tiktok] = variant.json()["variants"]
    assert tiktok["hashtags"] == ["Caracas", "motorizados"]
    assert "utm_source=tiktok" in tiktok["utm_url"] and content["code"] in tiktok["utm_url"]

    # The team can't approve, and the admin can't approve without a posting time.
    assert (await client.post(f"{API}/contents/{cid}/approve", headers=team)).status_code == 403
    not_ready = await client.post(f"{API}/contents/{cid}/approve", headers=admin_headers)
    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["details"]["missing"] == [
        {"platform": "tiktok", "field": "scheduled_at"}
    ]

    await client.patch(
        f"{API}/contents/{cid}/variants/{tiktok['id']}",
        json={"scheduled_at": _today_at(19)},
        headers=team,
    )
    approved = await client.post(f"{API}/contents/{cid}/approve", headers=admin_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "aprobado" and approved.json()["approved_at"]

    # Editing an approved piece sends it back to the approval queue.
    edited = await client.patch(
        f"{API}/contents/{cid}/variants/{tiktok['id']}",
        json={"caption": "Otro texto"},
        headers=team,
    )
    assert edited.json()["status"] == "producido" and edited.json()["approved_at"] is None
    assert (await client.get(f"{API}/queue", headers=poster)).json() == []
    await client.post(f"{API}/contents/{cid}/approve", headers=admin_headers)

    # The person posting sees only the day's cards, and nothing else of the registry.
    assert (await client.get(f"{API}/contents", headers=poster)).status_code == 403
    [card] = (await client.get(f"{API}/queue", headers=poster)).json()
    assert card["code"] == content["code"]
    assert card["hashtags"] == ["#Caracas", "#motorizados"]
    assert card["file_name"] == f"{content['code']}-tiktok.mp4"
    assert card["file_url"].endswith(f"name={content['code']}-tiktok.mp4")
    assert card["checklist"][0] == "Etiqueta de contenido de IA: activar"
    assert card["published_at"] is None and card["publication_id"] is None

    published = await client.post(f"{API}/variants/{tiktok['id']}/publish", json={}, headers=poster)
    assert published.status_code == 201, published.text
    again = await client.post(f"{API}/variants/{tiktok['id']}/publish", json={}, headers=poster)
    assert again.json()["error"]["code"] == "marketing_already_published"
    [done] = (await client.get(f"{API}/queue", headers=poster)).json()
    assert done["publication_id"] == published.json()["id"] and done["published_at"]
    link = await client.patch(
        f"{API}/publications/{published.json()['id']}",
        json={"url": "https://www.tiktok.com/@kuulis/video/1"},
        headers=poster,
    )
    assert link.json()["url"] == "https://www.tiktok.com/@kuulis/video/1"

    detail = (await client.get(f"{API}/contents/{cid}", headers=team)).json()
    assert detail["status"] == "publicado"
    locked = await client.patch(f"{API}/contents/{cid}", json={"title": "x"}, headers=team)
    assert locked.json()["error"]["code"] == "marketing_content_locked"

    publication_id = published.json()["id"]
    metric = await client.post(
        f"{API}/publications/{publication_id}/metrics",
        json={"views": 1500, "likes": 120, "completion_rate": 0.42},
        headers=team,
    )
    assert metric.status_code == 201, metric.text
    assert metric.json()["age_h"] == 0 and metric.json()["source"] == "manual"

    [row] = (await client.get(f"{API}/performance", headers=team)).json()
    assert row["code"] == content["code"] and row["snapshots"] == 1
    assert row["latest"]["views"] == 1500
    assert (await client.get(f"{API}/performance?platform=youtube", headers=team)).json() == []


async def test_codes_follow_the_planned_day(client, admin_headers) -> None:
    for _ in range(2):
        await client.post(
            f"{API}/contents",
            json={"title": "Idea", "scheduled_for": "2026-11-04"},
            headers=admin_headers,
        )
    async with SessionLocal() as session:
        assert await next_code(session, date(2026, 11, 4)) == "K-2026-11-04-C"
        assert await next_code(session, date(2026, 11, 5)) == "K-2026-11-05-A"
    listed = (
        await client.get(f"{API}/contents?from=2026-11-01&to=2026-11-30", headers=admin_headers)
    ).json()
    assert sorted(i["code"] for i in listed["items"]) == ["K-2026-11-04-A", "K-2026-11-04-B"]


async def test_template_pieces_record_their_production(client, admin_headers) -> None:
    created = await client.post(
        f"{API}/contents",
        json={"title": "Carrusel", "format": "F-CARRUSEL", "production": "plantilla"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["production"] == "plantilla"


async def test_assets_must_belong_to_the_piece_and_be_uploaded(
    client, admin_headers, bucket
) -> None:
    first = (
        await client.post(f"{API}/contents", json={"title": "A"}, headers=admin_headers)
    ).json()
    second = (
        await client.post(f"{API}/contents", json={"title": "B"}, headers=admin_headers)
    ).json()
    other = await _upload(client, admin_headers, bucket, second["id"])
    wrong = await client.post(
        f"{API}/contents/{first['id']}/variants",
        json={"platform": "instagram", "asset_id": other["id"]},
        headers=admin_headers,
    )
    assert wrong.json()["error"]["code"] == "marketing_invalid_asset"

    pending = await client.post(
        f"{API}/contents/{first['id']}/assets",
        json={"filename": "v.mp4", "content_type": "video/mp4", "size": 10, "source": "buzzy"},
        headers=admin_headers,
    )
    unconfirmed = pending.json()["asset"]
    not_there = await client.post(
        f"{API}/contents/{first['id']}/assets/{unconfirmed['id']}/confirm", headers=admin_headers
    )
    assert not_there.json()["error"]["code"] == "marketing_asset_not_uploaded"

    too_big = await client.post(
        f"{API}/contents/{first['id']}/assets",
        json={
            "filename": "v.mp4",
            "content_type": "video/mp4",
            "size": (settings.MARKETING_MAX_UPLOAD_MB + 1) * 1024 * 1024,
            "source": "buzzy",
        },
        headers=admin_headers,
    )
    assert too_big.json()["error"]["code"] == "file_too_large"
    bad_type = await client.post(
        f"{API}/contents/{first['id']}/assets",
        json={
            "filename": "x.exe",
            "content_type": "application/x-msdownload",
            "size": 1,
            "source": "x",
        },
        headers=admin_headers,
    )
    assert bad_type.status_code == 422


async def test_without_bucket_uploads_say_storage_is_off(client, admin_headers) -> None:
    content = (
        await client.post(f"{API}/contents", json={"title": "A"}, headers=admin_headers)
    ).json()
    response = await client.post(
        f"{API}/contents/{content['id']}/assets",
        json={"filename": "v.mp4", "content_type": "video/mp4", "size": 10, "source": "remotion"},
        headers=admin_headers,
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "marketing_storage_disabled"


async def test_request_changes_returns_the_piece_with_a_note(client, admin_headers, bucket) -> None:
    content = (
        await client.post(
            f"{API}/contents", json={"title": "A", "status": "guion"}, headers=admin_headers
        )
    ).json()
    for status in ("revisado", "producido"):
        await client.post(
            f"{API}/contents/{content['id']}/status", json={"status": status}, headers=admin_headers
        )
    back = await client.post(
        f"{API}/contents/{content['id']}/request-changes",
        json={"note": "El gancho tarda mucho"},
        headers=admin_headers,
    )
    assert back.json()["status"] == "revisado"
    assert back.json()["review_note"] == "El gancho tarda mucho"


async def test_learnings_spend_and_accounts(client, admin_headers) -> None:
    learning = await client.post(
        f"{API}/learnings",
        json={"statement": "Los ganchos con cifra retienen más", "platform": "tiktok"},
        headers=admin_headers,
    )
    assert learning.status_code == 201 and learning.json()["reviewed_at"] is None
    proved = await client.patch(
        f"{API}/learnings/{learning.json()['id']}",
        json={"status": "probado", "evidence": "K-2026-11-04-A: 62 % vs 41 %"},
        headers=admin_headers,
    )
    assert proved.json()["status"] == "probado" and proved.json()["reviewed_at"]

    for day, tool, amount in (
        ("2026-11-01", "Higgsfield", "64.10"),
        ("2026-11-02", "Buzzy", "19.00"),
        ("2026-12-01", "Buzzy", "19.00"),
    ):
        response = await client.post(
            f"{API}/spend",
            json={"date": day, "tool": tool, "concept": "suscripcion", "amount_usd": amount},
            headers=admin_headers,
        )
        assert response.status_code == 201, response.text
    month = (await client.get(f"{API}/spend?month=2026-11", headers=admin_headers)).json()
    assert month["total"] == "83.10"
    assert month["by_tool"] == {"Buzzy": "19.00", "Higgsfield": "64.10"}

    account = await client.post(
        f"{API}/accounts", json={"platform": "tiktok", "handle": "@kuulis"}, headers=admin_headers
    )
    assert account.status_code == 201
    duplicate = await client.post(
        f"{API}/accounts", json={"platform": "tiktok", "handle": "@kuulis"}, headers=admin_headers
    )
    assert duplicate.json()["error"]["code"] == "marketing_account_exists"
    active = await client.patch(
        f"{API}/accounts/{account.json()['id']}", json={"status": "activa"}, headers=admin_headers
    )
    assert active.json()["status"] == "activa"


async def test_queue_shows_only_approved_pieces_of_that_day(client, admin_headers, bucket) -> None:
    content = (
        await client.post(
            f"{API}/contents", json={"title": "A", "status": "guion"}, headers=admin_headers
        )
    ).json()
    cid = content["id"]
    video = await _upload(client, admin_headers, bucket, cid)
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).astimezone(CARACAS_TZ)
    await client.post(
        f"{API}/contents/{cid}/variants",
        json={"platform": "youtube", "asset_id": video["id"], "scheduled_at": tomorrow.isoformat()},
        headers=admin_headers,
    )
    for status in ("revisado", "producido"):
        await client.post(
            f"{API}/contents/{cid}/status", json={"status": status}, headers=admin_headers
        )
    assert (
        await client.get(f"{API}/queue?day={tomorrow.date()}", headers=admin_headers)
    ).json() == []
    await client.post(f"{API}/contents/{cid}/approve", headers=admin_headers)
    assert (await client.get(f"{API}/queue", headers=admin_headers)).json() == []
    [card] = (await client.get(f"{API}/queue?day={tomorrow.date()}", headers=admin_headers)).json()
    assert card["platform"] == "youtube" and card["checklist"] == [
        "Etiqueta de contenido de IA: activar"
    ]
