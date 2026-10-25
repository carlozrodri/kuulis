"""Content registry rules (docs/marketing/04 and 09).

A piece moves idea → guion → revisado → producido → aprobado → publicado → archivado (or
descartado from any step before publishing). Only someone with ``marketing.approve`` approves, and
only a piece whose every network version has its final file and posting time. Editing an approved
piece sends it back to ``producido``: nothing reaches the person posting without approval."""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.marketing import storage
from apps.marketing.models import (
    MarketingAccount,
    MarketingAsset,
    MarketingContent,
    MarketingLearning,
    MarketingMetricSnapshot,
    MarketingPublication,
    MarketingSpend,
    MarketingVariant,
)
from apps.marketing.schemas import (
    CONTENT_TYPES,
    AccountCreate,
    AccountUpdate,
    AssetCreate,
    AssetRead,
    AssetUpload,
    ContentCreate,
    ContentPreview,
    ContentRead,
    ContentSummary,
    ContentUpdate,
    LearningCreate,
    LearningUpdate,
    MetricCreate,
    MetricRead,
    PerformanceRow,
    PostingCard,
    PublicationCreate,
    PublicationRead,
    SpendCreate,
    SpendMonth,
    SpendRead,
    VariantCreate,
    VariantRead,
    VariantUpdate,
)
from apps.users.models import User
from kuulis.core.calendar import days_bounds, format_month, local_now
from kuulis.core.exceptions import AppError, ConflictError, NotFoundError
from kuulis.core.pagination import PageParams, paginate
from kuulis.core.storage import StorageCheckUnavailable
from kuulis.settings import settings

TRANSITIONS: dict[str, frozenset[str]] = {
    "idea": frozenset({"guion", "descartado"}),
    "guion": frozenset({"idea", "revisado", "descartado"}),
    "revisado": frozenset({"guion", "producido", "descartado"}),
    "producido": frozenset({"revisado", "descartado"}),  # "aprobado" only through approve()
    "aprobado": frozenset({"producido", "descartado"}),  # "publicado" only through publish()
    "publicado": frozenset({"archivado"}),
    "archivado": frozenset(),
    "descartado": frozenset({"idea"}),
}
# Texts, files and times can't change once the piece is out (the registry must match the post).
LOCKED = frozenset({"publicado", "archivado", "descartado"})
UTM_CAMPAIGN = "f1"


class ContentLockedError(ConflictError):
    code = "marketing_content_locked"
    message = "This piece was already published or discarded"


class InvalidTransitionError(ConflictError):
    code = "marketing_invalid_transition"
    message = "The piece can't move to that status"


class NotReadyError(ConflictError):
    code = "marketing_not_ready"
    message = "Every network version needs its final file and posting time"


class AssetNotUploadedError(AppError):
    code = "marketing_asset_not_uploaded"
    message = "The file is not in storage yet"


class InvalidAssetError(AppError):
    code = "marketing_invalid_asset"
    message = "That file can't be used here"


class FileTooLargeError(AppError):
    code = "file_too_large"
    message = "The file is too large"


class AlreadyPublishedError(ConflictError):
    code = "marketing_already_published"
    message = "This version is already registered as published"


class NotApprovedError(ConflictError):
    code = "marketing_not_approved"
    message = "Only approved pieces can be published"


async def get_or_404[M](session: AsyncSession, model: type[M], item_id: uuid.UUID) -> M:
    item = await session.get(model, item_id)
    if item is None:
        raise NotFoundError(code="marketing_not_found")
    return item


def _now() -> datetime:
    return datetime.now(UTC)


# --- Contents --------------------------------------------------------------------------------


async def next_code(session: AsyncSession, day: date) -> str:
    """``K-2026-11-04-A``, then ``-B``... (``-AA`` after ``-Z``): the date it's planned for."""
    prefix = f"K-{day.isoformat()}-"
    used = set(
        await session.scalars(
            select(MarketingContent.code).where(MarketingContent.code.startswith(prefix))
        )
    )
    n = 0
    while True:
        letters, k = "", n
        while True:
            letters = chr(ord("A") + k % 26) + letters
            k = k // 26 - 1
            if k < 0:
                break
        if f"{prefix}{letters}" not in used:
            return f"{prefix}{letters}"
        n += 1


async def create_content(
    session: AsyncSession, user: User, data: ContentCreate
) -> MarketingContent:
    content = MarketingContent(
        **data.model_dump(),
        code=await next_code(session, data.scheduled_for or local_now().date()),
        created_by_id=user.id,
    )
    session.add(content)
    await session.flush()
    return content


