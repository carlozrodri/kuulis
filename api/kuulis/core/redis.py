"""Shared Redis connection pool."""

from redis.asyncio import BlockingConnectionPool, Redis

from kuulis.settings import settings

# Blocking: under a burst a request waits for a free connection instead of failing at once
# (``MaxConnectionsError``), which turned short load spikes into 500s.
redis_client: Redis = Redis.from_pool(
    BlockingConnectionPool.from_url(
        str(settings.REDIS_URL),
        decode_responses=True,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        timeout=settings.REDIS_POOL_TIMEOUT,
        health_check_interval=30,
    )
)


async def get_redis() -> Redis:
    return redis_client
