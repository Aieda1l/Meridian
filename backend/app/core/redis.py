"""Redis connection pool for caching and rate limiting."""

from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import settings

redis: Redis = from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20,
)


async def get_redis() -> Redis:
    """FastAPI dependency that returns the shared Redis client."""
    return redis
