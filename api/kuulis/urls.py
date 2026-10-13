"""Root URL configuration (Django's urls.py): every app router is mounted here."""

from fastapi import APIRouter

from apps.analytics.router import router as analytics_router
from apps.approvals.router import router as approvals_router
from apps.audit.router import router as audit_router
from apps.auth.router import router as auth_router
from apps.config.router import router as config_router
from apps.control.router import router as control_router
from apps.drivers.router import admin_router as drivers_admin_router
from apps.drivers.router import router as drivers_router
from apps.files.router import router as files_router
from apps.geo.router import router as geo_router
from apps.health.client_errors import router as client_errors_router
from apps.health.router import router as health_router
from apps.legal.router import router as legal_router
from apps.moderation.router import admin_router as moderation_admin_router
from apps.moderation.router import router as moderation_router
from apps.monitoring.router import metrics_router
from apps.monitoring.router import router as monitoring_router
from apps.notifications.router import router as notifications_router
from apps.places.router import router as places_router
from apps.privacy.router import router as privacy_router
from apps.promotions.router import admin_router as promotions_admin_router
from apps.rates.router import router as rates_router
from apps.realtime.router import router as realtime_router
from apps.referrals.router import router as referrals_router
from apps.releases.router import router as releases_router
from apps.rides.router import admin_drivers_router as rides_admin_drivers_router
from apps.rides.router import admin_router as rides_admin_router
from apps.rides.router import driver_router as rides_driver_router
from apps.rides.router import router as rides_router
from apps.safety.router import admin_router as safety_admin_router
from apps.safety.router import router as safety_router
from apps.staff.router import public_router as staff_public_router
from apps.staff.router import router as staff_router
from apps.subscriptions.router import admin_router as subscriptions_admin_router
from apps.subscriptions.router import router as subscriptions_router
from apps.updates.router import router as updates_router
from apps.users.router import router as users_router
from apps.wallet.router import admin_router as wallet_admin_router
from apps.wallet.router import router as wallet_router

api_v1 = APIRouter()
# FastAPI tries the routes in this order on every request, so the ones the apps call most go
# first (a request to the last router scanned ~1 ms of routes). Only the order of routes that match
# the same path matters for behaviour; apps/health/tests/test_urls.py checks none hides another.
api_v1.include_router(rides_driver_router)
api_v1.include_router(rides_router)
api_v1.include_router(config_router)
api_v1.include_router(users_router)
api_v1.include_router(rates_router)
api_v1.include_router(notifications_router)
api_v1.include_router(drivers_router)
api_v1.include_router(auth_router)
api_v1.include_router(realtime_router)
api_v1.include_router(places_router)
api_v1.include_router(safety_router)
api_v1.include_router(legal_router)
api_v1.include_router(privacy_router)
api_v1.include_router(releases_router)
api_v1.include_router(updates_router)
api_v1.include_router(control_router)
api_v1.include_router(referrals_router)
api_v1.include_router(files_router)
# Before drivers_admin_router: /admin/drivers/online must win over /admin/drivers/{driver_id}.
api_v1.include_router(rides_admin_drivers_router)
api_v1.include_router(drivers_admin_router)
api_v1.include_router(geo_router)
api_v1.include_router(rides_admin_router)
api_v1.include_router(promotions_admin_router)
api_v1.include_router(wallet_router)
api_v1.include_router(wallet_admin_router)
api_v1.include_router(subscriptions_router)
api_v1.include_router(subscriptions_admin_router)
api_v1.include_router(moderation_router)
api_v1.include_router(moderation_admin_router)
api_v1.include_router(analytics_router)
api_v1.include_router(audit_router)
api_v1.include_router(approvals_router)
api_v1.include_router(staff_router)
api_v1.include_router(staff_public_router)
api_v1.include_router(client_errors_router)
api_v1.include_router(monitoring_router)
api_v1.include_router(safety_admin_router)

root = APIRouter()
root.include_router(health_router)
root.include_router(metrics_router)