def _ensure_editable(content: MarketingContent) -> None:
    """Locked pieces refuse edits; an approved one goes back to the approval queue."""
    if content.status in LOCKED:
        raise ContentLockedError()
    if content.status == "aprobado":
        content.status = "producido"
        content.approved_at = None
        content.approved_by_id = None


async def update_content(
    session: AsyncSession, content: MarketingContent, data: ContentUpdate
) -> MarketingContent:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return content
    _ensure_editable(content)
    for field, value in changes.items():
        if value is None and field in {"title", "audience", "production", "uses_character"}:
            continue  # required columns: null means "leave as is"
        setattr(content, field, value if value is not None or field != "script" else {})
    await session.flush()
    return content


def allowed_statuses(content: MarketingContent) -> list[str]:
    return sorted(TRANSITIONS[content.status])


async def change_status(
    session: AsyncSession, content: MarketingContent, status: str
) -> MarketingContent:
    if status == content.status:
        return content
    if status not in TRANSITIONS[content.status]:
        raise InvalidTransitionError(details={"from": content.status, "to": status})
    if content.status == "aprobado":
        content.approved_at = None
        content.approved_by_id = None
    content.status = status
    await session.flush()
    return content


async def _variants(session: AsyncSession, content_id: uuid.UUID) -> list[MarketingVariant]:
    rows = await session.scalars(
        select(MarketingVariant)
        .where(MarketingVariant.content_id == content_id)
        .order_by(MarketingVariant.scheduled_at.nulls_last(), MarketingVariant.platform)
    )
    return list(rows)


async def approve(session: AsyncSession, user: User, content: MarketingContent) -> MarketingContent:
    if content.status != "producido":
        raise InvalidTransitionError(details={"from": content.status, "to": "aprobado"})
    variants = await _variants(session, content.id)
    assets = {a.id: a for a in await _assets(session, content.id)}
    missing: list[dict[str, str]] = []
    if not variants:
        missing.append({"platform": "*", "field": "variants"})
    for variant in variants:
        asset = assets.get(variant.asset_id) if variant.asset_id else None
        if asset is None or asset.uploaded_at is None:
            missing.append({"platform": variant.platform, "field": "asset_id"})
        if variant.scheduled_at is None:
            missing.append({"platform": variant.platform, "field": "scheduled_at"})
    if missing:
        raise NotReadyError(details={"missing": missing})
    content.status = "aprobado"
    content.approved_by_id = user.id
    content.approved_at = _now()
    content.review_note = None
    await session.flush()
    return content


async def request_changes(
    session: AsyncSession, content: MarketingContent, note: str
) -> MarketingContent:
    if content.status not in {"producido", "aprobado"}:
        raise InvalidTransitionError(details={"from": content.status, "to": "revisado"})
    content.status = "revisado"
    content.approved_at = None
    content.approved_by_id = None
    content.review_note = note.strip()
    await session.flush()
    return content


async def list_contents(
    session: AsyncSession,
    params: PageParams,
    status: str | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[ContentSummary], int]:
    stmt: Select = select(MarketingContent)
    if status:
        stmt = stmt.where(MarketingContent.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(MarketingContent.title.ilike(like), MarketingContent.code.ilike(like))
        )
    if date_from:
        stmt = stmt.where(MarketingContent.scheduled_for >= date_from)
    if date_to:
        stmt = stmt.where(MarketingContent.scheduled_for <= date_to)
    stmt = stmt.order_by(
        MarketingContent.scheduled_for.desc().nulls_first(), MarketingContent.created_at.desc()
    )
    items, total = await paginate(session, stmt, params)
    return await summaries(session, items), total


async def summaries(
    session: AsyncSession, contents: list[MarketingContent]
) -> list[ContentSummary]:
    ids = [c.id for c in contents]
    platforms: dict[uuid.UUID, list[str]] = defaultdict(list)
    next_post: dict[uuid.UUID, datetime] = {}
    if ids:
        rows = await session.execute(
            select(
                MarketingVariant.content_id,
                MarketingVariant.platform,
                MarketingVariant.scheduled_at,
            )
            .where(MarketingVariant.content_id.in_(ids))
            .order_by(MarketingVariant.platform)
        )
        for content_id, platform, scheduled_at in rows:
            platforms[content_id].append(platform)
            if scheduled_at and (
                content_id not in next_post or scheduled_at < next_post[content_id]
            ):
                next_post[content_id] = scheduled_at
    files = await _uploaded_media(session, ids)
    result = []
    for content in contents:
        summary = ContentSummary.model_validate(content)
        summary.platforms = platforms[content.id]
        summary.next_post_at = next_post.get(content.id)
        summary.asset_count = len(files[content.id])
        summary.preview = _preview(files[content.id])
        result.append(summary)
    return result


