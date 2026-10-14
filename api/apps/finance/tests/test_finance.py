"""Doc 17: receipts, statements, monthly closings, Binance statement, invariants, disputes, fee
waivers and the tier simulator."""

import time
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update

from apps.finance import services as finance
from apps.finance.models import MonthlyClosing
from apps.moderation.models import Report, ReportCategory, ReportPriority
from apps.monitoring import checks, stats
from apps.rides.tests.conftest import make_driver
from apps.subscriptions import services as subscriptions
from apps.subscriptions.models import Charge, ChargeStatus
from apps.subscriptions.tests.test_subscriptions import _credit, _first_trip, _month, _ride
from apps.users.models import Role
from apps.wallet import binance, notify
from apps.wallet import services as wallet
from apps.wallet.models import EntryKind, Receipt, TopUp, Wallet, WalletEntry
from conftest import _login, _make_user, set_config
from kuulis.core import storage
from kuulis.core.calendar import format_month, month_bounds
from kuulis.core.db import SessionLocal

API = "/api/v1"


async def _emails(monkeypatch) -> list[tuple[str, dict]]:
    sent: list[tuple[str, dict]] = []

    async def fake(user_id, name, values=None):
        sent.append((name, dict(values or {})))

    monkeypatch.setattr(notify.emails, "send_to_user", fake)
    return sent


