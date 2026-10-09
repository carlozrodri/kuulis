"""Root URL configuration (Django's urls.py): every app router is mounted here."""

from fastapi import APIRouter

from apps.auth.router import router as auth_router
from apps.files.router import router as files_router
from apps.health.router import router as health_router
from apps.notifications.router import router as notifications_router
from apps.realtime.router import router as realtime_router
from apps.users.router import router as users_router

api_v1 = APIRouter()
api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(notifications_router)
api_v1.include_router(files_router)
api_v1.include_router(realtime_router)

root = APIRouter()
root.include_router(health_router)
