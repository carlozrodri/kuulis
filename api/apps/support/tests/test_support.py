from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from apps.moderation.models import Report
from apps.moderation.tests.test_moderation import _ride, _titles
from apps.notifications.models import Notification
from apps.rides.models import RideStatus
from apps.rides.tests.conftest import make_driver
from apps.support import services, tasks
from conftest import _login, _make_user, set_config
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def _push_data(user_id) -> list[dict]:
    async with SessionLocal() as session:
        return list(
            await session.scalars(select(Notification.data).where(Notification.user_id == user_id))
        )


async def test_conversation_between_user_and_team(client, staff_headers, passenger):
    created = await client.post(
        f"{API}/reports",
        json={"category": "app_issue", "description": "La app se cierra al pedir una moto"},
        headers=passenger.headers,
    )
    assert created.status_code == 201, created.text
    report = created.json()
    assert report["waiting_on"] == "staff" and report["source"] == "app"
    assert report["can_reply"] and not report["unread"] and not report["can_rate"]
    rid = report["id"]

    thread = (
        await client.get(f"{API}/reports/me/{rid}/messages", headers=passenger.headers)
    ).json()
    assert [(m["author_kind"], m["mine"]) for m in thread] == [("user", True)]
    assert thread[0]["body"] == "La app se cierra al pedir una moto"

    # A saved reply with variables, used as a macro that also tags the ticket.
    canned = await client.post(
        f"{API}/admin/support/canned",
        json={
            "title": "Pedir datos",
            "body": "Hola {nombre}, ¿qué teléfono usas?",
            "tags": ["App"],
        },
        headers=staff_headers,
    )
    assert canned.status_code == 201, canned.text
    answer = await client.post(
        f"{API}/admin/reports/{rid}/messages",
        json={"body": canned.json()["body"], "canned_response_id": canned.json()["id"]},
        headers=staff_headers,
    )
    assert answer.status_code == 200, answer.text
    detail = answer.json()
    assert detail["waiting_on"] == "user" and detail["status"] == "in_review"
    assert detail["first_response_at"] and detail["tags"] == ["app"]
    assert detail["messages"][-1]["body"] == "Hola Ana, ¿qué teléfono usas?"
    assert detail["messages"][-1]["author_kind"] == "staff"
    assert {"type": "support", "event": "support_reply", "report_id": rid} in await _push_data(
        passenger.user.id
    )
    listed = (await client.get(f"{API}/admin/support/canned", headers=staff_headers)).json()
    assert listed[0]["uses"] == 1

    mine = (await client.get(f"{API}/reports/me", headers=passenger.headers)).json()
    assert mine["items"][0]["unread"] is True
    thread = (
        await client.get(f"{API}/reports/me/{rid}/messages", headers=passenger.headers)
    ).json()
    assert thread[-1]["author_kind"] == "staff" and thread[-1]["author_name"]
    mine = (await client.get(f"{API}/reports/me", headers=passenger.headers)).json()
    assert mine["items"][0]["unread"] is False

    bad = await client.post(
        f"{API}/reports/me/{rid}/messages",
        json={"body": "foto", "attachments": ["test/uploads/otro/x.jpg"]},
        headers=passenger.headers,
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "attachment_invalid"
    key = f"test/uploads/{passenger.user.id}/abc-captura.png"
    replied = await client.post(
        f"{API}/reports/me/{rid}/messages",
        json={"body": "Un Samsung A14", "attachments": [key]},
        headers=passenger.headers,
    )
    assert replied.status_code == 201, replied.text
    assert [a["key"] for a in replied.json()["attachments"]] == [key]
    admin_view = (await client.get(f"{API}/admin/reports/{rid}", headers=staff_headers)).json()
    assert admin_view["waiting_on"] == "staff" and admin_view["messages_count"] == 3

    early = await client.post(
        f"{API}/reports/me/{rid}/csat", json={"score": 5}, headers=passenger.headers
    )
    assert early.status_code == 409 and early.json()["error"]["code"] == "report_not_closed"

    resolved = await client.post(
        f"{API}/admin/reports/{rid}/messages",
        json={"body": "Ya está arreglado en la última versión.", "then": "resolve"},
        headers=staff_headers,
    )
    assert resolved.json()["status"] == "resolved" and resolved.json()["waiting_on"] is None
    assert "Revisamos tu reporte" in await _titles(passenger.user.id)

    rated = await client.post(
        f"{API}/reports/me/{rid}/csat",
        json={"score": 4, "comment": "Rápido"},
        headers=passenger.headers,
    )
    assert rated.status_code == 200 and rated.json()["csat"] == 4
    assert not rated.json()["can_rate"]
    twice = await client.post(
        f"{API}/reports/me/{rid}/csat", json={"score": 1}, headers=passenger.headers
    )
    assert twice.json()["error"]["code"] == "csat_already_given"

    # Replying a few days after it was resolved reopens it.
    again = await client.post(
        f"{API}/reports/me/{rid}/messages",
        json={"body": "Me volvió a pasar"},
        headers=passenger.headers,
    )
    assert again.status_code == 201
    reopened = (await client.get(f"{API}/reports/me/{rid}", headers=passenger.headers)).json()
    assert reopened["status"] == "in_review" and reopened["waiting_on"] == "staff"

    metrics = await client.get(f"{API}/admin/support/metrics?days=7", headers=staff_headers)
    assert metrics.status_code == 200, metrics.text
    assert metrics.json()["csat_avg"] == 4.0 and len(metrics.json()["days"]) == 7
    tags = (await client.get(f"{API}/admin/support/tags", headers=staff_headers)).json()
    assert tags == [{"tag": "app", "count": 1}]


async def test_closed_long_ago_cannot_reply(client, staff_headers, passenger):
    rid = (
        await client.post(
            f"{API}/reports",
            json={"category": "other", "description": "Una pregunta sobre la app"},
            headers=passenger.headers,
        )
    ).json()["id"]
    await client.post(
        f"{API}/admin/reports/{rid}/resolve",
        json={"status": "resolved", "resolution": "Respondido"},
        headers=staff_headers,
    )
    async with SessionLocal() as session:
        await session.execute(
            update(Report)
            .where(Report.id == rid)
            .values(resolved_at=datetime.now(UTC) - timedelta(days=30))
        )
        await session.commit()
    late = await client.post(
        f"{API}/reports/me/{rid}/messages", json={"body": "Hola"}, headers=passenger.headers
    )
    assert late.status_code == 409 and late.json()["error"]["code"] == "report_closed"


async def test_sla_alert_and_auto_close(client, staff_headers, passenger, monkeypatch):
    sent: list[str] = []

    async def fake_notify(text: str) -> None:
        sent.append(text)

    from apps.monitoring import alerts

    monkeypatch.setattr(alerts, "notify", fake_notify)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _ride(passenger.user.id, luis.user.id)
    urgent = (
        await client.post(
            f"{API}/reports",
            json={"category": "safety", "description": "Manejó muy rápido", "ride_id": ride_id},
            headers=passenger.headers,
        )
    ).json()
    general = (
        await client.post(
            f"{API}/reports",
            json={"category": "other", "description": "Una pregunta sobre la app"},
            headers=passenger.headers,
        )
    ).json()
    await client.post(
        f"{API}/admin/reports/{general['id']}/messages",
        json={"body": "¿Nos das más detalles?"},
        headers=staff_headers,
    )
    past = datetime.now(UTC) - timedelta(days=8)
    async with SessionLocal() as session:
        await session.execute(
            update(Report)
            .where(Report.id == urgent["id"])
            .values(sla_due_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await session.execute(
            update(Report).where(Report.id == general["id"]).values(waiting_since=past)
        )
        await session.commit()

    listing = (await client.get(f"{API}/admin/reports?overdue=true", headers=staff_headers)).json()
    assert [r["id"] for r in listing["items"]] == [urgent["id"]]
    assert listing["items"][0]["overdue"] and listing["counts"]["overdue"] == 1

    assert await tasks.run_once() == (1, 1)
    assert len(sent) == 1 and urgent["id"][:8] in sent[0]
    assert await tasks.run_once() == (0, 0)  # alerted once
    closed = (
        await client.get(f"{API}/reports/me/{general['id']}", headers=passenger.headers)
    ).json()
    assert closed["status"] == "resolved" and closed["unread"] and closed["can_reply"]
    assert "Cerramos tu conversación" in await _titles(passenger.user.id)


async def test_help_center(client, admin_headers, staff_headers, user_headers):
    body = {
        "slug": "como-pagar",
        "topic": "payments",
        "title": "Cómo pagar",
        "body_md": "Le pagas **directo** al motorizado. [Más](https://kuulis.app)",
        "published": True,
    }
    created = await client.post(f"{API}/admin/help/articles", json=body, headers=admin_headers)
    assert created.status_code == 201, created.text
    article = created.json()
    assert article["excerpt"] == "Le pagas directo al motorizado. Más"
    taken = await client.post(f"{API}/admin/help/articles", json=body, headers=admin_headers)
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "help_slug_taken"
    hidden = {**body, "slug": "borrador", "published": False, "topic": "wallet"}
    await client.post(f"{API}/admin/help/articles", json=hidden, headers=admin_headers)
    driver_only = {**body, "slug": "cuota", "topic": "wallet", "audience": "driver"}
    await client.post(f"{API}/admin/help/articles", json=driver_only, headers=admin_headers)

    public = (await client.get(f"{API}/help/articles?locale=es")).json()
    assert {a["slug"] for a in public} == {"como-pagar", "cuota"}
    passenger_view = (await client.get(f"{API}/help/articles?audience=passenger")).json()
    assert [a["slug"] for a in passenger_view] == ["como-pagar"]
    found = (await client.get(f"{API}/help/articles?q=DIRECTO")).json()
    assert {a["slug"] for a in found} == {"como-pagar", "cuota"}

    # English falls back to Spanish while there is no translation.
    read = await client.get(f"{API}/help/articles/como-pagar?locale=en")
    assert read.status_code == 200 and read.json()["locale"] == "es"
    assert (await client.get(f"{API}/help/articles/borrador")).status_code == 404
    assert (
        await client.post(f"{API}/help/articles/{article['id']}/feedback", json={"helpful": True})
    ).status_code == 204

    # Staff need help.manage: the default soporte role has it, a role without it does not.
    from apps.users.models import Role
    from conftest import make_staff_role

    role = await make_staff_role("solo_reportes", {"reports.manage"})
    await _make_user("reportes@example.com", Role.STAFF, role)
    limited = await _login(client, "reportes@example.com")
    assert (await client.get(f"{API}/admin/help/articles", headers=limited)).status_code == 403
    stats = (await client.get(f"{API}/admin/help/articles", headers=admin_headers)).json()
    pay = next(a for a in stats if a["slug"] == "como-pagar")
    assert pay["views"] == 1 and pay["helpful_yes"] == 1 and pay["helpful_no"] == 0

    updated = await client.patch(
        f"{API}/admin/help/articles/{article['id']}",
        json={"published": False},
        headers=admin_headers,
    )
    assert updated.status_code == 200 and updated.json()["published"] is False
    assert (await client.get(f"{API}/help/articles/como-pagar")).status_code == 404

    contact = await client.post(
        f"{API}/reports",
        json={
            "category": "other",
            "description": "No entiendo cómo pagar al motorizado",
            "help_article_id": article["id"],
        },
        headers=user_headers,
    )
    assert contact.status_code == 201 and contact.json()["source"] == "help"
    detail = (
        await client.get(f"{API}/admin/reports/{contact.json()['id']}", headers=staff_headers)
    ).json()
    assert detail["help_article"]["slug"] == "como-pagar"


async def test_lost_item_flow(client, staff_headers, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ride_id = await _ride(passenger.user.id, luis.user.id)
    url = f"{API}/rides/{ride_id}/lost-item"

    assert (await client.post(url, json={"description": "Gorra"}, headers=luis.headers)).json()[
        "error"
    ]["code"] == "not_ride_participant"
    asked = await client.post(
        url, json={"description": "Una gorra azul"}, headers=passenger.headers
    )
    assert asked.status_code == 201, asked.text
    item = asked.json()
    assert item["answer"] is None and not item["chat_open"] and item["report_id"]
    assert {"type": "lost_item", "event": "lost_item_asked", "ride_id": ride_id} in (
        await _push_data(luis.user.id)
    )
    twice = await client.post(url, json={"description": "Gorra"}, headers=passenger.headers)
    assert twice.json()["error"]["code"] == "lost_item_exists"

    # The ride chat is closed until the driver has the item.
    chat = f"{API}/rides/{ride_id}/messages"
    closed = await client.post(chat, json={"text": "Hola"}, headers=passenger.headers)
    assert closed.status_code == 409

    assert (
        await client.post(f"{url}/answer", json={"has_it": True}, headers=passenger.headers)
    ).status_code == 403
    answered = await client.post(f"{url}/answer", json={"has_it": True}, headers=luis.headers)
    assert answered.status_code == 200, answered.text
    assert answered.json()["answer"] == "has_it" and answered.json()["chat_open"]
    again = await client.post(f"{url}/answer", json={"has_it": False}, headers=luis.headers)
    assert again.json()["error"]["code"] == "lost_item_answered"
    assert (await client.get(url, headers=passenger.headers)).json()["chat_open"]

    opened = await client.post(chat, json={"text": "¿Dónde nos vemos?"}, headers=passenger.headers)
    assert opened.status_code == 201, opened.text

    detail = (
        await client.get(f"{API}/admin/reports/{item['report_id']}", headers=staff_headers)
    ).json()
    assert detail["source"] == "lost_item" and detail["lost_item"]["answer"] == "has_it"
    assert detail["messages"][-1]["author_kind"] == "system"
    assert detail["waiting_on"] == "user"


async def test_lost_item_too_late(client, passenger):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    old = await _ride(passenger.user.id, luis.user.id)
    async with SessionLocal() as session:
        from apps.rides.models import Ride

        await session.execute(
            update(Ride)
            .where(Ride.id == old)
            .values(completed_at=datetime.now(UTC) - timedelta(days=10))
        )
        await session.commit()
    late = await client.post(
        f"{API}/rides/{old}/lost-item", json={"description": "Gorra"}, headers=passenger.headers
    )
    assert late.json()["error"]["code"] == "lost_item_too_late"
    live = await _ride(passenger.user.id, luis.user.id, RideStatus.IN_PROGRESS)
    busy = await client.post(
        f"{API}/rides/{live}/lost-item", json={"description": "Gorra"}, headers=passenger.headers
    )
    assert busy.json()["error"]["code"] == "ride_not_completed"


async def test_public_contact_form(client, staff_headers, monkeypatch):
    monkeypatch.setattr(services, "DIFFICULTY", 6)
    emails: list[tuple] = []

    async def fake_send(to, subject, html, text=None, reply_to=None):
        emails.append((to, subject, html, reply_to))
        return True

    monkeypatch.setattr(tasks, "send_email", fake_send)
    await set_config(app_links={"support_email": "soporte@kuulis.app"})

    challenge = (await client.get(f"{API}/public/contact/challenge")).json()
    assert challenge["difficulty"] == 6
    nonce = services.solve(challenge["challenge"], 6)
    body = {
        "name": "Pedro",
        "email": "Pedro@Correo.com",
        "message": "No puedo entrar, perdí el teléfono",
        "category": "app_issue",
        "challenge": challenge["challenge"],
        "nonce": nonce,
    }
    wrong = await client.post(f"{API}/public/contact", json={**body, "nonce": "x"})
    if (
        services.leading_zero_bits(
            __import__("hashlib").sha256(f"{challenge['challenge']}:x".encode()).digest()
        )
        < 6
    ):
        assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "captcha_invalid"
    sent = await client.post(f"{API}/public/contact", json=body)
    assert sent.status_code == 202, sent.text
    reused = await client.post(f"{API}/public/contact", json=body)
    assert reused.json()["error"]["code"] == "captcha_invalid"
    forged = await client.post(
        f"{API}/public/contact", json={**body, "challenge": challenge["challenge"][:-1] + "0"}
    )
    assert forged.status_code == 400
    assert emails and emails[0][0] == "pedro@correo.com" and emails[0][3] == "soporte@kuulis.app"

    listing = (await client.get(f"{API}/admin/reports?source=web", headers=staff_headers)).json()
    ticket = listing["items"][0]
    assert ticket["reporter"] is None and ticket["contact_email"] == "pedro@correo.com"
    answer = await client.post(
        f"{API}/admin/reports/{ticket['id']}/messages",
        json={"body": "Hola {nombre}, te ayudamos a recuperar tu cuenta <b>ya</b>."},
        headers=staff_headers,
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["reporter_summary"] is None
    last = emails[-1]
    assert "Hola Pedro" in last[2] and "&lt;b&gt;" in last[2]
