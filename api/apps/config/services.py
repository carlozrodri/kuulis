"""Admin-editable app configuration, read through a Redis cache.

Other apps call ``get_app_config(session)``; it is cheap (one Redis GET) and always returns every
key, falling back to the defaults in ``AppConfig`` for keys that were never edited.
"""

import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.config.models import AppSetting
from apps.config.schemas import AppConfig, AppConfigUpdate
from kuulis.core.cache import cache_delete, cached

logger = logging.getLogger(__name__)

CACHE_KEY = "app_config"
CACHE_TTL_SECONDS = 300  # Updates invalidate the cache; the TTL is only a safety net.


async def _load(session: AsyncSession) -> dict:
    rows = (await session.execute(select(AppSetting.key, AppSetting.value))).all()
    defaults = AppConfig().model_dump(mode="json")
    stored = {key: value for key, value in rows if key in AppConfig.model_fields}
    try:
        return AppConfig.model_validate(defaults | stored).model_dump(mode="json")
    except ValidationError:
        # A stored value no longer fits the schema (e.g. after a code change): keep what is valid.
        logger.exception("Invalid stored app config, falling back to defaults per key")
        merged = dict(defaults)
        for key, value in stored.items():
            try:
                AppConfig.model_validate(defaults | {key: value})
                merged[key] = value
            except ValidationError:
                continue
        return merged


async def get_app_config(session: AsyncSession) -> AppConfig:
    return AppConfig.model_validate(
        await cached(CACHE_KEY, lambda: _load(session), ttl=CACHE_TTL_SECONDS)
    )


async def update_app_config(session: AsyncSession, data: AppConfigUpdate) -> AppConfig:
    """Upserts the given keys. The caller commits, then calls ``invalidate_cache``."""
    current = AppConfig.model_validate(await _load(session))
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "vehicle_min_year" in changes:
        changes["vehicle_min_year"] = current.vehicle_min_year | changes["vehicle_min_year"]
    merged = AppConfig.model_validate(current.model_dump() | changes)
    values = merged.model_dump(mode="json")
    for key in changes:
        stmt = insert(AppSetting).values(key=key, value=values[key])
        await session.execute(
            stmt.on_conflict_do_update(index_elements=[AppSetting.key], set_={"value": values[key]})
        )
    return merged


async def invalidate_cache() -> None:
    await cache_delete(CACHE_KEY)
