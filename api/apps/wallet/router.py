from typing import Annotated

from fastapi import APIRouter, Depends

from apps.users.dependencies import CurrentUser, DBSession
from apps.wallet import services
from apps.wallet.schemas import WalletEntryRead, WalletRead
from kuulis.core.pagination import Page, PageParams, page_params

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/me", response_model=WalletRead)
async def read_me(user: CurrentUser, session: DBSession) -> WalletRead:
    return WalletRead(balance=await services.get_balance(session, user.id))


@router.get("/me/entries", response_model=Page[WalletEntryRead])
async def entries(
    user: CurrentUser,
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[WalletEntryRead]:
    rows, total = await services.list_entries(session, user.id, params)
    return Page(
        items=[WalletEntryRead.model_validate(r) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )
