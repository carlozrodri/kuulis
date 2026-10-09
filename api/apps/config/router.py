from fastapi import APIRouter

from apps.config import services
from apps.config.schemas import AppConfig, AppConfigUpdate
from apps.users.dependencies import AdminUser, DBSession, StaffUser

router = APIRouter(tags=["config"])


@router.get("/config/public", response_model=AppConfig)
async def public_config(session: DBSession) -> AppConfig:
    return await services.get_app_config(session)


@router.get("/admin/config", response_model=AppConfig)
async def admin_config(_: StaffUser, session: DBSession) -> AppConfig:
    return await services.get_app_config(session)


@router.patch("/admin/config", response_model=AppConfig)
async def update_config(data: AppConfigUpdate, _: AdminUser, session: DBSession) -> AppConfig:
    config = await services.update_app_config(session, data)
    await session.commit()
    await services.invalidate_cache()
    return config
