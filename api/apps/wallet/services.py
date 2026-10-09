"""Wallet ledger. Every movement goes through ``post_entry`` inside the caller's transaction.

Money coming in (``credit``) also tries to collect pending subscription fees, so a driver who
tops up after the 1st is unblocked right away.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.config.schemas import AppConfig
from apps.drivers.models import DriverProfile, DriverStatus
from apps.users.models import User
from apps.wallet import notify
from apps.wallet.models import EntryKind, TopUp, TopUpMethod, TopUpStatus, Wallet, WalletEntry
from apps.wallet.schemas import TransferLimit
from kuulis.core.calendar import local_now, month_bounds, month_start
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from kuulis.core.pagination import PageParams, paginate

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
MAX_PENDING_TOP_UPS = 3


# --- Errors (codes are part of the API contract) -----------------------------------------------


class InsufficientBalanceError(ConflictError):
    code = "insufficient_balance"
    message = "Not enough balance"


class TransferLimitExceededError(ConflictError):
    code = "transfer_limit_exceeded"
    message = "This transfer goes over the monthly limit"


class RecipientNotFoundError(NotFoundError):
    code = "recipient_not_found"
    message = "No driver with that email or phone"


class TransferToSelfError(AppError):
    code = "transfer_to_self"
    message = "You cannot transfer to yourself"


class BinancePayIdTakenError(ConflictError):
    code = "binance_pay_id_taken"
    message = "Another account already uses this Binance Pay ID"


class TooManyPendingTopUpsError(ConflictError):
    code = "too_many_pending_top_ups"
    message = "Wait until your pending top-ups are confirmed"


class TopUpNotFoundError(NotFoundError):
    code = "top_up_not_found"
    message = "Top-up not found"


class TopUpInvalidStatusError(ConflictError):
    code = "top_up_invalid_status"
    message = "The top-up cannot do that in its current status"


class NotADriverError(PermissionDeniedError):
    code = "not_a_driver"
    message = "Only drivers have a wallet"


class AmountTooLowError(AppError):
    code = "amount_too_low"
    message = "The amount is below the minimum"


# --- Basics ------------------------------------------------------------------------------------


def short_name(user: User | None) -> str:
    """ "Luis G." (first name and last initial)."""
    if user is None:
        return ""
    parts = (user.full_name or "").split()
    if not parts:
        return user.email.split("@")[0]
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else parts[0]


async def require_driver(session: AsyncSession, user_id: uuid.UUID) -> DriverProfile:
    profile = await session.scalar(select(DriverProfile).where(DriverProfile.user_id == user_id))
    if profile is None:
        raise NotADriverError()
    return profile


async def get_wallet(session: AsyncSession, user_id: uuid.UUID) -> Wallet | None:
    return await session.scalar(select(Wallet).where(Wallet.user_id == user_id))


async def get_balance(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    balance = await session.scalar(select(Wallet.balance).where(Wallet.user_id == user_id))
    return balance if balance is not None else ZERO


async def lock_wallet(session: AsyncSession, user_id: uuid.UUID) -> Wallet:
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
    counterpart_user_id: uuid.UUID | None = None,
    created_by_id: uuid.UUID | None = None,
    description: str = "",
    details: dict | None = None,
) -> WalletEntry:
    """Adds ``amount`` (negative to debit) and returns the entry. The caller commits."""
    wallet = await lock_wallet(session, user_id)
    balance = (wallet.balance + amount).quantize(CENT)
    if balance < 0:
        raise InsufficientBalanceError(details={"balance": f"{wallet.balance:.2f}"})
    wallet.balance = balance
    entry = WalletEntry(
        wallet_id=wallet.id,
        kind=kind,
        amount=amount,
        balance_after=balance,
        ride_id=ride_id,
        promotion_id=promotion_id,
        counterpart_user_id=counterpart_user_id,
        created_by_id=created_by_id,
        description=description[:200],
        details=details or {},
    )
    session.add(entry)
    await session.flush()
    return entry


async def credit(
    session: AsyncSession, user_id: uuid.UUID, kind: EntryKind, amount: Decimal, **kw
) -> WalletEntry:
    """A positive entry, then collect any pending subscription fee."""
    from apps.subscriptions import services as subscriptions  # circular: they debit wallets

    entry = await post_entry(session, user_id, kind, amount, **kw)
    await subscriptions.collect_pending(session, user_id)
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


async def set_binance_pay_id(session: AsyncSession, user: User, pay_id: str) -> Wallet:
    await require_driver(session, user.id)
    wallet = await lock_wallet(session, user.id)
    taken = await session.scalar(
        select(Wallet.id).where(Wallet.binance_pay_id == pay_id, Wallet.user_id != user.id)
    )
    if taken:
        raise BinancePayIdTakenError()
    wallet.binance_pay_id = pay_id
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise BinancePayIdTakenError() from exc
    return wallet


# --- Transfers ---------------------------------------------------------------------------------


async def sent_this_month(session: AsyncSession, user_id: uuid.UUID) -> Decimal:
    start, end = month_bounds(month_start(local_now()))
    total = await session.scalar(
        select(func.coalesce(func.sum(-WalletEntry.amount), 0))
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .where(
            Wallet.user_id == user_id,
            WalletEntry.kind == EntryKind.TRANSFER_OUT,
            WalletEntry.created_at >= start,
            WalletEntry.created_at < end,
        )
    )
    return Decimal(total or 0).quantize(CENT)


async def transfer_limit(
    session: AsyncSession, user_id: uuid.UUID, config: AppConfig
) -> TransferLimit:
    sent = await sent_this_month(session, user_id)
    limit = config.transfer_monthly_limit
    return TransferLimit(limit=limit, sent_this_month=sent, available=max(ZERO, limit - sent))


async def find_recipient(session: AsyncSession, query: str) -> User:
    query = query.strip()
    phone = "".join(ch for ch in query if ch.isdigit() or ch == "+")
    conditions = [func.lower(User.email) == query.lower()]
    if len(phone) >= 7:
        # Accept 04121234567, 4121234567 and +584121234567 for the same phone.
        digits = phone.lstrip("+").removeprefix("58").lstrip("0")
        conditions.append(func.right(DriverProfile.phone, len(digits)) == digits)
    user = await session.scalar(
        select(User)
        .join(DriverProfile, DriverProfile.user_id == User.id)
        .where(
            or_(*conditions),
            User.is_active,
            DriverProfile.status.in_([DriverStatus.APPROVED, DriverStatus.SUSPENDED]),
        )
        .limit(1)
    )
    if user is None:
        raise RecipientNotFoundError()
    return user


async def transfer(
    session: AsyncSession,
    sender: User,
    to_user_id: uuid.UUID,
    amount: Decimal,
    note: str | None,
    config: AppConfig,
) -> WalletEntry:
    await require_driver(session, sender.id)
    if to_user_id == sender.id:
        raise TransferToSelfError()
    recipient = await session.get(User, to_user_id)
    profile = await session.scalar(select(DriverProfile).where(DriverProfile.user_id == to_user_id))
    if (
        recipient is None
        or not recipient.is_active
        or profile is None
        or profile.status not in (DriverStatus.APPROVED, DriverStatus.SUSPENDED)
    ):
        raise RecipientNotFoundError()
    # Lock both wallets in a fixed order so two crossed transfers cannot deadlock.
    for user_id in sorted([sender.id, to_user_id]):
        await lock_wallet(session, user_id)
    limit = await transfer_limit(session, sender.id, config)
    if amount > limit.available:
        raise TransferLimitExceededError(details=limit.model_dump(mode="json"))
    sent = await post_entry(
        session,
        sender.id,
        EntryKind.TRANSFER_OUT,
        -amount,
        counterpart_user_id=recipient.id,
        details={"counterpart_name": short_name(recipient), "note": note},
    )
    await credit(
        session,
        recipient.id,
        EntryKind.TRANSFER_IN,
        amount,
        counterpart_user_id=sender.id,
        details={"counterpart_name": short_name(sender), "note": note},
    )
    await notify.send(
        session, recipient.id, "transfer_received", name=short_name(sender), amount=f"{amount:.2f}"
    )
    return sent


async def list_transfers(
    session: AsyncSession, q: str | None, params: PageParams
) -> tuple[list[tuple[WalletEntry, User, User | None]], int]:
    sender = aliased(User)
    receiver = aliased(User)
    stmt = (
        select(WalletEntry, sender, receiver)
        .join(Wallet, Wallet.id == WalletEntry.wallet_id)
        .join(sender, sender.id == Wallet.user_id)
        .outerjoin(receiver, receiver.id == WalletEntry.counterpart_user_id)
        .where(WalletEntry.kind == EntryKind.TRANSFER_OUT)
        .order_by(WalletEntry.created_at.desc())
    )
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                sender.full_name.ilike(like),
                sender.email.ilike(like),
                receiver.full_name.ilike(like),
                receiver.email.ilike(like),
            )
        )
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (await session.execute(stmt.limit(params.limit).offset(params.offset))).all()
    return [(e, s, r) for e, s, r in rows], int(total or 0)


# --- Top-ups -----------------------------------------------------------------------------------


async def request_top_up(
    session: AsyncSession, user: User, amount: Decimal, reference: str | None, config: AppConfig
) -> TopUp:
    await require_driver(session, user.id)
    if amount < config.topup_min_amount:
        raise AmountTooLowError(details={"min_amount": f"{config.topup_min_amount:.2f}"})
    pending = await session.scalar(
        select(func.count(TopUp.id)).where(
            TopUp.user_id == user.id, TopUp.status == TopUpStatus.PENDING
        )
    )
    if (pending or 0) >= MAX_PENDING_TOP_UPS:
        raise TooManyPendingTopUpsError()
    top_up = TopUp(
        user_id=user.id,
        status=TopUpStatus.PENDING,
        method=TopUpMethod.BINANCE_PAY,
        amount=amount,
        reference=reference,
    )
    session.add(top_up)
    await session.flush()
    return top_up


async def _complete(
    session: AsyncSession,
    top_up: TopUp,
    user_id: uuid.UUID,
    amount: Decimal,
    reviewer: User | None = None,
) -> TopUp:
    entry = await credit(
        session,
        user_id,
        EntryKind.TOP_UP,
        amount,
        created_by_id=reviewer.id if reviewer else None,
        details={
            "method": top_up.method.value,
            "reference": top_up.reference or top_up.transaction_id,
        },
    )
    top_up.user_id = user_id
    top_up.amount = amount
    top_up.status = TopUpStatus.COMPLETED
    top_up.entry_id = entry.id
    top_up.completed_at = datetime.now(UTC)
    top_up.reviewed_by_id = reviewer.id if reviewer else None
    await notify.send(session, user_id, "top_up_credited", amount=f"{amount:.2f}")
    return top_up


async def _locked_top_up(session: AsyncSession, top_up_id: uuid.UUID) -> TopUp:
    top_up = await session.scalar(select(TopUp).where(TopUp.id == top_up_id).with_for_update())
    if top_up is None:
        raise TopUpNotFoundError()
    return top_up


async def confirm_top_up(
    session: AsyncSession, admin: User, top_up_id: uuid.UUID, amount: Decimal, reference: str | None
) -> TopUp:
    top_up = await _locked_top_up(session, top_up_id)
    if top_up.status != TopUpStatus.PENDING or top_up.user_id is None:
        raise TopUpInvalidStatusError(details={"status": top_up.status.value})
    if reference:
        top_up.reference = reference
    return await _complete(session, top_up, top_up.user_id, amount, admin)


async def reject_top_up(
    session: AsyncSession, admin: User, top_up_id: uuid.UUID, reason: str
) -> TopUp:
    top_up = await _locked_top_up(session, top_up_id)
    if top_up.status != TopUpStatus.PENDING or top_up.user_id is None:
        raise TopUpInvalidStatusError(details={"status": top_up.status.value})
    top_up.status = TopUpStatus.REJECTED
    top_up.rejection_reason = reason
    top_up.reviewed_by_id = admin.id
    await notify.send(session, top_up.user_id, "top_up_rejected", reason=reason)
    return top_up


async def assign_top_up(
    session: AsyncSession, admin: User, top_up_id: uuid.UUID, user_id: uuid.UUID
) -> TopUp:
    top_up = await _locked_top_up(session, top_up_id)
    if top_up.status != TopUpStatus.UNMATCHED:
        raise TopUpInvalidStatusError(details={"status": top_up.status.value})
    await require_driver(session, user_id)
    await _close_oldest_request(session, user_id)
    return await _complete(session, top_up, user_id, top_up.amount, admin)


async def _close_oldest_request(session: AsyncSession, user_id: uuid.UUID) -> None:
    """A payment arrived: the driver's oldest "I paid" notice is settled by it."""
    request = await session.scalar(
        select(TopUp)
        .where(TopUp.user_id == user_id, TopUp.status == TopUpStatus.PENDING)
        .order_by(TopUp.created_at)
        .limit(1)
        .with_for_update()
    )
    if request is not None:
        request.status = TopUpStatus.COMPLETED
        request.completed_at = datetime.now(UTC)
        request.note = "settled by a Binance Pay payment"


