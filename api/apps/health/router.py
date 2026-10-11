"""Liveness/readiness probes used by Coolify health checks."""

import asyncio

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from apps.geo.clients import http
from apps.realtime.manager import manager
from kuulis.core.db import engine
from kuulis.core.redis import redis_client
from kuulis.settings import settings

router = APIRouter(tags=["health"])


def _version() -> dict:
    return {"env": settings.APP_ENV, "commit": settings.SOURCE_COMMIT[:12] or None}


@router.get("/health/live")
async def live() -> dict:
    return {"status": "ok", **_version()}


async def _probe(base_url: str, path: str) -> bool | None:
    """Optional providers: None when not configured. Their failure degrades quotes and search
    (estimated routes, no suggestions) but never makes the API unready."""
    if not base_url:
        return None
    try:
        response = await http().get(f"{base_url.rstrip('/')}{path}", timeout=3)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


@router.get("/health/ready")
async def ready() -> JSONResponse:
    async def check_db() -> bool:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def check_redis() -> bool:
        return bool(await redis_client.ping())

    results = await asyncio.gather(
        asyncio.wait_for(check_db(), 3),
        asyncio.wait_for(check_redis(), 3),
        _probe(settings.OSRM_URL, "/route/v1/driving/-66.88,10.49;-66.85,10.50?overview=false"),
        _probe(settings.PHOTON_URL, "/api?q=caracas&limit=1"),
        return_exceptions=True,
    )
    checks = {
        "database": results[0] is True,
        "redis": results[1] is True,
    }
    providers = {
        name: False if isinstance(result, BaseException) else result
        for name, result in (("osrm", results[2]), ("photon", results[3]))
    }
    healthy = all(checks.values())
    # A configured provider that is down degrades the API but keeps it in rotation.
    degraded = not healthy or False in providers.values()
    return JSONResponse(
        {
            "status": "degraded" if degraded else "ok",
            **_version(),
            "checks": checks,
            "providers": providers,
            "websockets": manager.active_connections,
        },
        status_code=200 if healthy else 503,
    )
