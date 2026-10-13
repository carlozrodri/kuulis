import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response, status

from apps.audit.services import audit, note, snapshot
from apps.config.services import get_app_config
from apps.support import services
from apps.support.models import HelpAudience, HelpTopic
from apps.support.schemas import (
    CannedCreate,
    CannedRead,
    CannedUpdate,
    ContactAccepted,
    ContactChallenge,
    ContactCreate,
    HelpArticleAdminRead,
    HelpArticleCreate,
    HelpArticleRead,
    HelpArticleSummary,
    HelpArticleUpdate,
    HelpFeedback,
    LostItemAnswerCreate,
    LostItemCreate,
    LostItemRead,
    SupportMetrics,
    TagCount,
)
from apps.users.dependencies import Can, CurrentUser, DBSession
from kuulis.core.rate_limit import limiter

help_router = APIRouter(prefix="/help", tags=["support"])
lost_router = APIRouter(prefix="/rides", tags=["support"])
public_router = APIRouter(prefix="/public", tags=["support"])
admin_router = APIRouter(prefix="/admin", tags=["support"])

Locale = Literal["es", "en"]

# --- Help center (public) ----------------------------------------------------------------------


@help_router.get("/articles", response_model=list[HelpArticleSummary])
async def articles(
    session: DBSession,
    locale: Locale = "es",
    topic: HelpTopic | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    audience: HelpAudience | None = None,
) -> list[HelpArticleSummary]:
    rows = await services.published_articles(session, locale, topic, q, audience)
    return [HelpArticleSummary(**services.summary(a)) for a in rows]


@help_router.get("/articles/{slug}", response_model=HelpArticleRead)
async def article(slug: str, session: DBSession, locale: Locale = "es") -> HelpArticleRead:
    found = await services.published_article(session, slug[:120], locale)
    read = HelpArticleRead(**services.summary(found), body_md=found.body_md)
    await session.commit()  # the view
    return read


@help_router.post("/articles/{article_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/hour")
async def article_feedback(
    request: Request, article_id: uuid.UUID, data: HelpFeedback, session: DBSession
) -> Response:
    await services.feedback(session, article_id, data.helpful)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Lost items --------------------------------------------------------------------------------


@lost_router.post(
    "/{ride_id}/lost-item", response_model=LostItemRead, status_code=status.HTTP_201_CREATED
)
@limiter.limit("10/hour")
async def ask_lost_item(
    request: Request,
    ride_id: uuid.UUID,
    data: LostItemCreate,
    user: CurrentUser,
    session: DBSession,
) -> LostItemRead:
    config = await get_app_config(session)
    item = await services.ask_lost_item(session, user, ride_id, data.description, config)
    await session.commit()
    await session.refresh(item)
    return services.lost_item_read(item)


@lost_router.get("/{ride_id}/lost-item", response_model=LostItemRead)
async def lost_item(ride_id: uuid.UUID, user: CurrentUser, session: DBSession) -> LostItemRead:
    item = await services.lost_item_for_ride(session, ride_id)
    if item is None or user.id not in (item.passenger_id, item.driver_id):
        raise services.LostItemNotFoundError()
    return services.lost_item_read(item)


@lost_router.post("/{ride_id}/lost-item/answer", response_model=LostItemRead)
async def answer_lost_item(
    ride_id: uuid.UUID, data: LostItemAnswerCreate, user: CurrentUser, session: DBSession
) -> LostItemRead:
    config = await get_app_config(session)
    item = await services.answer_lost_item(session, user, ride_id, data.has_it, config)
    await session.commit()
    await session.refresh(item)
    return services.lost_item_read(item)


# --- Public contact form -----------------------------------------------------------------------


@public_router.get("/contact/challenge", response_model=ContactChallenge)
@limiter.limit("30/hour")
async def contact_challenge(request: Request) -> ContactChallenge:
    challenge, difficulty = services.new_challenge()
    return ContactChallenge(
        challenge=challenge, difficulty=difficulty, expires_in=services.CHALLENGE_TTL
    )


