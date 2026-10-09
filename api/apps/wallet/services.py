"""Wallet ledger. Every movement goes through ``post_entry`` inside the caller's transaction."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.wallet.models import EntryKind, Wallet, WalletEntry
from kuulis.core.pagination import PageParams, paginate

ZERO = Decimal("0.00")


async def get_balance(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    balance = await session.scalar(select(Wallet.balance).where(Wallet.user_id == user_id))
    return balance if balance is not None else ZERO


async def _lock_wallet(session: AsyncSession, user_id: uuid.UUID) -> Wallet:
    await session.execute(
        insert(Wallet)
        .values(id=uuid.uuid4(), user_id=user_id, balance=ZERO)
        .on_conflict_do_nothing(index_elements=[Wallet.user_id])
    )
    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
    assert wallet is not None
    return wallet


async def post_entry(
    session: AsyncSession,
    user_id: uuid.UUID,
    kind: EntryKind,
    amount: Decimal,
    *,
    ride_id: uuid.UUID | None = None,
    promotion_id: uuid.UUID | None = None,
    description: str = "",
    details: dict | None = None,
) -> WalletEntry:
    """Adds ``amount`` (negative to debit) and returns the entry. The caller commits."""
    wallet = await _lock_wallet(session, user_id)
    wallet.balance = (wallet.balance + amount).quantize(Decimal("0.01"))
    entry = WalletEntry(
        wallet_id=wallet.id,
        kind=kind,
        amount=amount,
        balance_after=wallet.balance,
        ride_id=ride_id,
        promotion_id=promotion_id,
        description=description[:200],
        details=details or {},
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_entries(
    session: AsyncSession, user_id: uuid.UUID, params: PageParams
) -> tuple[list[WalletEntry], int]:
    stmt = (
        select(WalletEntry)
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .where(Wallet.user_id == user_id)
        .order_by(WalletEntry.created_at.desc(), WalletEntry.id)
    )
    return await paginate(session, stmt, params)