async def _uploaded_media(
    session: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[MarketingAsset]]:
    """Uploaded files per piece, newest first."""
    files: dict[uuid.UUID, list[MarketingAsset]] = defaultdict(list)
    if ids:
        rows = await session.scalars(
            select(MarketingAsset)
            .where(MarketingAsset.content_id.in_(ids), MarketingAsset.uploaded_at.is_not(None))
            .order_by(MarketingAsset.created_at.desc())
        )
        for asset in rows:
            files[asset.content_id].append(asset)
    return files


def _newest(assets: list[MarketingAsset], kind: str, role: str) -> MarketingAsset | None:
    """The newest file of that kind with that role, else the newest of that kind."""
    of_kind = [a for a in assets if a.kind == kind]
    return next((a for a in of_kind if a.role == role), of_kind[0] if of_kind else None)


def _preview(assets: list[MarketingAsset]) -> ContentPreview | None:
    video = _newest(assets, "video", "final")
    image = _newest(assets, "imagen", "portada")
    if not video and not image:
        return None
    # No filename: the link plays inline instead of downloading.
    shown = video or image
    return ContentPreview(
        video_url=storage.download_url_or_none(video.s3_key) if video else None,
        image_url=storage.download_url_or_none(image.s3_key) if image else None,
        duration_s=video.duration_s if video else None,
        width=shown.width if shown else None,
        height=shown.height if shown else None,
    )


def utm_url(code: str, platform: str) -> str:
    query = urlencode(
        {
            "utm_source": platform,
            "utm_medium": "social",
            "utm_campaign": UTM_CAMPAIGN,
            "utm_content": code,
        }
    )
    return f"{settings.FRONTEND_URL.rstrip('/')}/descargar?{query}"


async def read_content(session: AsyncSession, content: MarketingContent) -> ContentRead:
    read = ContentRead.model_validate(content)
    [summary] = await summaries(session, [content])
    read.platforms, read.next_post_at = summary.platforms, summary.next_post_at
    read.preview, read.asset_count = summary.preview, summary.asset_count
    read.assets = [asset_read(a) for a in await _assets(session, content.id)]
    variants = await _variants(session, content.id)
    publications = await _publications(session, [v.id for v in variants])
    read.variants = []
    for variant in variants:
        item = VariantRead.model_validate(variant)
        item.utm_url = utm_url(content.code, variant.platform)
        item.publication = publications.get(variant.id)
        read.variants.append(item)
    read.allowed_statuses = allowed_statuses(content)
    return read


# --- Assets ----------------------------------------------------------------------------------


async def _assets(session: AsyncSession, content_id: uuid.UUID) -> list[MarketingAsset]:
    rows = await session.scalars(
        select(MarketingAsset)
        .where(MarketingAsset.content_id == content_id)
        .order_by(MarketingAsset.created_at)
    )
    return list(rows)


def asset_read(asset: MarketingAsset) -> AssetRead:
    read = AssetRead.model_validate(asset)
    if asset.uploaded_at:
        read.download_url = storage.download_url_or_none(asset.s3_key, asset.filename)
    return read


async def create_asset(
    session: AsyncSession, user: User, content: MarketingContent, data: AssetCreate
) -> AssetUpload:
    """Registers the file and hands back a presigned PUT; ``confirm_asset`` after uploading."""
    if content.status in LOCKED and data.role != "fuente":
        raise ContentLockedError()
    if data.size > settings.MARKETING_MAX_UPLOAD_MB * 1024 * 1024:
        raise FileTooLargeError(details={"max_mb": settings.MARKETING_MAX_UPLOAD_MB})
    key = storage.build_key(content.code, content.created_at, data.role, data.filename)
    upload_url = storage.presigned_upload(key, data.content_type)
    asset = MarketingAsset(
        **data.model_dump(),
        content_id=content.id,
        kind=CONTENT_TYPES[data.content_type],
        s3_key=key,
        created_by_id=user.id,
    )
    session.add(asset)
    await session.flush()
    return AssetUpload(
        asset=asset_read(asset), upload_url=upload_url, headers={"Content-Type": data.content_type}
    )


