import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from apps.config.services import get_app_config
from apps.subscriptions import services as subscriptions
from apps.subscriptions.schemas import ChargeRead
from apps.users.dependencies import AdminUser, CurrentUser, DBSession, StaffUser
from apps.users.models import User
from apps.wallet import services
from apps.wallet.models import TopUp, TopUpStatus
from apps.wallet.schemas import (
    Adjustment,
    BinancePayIdWrite,
    MoneyStr,
    ReasonBody,
    Recipient,
    TopUpAdminRead,
    TopUpAssign,
    TopUpConfirm,
    TopUpCreate,
    TopUpInfo,
    TopUpRead,
    TransferAdminRead,
    TransferCreate,
    UserBrief,
    WalletEntryRead,
    WalletRead,
)
from kuulis.core.exceptions import NotFoundError
from kuulis.core.pagination import Page, PageParams, page_params
from kuulis.settings import settings

router = APIRouter(prefix="/wallet", tags=["wallet"])
admin_router = APIRouter(prefix="/admin", tags=["wallet"])

Params = Annotated[PageParams, Depends(page_params)]


def _brief(user: User) -> UserBrief:
    return UserBrief(id=user.id, name=user.full_name or "", email=user.email)


def _page[T](items: list[T], total: int, params: PageParams) -> Page[T]:
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


async def _wallet_read(session: DBSession, user: User) -> WalletRead:
    config = await get_app_config(session)
    wallet = await services.get_wallet(session, user.id)
    return WalletRead(
        balance=wallet.balance if wallet else services.ZERO,
        binance_pay_id=wallet.binance_pay_id if wallet else None,
        transfer=await services.transfer_limit(session, user.id, config),
    )


def _top_up_admin(top_up: TopUp, user: User | None) -> TopUpAdminRead:
    return TopUpAdminRead(
        **TopUpRead.model_validate(top_up).model_dump(),
        transaction_id=top_up.transaction_id,
        user=_brief(user) if user else None,
    )


# --- Driver ------------------------------------------------------------------------------------


@router.get("/me", response_model=WalletRead)
async def read_me(user: CurrentUser, session: DBSession) -> WalletRead:
    return await _wallet_read(session, user)


@router.put("/me/binance", response_model=WalletRead)
async def set_binance(data: BinancePayIdWrite, user: CurrentUser, session: DBSession) -> WalletRead:
    await services.set_binance_pay_id(session, user, data.binance_pay_id)
    await session.commit()
    return await _wallet_read(session, user)


@router.get("/me/entries", response_model=Page[WalletEntryRead])
async def entries(user: CurrentUser, session: DBSession, params: Params) -> Page[WalletEntryRead]:
    rows, total = await services.list_entries(session, user.id, params)
    return _page([WalletEntryRead.model_validate(r) for r in rows], total, params)


@router.get("/top-up-info", response_model=TopUpInfo)
async def top_up_info(user: CurrentUser, session: DBSession) -> TopUpInfo:
    await services.require_driver(session, user.id)
    config = await get_app_config(session)
    return TopUpInfo(
        pay_id=config.topup_binance_pay_id,
        account_name=config.topup_account_name,
        min_amount=config.topup_min_amount,
        automatic=bool(settings.BINANCE_API_KEY and settings.BINANCE_API_SECRET),
    )


@router.post("/me/top-ups", response_model=TopUpRead, status_code=201)
async def request_top_up(data: TopUpCreate, user: CurrentUser, session: DBSession) -> TopUpRead:
    config = await get_app_config(session)
    top_up = await services.request_top_up(session, user, data.amount, data.reference, config)
    await session.commit()
    await session.refresh(top_up)
    return TopUpRead.model_validate(top_up)


@router.get("/me/top-ups", response_model=Page[TopUpRead])
async def my_top_ups(user: CurrentUser, session: DBSession, params: Params) -> Page[TopUpRead]:
    rows, total = await services.list_top_ups(session, params, user_id=user.id)
    return _page([TopUpRead.model_validate(t) for t, _ in rows], total, params)


@router.get("/recipients", response_model=Recipient)
async def recipient(
    user: CurrentUser, session: DBSession, q: Annotated[str, Query(min_length=3, max_length=120)]
) -> Recipient:
    await services.require_driver(session, user.id)
    found = await services.find_recipient(session, q)
    return Recipient(user_id=found.id, name=services.short_name(found))


