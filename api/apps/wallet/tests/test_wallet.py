from decimal import Decimal

import pytest
from sqlalchemy import select

from apps.notifications.models import Notification
from apps.rides.tests.conftest import make_driver
from apps.wallet import binance, services
from apps.wallet.models import TopUp, TopUpStatus
from conftest import _make_user
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def _credit(user_id, amount: str) -> None:
    async with SessionLocal() as session:
        await services.credit(session, user_id, services.EntryKind.ADJUSTMENT, Decimal(amount))
        await session.commit()


async def test_wallet_requires_driver(client, user_headers):
    response = await client.put(
        f"{API}/wallet/me/binance", json={"binance_pay_id": "123456789"}, headers=user_headers
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "not_a_driver"
    assert (await client.get(f"{API}/wallet/top-up-info", headers=user_headers)).status_code == 403


async def test_binance_pay_id(client):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ana = await make_driver(client, "ana2@example.com", "Ana Ruiz")
    bad = await client.put(
        f"{API}/wallet/me/binance", json={"binance_pay_id": "12ab"}, headers=luis.headers
    )
    assert bad.status_code == 422
    ok = await client.put(
        f"{API}/wallet/me/binance", json={"binance_pay_id": "123 456 789"}, headers=luis.headers
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["binance_pay_id"] == "123456789" and body["balance"] == "0.00"
    assert body["transfer"] == {"limit": "50.00", "sent_this_month": "0.00", "available": "50.00"}
    taken = await client.put(
        f"{API}/wallet/me/binance", json={"binance_pay_id": "123456789"}, headers=ana.headers
    )
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "binance_pay_id_taken"


async def test_top_up_request_confirm_reject(client, admin_headers, staff_headers):
    await client.patch(
        f"{API}/admin/config", json={"topup_binance_pay_id": "987654321"}, headers=admin_headers
    )
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    info = (await client.get(f"{API}/wallet/top-up-info", headers=luis.headers)).json()
    assert info == {
        "method": "binance_pay",
        "pay_id": "987654321",
        "account_name": "Kuulis",
        "min_amount": "5.00",
        "automatic": False,
    }
    low = await client.post(f"{API}/wallet/me/top-ups", json={"amount": "4"}, headers=luis.headers)
    assert low.status_code == 400 and low.json()["error"]["code"] == "amount_too_low"
    ids = []
    for _ in range(3):
        response = await client.post(
            f"{API}/wallet/me/top-ups",
            json={"amount": "10", "reference": " 4012 "},
            headers=luis.headers,
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    assert response.json()["status"] == "pending" and response.json()["reference"] == "4012"
    too_many = await client.post(
        f"{API}/wallet/me/top-ups", json={"amount": "10"}, headers=luis.headers
    )
    assert too_many.status_code == 409

    url = f"{API}/admin/top-ups/{ids[0]}/confirm"
    assert (
        await client.post(url, json={"amount": "9.5"}, headers=staff_headers)
    ).status_code == 403
    confirmed = await client.post(url, json={"amount": "9.5"}, headers=admin_headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "completed" and confirmed.json()["user"]["name"]
    assert (
        await client.post(url, json={"amount": "9.5"}, headers=admin_headers)
    ).status_code == 409
    rejected = await client.post(
        f"{API}/admin/top-ups/{ids[1]}/reject", json={"reason": "No llegó"}, headers=admin_headers
    )
    assert rejected.json()["status"] == "rejected"

    wallet = (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()
    assert wallet["balance"] == "9.50"
    entries = (await client.get(f"{API}/wallet/me/entries", headers=luis.headers)).json()
    assert entries["items"][0]["kind"] == "top_up"
    assert entries["items"][0]["details"] == {"method": "binance_pay", "reference": "4012"}
    pending = await client.get(f"{API}/admin/top-ups?status=pending", headers=staff_headers)
    assert pending.json()["total"] == 1
    mine = await client.get(f"{API}/wallet/me/top-ups", headers=luis.headers)
    assert mine.json()["total"] == 3
    async with SessionLocal() as session:
        titles = list(
            await session.scalars(
                select(Notification.title).where(Notification.user_id == luis.user.id)
            )
        )
    assert "Recarga acreditada" in titles and "Recarga rechazada" in titles


async def test_binance_payments_match_or_wait(client, admin_headers, monkeypatch):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await client.put(
        f"{API}/wallet/me/binance", json={"binance_pay_id": "111222333"}, headers=luis.headers
    )
    await client.post(f"{API}/wallet/me/top-ups", json={"amount": "5"}, headers=luis.headers)

    items = [
        {
            "transactionId": "T1",
            "transactionTime": 1,
            "amount": "5.00",
            "currency": "USDT",
            "payerInfo": {"name": "Luis", "binanceId": 111222333},
        },
        {
            "transactionId": "T2",
            "transactionTime": 2,
            "amount": "7",
            "currency": "USDT",
            "payerInfo": {"name": "Desconocido", "binanceId": 999},
        },
        {"transactionId": "T3", "transactionTime": 3, "amount": "-3", "currency": "USDT"},
        {"transactionId": "T4", "transactionTime": 4, "amount": "8", "currency": "BTC"},
    ]

    async def fake_fetch(start, end):
        return items

    monkeypatch.setattr(binance, "fetch_transactions", fake_fetch)
    async with SessionLocal() as session:
        assert await binance.reconcile(session) == 2
    await binance.redis_client.delete(binance.LOCK_KEY)
    async with SessionLocal() as session:  # the same payments again: ignored
        assert await binance.reconcile(session) == 0
    async with SessionLocal() as session:  # lock still held: not this worker's turn
        assert await binance.reconcile(session) is None

    assert (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()["balance"] == "5.00"
    async with SessionLocal() as session:
        rows = list(await session.scalars(select(TopUp).order_by(TopUp.created_at)))
    assert [r.status for r in rows] == [
        TopUpStatus.COMPLETED,  # the driver's notice, settled by T1
        TopUpStatus.COMPLETED,  # T1
        TopUpStatus.UNMATCHED,  # T2
    ]
    unmatched = rows[2]
    assigned = await client.post(
        f"{API}/admin/top-ups/{unmatched.id}/assign",
        json={"user_id": luis.id},
        headers=admin_headers,
    )
    assert assigned.status_code == 200, assigned.text
    assert (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()["balance"] == "12.00"


@pytest.mark.parametrize(
    "query", ["luis@example.com", "LUIS@example.com", "04121234567", "+584121234567"]
)
async def test_recipient_lookup(client, query):
    await make_driver(client, "luis@example.com", "Luis Gómez")
    ana = await make_driver(client, "ana2@example.com", "Ana Ruiz")
    response = await client.get(
        f"{API}/wallet/recipients", params={"q": query}, headers=ana.headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Luis G."


async def test_transfers(client, admin_headers, staff_headers):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ana = await make_driver(client, "ana2@example.com", "Ana Ruiz")
    missing = await client.get(
        f"{API}/wallet/recipients", params={"q": "nadie@example.com"}, headers=ana.headers
    )
    assert missing.status_code == 404
    url = f"{API}/wallet/me/transfers"
    self_transfer = await client.post(
        url, json={"to_user_id": ana.id, "amount": "1"}, headers=ana.headers
    )
    assert self_transfer.json()["error"]["code"] == "transfer_to_self"
    broke = await client.post(url, json={"to_user_id": luis.id, "amount": "1"}, headers=ana.headers)
    assert broke.status_code == 409 and broke.json()["error"]["code"] == "insufficient_balance"

    await _credit(ana.user.id, "80")
    sent = await client.post(
        url, json={"to_user_id": luis.id, "amount": "30", "note": "Gasolina"}, headers=ana.headers
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["kind"] == "transfer_out" and sent.json()["amount"] == "-30.00"
    assert sent.json()["details"] == {"counterpart_name": "Luis G.", "note": "Gasolina"}
    over = await client.post(url, json={"to_user_id": luis.id, "amount": "25"}, headers=ana.headers)
    assert over.status_code == 409
    assert over.json()["error"]["details"] == {
        "limit": "50.00",
        "sent_this_month": "30.00",
        "available": "20.00",
    }
    back = await client.post(url, json={"to_user_id": ana.id, "amount": "10"}, headers=luis.headers)
    assert back.status_code == 201  # what Ana received does not count for Luis' limit... nor hers

    ana_wallet = (await client.get(f"{API}/wallet/me", headers=ana.headers)).json()
    assert ana_wallet["balance"] == "60.00" and ana_wallet["transfer"]["available"] == "20.00"
    luis_wallet = (await client.get(f"{API}/wallet/me", headers=luis.headers)).json()
    assert luis_wallet["balance"] == "20.00"

    listing = await client.get(f"{API}/admin/transfers?q=ruiz", headers=staff_headers)
    assert listing.json()["total"] == 2
    first = listing.json()["items"][-1]
    assert first["amount"] == "30.00" and first["note"] == "Gasolina"
    assert first["sender"]["email"] == "ana2@example.com"


async def test_admin_adjust_and_wallet_view(client, admin_headers, staff_headers):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    url = f"{API}/admin/wallets/{luis.id}"
    negative = await client.post(
        f"{url}/adjust", json={"amount": "-1", "reason": "x"}, headers=admin_headers
    )
    assert negative.status_code == 409
    assert (
        await client.post(
            f"{url}/adjust", json={"amount": "3", "reason": "x"}, headers=staff_headers
        )
    ).status_code == 403
    ok = await client.post(
        f"{url}/adjust", json={"amount": "3", "reason": "Compensación"}, headers=admin_headers
    )
    assert ok.status_code == 201 and ok.json()["details"] == {"reason": "Compensación"}
    view = (await client.get(url, headers=staff_headers)).json()
    assert view["balance"] == "3.00" and len(view["entries"]) == 1
    assert view["pending_charges"] == [] and view["user"]["email"] == "luis@example.com"
    other = await _make_user("nadie@example.com")
    assert (
        await client.get(f"{API}/admin/wallets/{other.id}", headers=staff_headers)
    ).status_code == 403


def test_parse_ignores_outgoing_and_other_coins():
    assert binance.parse({"transactionId": 1, "amount": "-1", "currency": "USDT"}) is None
    assert binance.parse({"transactionId": 1, "amount": "1", "currency": "BUSD"}) is None
    assert binance.parse(
        {"transactionId": 9, "amount": "5.004", "currency": "usdt", "payerInfo": {"binanceId": 12}}
    ) == ("9", Decimal("5.00"), "12", None)
