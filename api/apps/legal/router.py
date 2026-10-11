import uuid

from fastapi import APIRouter, Request, status

from apps.audit.services import audit, note
from apps.legal import services
from apps.legal.schemas import (
    Accept,
    AcceptanceRead,
    Kind,
    LegalDocumentRead,
    LegalVersionSummary,
    Locale,
    Publish,
)
from apps.users.dependencies import AdminUser, Can, CurrentUser, DBSession

router = APIRouter(tags=["legal"])


@router.get("/legal", response_model=list[LegalVersionSummary])
async def documents(session: DBSession, locale: Locale = "es") -> list[LegalVersionSummary]:
    """Current version of every legal text (public: the apps and the website link to them)."""
    rows = await services.latest_versions(session, locale)
    return [LegalVersionSummary.model_validate(r) for r in rows]


@router.get("/legal/{kind}", response_model=LegalDocumentRead)
async def document(kind: Kind, session: DBSession, locale: Locale = "es") -> LegalDocumentRead:
    return LegalDocumentRead.model_validate(await services.current(session, kind, locale))


@router.post("/legal/accept", response_model=list[str])
async def accept(
    data: Accept, request: Request, user: CurrentUser, session: DBSession
) -> list[str]:
    """Accepts the latest version of each kind; answers what is still pending."""
    await services.accept(session, user, list(data.kinds), request)
    await session.commit()
    return await services.pending(session, user)


# --- Admin panel endpoints ---------------------------------------------------------------------


@router.get("/admin/legal", response_model=list[LegalVersionSummary])
async def admin_history(
    _: AdminUser, session: DBSession, kind: Kind | None = None
) -> list[LegalVersionSummary]:
    kinds = [kind] if kind else list(services.KINDS)
    rows = [row for k in kinds for row in await services.history(session, k)]
    return [LegalVersionSummary.model_validate(r) for r in rows]


@router.get("/admin/legal/{kind}/{version}", response_model=list[LegalDocumentRead])
async def admin_version(
    kind: Kind, version: int, _: AdminUser, session: DBSession
) -> list[LegalDocumentRead]:
    rows = [r for r in await services.history(session, kind) if r.version == version]
    if not rows:
        raise services.LegalDocumentNotFoundError()
    return [LegalDocumentRead.model_validate(r) for r in rows]


@router.post(
    "/admin/legal/{kind}",
    dependencies=[audit("legal.publish", "legal", "kind")],
    response_model=list[LegalDocumentRead],
    status_code=status.HTTP_201_CREATED,
)
async def publish(
    kind: Kind, data: Publish, admin: AdminUser, session: DBSession
) -> list[LegalDocumentRead]:
    texts = {
        loc: (getattr(data, loc).title, getattr(data, loc).body_md) for loc in services.LOCALES
    }
    version = await services.publish(
        session, admin, kind, texts, data.summary, data.requires_reacceptance
    )
    note(
        after={
            "version": version,
            "summary": data.summary,
            "requires_reacceptance": data.requires_reacceptance,
        }
    )
    await session.commit()
    await services.invalidate_cache()
    rows = [r for r in await services.history(session, kind) if r.version == version]
    return [LegalDocumentRead.model_validate(r) for r in rows]


@router.get("/admin/users/{user_id}/legal", response_model=list[AcceptanceRead])
async def user_acceptances(
    user_id: uuid.UUID, _: Can("users.view"), session: DBSession
) -> list[AcceptanceRead]:
    return [AcceptanceRead.model_validate(r) for r in await services.acceptances(session, user_id)]