async def record_payment(
    session: AsyncSession,
    transaction_id: str,
    amount: Decimal,
    payer_binance_id: str | None,
    payer_name: str | None,
) -> TopUp | None:
    """A Binance Pay payment seen by the reconciler. Credits the owner of the payer's Pay ID or
    leaves it ``unmatched``. Returns None if the payment was already recorded."""
    exists = await session.scalar(select(TopUp.id).where(TopUp.transaction_id == transaction_id))
    if exists:
        return None
    owner = None
    if payer_binance_id:
        owner = await session.scalar(
            select(Wallet.user_id).where(Wallet.binance_pay_id == payer_binance_id)
        )
    top_up = TopUp(
        user_id=None,
        status=TopUpStatus.UNMATCHED,
        method=TopUpMethod.BINANCE_PAY,
        amount=amount,
        transaction_id=transaction_id,
        payer_binance_id=payer_binance_id,
        payer_name=payer_name,
    )
    session.add(top_up)
    await session.flush()
    if owner is not None:
        await _close_oldest_request(session, owner)
        await _complete(session, top_up, owner, amount)
    return top_up


async def list_top_ups(
    session: AsyncSession,
    params: PageParams,
    *,
    user_id: uuid.UUID | None = None,
    status: TopUpStatus | None = None,
    q: str | None = None,
) -> tuple[list[tuple[TopUp, User | None]], int]:
    stmt = (
        select(TopUp, User)
        .outerjoin(User, User.id == TopUp.user_id)
        .order_by(TopUp.created_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(TopUp.user_id == user_id)
    if status is not None:
        stmt = stmt.where(TopUp.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.full_name.ilike(like),
                User.email.ilike(like),
                TopUp.reference.ilike(like),
                TopUp.transaction_id.ilike(like),
                TopUp.payer_binance_id.ilike(like),
                TopUp.payer_name.ilike(like),
            )
        )
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = (await session.execute(stmt.limit(params.limit).offset(params.offset))).all()
    return [(t, u) for t, u in rows], int(total or 0)


# --- Admin -------------------------------------------------------------------------------------


async def adjust(
    session: AsyncSession, admin: User, user_id: uuid.UUID, amount: Decimal, reason: str
) -> WalletEntry:
    await require_driver(session, user_id)
    kwargs = {"created_by_id": admin.id, "details": {"reason": reason}}
    if amount > 0:
        entry = await credit(session, user_id, EntryKind.ADJUSTMENT, amount, **kwargs)
    else:
        entry = await post_entry(session, user_id, EntryKind.ADJUSTMENT, amount, **kwargs)
    await notify.send(session, user_id, "adjustment", amount=f"{amount:+.2f}", reason=reason)
    return entry
