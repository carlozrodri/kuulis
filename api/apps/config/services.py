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
from apps.config.schemas import AppConfig, AppConfigUpdate, PublicSite
from kuulis.core.cache import cache_delete, cached
from kuulis.core.exceptions import AppError

logger = logging.getLogger(__name__)

CACHE_KEY = "app_config"
CACHE_TTL_SECONDS = 300  # Updates invalidate the cache; the TTL is only a safety net.
# Dict settings merged per key on PATCH (sending one vehicle type keeps the others).
MERGED_KEYS = ("vehicle_min_year", "fares", "rates_stale_minutes")


class ConfigInvalidError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Invalid configuration"


async def _load(session: AsyncSession) -> dict:
    rows = (await session.execute(select(AppSetting.key, AppSetting.value))).all()
    defaults = AppConfig().model_dump(mode="json")
    raw = dict(rows)
    if "service_area" in raw and "service_areas" not in raw:
        # Before multi-city support the config held a single box (Caracas).
        raw["service_areas"] = [{"name": "Caracas"} | raw["service_area"]]
    stored = {key: value for key, value in raw.items() if key in AppConfig.model_fields}
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


async def preview_app_config(session: AsyncSession, data: AppConfigUpdate) -> AppConfig:
    """The settings as they would be after ``data``, validated but not saved."""
    merged, _ = await _merge(session, data)
    return merged


async def update_app_config(session: AsyncSession, data: AppConfigUpdate) -> AppConfig:
    """Upserts the given keys. The caller commits, then calls ``invalidate_cache``."""
    merged, changes = await _merge(session, data)
    values = merged.model_dump(mode="json")
    for key in changes:
        stmt = insert(AppSetting).values(key=key, value=values[key])
        await session.execute(
            stmt.on_conflict_do_update(index_elements=[AppSetting.key], set_={"value": values[key]})
        )
    return merged


async def _merge(session: AsyncSession, data: AppConfigUpdate) -> tuple[AppConfig, dict]:
    current = AppConfig.model_validate(await _load(session))
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for key in MERGED_KEYS:
        if key in changes:
            changes[key] = getattr(current, key) | changes[key]
    try:
        # Cross-field rules (fares for every enabled type, search vs offer timeout...).
        merged = AppConfig.model_validate(current.model_dump() | changes)
    except ValidationError as exc:
        details = [
            {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
            for err in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise ConfigInvalidError(details=details) from exc
    return merged, changes


async def invalidate_cache() -> None:
    await cache_delete(CACHE_KEY)


async def public_site(session: AsyncSession) -> PublicSite:
    """The public subset of the settings plus this month's fee tiers, for the website."""
    from apps.subscriptions.services import schedule_for
    from kuulis.core.calendar import local_now, month_start

    config = await get_app_config(session)
    schedule = await schedule_for(session, month_start(local_now()))
    return PublicSite.model_validate(
        {
            "cities": list(dict.fromkeys(area.name for area in config.service_areas)),
            "driver": {
                "min_age": config.driver_min_age,
                "vehicle_types": config.enabled_vehicle_types,
                "vehicle_min_year": {
                    t: y
                    for t, y in config.vehicle_min_year.items()
                    if t in config.enabled_vehicle_types
                },
                "documents": config.driver_required_documents,
                "vehicle_photo_min_count": config.vehicle_photo_min_count,
            },
            "free_months": config.subscription_free_months,
            "fee_tiers": [t.model_dump() for t in schedule.tiers],
            "payment_methods": config.payment_methods,
        }
    )