async def confirm_asset(session: AsyncSession, asset: MarketingAsset) -> MarketingAsset:
    if asset.uploaded_at:
        return asset
    try:
        head = storage.head_object(asset.s3_key)
    except StorageCheckUnavailable:
        head = {}  # the endpoint refuses server-side reads: trust the presigned upload
    if head is None:
        raise AssetNotUploadedError()
    if head.get("ContentLength"):
        asset.size = int(head["ContentLength"])
    asset.uploaded_at = _now()
    await session.flush()
    return asset


# --- Variants --------------------------------------------------------------------------------


async def _check_assets(
    session: AsyncSession, content: MarketingContent, changes: dict[str, Any]
) -> None:
    for field, kinds in (("asset_id", {"video", "imagen"}), ("cover_asset_id", {"imagen"})):
        asset_id = changes.get(field)
        if asset_id is None:
            continue
        asset = await session.get(MarketingAsset, asset_id)
        if asset is None or asset.content_id != content.id or asset.kind not in kinds:
            raise InvalidAssetError(details={"field": field})
        if asset.uploaded_at is None:
            raise AssetNotUploadedError(details={"field": field})


async def create_variant(
    session: AsyncSession, content: MarketingContent, data: VariantCreate
) -> MarketingVariant:
    _ensure_editable(content)
    changes = data.model_dump()
    await _check_assets(session, content, changes)
    exists = await session.scalar(
        select(MarketingVariant.id).where(
            MarketingVariant.content_id == content.id, MarketingVariant.platform == data.platform
        )
    )
    if exists:
        raise ConflictError(code="marketing_variant_exists", details={"platform": data.platform})
    variant = MarketingVariant(**changes, content_id=content.id)
    session.add(variant)
    await session.flush()
    return variant


_REQUIRED_VARIANT_FIELDS = frozenset({"hook_index", "caption", "hashtags", "checklist", "ai_label"})


async def update_variant(
    session: AsyncSession,
    content: MarketingContent,
    variant: MarketingVariant,
    data: VariantUpdate,
) -> MarketingVariant:
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return variant
    _ensure_editable(content)
    await _check_assets(session, content, changes)
    for field, value in changes.items():
        if value is None and field in _REQUIRED_VARIANT_FIELDS:
            continue
        setattr(variant, field, value)
    await session.flush()
    return variant


async def delete_variant(
    session: AsyncSession, content: MarketingContent, variant: MarketingVariant
) -> None:
    _ensure_editable(content)
    await session.delete(variant)
    await session.flush()


# --- Posting package and publications ----------------------------------------------------------


def _default_checklist(platform: str, ai_label: bool) -> list[str]:
    items = ["Etiqueta de contenido de IA: activar"] if ai_label else []
    if platform in {"tiktok", "instagram"}:
        items.append("Ubicación: Caracas")
    return items


async def posting_queue(session: AsyncSession, day: date) -> list[PostingCard]:
    """The cards of one Caracas day for the person posting (approved pieces only)."""
    start, end = days_bounds(day, day)
    rows = await session.execute(
        select(MarketingVariant, MarketingContent)
        .join(MarketingContent, MarketingContent.id == MarketingVariant.content_id)
        .where(
            MarketingContent.status.in_(("aprobado", "publicado")),
            MarketingVariant.scheduled_at >= start,
            MarketingVariant.scheduled_at < end,
        )
        .order_by(MarketingVariant.scheduled_at, MarketingVariant.platform)
    )
    pairs = list(rows.tuples())
    asset_ids = {a for v, _ in pairs for a in (v.asset_id, v.cover_asset_id) if a}
    assets = (
        {
            a.id: a
            for a in await session.scalars(
                select(MarketingAsset).where(MarketingAsset.id.in_(asset_ids))
            )
        }
        if asset_ids
        else {}
    )
    publications = await _publications(session, [v.id for v, _ in pairs])
    cards = []
    for variant, content in pairs:
        file = assets.get(variant.asset_id) if variant.asset_id else None
        cover = assets.get(variant.cover_asset_id) if variant.cover_asset_id else None
        file_name = None
        if file:
            extension = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "mp4"
            file_name = f"{content.code}-{variant.platform}.{extension}"
        publication = publications.get(variant.id)
        cards.append(
            PostingCard(
                variant_id=variant.id,
                content_id=content.id,
                code=content.code,
                content_title=content.title,
                platform=variant.platform,
                account=variant.account,
                scheduled_at=variant.scheduled_at,  # type: ignore[arg-type]  # filtered above
                title=variant.title,
                caption=variant.caption,
                hashtags=[f"#{tag}" for tag in variant.hashtags],
                checklist=_default_checklist(variant.platform, variant.ai_label)
                + list(variant.checklist),
                file_url=storage.download_url_or_none(file.s3_key, file_name) if file else None,
                file_name=file_name,
                file_kind=file.kind if file else None,
                cover_url=storage.download_url_or_none(cover.s3_key, cover.filename)
                if cover
                else None,
                publication_id=publication.id if publication else None,
                published_at=publication.published_at if publication else None,
                published_url=publication.url if publication else None,
            )
        )
    return cards


