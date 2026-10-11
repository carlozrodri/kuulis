from datetime import UTC, datetime

from sqlalchemy import select

from apps.audit.models import AuditLog
from apps.legal import services
from apps.legal.models import LegalAcceptance, LegalDocument
from apps.rides.tests.conftest import DROPOFF, NEAR, PICKUP, Actor, make_driver, request_ride
from conftest import PASSWORD, _login, _make_user
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def seed_legal() -> None:
    """Version 1 of every text, as the migration publishes it."""
    async with SessionLocal() as session:
        for kind, titles in services.TITLES.items():
            for locale, title in titles.items():
                session.add(
                    LegalDocument(
                        kind=kind,
                        version=1,
                        locale=locale,
                        title=title,
                        body_md=services.bundled_text(kind, locale),
                        summary="",
                        requires_reacceptance=True,
                        published_at=datetime.now(UTC),
                    )
                )
        await session.commit()
    await services.invalidate_cache()


def test_every_kind_has_a_draft_in_both_languages():
    for kind in services.KINDS:
        for locale in services.LOCALES:
            assert services.bundled_text(kind, locale).startswith("> **")  # draft notice


async def test_public_texts(client):
    await seed_legal()
    listing = (await client.get(f"{API}/legal", params={"locale": "en"})).json()
    assert [d["kind"] for d in listing] == list(services.KINDS)
    assert all("body_md" not in d for d in listing)
    terms = (await client.get(f"{API}/legal/terms", params={"locale": "en"})).json()
    assert terms["title"] == "Terms and conditions" and terms["version"] == 1
    assert "Kuulis does not provide transportation" in terms["body_md"]
    assert (await client.get(f"{API}/legal/cookies")).status_code == 422


async def test_sign_up_records_the_acceptance(client):
    await seed_legal()
    body = {"email": "nuevo@example.com", "password": PASSWORD, "accept_legal": True}
    response = await client.post(
        f"{API}/auth/register", json=body, headers={"X-Client-Platform": "android"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["user"]["pending_legal"] == []
    async with SessionLocal() as session:
        rows = list(await session.scalars(select(LegalAcceptance)))
    assert {(r.kind, r.version, r.platform) for r in rows} == {
        ("terms", 1, "android"),
        ("privacy", 1, "android"),
    }
    assert all(r.ip for r in rows)


async def test_rides_wait_until_the_terms_are_accepted(client):
    await seed_legal()
    ana = await _make_user("ana@example.com")
    headers = await _login(client, "ana@example.com")
    me = (await client.get(f"{API}/users/me", headers=headers)).json()
    assert me["pending_legal"] == ["terms", "privacy"]

    quote = await client.post(
        f"{API}/rides/quote",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_type": "moto"},
        headers=headers,
    )
    blocked = await client.post(
        f"{API}/rides",
        json={"quote_id": quote.json()["quote_id"], "payment_method": "cash_usd"},
        headers=headers,
    )
    assert blocked.status_code == 409
    error = blocked.json()["error"]
    assert error["code"] == "legal_acceptance_required"
    assert error["details"] == {"kinds": ["terms", "privacy"]}

    accepted = await client.post(
        f"{API}/legal/accept", json={"kinds": ["terms", "privacy"]}, headers=headers
    )
    assert accepted.status_code == 200 and accepted.json() == []
    await request_ride(client, Actor(ana, headers))


async def test_drivers_also_accept_driver_terms(client):
    await seed_legal()
    driver = await make_driver(client, "luis@example.com", "Luis Gómez")
    await client.post(
        f"{API}/legal/accept", json={"kinds": ["terms", "privacy"]}, headers=driver.headers
    )
    online = await client.post(
        f"{API}/drivers/me/online", json={"lat": NEAR[0], "lng": NEAR[1]}, headers=driver.headers
    )
    assert online.status_code == 409
    assert online.json()["error"]["details"] == {"kinds": ["driver_terms", "wallet"]}
    await client.post(
        f"{API}/legal/accept", json={"kinds": ["driver_terms", "wallet"]}, headers=driver.headers
    )
    online = await client.post(
        f"{API}/drivers/me/online", json={"lat": NEAR[0], "lng": NEAR[1]}, headers=driver.headers
    )
    assert online.status_code == 200, online.text


async def test_publishing_a_major_version_asks_again(client, admin_headers, staff_headers):
    await seed_legal()
    user = await _make_user("ana@example.com")
    headers = await _login(client, "ana@example.com")
    await client.post(f"{API}/legal/accept", json={"kinds": ["terms", "privacy"]}, headers=headers)
    body = {
        "es": {
            "title": "Términos y condiciones",
            "body_md": "## 1. Nuevo\nTexto nuevo en español.",
        },
        "en": {"title": "Terms and conditions", "body_md": "## 1. New\nNew text in English here."},
        "summary": "Aclaramos las cancelaciones",
    }
    url = f"{API}/admin/legal/terms"
    assert (await client.post(url, json=body, headers=staff_headers)).status_code == 403

    minor = await client.post(url, json=body, headers=admin_headers)
    assert minor.status_code == 201, minor.text
    assert {d["version"] for d in minor.json()} == {2}
    me = (await client.get(f"{API}/users/me", headers=headers)).json()
    assert me["pending_legal"] == []  # a minor change does not ask again

    major = await client.post(
        url, json=body | {"requires_reacceptance": True}, headers=admin_headers
    )
    assert major.status_code == 201
    me = (await client.get(f"{API}/users/me", headers=headers)).json()
    assert me["pending_legal"] == ["terms"]
    current = (await client.get(f"{API}/legal/terms")).json()
    assert current["version"] == 3 and current["summary"] == "Aclaramos las cancelaciones"

    async with SessionLocal() as session:
        audit = list(
            await session.scalars(select(AuditLog).where(AuditLog.action == "legal.publish"))
        )
    assert [a.after["version"] for a in audit] == [2, 3]
    assert audit[0].entity_id == "terms"

    history = (await client.get(f"{API}/admin/legal?kind=terms", headers=admin_headers)).json()
    assert [(h["version"], h["locale"]) for h in history][:2] == [(3, "en"), (3, "es")]
    acceptances = await client.get(f"{API}/admin/users/{user.id}/legal", headers=staff_headers)
    assert {(a["kind"], a["version"]) for a in acceptances.json()} == {("terms", 1), ("privacy", 1)}


async def test_staff_are_not_asked(client, staff_headers):
    await seed_legal()
    me = (await client.get(f"{API}/users/me", headers=staff_headers)).json()
    assert me["pending_legal"] == []
