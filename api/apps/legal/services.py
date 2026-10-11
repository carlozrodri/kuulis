"""Versioned legal texts and their acceptance (doc 07).

Each kind has numbered versions, published in Spanish and English together. A user must have
accepted, for every kind that applies to them, at least the latest version published with
``requires_reacceptance`` (version 1 always requires it). Riders accept the terms and the privacy
policy; drivers also the driver terms and the wallet conditions. Staff accounts are not asked.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.legal.models import LegalAcceptance, LegalDocument
from apps.users.models import Role, User
from kuulis.core.cache import cache_delete, cached
from kuulis.core.exceptions import ConflictError, NotFoundError
from kuulis.core.rate_limit import client_ip

KINDS = ("terms", "privacy", "community", "driver_terms", "wallet")
FOR_EVERYONE = ("terms", "privacy")
FOR_DRIVERS = ("driver_terms", "wallet")
LOCALES = ("es", "en")
DEFAULT_LOCALE = "es"
TEXTS = Path(__file__).parent / "texts"
TITLES = {
    "terms": {"es": "Términos y condiciones", "en": "Terms and conditions"},
    "privacy": {"es": "Política de privacidad", "en": "Privacy policy"},
    "community": {"es": "Normas de la comunidad", "en": "Community guidelines"},
    "driver_terms": {"es": "Términos para motorizados", "en": "Driver terms"},
    "wallet": {"es": "Condiciones de la billetera", "en": "Wallet conditions"},
}
_REQUIRED_KEY = "legal:required"


class LegalDocumentNotFoundError(NotFoundError):
    code = "legal_document_not_found"
    message = "Legal document not found"


class LegalAcceptanceRequiredError(ConflictError):
    code = "legal_acceptance_required"
    message = "Accept the updated terms to continue"


def bundled_text(kind: str, locale: str) -> str:
    """First draft shipped with the code (seeded as version 1 by the migration)."""
    return (TEXTS / f"{kind}.{locale}.md").read_text(encoding="utf-8")


async def current(session: AsyncSession, kind: str, locale: str) -> LegalDocument:
    """Latest version of ``kind`` in ``locale`` (Spanish when that language is missing)."""
    for loc in dict.fromkeys((locale, DEFAULT_LOCALE)):
        row = await session.scalar(
            select(LegalDocument)
            .where(LegalDocument.kind == kind, LegalDocument.locale == loc)
            .order_by(LegalDocument.version.desc())
            .limit(1)
        )
        if row is not None:
            return row
    raise LegalDocumentNotFoundError()


async def latest_versions(session: AsyncSession, locale: str) -> list[LegalDocument]:
    return [await current(session, kind, locale) for kind in KINDS if await _exists(session, kind)]


async def _exists(session: AsyncSession, kind: str) -> bool:
    return (
        await session.scalar(select(LegalDocument.id).where(LegalDocument.kind == kind).limit(1))
        is not None
    )


async def history(session: AsyncSession, kind: str) -> list[LegalDocument]:
    return list(
        await session.scalars(
            select(LegalDocument)
            .where(LegalDocument.kind == kind)
            .order_by(LegalDocument.version.desc(), LegalDocument.locale)
        )
    )


async def _required(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(LegalDocument.kind, func.max(LegalDocument.version))
        .where(LegalDocument.requires_reacceptance.is_(True))
        .group_by(LegalDocument.kind)
    )
    return {kind: version for kind, version in rows}


async def required_versions(session: AsyncSession) -> dict[str, int]:
    """Minimum accepted version per kind; cached because every ride request asks."""
    return await cached(_REQUIRED_KEY, lambda: _required(session), ttl=300)


async def applicable_kinds(session: AsyncSession, user: User) -> tuple[str, ...]:
    from apps.drivers.models import DriverProfile

    if user.role != Role.USER:
        return ()
    is_driver = await session.scalar(
        select(DriverProfile.id).where(DriverProfile.user_id == user.id)
    )
    return FOR_EVERYONE + (FOR_DRIVERS if is_driver else ())


async def accepted_versions(session: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    rows = await session.execute(
        select(LegalAcceptance.kind, func.max(LegalAcceptance.version))
        .where(LegalAcceptance.user_id == user_id)
        .group_by(LegalAcceptance.kind)
    )
    return {kind: version for kind, version in rows}


async def pending(session: AsyncSession, user: User) -> list[str]:
    """Kinds this user still has to accept (empty when up to date)."""
    kinds = await applicable_kinds(session, user)
    if not kinds:
        return []
    required = await required_versions(session)
    accepted = await accepted_versions(session, user.id)
    return [k for k in kinds if k in required and accepted.get(k, 0) < required[k]]


async def ensure_accepted(session: AsyncSession, user: User) -> None:
    missing = await pending(session, user)
    if missing:
        raise LegalAcceptanceRequiredError(details={"kinds": missing})


async def accept(
    session: AsyncSession, user: User, kinds: list[str], request: Request | None
) -> list[LegalAcceptance]:
    """Records the acceptance of the latest version of each kind."""
    rows = []
    for kind in dict.fromkeys(kinds):
        version = await session.scalar(
            select(func.max(LegalDocument.version)).where(LegalDocument.kind == kind)
        )
        if version is None:
            continue
        row = LegalAcceptance(
            user_id=user.id,
            kind=kind,
            version=version,
            ip=client_ip(request)[:45] if request else None,
            platform=(request.headers.get("x-client-platform", "")[:20] or None)
            if request
            else None,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def acceptances(session: AsyncSession, user_id: uuid.UUID) -> list[LegalAcceptance]:
    return list(
        await session.scalars(
            select(LegalAcceptance)
            .where(LegalAcceptance.user_id == user_id)
            .order_by(LegalAcceptance.created_at.desc())
        )
    )


async def publish(
    session: AsyncSession,
    admin: User,
    kind: str,
    texts: dict[str, tuple[str, str]],
    summary: str,
    requires_reacceptance: bool,
) -> int:
    """Publishes the next version of ``kind`` in every language at once; returns its number."""
    # Two admins publishing at once: the unique (kind, version, locale) makes one of them fail.
    last = await session.scalar(
        select(func.max(LegalDocument.version)).where(LegalDocument.kind == kind)
    )
    version = (last or 0) + 1
    now = datetime.now(UTC)
    for locale, (title, body) in texts.items():
        session.add(
            LegalDocument(
                kind=kind,
                version=version,
                locale=locale,
                title=title,
                body_md=body,
                summary=summary,
                requires_reacceptance=requires_reacceptance or version == 1,
                published_at=now,
                published_by_id=admin.id,
            )
        )
    await session.flush()
    return version


async def invalidate_cache() -> None:
    await cache_delete(_REQUIRED_KEY)
