"""Liveness/readiness probes used by Coolify health checks."""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from apps.realtime.manager import manager
from kuulis.core.db import engine
from kuulis.core.redis import redis_client
from kuulis.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> JSONResponse:
    async def check_db() -> bool:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def check_redis() -> bool:
        return bool(await redis_client.ping())

    results = await asyncio.gather(
        asyncio.wait_for(check_db(), 3), asyncio.wait_for(check_redis(), 3), return_exceptions=True
    )
    checks = {
        "database": results[0] is True,
        "redis": results[1] is True,
    }
    healthy = all(checks.values())
    return JSONResponse(
        {
            "status": "ok" if healthy else "degraded",
            "env": settings.APP_ENV,
            "checks": checks,
            "websockets": manager.active_connections,
        },
        status_code=200 if healthy else 503,
    )