async def _publications(
    session: AsyncSession, variant_ids: list[uuid.UUID]
) -> dict[uuid.UUID, PublicationRead]:
    if not variant_ids:
        return {}
    publications = list(
        await session.scalars(
            select(MarketingPublication).where(MarketingPublication.variant_id.in_(variant_ids))
        )
    )
    metrics: dict[uuid.UUID, list[MetricRead]] = defaultdict(list)
    if publications:
        snapshots = await session.scalars(
            select(MarketingMetricSnapshot)
            .where(MarketingMetricSnapshot.publication_id.in_([p.id for p in publications]))
            .order_by(MarketingMetricSnapshot.taken_at)
        )
        for snapshot in snapshots:
            metrics[snapshot.publication_id].append(MetricRead.model_validate(snapshot))
    result = {}
    for publication in publications:
        read = PublicationRead.model_validate(publication)
        read.metrics = metrics[publication.id]
        result[publication.variant_id] = read
    return result


async def publish_variant(
    session: AsyncSession, user: User, variant: MarketingVariant, data: PublicationCreate
) -> MarketingPublication:
    """The person posting says "done": registers the publication and, once every network version
    is out, marks the piece published."""
    content = await session.get(MarketingContent, variant.content_id, with_for_update=True)
    assert content is not None
    if content.status not in {"aprobado", "publicado"}:
        raise NotApprovedError()
    exists = await session.scalar(
        select(MarketingPublication.id).where(MarketingPublication.variant_id == variant.id)
    )
    if exists:
        raise AlreadyPublishedError()
    publication = MarketingPublication(
        variant_id=variant.id,
        platform=variant.platform,
        account=variant.account,
        url=data.url,
        external_id=data.external_id,
        published_at=data.published_at or _now(),
        method="manual",
        published_by_id=user.id,
    )
    session.add(publication)
    await session.flush()
    pending = await session.scalar(
        select(func.count(MarketingVariant.id))
        .outerjoin(MarketingPublication, MarketingPublication.variant_id == MarketingVariant.id)
        .where(MarketingVariant.content_id == content.id, MarketingPublication.id.is_(None))
    )
    if not pending:
        content.status = "publicado"
    await session.flush()
    return publication


async def update_publication(
    session: AsyncSession, publication: MarketingPublication, data: PublicationCreate
) -> MarketingPublication:
    """Adds the link later (the person may post first and paste the URL afterwards)."""
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(publication, field, value)
    await session.flush()
    return publication


# --- Metrics ---------------------------------------------------------------------------------


