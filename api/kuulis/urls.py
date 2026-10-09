"""Root URL configuration (Django's urls.py): every app router is mounted here."""

from fastapi import APIRouter

from apps.auth.router import router as auth_router
from apps.config.router import router as config_router
from apps.drivers.router import admin_router as drivers_admin_router
from apps.drivers.router import router as drivers_router
from apps.files.router import router as files_router
from apps.geo.router import router as geo_router
from apps.health.router import router as health_router
from apps.notifications.router import router as notifications_router
from apps.realtime.router import router as realtime_router
from apps.rides.router import admin_drivers_router as rides_admin_drivers_router
from apps.rides.router import admin_router as rides_admin_router
from apps.rides.router import driver_router as rides_driver_router
from apps.rides.router import router as rides_router
from apps.users.router import router as users_router

api_v1 = APIRouter()
api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(notifications_router)
api_v1.include_router(files_router)
api_v1.include_router(realtime_router)
api_v1.include_router(config_router)
api_v1.include_router(rides_driver_router)
api_v1.include_router(drivers_router)
# Before drivers_admin_router: /admin/drivers/online must win over /admin/drivers/{driver_id}.
api_v1.include_router(rides_admin_drivers_router)
api_v1.include_router(drivers_admin_router)
api_v1.include_router(geo_router)
api_v1.include_router(rides_router)
api_v1.include_router(rides_admin_router)

root = APIRouter()
root.include_router(health_router)
