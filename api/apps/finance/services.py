"""Monthly closings, Binance statement reconciliation and the daily ledger invariants (doc 17)."""

import csv
import hashlib
import io
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import orjson
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.finance.models import MonthlyClosing
from apps.subscriptions.models import Charge, ChargeStatus
from apps.users.models import User
from apps.wallet.models import EntryKind, TopUp, TopUpStatus, Wallet, WalletEntry
from kuulis.core.calendar import format_month, local_now, month_bounds, month_start
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError
from kuulis.core.redis import redis_client
from kuulis.settings import settings

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
INVARIANTS_KEY = f"{settings.APP_ENV}:finance:invariants"
MAX_ISSUES = 50


class MonthOpenError(AppError):
    code = "month_open"
    message = "Only months that already ended can be closed"


class MonthClosedError(ConflictError):
    code = "month_already_closed"
    message = "This month is already closed"


class ClosingOrderError(ConflictError):
    code = "closing_out_of_order"
    message = "A later month is already closed"


class ClosingNotFoundError(NotFoundError):
    code = "closing_not_found"
    message = "This month is not closed"


class StatementInvalidError(AppError):
    code = "statement_invalid"
    message = "The file does not look like a Binance Pay history"


class AlreadyReconciledError(ConflictError):
    code = "closing_reconciled"
    message = "This month was already reconciled"


class NoteRequiredError(AppError):
    code = "reconcile_note_required"
    message = "Explain the differences before marking the month as reconciled"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _money(value: Any) -> str:
    return f"{Decimal(value or 0).quantize(CENT):.2f}"


# --- Totals -----------------------------------------------------------------------------------


async def month_totals(session: AsyncSession, month: date) -> dict[str, Any]:
    """Everything that moved in the ledger during a Caracas month, as JSON-ready strings."""
    start, end = month_bounds(month)
    in_month = (WalletEntry.created_at >= start, WalletEntry.created_at < end)
    rows = await session.execute(
        select(
            WalletEntry.kind,
            func.count(WalletEntry.id),
            func.sum(func.greatest(WalletEntry.amount, 0)),
            func.sum(func.least(WalletEntry.amount, 0)),
        )
        .where(*in_month)
        .group_by(WalletEntry.kind)
    )
    found = {kind: (count, plus, minus) for kind, count, plus, minus in rows}
    entries = {
        kind.value: {
            "count": int(found.get(kind, (0,))[0]),
            "credits": _money(found.get(kind, (0, 0, 0))[1]),
            "debits": _money(found.get(kind, (0, 0, 0))[2]),
        }
        for kind in EntryKind
    }

    async def balance_before(moment: datetime) -> Decimal:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletEntry.amount), 0)).where(
                WalletEntry.created_at < moment
            )
        )
        return Decimal(total or 0)

    opening, closing = await balance_before(start), await balance_before(end)

    async def top_ups(*where: Any) -> dict[str, Any]:
        count, amount = (
            await session.execute(
                select(func.count(TopUp.id), func.sum(TopUp.amount)).where(*where)
            )
        ).one()
        return {"count": int(count or 0), "amount": _money(amount)}

    completed = (
        TopUp.status == TopUpStatus.COMPLETED,
        TopUp.entry_id.is_not(None),
        TopUp.completed_at >= start,
        TopUp.completed_at < end,
    )
    created = (TopUp.created_at >= start, TopUp.created_at < end)
    charges = {
        status.value: {"count": int(count or 0), "fees": _money(fees)}
        for status, count, fees in await session.execute(
            select(Charge.status, func.count(Charge.id), func.sum(Charge.fee))
            .where(Charge.created_at >= start, Charge.created_at < end)
            .group_by(Charge.status)
        )
    }
    return {
        "entries": entries,
        "top_ups": {
            "credited": await top_ups(*completed),
            "credited_auto": await top_ups(*completed, TopUp.reviewed_by_id.is_(None)),
            "credited_manual": await top_ups(*completed, TopUp.reviewed_by_id.is_not(None)),
            "unmatched": await top_ups(TopUp.status == TopUpStatus.UNMATCHED, *created),
        },
        # Fees billed this month (the 1st bills the month before), by status at closing time.
        "charges": {
            s.value: charges.get(s.value, {"count": 0, "fees": "0.00"}) for s in ChargeStatus
        },
        "fees_collected": _money(-Decimal(entries[EntryKind.SUBSCRIPTION_FEE.value]["debits"])),
        "balances": {
            "opening": _money(opening),
            "closing": _money(closing),
            "net": _money(closing - opening),
        },
    }