@router.post("/me/transfers", response_model=WalletEntryRead, status_code=201)
async def transfer(data: TransferCreate, user: CurrentUser, session: DBSession) -> WalletEntryRead:
    config = await get_app_config(session)
    entry = await services.transfer(session, user, data.to_user_id, data.amount, data.note, config)
    await session.commit()
    await session.refresh(entry)
    return WalletEntryRead.model_validate(entry)


# --- Admin -------------------------------------------------------------------------------------


@admin_router.get("/top-ups", response_model=Page[TopUpAdminRead])
async def admin_top_ups(
    _: StaffUser,
    session: DBSession,
    params: Params,
    status: Annotated[TopUpStatus | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[TopUpAdminRead]:
    rows, total = await services.list_top_ups(session, params, status=status, q=q)
    return _page([_top_up_admin(t, u) for t, u in rows], total, params)


async def _top_up_response(session: DBSession, top_up: TopUp) -> TopUpAdminRead:
    await session.commit()
    await session.refresh(top_up)
    user = await session.get(User, top_up.user_id) if top_up.user_id else None
    return _top_up_admin(top_up, user)


@admin_router.post("/top-ups/{top_up_id}/confirm", response_model=TopUpAdminRead)
async def confirm(
    top_up_id: uuid.UUID, data: TopUpConfirm, admin: AdminUser, session: DBSession
) -> TopUpAdminRead:
    top_up = await services.confirm_top_up(session, admin, top_up_id, data.amount, data.reference)
    return await _top_up_response(session, top_up)


@admin_router.post("/top-ups/{top_up_id}/reject", response_model=TopUpAdminRead)
async def reject(
    top_up_id: uuid.UUID, data: ReasonBody, admin: AdminUser, session: DBSession
) -> TopUpAdminRead:
    top_up = await services.reject_top_up(session, admin, top_up_id, data.reason)
    return await _top_up_response(session, top_up)


@admin_router.post("/top-ups/{top_up_id}/assign", response_model=TopUpAdminRead)
async def assign(
    top_up_id: uuid.UUID, data: TopUpAssign, admin: AdminUser, session: DBSession
) -> TopUpAdminRead:
    top_up = await services.assign_top_up(session, admin, top_up_id, data.user_id)
    return await _top_up_response(session, top_up)


class AdminWallet(BaseModel):
    user: UserBrief
    balance: MoneyStr
    binance_pay_id: str | None
    sent_this_month: MoneyStr
    entries: list[WalletEntryRead]
    pending_charges: list[ChargeRead]


@admin_router.get("/wallets/{user_id}", response_model=AdminWallet)
async def admin_wallet(user_id: uuid.UUID, _: StaffUser, session: DBSession) -> AdminWallet:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found", code="user_not_found")
    await services.require_driver(session, user_id)
    wallet = await services.get_wallet(session, user_id)
    rows, _ = await services.list_entries(session, user_id, PageParams(limit=20, offset=0))
    summary = await subscriptions.summary(session, user_id)
    return AdminWallet(
        user=_brief(user),
        balance=wallet.balance if wallet else services.ZERO,
        binance_pay_id=wallet.binance_pay_id if wallet else None,
        sent_this_month=await services.sent_this_month(session, user_id),
        entries=[WalletEntryRead.model_validate(r) for r in rows],
        pending_charges=[subscriptions.charge_read(c) for c in summary.pending],
    )


@admin_router.get("/wallets/{user_id}/entries", response_model=Page[WalletEntryRead])
async def admin_entries(
    user_id: uuid.UUID, _: StaffUser, session: DBSession, params: Params
) -> Page[WalletEntryRead]:
    rows, total = await services.list_entries(session, user_id, params)
    return _page([WalletEntryRead.model_validate(r) for r in rows], total, params)


@admin_router.post("/wallets/{user_id}/adjust", response_model=WalletEntryRead, status_code=201)
async def adjust(
    user_id: uuid.UUID, data: Adjustment, admin: AdminUser, session: DBSession
) -> WalletEntryRead:
    entry = await services.adjust(session, admin, user_id, data.amount, data.reason)
    await session.commit()
    await session.refresh(entry)
    return WalletEntryRead.model_validate(entry)


@admin_router.get("/transfers", response_model=Page[TransferAdminRead])
async def transfers(
    _: StaffUser,
    session: DBSession,
    params: Params,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[TransferAdminRead]:
    rows, total = await services.list_transfers(session, q, params)
    items = [
        TransferAdminRead(
            id=entry.id,
            sender=_brief(sender),
            recipient=_brief(receiver) if receiver else None,
            amount=-entry.amount,
            note=(entry.details or {}).get("note"),
            created_at=entry.created_at,
        )
        for entry, sender, receiver in rows
    ]
    return _page(items, total, params)
