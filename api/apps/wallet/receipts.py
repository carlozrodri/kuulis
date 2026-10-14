"""Non-fiscal receipts (doc 17): one per credited top-up and per paid monthly fee, written in the
same transaction as the ledger entry. Kuulis has no company yet, so they say "no fiscal"."""

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.users.models import User
from apps.wallet.models import Receipt, ReceiptKind, WalletEntry
from kuulis.core.exceptions import NotFoundError


class ReceiptNotFoundError(NotFoundError):
    code = "receipt_not_found"
    message = "Receipt not found"


def concept(kind: ReceiptKind, locale: str, month: date | None = None) -> str:
    from apps.wallet.notify import month_label

    en = locale == "en"
    if kind == ReceiptKind.TOP_UP:
        return "Wallet top-up (Binance Pay)" if en else "Recarga de billetera (Binance Pay)"
    label = month_label(month, locale) if month else ""
    return f"Monthly fee for {label}" if en else f"Cuota mensual de {label}"


def number_label(number: int) -> str:
    return f"{number:06d}"


async def issue(
    session: AsyncSession,
    entry: WalletEntry,
    user_id: uuid.UUID,
    kind: ReceiptKind,
    *,
    month: date | None = None,
    reference: str | None = None,
) -> Receipt:
    user = await session.get(User, user_id)
    receipt = Receipt(
        user_id=user_id,
        entry_id=entry.id,
        kind=kind,
        amount=abs(entry.amount),
        balance_after=entry.balance_after,
        concept=concept(kind, user.locale if user else "es", month)[:200],
        reference=(reference or None) and reference[:64],
        issued_at=datetime.now(UTC),
    )
    session.add(receipt)
    await session.flush()
    return receipt


async def email_values(session: AsyncSession, entry_id: uuid.UUID | None) -> dict[str, str]:
    """``receipt`` and ``balance`` for the emails that double as receipts."""
    if entry_id is None:
        return {}
    receipt = await session.scalar(select(Receipt).where(Receipt.entry_id == entry_id))
    if receipt is None:
        return {}
    return {"receipt": number_label(receipt.number), "balance": f"{receipt.balance_after:.2f}"}


async def for_entries(session: AsyncSession, entry_ids: Iterable[uuid.UUID]) -> dict:
    ids = list(entry_ids)
    if not ids:
        return {}
    rows = await session.execute(
        select(Receipt.entry_id, Receipt.id).where(Receipt.entry_id.in_(ids))
    )
    return dict(rows.all())


async def get_mine(session: AsyncSession, user_id: uuid.UUID, receipt_id: uuid.UUID) -> Receipt:
    receipt = await session.get(Receipt, receipt_id)
    if receipt is None or receipt.user_id != user_id:
        raise ReceiptNotFoundError()
    return receipt
