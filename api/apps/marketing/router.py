import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from apps.audit.services import audit, note
from apps.marketing import services
from apps.marketing.models import (
    MarketingAccount,
    MarketingAsset,
    MarketingContent,
    MarketingLearning,
    MarketingPublication,
    MarketingSpend,
    MarketingVariant,
)
from apps.marketing.schemas import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    AssetCreate,
    AssetRead,
    AssetUpload,
    ChangesRequested,
    ContentCreate,
    ContentRead,
    ContentSummary,
    ContentUpdate,
    LearningCreate,
    LearningRead,
    LearningStatus,
    LearningUpdate,
    MetricCreate,
    MetricRead,
    PerformanceRow,
    Platform,
    PostingCard,
    PublicationCreate,
    PublicationRead,
    SpendCreate,
    SpendMonth,
    SpendRead,
    Status,
    StatusChange,
    VariantCreate,
    VariantUpdate,
)
from apps.users.dependencies import Can, DBSession
from kuulis.core.calendar import local_now, parse_month
from kuulis.core.exceptions import AppError
from kuulis.core.pagination import Page, PageParams, page_params

admin_router = APIRouter(prefix="/admin/marketing", tags=["marketing"])


async def _content(session: DBSession, content_id: uuid.UUID) -> MarketingContent:
    return await services.get_or_404(session, MarketingContent, content_id)


async def _variant(
    session: DBSession, content_id: uuid.UUID, variant_id: uuid.UUID
) -> tuple[MarketingContent, MarketingVariant]:
    content = await _content(session, content_id)
    variant = await services.get_or_404(session, MarketingVariant, variant_id)
    if variant.content_id != content.id:
        raise services.NotFoundError(code="marketing_not_found")
    return content, variant


async def _detail(session: DBSession, content: MarketingContent) -> ContentRead:
    await session.refresh(content)
    return await services.read_content(session, content)


# --- Contents --------------------------------------------------------------------------------


@admin_router.get("/contents", response_model=Page[ContentSummary])
async def list_contents(
    _: Can("marketing.view"),
    session: DBSession,
    params: Annotated[PageParams, Depends(page_params)],
    status: Status | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> Page[ContentSummary]:
    items, total = await services.list_contents(session, params, status, q, date_from, date_to)
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)


@admin_router.post(
    "/contents",
    response_model=ContentRead,
    status_code=201,
    dependencies=[audit("marketing.content.create", "marketing_content")],
)
async def create_content(
    data: ContentCreate, user: Can("marketing.manage"), session: DBSession
) -> ContentRead:
    content = await services.create_content(session, user, data)
    await session.commit()
    note(entity_id=content.id)
    return await _detail(session, content)


@admin_router.get("/contents/{content_id}", response_model=ContentRead)
async def content_detail(
    content_id: uuid.UUID, _: Can("marketing.view"), session: DBSession
) -> ContentRead:
    return await services.read_content(session, await _content(session, content_id))


@admin_router.patch(
    "/contents/{content_id}",
    response_model=ContentRead,
    dependencies=[audit("marketing.content.update", "marketing_content", "content_id")],
)
async def update_content(
    content_id: uuid.UUID, data: ContentUpdate, _: Can("marketing.manage"), session: DBSession
) -> ContentRead:
    content = await services.update_content(session, await _content(session, content_id), data)
    await session.commit()
    return await _detail(session, content)


@admin_router.post(
    "/contents/{content_id}/status",
    response_model=ContentRead,
    dependencies=[audit("marketing.content.status", "marketing_content", "content_id")],
)
async def change_status(
    content_id: uuid.UUID, data: StatusChange, _: Can("marketing.manage"), session: DBSession
) -> ContentRead:
    content = await _content(session, content_id)
    before = content.status
    content = await services.change_status(session, content, data.status)
    await session.commit()
    note(before={"status": before}, after={"status": content.status})
    return await _detail(session, content)


@admin_router.post(
    "/contents/{content_id}/approve",
    response_model=ContentRead,
    dependencies=[audit("marketing.content.approve", "marketing_content", "content_id")],
)
async def approve(
    content_id: uuid.UUID, user: Can("marketing.approve"), session: DBSession
) -> ContentRead:
    content = await services.approve(session, user, await _content(session, content_id))
    await session.commit()
    return await _detail(session, content)


@admin_router.post(
    "/contents/{content_id}/request-changes",
    response_model=ContentRead,
    dependencies=[audit("marketing.content.request_changes", "marketing_content", "content_id")],
)
async def request_changes(
    content_id: uuid.UUID, data: ChangesRequested, _: Can("marketing.approve"), session: DBSession
) -> ContentRead:
    content = await services.request_changes(
        session, await _content(session, content_id), data.note
    )
    await session.commit()
    return await _detail(session, content)