def closing_hash(month: date, totals: dict[str, Any], previous: str | None) -> str:
    body = orjson.dumps(
        {"month": format_month(month), "totals": totals, "previous": previous},
        option=orjson.OPT_SORT_KEYS,
    )
    return hashlib.sha256(body).hexdigest()


async def list_closings(session: AsyncSession) -> list[tuple[MonthlyClosing, bool]]:
    """Newest first, each with whether its hash (and the chain up to it) still checks out."""
    rows = list(await session.scalars(select(MonthlyClosing).order_by(MonthlyClosing.month)))
    result, previous, chain_ok = [], None, True
    for row in rows:
        ok = (
            chain_ok
            and row.previous_hash == previous
            and row.hash == closing_hash(row.month, row.totals, row.previous_hash)
        )
        chain_ok = ok
        result.append((row, ok))
        previous = row.hash
    return list(reversed(result))


async def get_closing(session: AsyncSession, month: date) -> MonthlyClosing:
    row = await session.scalar(
        select(MonthlyClosing).where(MonthlyClosing.month == month_start(month))
    )
    if row is None:
        raise ClosingNotFoundError()
    return row


async def close_month(session: AsyncSession, admin: User, month: date) -> MonthlyClosing:
    month = month_start(month)
    if month >= month_start(local_now()):
        raise MonthOpenError()
    latest = await session.scalar(
        select(MonthlyClosing).order_by(MonthlyClosing.month.desc()).limit(1)
    )
    if latest is not None and latest.month == month:
        raise MonthClosedError()
    if latest is not None and latest.month > month:
        exists = await session.scalar(
            select(MonthlyClosing.id).where(MonthlyClosing.month == month)
        )
        raise MonthClosedError() if exists else ClosingOrderError()
    totals = await month_totals(session, month)
    previous = latest.hash if latest else None
    row = MonthlyClosing(
        month=month,
        totals=totals,
        hash=closing_hash(month, totals, previous),
        previous_hash=previous,
        closed_by_id=admin.id,
        closed_at=utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


# --- Binance statement ------------------------------------------------------------------------

_ID_COLUMNS = ("transaction id", "transactionid", "order id", "orderid", "order no", "id")
_AMOUNT_COLUMNS = ("amount", "monto", "importe")
_CURRENCY_COLUMNS = ("currency", "coin", "asset", "moneda")
_TIME_COLUMNS = ("time", "date", "transaction time", "create time", "fecha", "hora")
_NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def _column(headers: list[str], names: tuple[str, ...]) -> int | None:
    lowered = [h.strip().lower().replace("_", " ") for h in headers]
    for name in names:
        if name in lowered:
            return lowered.index(name)
    for name in names:
        for index, header in enumerate(lowered):
            if name in header:
                return index
    return None


def _amount(text: str) -> Decimal | None:
    """ "15", "-3", "1,234.50", "12,50" (decimal comma) or "4.5 USDT"."""
    match = _NUMBER.search(text or "")
    if not match:
        return None
    raw = match.group()
    if "," in raw and "." not in raw and len(raw.rsplit(",", 1)[1]) <= 2:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw.replace(",", "")).quantize(CENT)
    except InvalidOperation:
        return None


