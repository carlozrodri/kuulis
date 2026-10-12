"""Async SQLAlchemy engine and session management."""

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kuulis.settings import settings


def build_engine() -> AsyncEngine:
    return create_async_engine(
        str(settings.DATABASE_URL),
        echo=settings.DB_ECHO,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
    )


engine: AsyncEngine = build_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Request-scoped session. Commits on success, rolls back on error."""
    from apps.audit.services import stage as stage_audit  # app code; avoid a core->apps cycle

    async with SessionLocal() as session:
        # The admin action and its audit row commit together.
        event.listen(session.sync_session, "before_commit", stage_audit)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
