"""Shared Redis connection pool."""

from redis.asyncio import Redis

from kuulis.settings import settings

redis_client: Redis = Redis.from_url(
    str(settings.REDIS_URL),
    decode_responses=True,
    max_connections=100,
    health_check_interval=30,
)


async def get_redis() -> Redis:
    return redis_client