# --- Assets ----------------------------------------------------------------------------------


@admin_router.post(
    "/contents/{content_id}/assets",
    response_model=AssetUpload,
    status_code=201,
    dependencies=[audit("marketing.asset.create", "marketing_content", "content_id")],
)
async def create_asset(
    content_id: uuid.UUID, data: AssetCreate, user: Can("marketing.manage"), session: DBSession
) -> AssetUpload:
    """Registers a file and returns a presigned PUT; call ``.../confirm`` once it's uploaded."""
    upload = await services.create_asset(session, user, await _content(session, content_id), data)
    await session.commit()
    return upload


@admin_router.post(
    "/contents/{content_id}/assets/{asset_id}/confirm",
    response_model=AssetRead,
    dependencies=[audit("marketing.asset.confirm", "marketing_asset", "asset_id")],
)
async def confirm_asset(
    content_id: uuid.UUID, asset_id: uuid.UUID, _: Can("marketing.manage"), session: DBSession
) -> AssetRead:
    asset = await services.get_or_404(session, MarketingAsset, asset_id)
    if asset.content_id != content_id:
        raise services.NotFoundError(code="marketing_not_found")
    asset = await services.confirm_asset(session, asset)
    await session.commit()
    return services.asset_read(asset)


# --- Variants --------------------------------------------------------------------------------


@admin_router.post(
    "/contents/{content_id}/variants",
    response_model=ContentRead,
    status_code=201,
    dependencies=[audit("marketing.variant.create", "marketing_content", "content_id")],
)
async def create_variant(
    content_id: uuid.UUID, data: VariantCreate, _: Can("marketing.manage"), session: DBSession
) -> ContentRead:
    content = await _content(session, content_id)
    await services.create_variant(session, content, data)
    await session.commit()
    return await _detail(session, content)


@admin_router.patch(
    "/contents/{content_id}/variants/{variant_id}",
    response_model=ContentRead,
    dependencies=[audit("marketing.variant.update", "marketing_variant", "variant_id")],
)
async def update_variant(
    content_id: uuid.UUID,
    variant_id: uuid.UUID,
    data: VariantUpdate,
    _: Can("marketing.manage"),
    session: DBSession,
) -> ContentRead:
    content, variant = await _variant(session, content_id, variant_id)
    await services.update_variant(session, content, variant, data)
    await session.commit()
    return await _detail(session, content)


@admin_router.delete(
    "/contents/{content_id}/variants/{variant_id}",
    response_model=ContentRead,
    dependencies=[audit("marketing.variant.delete", "marketing_variant", "variant_id")],
)
async def delete_variant(
    content_id: uuid.UUID, variant_id: uuid.UUID, _: Can("marketing.manage"), session: DBSession
) -> ContentRead:
    content, variant = await _variant(session, content_id, variant_id)
    await services.delete_variant(session, content, variant)
    await session.commit()
    return await _detail(session, content)


# --- Posting package -------------------------------------------------------------------------


@admin_router.get("/queue", response_model=list[PostingCard])
async def posting_queue(
    _: Can("marketing.publish"), session: DBSession, response: Response, day: date | None = None
) -> list[PostingCard]:
    """What to post on a Caracas day (today by default), in posting order."""
    response.headers["Cache-Control"] = "no-store"  # the download links expire
    return await services.posting_queue(session, day or local_now().date())


@admin_router.post(
    "/variants/{variant_id}/publish",
    response_model=PublicationRead,
    status_code=201,
    dependencies=[audit("marketing.variant.publish", "marketing_variant", "variant_id")],
)
async def publish_variant(
    variant_id: uuid.UUID,
    data: PublicationCreate,
    user: Can("marketing.publish"),
    session: DBSession,
) -> PublicationRead:
    variant = await services.get_or_404(session, MarketingVariant, variant_id)
    publication = await services.publish_variant(session, user, variant, data)
    await session.commit()
    note(entity_id=publication.id)
    return PublicationRead.model_validate(publication)


@admin_router.patch(
    "/publications/{publication_id}",
    response_model=PublicationRead,
    dependencies=[audit("marketing.publication.update", "marketing_publication", "publication_id")],
)
async def update_publication(
    publication_id: uuid.UUID,
    data: PublicationCreate,
    _: Can("marketing.publish"),
    session: DBSession,
) -> PublicationRead:
    publication = await services.get_or_404(session, MarketingPublication, publication_id)
    publication = await services.update_publication(session, publication, data)
    await session.commit()
    return PublicationRead.model_validate(publication)


# --- Metrics and performance -----------------------------------------------------------------