@public_router.post(
    "/contact", response_model=ContactAccepted, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("5/hour")
async def contact(request: Request, data: ContactCreate, session: DBSession) -> ContactAccepted:
    await services.check_proof(data.challenge, data.nonce)
    await services.public_contact(session, data, await get_app_config(session))
    await session.commit()
    return ContactAccepted()


# --- Admin: saved replies, tags and metrics ----------------------------------------------------


@admin_router.get("/support/canned", response_model=list[CannedRead])
async def canned_list(
    _: Can("reports.manage"), session: DBSession, locale: Locale | None = None
) -> list[CannedRead]:
    return [CannedRead.model_validate(c) for c in await services.canned_list(session, locale)]


@admin_router.post(
    "/support/canned",
    dependencies=[audit("canned.create", "canned_response")],
    response_model=CannedRead,
    status_code=status.HTTP_201_CREATED,
)
async def canned_create(
    data: CannedCreate, admin: Can("reports.manage"), session: DBSession
) -> CannedRead:
    canned = await services.create_canned(session, admin, data)
    await session.commit()
    await session.refresh(canned)
    note(entity_id=canned.id, after=snapshot(canned, ("title", "locale", "action")))
    return CannedRead.model_validate(canned)


@admin_router.patch(
    "/support/canned/{canned_id}",
    dependencies=[audit("canned.update", "canned_response", "canned_id")],
    response_model=CannedRead,
)
async def canned_update(
    canned_id: uuid.UUID, data: CannedUpdate, _: Can("reports.manage"), session: DBSession
) -> CannedRead:
    canned = await services.update_canned(
        session, await services.get_canned(session, canned_id), data
    )
    await session.commit()
    await session.refresh(canned)
    return CannedRead.model_validate(canned)


@admin_router.delete(
    "/support/canned/{canned_id}",
    dependencies=[audit("canned.delete", "canned_response", "canned_id")],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def canned_delete(
    canned_id: uuid.UUID, _: Can("reports.manage"), session: DBSession
) -> Response:
    await session.delete(await services.get_canned(session, canned_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/support/tags", response_model=list[TagCount])
async def tags(_: Can("reports.manage"), session: DBSession) -> list[TagCount]:
    return [TagCount(tag=t, count=c) for t, c in await services.tag_counts(session)]


@admin_router.get("/support/metrics", response_model=SupportMetrics)
async def metrics(
    _: Can("reports.manage"),
    session: DBSession,
    days: Annotated[int, Query(ge=1, le=180)] = 30,
) -> SupportMetrics:
    return await services.metrics(session, days)


# --- Admin: help center ------------------------------------------------------------------------


def _admin_article(article) -> HelpArticleAdminRead:
    return HelpArticleAdminRead(
        **services.summary(article),
        body_md=article.body_md,
        published=article.published,
        views=article.views,
        helpful_yes=article.helpful_yes,
        helpful_no=article.helpful_no,
    )


@admin_router.get("/help/articles", response_model=list[HelpArticleAdminRead])
async def admin_articles(
    _: Can("help.manage"),
    session: DBSession,
    locale: Locale | None = None,
    topic: HelpTopic | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[HelpArticleAdminRead]:
    return [_admin_article(a) for a in await services.admin_articles(session, locale, topic, q)]


@admin_router.get("/help/articles/{article_id}", response_model=HelpArticleAdminRead)
async def admin_article(
    article_id: uuid.UUID, _: Can("help.manage"), session: DBSession
) -> HelpArticleAdminRead:
    return _admin_article(await services.get_article(session, article_id))


@admin_router.post(
    "/help/articles",
    dependencies=[audit("help.create", "help_article")],
    response_model=HelpArticleAdminRead,
    status_code=status.HTTP_201_CREATED,
)
async def admin_article_create(
    data: HelpArticleCreate, admin: Can("help.manage"), session: DBSession
) -> HelpArticleAdminRead:
    article = await services.create_article(session, admin, data)
    await session.commit()
    await session.refresh(article)
    note(entity_id=article.id, after=snapshot(article, ("slug", "locale", "published")))
    return _admin_article(article)


@admin_router.patch(
    "/help/articles/{article_id}",
    dependencies=[audit("help.update", "help_article", "article_id")],
    response_model=HelpArticleAdminRead,
)
async def admin_article_update(
    article_id: uuid.UUID, data: HelpArticleUpdate, admin: Can("help.manage"), session: DBSession
) -> HelpArticleAdminRead:
    article = await services.get_article(session, article_id)
    before = snapshot(article, ("slug", "locale", "title", "published"))
    article = await services.update_article(session, admin, article, data)
    await session.commit()
    await session.refresh(article)
    note(before=before, after=snapshot(article, ("slug", "locale", "title", "published")))
    return _admin_article(article)


@admin_router.delete(
    "/help/articles/{article_id}",
    dependencies=[audit("help.delete", "help_article", "article_id")],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def admin_article_delete(
    article_id: uuid.UUID, _: Can("help.manage"), session: DBSession
) -> Response:
    await session.delete(await services.get_article(session, article_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
