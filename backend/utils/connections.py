"""Database and Cache connection managers for optional Postgres and Redis integration."""

import os
from typing import Optional, Any
import structlog

logger = structlog.get_logger("connections")


class PostgresDBWrapper:
    """Wrapper for optional async Postgres connection pool."""

    def __init__(self) -> None:
        """Initialize PostgresDBWrapper with an empty pool."""
        self.pool: Optional[Any] = None

    async def connect(self) -> None:
        """Connect to Postgres pool if DATABASE_URL is set."""
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            return
        try:
            import psycopg_pool
            self.pool = psycopg_pool.AsyncConnectionPool(conninfo=db_url, open=True)
            await self.pool.wait()
            logger.info("Connected to Postgres pool successfully")
        except Exception as e:
            logger.warning(f"Postgres connection failed: {e}")
            self.pool = None
            if os.environ.get("SARTHI_ENV", "development").lower() == "production":
                raise

    async def disconnect(self) -> None:
        """Close the Postgres pool if connected."""
        if self.pool:
            try:
                await self.pool.close()
            except Exception as e:
                logger.warning(f"Error closing Postgres pool: {e}")
            finally:
                self.pool = None


class RedisCacheWrapper:
    """Wrapper for optional async Redis client."""

    def __init__(self) -> None:
        """Initialize RedisCacheWrapper with an empty client."""
        self.client: Optional[Any] = None

    async def connect(self) -> None:
        """Connect to Redis if REDIS_URL is set."""
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return
        try:
            import redis.asyncio as aioredis
            self.client = aioredis.from_url(redis_url)
            await self.client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.client = None
            if os.environ.get("SARTHI_ENV", "development").lower() == "production":
                raise

    async def disconnect(self) -> None:
        """Close the Redis connection if connected."""
        if self.client:
            try:
                await self.client.aclose()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
            finally:
                self.client = None


postgres_db = PostgresDBWrapper()
redis_cache = RedisCacheWrapper()