async def add_metric(
    session: AsyncSession, user: User, publication: MarketingPublication, data: MetricCreate
) -> MarketingMetricSnapshot:
    values = data.model_dump()
    taken_at = values.pop("taken_at") or _now()
    age_h = values.pop("age_h")
    if age_h is None:
        age_h = max(0, round((taken_at - publication.published_at).total_seconds() / 3600))
    snapshot = MarketingMetricSnapshot(
        **values,
        publication_id=publication.id,
        taken_at=taken_at,
        age_h=age_h,
        entered_by_id=user.id,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot


async def performance(
    session: AsyncSession,
    platform: str | None = None,
    pillar: str | None = None,
    format_: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[PerformanceRow]:
    """One row per publication with its latest snapshot, newest first."""
    stmt = (
        select(MarketingPublication, MarketingVariant, MarketingContent)
        .join(MarketingVariant, MarketingVariant.id == MarketingPublication.variant_id)
        .join(MarketingContent, MarketingContent.id == MarketingVariant.content_id)
        .order_by(MarketingPublication.published_at.desc())
        .limit(500)
    )
    if platform:
        stmt = stmt.where(MarketingPublication.platform == platform)
    if pillar:
        stmt = stmt.where(MarketingContent.pillar == pillar)
    if format_:
        stmt = stmt.where(MarketingContent.format == format_)
    if date_from or date_to:
        start, end = days_bounds(date_from or date(2000, 1, 1), date_to or date(2100, 1, 1))
        stmt = stmt.where(
            MarketingPublication.published_at >= start, MarketingPublication.published_at < end
        )
    rows = list((await session.execute(stmt)).tuples())
    latest: dict[uuid.UUID, MarketingMetricSnapshot] = {}
    counts: dict[uuid.UUID, int] = defaultdict(int)
    if rows:
        snapshots = await session.scalars(
            select(MarketingMetricSnapshot)
            .where(MarketingMetricSnapshot.publication_id.in_([p.id for p, _, _ in rows]))
            .order_by(MarketingMetricSnapshot.taken_at)
        )
        for snapshot in snapshots:
            latest[snapshot.publication_id] = snapshot
            counts[snapshot.publication_id] += 1
    return [
        PerformanceRow(
            publication_id=publication.id,
            content_id=content.id,
            code=content.code,
            title=content.title,
            pillar=content.pillar,
            format=content.format,
            platform=publication.platform,
            hook_index=variant.hook_index,
            url=publication.url,
            published_at=publication.published_at,
            snapshots=counts[publication.id],
            latest=MetricRead.model_validate(latest[publication.id])
            if publication.id in latest
            else None,
        )
        for publication, variant, content in rows
    ]


# --- Learnings, spend, accounts --------------------------------------------------------------


async def list_learnings(session: AsyncSession, status: str | None) -> list[MarketingLearning]:
    stmt = select(MarketingLearning).order_by(MarketingLearning.created_at.desc())
    if status:
        stmt = stmt.where(MarketingLearning.status == status)
    return list(await session.scalars(stmt))


async def create_learning(session: AsyncSession, data: LearningCreate) -> MarketingLearning:
    learning = MarketingLearning(**data.model_dump())
    if learning.status != "hipotesis":
        learning.reviewed_at = _now()
    session.add(learning)
    await session.flush()
    return learning


async def update_learning(
    session: AsyncSession, learning: MarketingLearning, data: LearningUpdate
) -> MarketingLearning:
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if value is None and field in {"statement", "status"}:
            continue
        setattr(learning, field, value)
    if changes.get("status"):
        learning.reviewed_at = _now()
    await session.flush()
    return learning


async def spend_month(session: AsyncSession, month: date) -> SpendMonth:
    items = list(
        await session.scalars(
            select(MarketingSpend)
            .where(
                MarketingSpend.date >= month.replace(day=1),
                MarketingSpend.date < _next_month(month),
            )
            .order_by(MarketingSpend.date, MarketingSpend.created_at)
        )
    )
    by_tool: dict[str, Decimal] = defaultdict(Decimal)
    for item in items:
        by_tool[item.tool] += item.amount_usd
    return SpendMonth(
        month=format_month(month),
        total=sum((i.amount_usd for i in items), Decimal("0")),
        by_tool=dict(sorted(by_tool.items())),
        items=[SpendRead.model_validate(i) for i in items],
    )


def _next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


async def create_spend(session: AsyncSession, data: SpendCreate) -> MarketingSpend:
    spend = MarketingSpend(**data.model_dump())
    session.add(spend)
    await session.flush()
    return spend


async def list_accounts(session: AsyncSession) -> list[MarketingAccount]:
    return list(
        await session.scalars(
            select(MarketingAccount).order_by(MarketingAccount.platform, MarketingAccount.handle)
        )
    )


async def create_account(session: AsyncSession, data: AccountCreate) -> MarketingAccount:
    handle = data.handle.strip()
    exists = await session.scalar(
        select(MarketingAccount.id).where(
            MarketingAccount.platform == data.platform, MarketingAccount.handle == handle
        )
    )
    if exists:
        raise ConflictError(code="marketing_account_exists")
    account = MarketingAccount(**{**data.model_dump(), "handle": handle})
    session.add(account)
    await session.flush()
    return account


async def update_account(
    session: AsyncSession, account: MarketingAccount, data: AccountUpdate
) -> MarketingAccount:
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is None and field in {"handle", "status", "connection"}:
            continue
        setattr(account, field, value)
    await session.flush()
    return account
