"""Doc 14: preferences, Android channels, campaigns, branded emails and housekeeping."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, update

from apps.drivers.models import DriverProfile, DriverStatus
from apps.notifications import delivery, emails, tasks
from apps.notifications.models import (
    CampaignRecipient,
    Category,
    Device,
    Notification,
)
from conftest import PASSWORD, _login, _make_user, set_config
from kuulis.core.db import SessionLocal

API = "/api/v1"


@pytest.fixture
def pushes(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    async def fake(messages):
        sent.extend(messages)
        return [{"status": "ok", "id": f"t{i}"} for i, _ in enumerate(messages)]

    monkeypatch.setattr(tasks, "send_expo_push", fake)
    return sent


@pytest.fixture
def mails(monkeypatch) -> list[tuple[str, str, str]]:
    sent: list[tuple[str, str, str]] = []

    async def fake(to, subject, html, text=None, reply_to=None):
        sent.append((to, subject, html))
        return True

    monkeypatch.setattr(tasks, "send_email", fake)
    return sent


async def _user(client, email: str, **values) -> tuple[str, dict]:
    user = await _make_user(email)
    if values:
        async with SessionLocal() as session:
            await session.execute(
                update(type(user)).where(type(user).id == user.id).values(**values)
            )
            await session.commit()
    return str(user.id), await _login(client, email)


async def _approve_driver(user_id: str, city: str = "caracas") -> None:
    async with SessionLocal() as session:
        session.add(
            DriverProfile(
                user_id=user_id,
                status=DriverStatus.APPROVED,
                birth_date=date(1990, 1, 1),
                national_id=f"V{user_id[:8]}",
                rif=f"J{user_id[:8]}",
                phone="+584121234567",
                city=city,
            )
        )
        await session.commit()


async def _device(client, headers, token: str, channels: list[str] | None = None, version=None):
    body = {"push_token": token, "platform": "android"}
    if channels is not None:
        body["channels"] = channels
    if version:
        body["app_version"] = version
    response = await client.post(f"{API}/notifications/devices", json=body, headers=headers)
    assert response.status_code == 201, response.text


# --- Delivery rules ------------------------------------------------------------------------------


def test_quiet_hours_cross_midnight():
    # 22:30 and 07:59 Caracas (UTC-4) are inside 21:00-08:00; 12:00 is not.
    assert delivery.in_quiet_hours(datetime(2026, 10, 14, 2, 30, tzinfo=UTC), "21:00", "08:00")
    assert delivery.in_quiet_hours(datetime(2026, 10, 14, 11, 59, tzinfo=UTC), "21:00", "08:00")
    assert not delivery.in_quiet_hours(datetime(2026, 10, 14, 16, 0, tzinfo=UTC), "21:00", "08:00")
    assert not delivery.in_quiet_hours(datetime(2026, 10, 14, 2, 30, tzinfo=UTC), "00:00", "00:00")


def test_categories_and_channels():
    assert delivery.category_of({"type": "safety"}) == Category.SAFETY
    assert delivery.category_of({"type": "lost_item"}) == Category.SUPPORT
    assert delivery.category_of({"type": "campaign"}) == Category.MARKETING
    assert delivery.category_of({"type": "wallet"}) == Category.TRANSACTIONAL
    offer = delivery.wanted_channel({"type": "ride", "event": "offer"})
    assert delivery.pick_channel(offer, ["default", "ride_offer"]) == "ride_offer"
    assert delivery.pick_channel(offer, ["ride_offer", "ride_offer_sound"]) == "ride_offer_sound"
    assert delivery.pick_channel(offer, []) == "default"  # older app: only "default" exists
    assert delivery.pick_channel(delivery.wanted_channel({"type": "support"}), ["account"]) == (
        "account"
    )


async def test_push_goes_to_the_channel_each_phone_has(client, pushes):
    user_id, headers = await _user(client, "ana@example.com")
    await _device(client, headers, "ExponentPushToken[new]", ["default", "ride_offer", "account"])
    await _device(client, headers, "ExponentPushToken[old]")  # an app from before doc 14
    await tasks.send_push.kiq([user_id], "Nuevo viaje", "", {"type": "ride", "event": "offer"})
    channels = {m["to"]: m["channelId"] for m in pushes}
    assert channels == {"ExponentPushToken[new]": "ride_offer", "ExponentPushToken[old]": "default"}


# --- Preferences ---------------------------------------------------------------------------------


async def test_preferences_default_and_update(client):
    _, headers = await _user(client, "ana@example.com")
    prefs = (await client.get(f"{API}/notifications/preferences", headers=headers)).json()
    assert prefs["marketing_push"] is True and prefs["quiet_start"] == "21:00"
    response = await client.put(
        f"{API}/notifications/preferences",
        json={"marketing_push": False, "quiet_start": "22:30", "quiet_end": "07:00"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["marketing_push"] is False and body["marketing_email"] is True
    assert (body["quiet_start"], body["quiet_end"]) == ("22:30", "07:00")
    assert body["default_quiet_start"] == "21:00"
    bad = await client.put(
        f"{API}/notifications/preferences", json={"quiet_start": "25:00"}, headers=headers
    )
    assert bad.status_code == 422


# --- Campaigns -----------------------------------------------------------------------------------


async def _campaign(client, staff_headers, **overrides) -> dict:
    body = {
        "name": "Fin de semana",
        "segment": {"audience": "passengers"},
        "channels": ["push", "inbox"],
        "title_es": "Viaja más barato",
        "body_es": "Este sábado 20 % menos.",
        "title_en": "Ride for less",
        "body_en": "20 % off this Saturday.",
        "deep_link": "/wallet",
    } | overrides
    response = await client.post(f"{API}/admin/campaigns", json=body, headers=staff_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_campaign_reaches_its_segment_once(client, staff_headers, pushes):
    await set_config(
        approval_broadcasts=False, notifications={"quiet_start": "00:00", "quiet_end": "00:00"}
    )
    _, ana_headers = await _user(client, "ana@example.com", locale="en")
    _, beto_headers = await _user(client, "beto@example.com")
    luis, _ = await _user(client, "luis@example.com")
    await _approve_driver(luis)
    await _device(client, ana_headers, "ExponentPushToken[ana]", ["default", "marketing"])
    await client.put(
        f"{API}/notifications/preferences", json={"marketing_push": False}, headers=beto_headers
    )

    count = await client.get(
        f"{API}/admin/campaigns/audience-count",
        params={"segment": '{"audience": "passengers"}'},
        headers=staff_headers,
    )
    assert count.json() == {"total": 2, "with_push": 1, "passengers": 2, "drivers": 0}

    campaign = await _campaign(client, staff_headers)
    scheduled = await client.post(
        f"{API}/admin/campaigns/{campaign['id']}/schedule", json={}, headers=staff_headers
    )
    assert scheduled.json()["status"] == "scheduled"
    assert await tasks.run_campaigns_once() == 2

    result = (
        await client.get(f"{API}/admin/campaigns/{campaign['id']}", headers=staff_headers)
    ).json()
    assert result["status"] == "sent"
    stats = result["stats"]
    assert (stats["targeted"], stats["sent"], stats["skipped_opt_out"]) == (2, 1, 1)
    assert stats["pushed"] == 1
    [push] = pushes
    assert push["title"] == "Ride for less" and push["channelId"] == "marketing"
    assert push["data"]["deep_link"] == "/wallet"

    inbox = (await client.get(f"{API}/notifications", headers=ana_headers)).json()
    [item] = inbox["items"]
    assert item["category"] == "marketing" and item["deep_link"] == "/wallet"
    await client.post(f"{API}/notifications/{item['id']}/read", headers=ana_headers)
    result = (
        await client.get(f"{API}/admin/campaigns/{campaign['id']}", headers=staff_headers)
    ).json()
    assert result["stats"]["opened"] == 1

    # Sent campaigns no longer change; a second one the same day hits the daily limit.
    locked = await client.patch(
        f"{API}/admin/campaigns/{campaign['id']}", json={"name": "Otro"}, headers=staff_headers
    )
    assert locked.status_code == 409
    second = await _campaign(client, staff_headers, name="Otra")
    await client.post(
        f"{API}/admin/campaigns/{second['id']}/schedule", json={}, headers=staff_headers
    )
    await tasks.run_campaigns_once()
    async with SessionLocal() as session:
        reasons = set(
            await session.scalars(
                select(CampaignRecipient.skip_reason).where(
                    CampaignRecipient.campaign_id == second["id"]
                )
            )
        )
    assert reasons == {"cap", "opt_out"}


async def test_quiet_hours_hold_marketing_back(client, staff_headers, pushes):
    await set_config(approval_broadcasts=False)
    _, headers = await _user(client, "ana@example.com")
    await client.put(
        f"{API}/notifications/preferences",
        json={"quiet_start": "00:00", "quiet_end": "23:59"},
        headers=headers,
    )
    campaign = await _campaign(client, staff_headers)
    await client.post(
        f"{API}/admin/campaigns/{campaign['id']}/schedule", json={}, headers=staff_headers
    )
    await tasks.run_campaigns_once()
    result = (
        await client.get(f"{API}/admin/campaigns/{campaign['id']}", headers=staff_headers)
    ).json()
    assert result["status"] == "sending" and result["stats"]["pending"] == 1
    assert pushes == []


async def test_campaign_waits_for_a_second_approval(client, staff_headers):
    await set_config(approval_broadcasts=True)
    campaign = await _campaign(client, staff_headers)
    held = await client.post(
        f"{API}/admin/campaigns/{campaign['id']}/schedule", json={}, headers=staff_headers
    )
    assert held.status_code == 202, held.text
    state = (
        await client.get(f"{API}/admin/campaigns/{campaign['id']}", headers=staff_headers)
    ).json()
    assert state["status"] == "pending_approval"
    # Editing it sends it back to draft: the approval was for the old text.
    edited = await client.patch(
        f"{API}/admin/campaigns/{campaign['id']}", json={"title_es": "Nuevo"}, headers=staff_headers
    )
    assert edited.json()["status"] == "draft"


async def test_segment_filters(client, staff_headers):
    _, ana_headers = await _user(client, "ana@example.com")
    luis, luis_headers = await _user(client, "luis@example.com")
    await _approve_driver(luis, city="valencia")
    await _device(client, ana_headers, "ExponentPushToken[ana]", version="1.2.0")
    await _device(client, luis_headers, "ExponentPushToken[luis]", version="1.10.0")

    async def count(segment: str) -> dict:
        response = await client.get(
            f"{API}/admin/campaigns/audience-count",
            params={"segment": segment},
            headers=staff_headers,
        )
        assert response.status_code == 200, response.text
        return response.json()

    assert (await count('{"audience": "drivers"}'))["total"] == 1
    assert (await count('{"app_version_below": "1.3"}'))["total"] == 1  # 1.10.0 is newer
    assert (await count('{"cities": ["Valencia"]}'))["drivers"] == 1
    assert (await count('{"new_without_ride_days": 7}'))["total"] == 2
    bad = await client.get(
        f"{API}/admin/campaigns/audience-count",
        params={"segment": '{"audience": "aliens"}'},
        headers=staff_headers,
    )
    assert bad.status_code == 422


async def test_test_send_goes_to_me_only(client, staff_headers, pushes):
    await _user(client, "ana@example.com")
    campaign = await _campaign(client, staff_headers)
    response = await client.post(
        f"{API}/admin/campaigns/{campaign['id']}/test", headers=staff_headers
    )
    assert response.json() == {"pushed": True, "emailed": False}
    inbox = (await client.get(f"{API}/notifications", headers=staff_headers)).json()
    assert inbox["items"][0]["title"].startswith("[Prueba]")


async def test_users_cannot_manage_campaigns(client, user_headers):
    response = await client.get(f"{API}/admin/campaigns", headers=user_headers)
    assert response.status_code == 403


# --- Emails ------------------------------------------------------------------------------------


def test_every_email_renders_in_both_languages():
    for name in emails.TEMPLATES:
        for locale in ("es", "en"):
            subject, html, text = emails.render(name, locale, emails.sample(name))
            assert subject and "{" not in subject, name
            assert "Kuulis" in html and "{" not in text, name


def test_email_values_are_escaped():
    _, html, text = emails.render(
        "verify", "es", {"name": "<b>Ana</b>", "link": "https://x.y/?a=1&b=2"}
    )
    assert "<b>Ana</b>" not in html and "&lt;b&gt;Ana&lt;/b&gt;" in html
    assert "a=1&amp;b=2" in html and "<b>Ana</b>" in text


async def test_email_preview(client, staff_headers):
    names = (await client.get(f"{API}/admin/email-templates", headers=staff_headers)).json()
    assert {"verify", "fee_paid", "campaign"} <= {n["name"] for n in names}
    preview = await client.get(
        f"{API}/admin/email-templates/fee_paid", params={"locale": "en"}, headers=staff_headers
    )
    assert preview.status_code == 200
    assert preview.json()["subject"] == "Receipt for your September 2026 fee"
    missing = await client.get(f"{API}/admin/email-templates/nope", headers=staff_headers)
    assert missing.status_code == 404


async def test_password_change_emails_the_owner(client, mails):
    _, headers = await _user(client, "ana@example.com", full_name="Ana Pérez")
    response = await client.post(
        f"{API}/users/me/password",
        json={"current_password": PASSWORD, "new_password": "Otra-Clave-Larga-99"},
        headers=headers,
    )
    assert response.status_code == 204, response.text
    [(to, subject, html)] = mails
    assert to == "ana@example.com" and subject == "Tu contraseña cambió" and "Hola Ana" in html


# --- Housekeeping --------------------------------------------------------------------------------


async def test_cleanup_deletes_old_rows_and_idle_phones(client):
    user_id, headers = await _user(client, "ana@example.com")
    await _device(client, headers, "ExponentPushToken[ana]")
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        session.add_all(
            [
                Notification(user_id=user_id, title="vieja", created_at=now - timedelta(days=91)),
                Notification(user_id=user_id, title="nueva"),
            ]
        )
        await session.execute(update(Device).values(last_seen_at=now - timedelta(days=61)))
        await session.commit()
    assert await tasks.cleanup(now) == (1, 1)
    async with SessionLocal() as session:
        titles = list(await session.scalars(select(Notification.title)))
        active = await session.scalar(select(Device.is_active))
    assert titles == ["nueva"] and active is False