@admin_router.post(
    "/publications/{publication_id}/metrics",
    response_model=MetricRead,
    status_code=201,
    dependencies=[audit("marketing.metric.create", "marketing_publication", "publication_id")],
)
async def add_metric(
    publication_id: uuid.UUID, data: MetricCreate, user: Can("marketing.manage"), session: DBSession
) -> MetricRead:
    publication = await services.get_or_404(session, MarketingPublication, publication_id)
    snapshot = await services.add_metric(session, user, publication, data)
    await session.commit()
    return MetricRead.model_validate(snapshot)


@admin_router.get("/performance", response_model=list[PerformanceRow])
async def performance(
    _: Can("marketing.view"),
    session: DBSession,
    platform: Platform | None = None,
    pillar: Annotated[str | None, Query(max_length=40)] = None,
    format: Annotated[str | None, Query(max_length=40)] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> list[PerformanceRow]:
    return await services.performance(session, platform, pillar, format, date_from, date_to)


# --- Learnings -------------------------------------------------------------------------------


@admin_router.get("/learnings", response_model=list[LearningRead])
async def learnings(
    _: Can("marketing.view"), session: DBSession, status: LearningStatus | None = None
) -> list[MarketingLearning]:
    return await services.list_learnings(session, status)


@admin_router.post(
    "/learnings",
    response_model=LearningRead,
    status_code=201,
    dependencies=[audit("marketing.learning.create", "marketing_learning")],
)
async def create_learning(
    data: LearningCreate, _: Can("marketing.manage"), session: DBSession
) -> MarketingLearning:
    learning = await services.create_learning(session, data)
    await session.commit()
    await session.refresh(learning)
    note(entity_id=learning.id)
    return learning


@admin_router.patch(
    "/learnings/{learning_id}",
    response_model=LearningRead,
    dependencies=[audit("marketing.learning.update", "marketing_learning", "learning_id")],
)
async def update_learning(
    learning_id: uuid.UUID, data: LearningUpdate, _: Can("marketing.manage"), session: DBSession
) -> MarketingLearning:
    learning = await services.get_or_404(session, MarketingLearning, learning_id)
    learning = await services.update_learning(session, learning, data)
    await session.commit()
    await session.refresh(learning)
    return learning


# --- Spend -----------------------------------------------------------------------------------


@admin_router.get("/spend", response_model=SpendMonth)
async def spend(
    _: Can("marketing.view"),
    session: DBSession,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> SpendMonth:
    try:
        first = parse_month(month) if month else local_now().date().replace(day=1)
    except ValueError as exc:
        raise AppError(code="month_invalid") from exc
    return await services.spend_month(session, first)


@admin_router.post(
    "/spend",
    response_model=SpendRead,
    status_code=201,
    dependencies=[audit("marketing.spend.create", "marketing_spend")],
)
async def create_spend(
    data: SpendCreate, _: Can("marketing.manage"), session: DBSession
) -> MarketingSpend:
    spend = await services.create_spend(session, data)
    await session.commit()
    await session.refresh(spend)
    note(entity_id=spend.id)
    return spend


@admin_router.delete(
    "/spend/{spend_id}",
    status_code=204,
    dependencies=[audit("marketing.spend.delete", "marketing_spend", "spend_id")],
)
async def delete_spend(spend_id: uuid.UUID, _: Can("marketing.manage"), session: DBSession) -> None:
    await session.delete(await services.get_or_404(session, MarketingSpend, spend_id))
    await session.commit()


# --- Accounts --------------------------------------------------------------------------------


@admin_router.get("/accounts", response_model=list[AccountRead])
async def accounts(_: Can("marketing.view"), session: DBSession) -> list[MarketingAccount]:
    return await services.list_accounts(session)


@admin_router.post(
    "/accounts",
    response_model=AccountRead,
    status_code=201,
    dependencies=[audit("marketing.account.create", "marketing_account")],
)
async def create_account(
    data: AccountCreate, _: Can("marketing.manage"), session: DBSession
) -> MarketingAccount:
    account = await services.create_account(session, data)
    await session.commit()
    await session.refresh(account)
    note(entity_id=account.id)
    return account


@admin_router.patch(
    "/accounts/{account_id}",
    response_model=AccountRead,
    dependencies=[audit("marketing.account.update", "marketing_account", "account_id")],
)
async def update_account(
    account_id: uuid.UUID, data: AccountUpdate, _: Can("marketing.manage"), session: DBSession
) -> MarketingAccount:
    account = await services.get_or_404(session, MarketingAccount, account_id)
    account = await services.update_account(session, account, data)
    await session.commit()
    await session.refresh(account)
    return account