def _when(text: str) -> datetime | None:
    text = (text or "").strip()
    if text.isdigit() and len(text) >= 12:  # milliseconds since the epoch
        return datetime.fromtimestamp(int(text) / 1000, UTC)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse_statement(text: str) -> list[dict[str, Any]]:
    """Incoming USDT rows of a Binance Pay history export: {id, amount, at}. Binance changes its
    column names now and then, so columns are found by name, in English or Spanish."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text.lstrip("﻿")), dialect)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if len(rows) < 1:
        raise StatementInvalidError()
    headers, body = rows[0], rows[1:]
    id_col = _column(headers, _ID_COLUMNS)
    amount_col = _column(headers, _AMOUNT_COLUMNS)
    if id_col is None or amount_col is None:
        raise StatementInvalidError(details={"headers": headers[:20]})
    currency_col = _column(headers, _CURRENCY_COLUMNS)
    time_col = _column(headers, _TIME_COLUMNS)
    result = []
    for row in body:
        if len(row) <= max(id_col, amount_col):
            continue
        amount = _amount(row[amount_col])
        currency = row[currency_col].strip().upper() if currency_col is not None else "USDT"
        if "USDT" in row[amount_col].upper():
            currency = "USDT"
        if amount is None or amount <= 0 or currency != "USDT":
            continue
        at = _when(row[time_col]) if time_col is not None and time_col < len(row) else None
        result.append({"id": row[id_col].strip(), "amount": amount, "at": at})
    return result


async def _kuulis_payments(session: AsyncSession, month: date) -> list[TopUp]:
    """Top-ups of the month that should be in Binance: credited ones and unmatched payments."""
    start, end = month_bounds(month)
    return list(
        await session.scalars(
            select(TopUp).where(
                or_(
                    and_(
                        TopUp.status == TopUpStatus.COMPLETED,
                        TopUp.entry_id.is_not(None),
                        TopUp.completed_at >= start,
                        TopUp.completed_at < end,
                    ),
                    and_(
                        TopUp.status == TopUpStatus.UNMATCHED,
                        TopUp.created_at >= start,
                        TopUp.created_at < end,
                    ),
                )
            )
        )
    )


def compare(statement: list[dict[str, Any]], payments: list[TopUp], month: date) -> dict[str, Any]:
    start, end = month_bounds(month)
    rows = [r for r in statement if r["at"] is None or start <= r["at"] < end]
    by_id = {r["id"]: r for r in rows}
    seen: set[str] = set()
    missing_in_binance, mismatch = [], []
    for top_up in payments:
        ids = [i for i in (top_up.transaction_id, top_up.reference) if i]
        match = next((by_id[i] for i in ids if i in by_id), None)
        item = {
            "top_up_id": str(top_up.id),
            "id": ids[0] if ids else None,
            "amount": _money(top_up.amount),
            "status": top_up.status.value,
        }
        if match is None:
            missing_in_binance.append(item | {"reason": "not_found" if ids else "no_reference"})
            continue
        seen.add(match["id"])
        if match["amount"] != top_up.amount:
            mismatch.append(item | {"binance_amount": _money(match["amount"])})
    missing_in_kuulis = [
        {
            "id": r["id"],
            "amount": _money(r["amount"]),
            "at": r["at"].isoformat() if r["at"] else None,
        }
        for r in rows
        if r["id"] not in seen
    ]
    return {
        "statement_rows": len(rows),
        "statement_total": _money(sum((r["amount"] for r in rows), ZERO)),
        "kuulis_rows": len(payments),
        "kuulis_total": _money(sum((t.amount for t in payments), ZERO)),
        "matched": len(seen),
        "missing_in_kuulis": missing_in_kuulis[:500],
        "missing_in_binance": missing_in_binance[:500],
        "amount_mismatch": mismatch[:500],
    }


def has_differences(differences: dict[str, Any] | None) -> bool:
    return bool(
        differences
        and (
            differences.get("missing_in_kuulis")
            or differences.get("missing_in_binance")
            or differences.get("amount_mismatch")
        )
    )


async def upload_statement(
    session: AsyncSession, month: date, text: str, filename: str | None
) -> MonthlyClosing:
    import asyncio

    from kuulis.core import storage

    closing = await get_closing(session, month)
    if closing.reconciled_at is not None:
        raise AlreadyReconciledError()
    rows = parse_statement(text)
    closing.differences = compare(rows, await _kuulis_payments(session, closing.month), month)
    closing.statement_uploaded_at = utcnow()
    if settings.storage_enabled:
        key = storage.build_key(
            f"finance/statements/{format_month(closing.month)}", filename or "binance.csv"
        )
        await asyncio.to_thread(storage.put_object, key, text.encode(), "text/csv")
        closing.binance_statement_key = key
    await session.flush()
    return closing


async def reconcile(
    session: AsyncSession, admin: User, month: date, note: str | None
) -> MonthlyClosing:
    closing = await get_closing(session, month)
    if closing.reconciled_at is not None:
        raise AlreadyReconciledError()
    if closing.differences is None or (has_differences(closing.differences) and not note):
        raise NoteRequiredError()
    closing.reconciled_at = utcnow()
    closing.reconciled_by_id = admin.id
    closing.reconcile_note = note
    await session.flush()
    return closing


# --- Ledger invariants ------------------------------------------------------------------------


async def check_invariants(session: AsyncSession) -> dict[str, Any]:
    """The books must add up: every wallet's balance is the sum of its entries and its last
    ``balance_after``, nothing is negative, each Binance payment is credited at most once and
    every paid fee has its debit."""
    issues: list[dict[str, Any]] = []
    sums = (
        select(WalletEntry.wallet_id, func.sum(WalletEntry.amount).label("total"))
        .group_by(WalletEntry.wallet_id)
        .subquery()
    )
    for wallet_id, user_id, balance, total in await session.execute(
        select(Wallet.id, Wallet.user_id, Wallet.balance, func.coalesce(sums.c.total, 0))
        .outerjoin(sums, sums.c.wallet_id == Wallet.id)
        .where(Wallet.balance != func.coalesce(sums.c.total, 0))
        .limit(MAX_ISSUES)
    ):
        issues.append(
            {
                "kind": "balance_mismatch",
                "user_id": str(user_id),
                "wallet_id": str(wallet_id),
                "balance": _money(balance),
                "entries": _money(total),
            }
        )
    last = (
        select(WalletEntry.wallet_id, WalletEntry.balance_after)
        .distinct(WalletEntry.wallet_id)
        .order_by(WalletEntry.wallet_id, WalletEntry.created_at.desc(), WalletEntry.id.desc())
        .subquery()
    )
    for user_id, balance, after in await session.execute(
        select(Wallet.user_id, Wallet.balance, last.c.balance_after)
        .join(last, last.c.wallet_id == Wallet.id)
        .where(last.c.balance_after != Wallet.balance)
        .limit(MAX_ISSUES)
    ):
        issues.append(
            {
                "kind": "last_entry_mismatch",
                "user_id": str(user_id),
                "balance": _money(balance),
                "balance_after": _money(after),
            }
        )
    for user_id, balance in await session.execute(
        select(Wallet.user_id, Wallet.balance).where(Wallet.balance < 0).limit(MAX_ISSUES)
    ):
        issues.append(
            {"kind": "negative_balance", "user_id": str(user_id), "balance": _money(balance)}
        )
    payment_id = func.coalesce(TopUp.transaction_id, TopUp.reference)
    for ident, count in await session.execute(
        select(payment_id, func.count(TopUp.id))
        .where(TopUp.entry_id.is_not(None), payment_id.is_not(None))
        .group_by(payment_id)
        .having(func.count(TopUp.id) > 1)
        .limit(MAX_ISSUES)
    ):
        issues.append({"kind": "duplicate_top_up", "id": ident, "count": int(count)})
    for top_up_id, user_id in await session.execute(
        select(TopUp.id, TopUp.user_id)
        .where(
            TopUp.status == TopUpStatus.COMPLETED,
            TopUp.transaction_id.is_not(None),
            TopUp.entry_id.is_(None),
        )
        .limit(MAX_ISSUES)
    ):
        issues.append(
            {"kind": "top_up_without_entry", "top_up_id": str(top_up_id), "user_id": str(user_id)}
        )
    for charge_id, user_id in await session.execute(
        select(Charge.id, Charge.user_id)
        .where(Charge.status == ChargeStatus.PAID, Charge.fee > 0, Charge.entry_id.is_(None))
        .limit(MAX_ISSUES)
    ):
        issues.append(
            {"kind": "fee_without_entry", "charge_id": str(charge_id), "user_id": str(user_id)}
        )
    wallets = await session.scalar(select(func.count(Wallet.id)))
    return {
        "ok": not issues,
        "checked_at": utcnow().isoformat(),
        "wallets": int(wallets or 0),
        "issues": issues[:MAX_ISSUES],
    }


async def run_invariants(session: AsyncSession) -> dict[str, Any]:
    result = await check_invariants(session)
    await redis_client.set(INVARIANTS_KEY, orjson.dumps(result))
    return result


async def last_invariants() -> dict[str, Any] | None:
    raw = await redis_client.get(INVARIANTS_KEY)
    return orjson.loads(raw) if raw else None


def brief_ids(rows: list[MonthlyClosing]) -> set[uuid.UUID]:
    ids = set()
    for row in rows:
        ids |= {i for i in (row.closed_by_id, row.reconciled_by_id) if i}
    return ids