async def _top_up(client, driver, amount="10", reference="ORD123") -> str:
    created = await client.post(
        f"{API}/wallet/me/top-ups",
        json={"amount": amount, "reference": reference},
        headers=driver.headers,
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _charge_last_month(*drivers) -> None:
    for driver in drivers:
        await _first_trip(driver, -6)
    async with SessionLocal() as session:
        await subscriptions.charge_month(session, _month(-1))


# --- Receipts and statements -------------------------------------------------------------------


async def test_receipts_for_top_ups_and_fees(client, admin_headers, recorder, monkeypatch):
    emails = await _emails(monkeypatch)
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ana = await make_driver(client, "ana@example.com", "Ana Ruiz")
    top_up_id = await _top_up(client, luis)
    confirmed = await client.post(
        f"{API}/admin/top-ups/{top_up_id}/confirm", json={"amount": "10"}, headers=admin_headers
    )
    assert confirmed.status_code == 200, confirmed.text
    await _ride(luis, "150", -1)
    await _charge_last_month(luis)  # 5.00 fee paid from the 10.00

    entries = (await client.get(f"{API}/wallet/me/entries", headers=luis.headers)).json()["items"]
    by_kind = {e["kind"]: e for e in entries}
    assert by_kind["top_up"]["receipt_id"] and by_kind["subscription_fee"]["receipt_id"]
    top = (
        await client.get(
            f"{API}/wallet/me/receipts/{by_kind['top_up']['receipt_id']}", headers=luis.headers
        )
    ).json()
    fee = (
        await client.get(
            f"{API}/wallet/me/receipts/{by_kind['subscription_fee']['receipt_id']}",
            headers=luis.headers,
        )
    ).json()
    assert top["kind"] == "top_up" and top["amount"] == "10.00" and top["balance_after"] == "10.00"
    assert top["reference"] == "ORD123" and top["fiscal"] is False
    assert top["driver"]["name"] == "Luis Gómez"
    assert fee["kind"] == "subscription_fee" and fee["amount"] == "5.00"
    assert fee["balance_after"] == "5.00" and fee["concept"].startswith("Cuota mensual de ")
    assert int(fee["number"]) == int(top["number"]) + 1
    other = await client.get(f"{API}/wallet/me/receipts/{top['id']}", headers=ana.headers)
    assert other.status_code == 404 and other.json()["error"]["code"] == "receipt_not_found"

    sent = dict(emails)
    assert sent["top_up_credited"]["receipt"] == top["number"]
    assert sent["fee_paid"] == sent["fee_paid"] | {"receipt": fee["number"], "balance": "5.00"}


async def test_statement(client, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _ride(luis, "250", -1)
    await _credit(luis, "20")
    await _charge_last_month(luis)  # 10.00 fee
    url = f"{API}/wallet/me/statements"
    previous = format_month(_month(-1))
    body = (await client.get(url, headers=luis.headers)).json()
    assert body["month"] == previous and body["months"][0] == format_month(_month(0))
    assert body["trips"] == 1 and body["earned"] == "250.00" and body["counted"] == "250.00"
    assert body["tier"] == {"above": "200.00", "fee": "10.00"} and body["fee"] == "10.00"
    assert body["estimated"] is False and body["charge"]["status"] == "paid"
    # The credit and the fee happened today (this month), so last month's balance didn't move.
    assert body["opening_balance"] == "0.00" and body["closing_balance"] == "0.00"
    current = (
        await client.get(f"{url}?month={format_month(_month(0))}", headers=luis.headers)
    ).json()
    assert current["estimated"] is True and current["charge"] is None
    assert current["movements"]["fees"] == "10.00"
    assert current["movements"]["adjustments"] == "20.00"
    assert current["closing_balance"] == "10.00"
    passenger = await _make_user("pasajero@example.com")
    headers = await _login(client, passenger.email)
    assert (await client.get(url, headers=headers)).status_code == 403


# --- Monthly closings --------------------------------------------------------------------------


async def test_close_month_and_reconcile(client, admin_headers, staff_headers, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    previous = _month(-1)
    start, _ = month_bounds(previous)
    async with SessionLocal() as session:
        top_up = await wallet.record_payment(session, "TX1", Decimal("15"), None, None)
        top_up.created_at = start + timedelta(days=3)
        await wallet.record_payment(session, "TX2", Decimal("7"), None, None)
        await session.commit()
    # Last month: TX1 arrived unmatched; TX2 is this month.
    url = f"{API}/admin/finance/closings"
    label = format_month(previous)
    preview = await client.get(f"{url}/preview?month={label}", headers=staff_headers)
    assert preview.status_code == 200
    assert preview.json()["top_ups"]["unmatched"] == {"count": 1, "amount": "15.00"}

    forbidden = await client.post(url, json={"month": label}, headers=luis.headers)
    assert forbidden.status_code == 403
    current = await client.post(url, json={"month": format_month(_month(0))}, headers=admin_headers)
    assert current.status_code == 400 and current.json()["error"]["code"] == "month_open"
    closed = await client.post(url, json={"month": label}, headers=admin_headers)
    assert closed.status_code == 201, closed.text
    body = closed.json()
    assert body["hash_ok"] is True and body["previous_hash"] is None
    assert body["totals"]["balances"] == {"opening": "0.00", "closing": "0.00", "net": "0.00"}
    again = await client.post(url, json={"month": label}, headers=admin_headers)
    assert again.status_code == 409
    older = await client.post(url, json={"month": format_month(_month(-2))}, headers=admin_headers)
    assert older.json()["error"]["code"] == "closing_out_of_order"

    # Later movements land in the open month: the closing does not change.
    await _credit(luis, "30")
    listed = (await client.get(url, headers=staff_headers)).json()
    assert listed[0]["totals"] == body["totals"] and listed[0]["hash_ok"] is True

    csv = (
        "Order Type,Order ID,Time,Amount,Currency\n"
        f"C2C,TX1,{(start + timedelta(days=3)):%Y-%m-%d %H:%M:%S},15,USDT\n"
        f"C2C,TX9,{(start + timedelta(days=4)):%Y-%m-%d %H:%M:%S},4.5,USDT\n"
        f"C2C,TX8,{(start + timedelta(days=4)):%Y-%m-%d %H:%M:%S},-3,USDT\n"
        f"C2C,TX7,{(start + timedelta(days=4)):%Y-%m-%d %H:%M:%S},9,BNB\n"
    )
    reconcile = f"{url}/{label}/reconcile"
    early = await client.post(reconcile, json={}, headers=admin_headers)
    assert early.json()["error"]["code"] == "reconcile_note_required"
    bad = await client.post(
        f"{url}/{label}/statement", json={"csv": "a,b\n1,2"}, headers=admin_headers
    )
    assert bad.json()["error"]["code"] == "statement_invalid"
    uploaded = await client.post(
        f"{url}/{label}/statement", json={"csv": csv, "filename": "pay.csv"}, headers=admin_headers
    )
    assert uploaded.status_code == 200, uploaded.text
    diff = uploaded.json()["differences"]
    assert diff["matched"] == 1 and diff["statement_rows"] == 2
    assert [d["id"] for d in diff["missing_in_kuulis"]] == ["TX9"]
    assert diff["missing_in_binance"] == [] and uploaded.json()["has_differences"] is True
    assert (await client.post(reconcile, json={}, headers=admin_headers)).status_code == 400
    done = await client.post(
        reconcile, json={"note": "TX9 fue un pago personal"}, headers=admin_headers
    )
    assert done.status_code == 200 and done.json()["reconciled_at"]

    async with SessionLocal() as session:
        await session.execute(
            update(MonthlyClosing).values(totals=body["totals"] | {"fees_collected": "99.00"})
        )
        await session.commit()
    assert (await client.get(url, headers=staff_headers)).json()[0]["hash_ok"] is False


def test_parse_statement_spanish_semicolons():
    rows = finance.parse_statement(
        "﻿Fecha;ID de transacción;Monto;Moneda\n2026-09-02 10:00:00;A1;12,50;USDT\n"
        "2026-09-02 11:00:00;A2;+3 USDT;\n"
    )
    assert [(r["id"], r["amount"]) for r in rows] == [
        ("A1", Decimal("12.50")),
        ("A2", Decimal("3.00")),
    ]


# --- Invariants --------------------------------------------------------------------------------


async def test_invariants_alert_on_a_mismatch(client, admin_headers, staff_headers, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _credit(luis, "10")
    ran = await client.post(f"{API}/admin/finance/invariants/run", headers=admin_headers)
    assert ran.status_code == 200 and ran.json()["ok"] is True and ran.json()["wallets"] == 1

    async with SessionLocal() as session:  # a balance changed behind the ledger's back
        await session.execute(update(Wallet).values(balance=Decimal("12.00")))
        await session.commit()
    async with SessionLocal() as session:
        result = await finance.run_invariants(session)
    kinds = {i["kind"] for i in result["issues"]}
    assert result["ok"] is False and kinds == {"balance_mismatch", "last_entry_mismatch"}
    last = (await client.get(f"{API}/admin/finance/invariants", headers=staff_headers)).json()
    assert last["ok"] is False and len(last["issues"]) == 2
    async with SessionLocal() as session:
        health = await checks.collect(session)
    assert health.ledger is not None and health.ledger.issues == 2
    assert any(p.key == "ledger:invariants" for p in checks.problems(health))


async def test_duplicate_top_up_is_an_issue(client, admin_headers, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    for _ in range(2):  # the same Binance order confirmed twice by hand
        top_up_id = await _top_up(client, luis, reference="SAME1")
        await client.post(
            f"{API}/admin/top-ups/{top_up_id}/confirm", json={"amount": "10"}, headers=admin_headers
        )
    async with SessionLocal() as session:
        result = await finance.check_invariants(session)
    assert [i["kind"] for i in result["issues"]] == ["duplicate_top_up"]


# --- Binance fallback --------------------------------------------------------------------------


async def test_binance_failing_switches_to_manual(client, monkeypatch, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    monkeypatch.setattr(binance, "enabled", lambda: True)
    await stats.redis_client.hset(stats.HEARTBEATS_KEY, "binance", time.time())
    info = (await client.get(f"{API}/wallet/top-up-info", headers=luis.headers)).json()
    assert info["automatic"] is True and info["manual_reason"] is None

    for name in checks.expected_loops():
        await stats.redis_client.hset(stats.HEARTBEATS_KEY, name, time.time())
    await stats.redis_client.hset(stats.HEARTBEATS_KEY, "binance", time.time() - 11 * 60)
    info = (await client.get(f"{API}/wallet/top-up-info", headers=luis.headers)).json()
    assert info["automatic"] is False and info["manual_reason"] == "binance_down"
    async with SessionLocal() as session:
        health = await checks.collect(session)
    found = {p.key: p.message for p in checks.problems(health)}
    assert "confirmación manual" in found["loop:binance"]


# --- Disputes ----------------------------------------------------------------------------------


async def test_dispute_a_top_up(client, admin_headers, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    top_up_id = await _top_up(client, luis, reference=None)
    shot = storage.build_key(f"uploads/{luis.user.id}", "binance.jpg")
    url = f"{API}/wallet/me/top-ups/{top_up_id}/dispute"
    body = {"transaction_id": " 3301 2299 ", "attachments": [shot], "note": "Pagué ayer"}
    disputed = await client.post(url, json=body, headers=luis.headers)
    assert disputed.status_code == 201, disputed.text
    assert disputed.json()["reference"] == "33012299" and disputed.json()["dispute_report_id"]
    again = await client.post(url, json=body, headers=luis.headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "top_up_dispute_open"

    async with SessionLocal() as session:
        report = await session.scalar(select(Report))
    assert report.category == ReportCategory.PAYMENT and report.priority == ReportPriority.URGENT
    assert "33012299" in report.description and report.reporter_id == luis.user.id
    detail = await client.get(f"{API}/admin/reports/{report.id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["top_up"]["id"] == top_up_id

    confirmed = await client.post(
        f"{API}/admin/top-ups/{top_up_id}/confirm", json={"amount": "10"}, headers=admin_headers
    )
    assert confirmed.status_code == 200
    late = await client.post(url, json=body, headers=luis.headers)
    assert late.json()["error"]["code"] == "top_up_dispute_not_allowed"
    ana = await make_driver(client, "ana@example.com", "Ana Ruiz")
    foreign = await client.post(url, json=body, headers=ana.headers)
    assert foreign.status_code == 404


# --- Waivers and the simulator -----------------------------------------------------------------


async def _two_charges(client):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    ana = await make_driver(client, "ana@example.com", "Ana Ruiz")
    await _ride(luis, "150", -1)  # 5.00, pending
    await _ride(ana, "250", -1)  # 10.00, paid
    await _credit(ana, "12")
    await _charge_last_month(luis, ana)
    async with SessionLocal() as session:
        charges = {
            c.user_id: c
            for c in await session.scalars(select(Charge).where(Charge.month == _month(-1)))
        }
    return luis, ana, charges[luis.user.id], charges[ana.user.id]


async def test_waivers_need_a_second_person(client, admin_headers, recorder):
    _, ana, pending, paid = await _two_charges(client)
    await _make_user("admin2@example.com", Role.ADMIN)
    other = await _login(client, "admin2@example.com")
    url = f"{API}/admin/subscriptions/charges"

    higher = await client.post(
        f"{url}/{pending.id}/waive", json={"reason": "x", "fee": "5"}, headers=admin_headers
    )
    assert higher.json()["error"]["code"] == "fee_not_lower"
    held = await client.post(
        f"{url}/{pending.id}/waive", json={"reason": "Moto robada"}, headers=admin_headers
    )
    assert held.status_code == 202, held.text
    approval = held.json()["approval"]["id"]
    approved = await client.post(
        f"{API}/admin/approvals/{approval}/approve", json={}, headers=other
    )
    assert approved.status_code == 200, approved.text
    async with SessionLocal() as session:
        waived = await session.get(Charge, pending.id)
        assert waived.status == ChargeStatus.WAIVED and waived.original_fee == Decimal("5.00")

    await set_config(approval_waivers=False)
    reduced = await client.post(
        f"{url}/{paid.id}/waive",
        json={"reason": "Error de tramo", "fee": "4"},
        headers=admin_headers,
    )
    assert reduced.status_code == 200, reduced.text
    assert reduced.json()["fee"] == "4.00" and reduced.json()["original_fee"] == "10.00"
    assert reduced.json()["status"] == "paid"
    async with SessionLocal() as session:
        refund = await session.scalar(
            select(WalletEntry)
            .join(Wallet, Wallet.id == WalletEntry.wallet_id)
            .where(Wallet.user_id == ana.user.id, WalletEntry.kind == EntryKind.ADJUSTMENT)
            .order_by(WalletEntry.created_at.desc())
            .limit(1)
        )
    assert refund.amount == Decimal("6.00") and refund.details["fee_refund"] is True
    assert (await client.get(f"{API}/wallet/me", headers=ana.headers)).json()["balance"] == "8.00"


async def test_simulator_reproduces_last_month(client, staff_headers, recorder):
    await _two_charges(client)
    url = f"{API}/admin/subscriptions/simulate"
    same = (await client.post(url, json={}, headers=staff_headers)).json()
    assert same["drivers"] == 2 and same["billed"] == "15.00"
    assert same["matches"] is True and same["current_total"] == "15.00"
    assert same["difference"] == "0.00"
    proposed = [{"above": "0", "fee": "0"}, {"above": "100", "fee": "8"}]
    body = (
        await client.post(
            url, json={"month": format_month(_month(-1)), "tiers": proposed}, headers=staff_headers
        )
    ).json()
    assert body["proposed_total"] == "16.00" and body["difference"] == "1.00"
    assert [t["drivers"] for t in body["proposed"]] == [0, 2]
    bad = await client.post(
        url, json={"tiers": [{"above": "50", "fee": "1"}]}, headers=staff_headers
    )
    assert bad.status_code == 422 or bad.status_code == 400


async def test_receipt_rows_survive_in_db(client, admin_headers, recorder):
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    top_up_id = await _top_up(client, luis)
    await client.post(
        f"{API}/admin/top-ups/{top_up_id}/confirm", json={"amount": "10"}, headers=admin_headers
    )
    async with SessionLocal() as session:
        receipt = await session.scalar(select(Receipt))
        top_up = await session.get(TopUp, top_up_id)
    assert receipt.entry_id == top_up.entry_id and receipt.user_id == luis.user.id


async def test_statement_email_waits_for_the_charges(client, monkeypatch, recorder):
    from apps.notifications import tasks
    from apps.subscriptions import tasks as subscription_tasks
    from kuulis.core.redis import redis_client

    sent: list[tuple[str, str, dict]] = []

    class Fake:
        async def kiq(self, user_id, name, values):
            sent.append((user_id, name, values))

    monkeypatch.setattr(tasks, "send_user_email", Fake())
    luis = await make_driver(client, "luis@example.com", "Luis Gómez")
    await _ride(luis, "250", -1)
    await _credit(luis, "20")
    assert await tasks.run_monthly_once() is None  # fees not charged yet
    await _charge_last_month(luis)
    await redis_client.set(subscription_tasks._done_key(format_month(_month(-1))), "1")
    assert await tasks.run_monthly_once() == 1
    assert await tasks.run_monthly_once() is None  # once a month
    [(user_id, values)] = [(u, v) for u, n, v in sent if n == "monthly_summary"]
    assert user_id == str(luis.user.id)
    assert values["fee"] == "10.00" and values["tier"] == "200.00" and values["rides"] == "1"
