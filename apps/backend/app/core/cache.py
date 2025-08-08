"""Redis caching infrastructure for performance optimization."""

import functools
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, ParamSpec, TypeVar, cast

import redis
from pydantic import BaseModel
from redis import ConnectionPool
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class CacheManager:
    """Manages Redis cache connections and operations."""

    _instance: "CacheManager | None" = None
    _pool: ConnectionPool | None = None

    def __new__(cls) -> "CacheManager":
        """Singleton pattern for cache manager."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize Redis connection pool."""
        if self._pool is None:
            self._pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,
            )

    @property
    def client(self) -> redis.Redis:
        """Get Redis client from connection pool."""
        return redis.Redis(connection_pool=self._pool)

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        try:
            value = self.client.get(self._make_key(key))
            if value:
                return json.loads(value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        nx: bool = False,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            nx: Only set if key doesn't exist
        """
        try:
            cache_key = self._make_key(key)
            serialized = json.dumps(value, default=str)

            if nx:
                return bool(
                    self.client.set(
                        cache_key,
                        serialized,
                        ex=ttl or settings.REDIS_CACHE_TTL,
                        nx=True,
                    )
                )
            else:
                return bool(
                    self.client.set(
                        cache_key, serialized, ex=ttl or settings.REDIS_CACHE_TTL
                    )
                )
        except (RedisError, TypeError) as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            return bool(self.client.delete(self._make_key(key)))
        except RedisError as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            pattern_key = self._make_key(pattern)
            keys = self.client.keys(pattern_key)
            if keys:
                return self.client.delete(*keys)
            return 0
        except RedisError as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return bool(self.client.exists(self._make_key(key)))
        except RedisError as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for key."""
        try:
            return bool(self.client.expire(self._make_key(key), ttl))
        except RedisError as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False

    def increment(self, key: str, amount: int = 1) -> int | None:
        """Increment counter in cache."""
        try:
            return self.client.incr(self._make_key(key), amount)
        except RedisError as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None

    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        try:
            ttl = self.client.ttl(self._make_key(key))
            return ttl if ttl >= 0 else 0
        except RedisError as e:
            logger.error(f"Cache get TTL error for key {key}: {e}")
            return 0

    def mget(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from cache."""
        try:
            cache_keys = [self._make_key(k) for k in keys]
            values = self.client.mget(cache_keys)
            result = {}
            for key, value in zip(keys, values, strict=False):
                if value:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        pass
            return result
        except RedisError as e:
            logger.error(f"Cache mget error: {e}")
            return {}

    def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """Set multiple values in cache."""
        try:
            cache_mapping = {
                self._make_key(k): json.dumps(v, default=str)
                for k, v in mapping.items()
            }

            if self.client.mset(cache_mapping):
                if ttl:
                    for key in cache_mapping:
                        self.client.expire(key, ttl)
                return True
            return False
        except (RedisError, TypeError) as e:
            logger.error(f"Cache mset error: {e}")
            return False

    def flush_db(self) -> bool:
        """Flush entire cache database (use with caution)."""
        try:
            return bool(self.client.flushdb())
        except RedisError as e:
            logger.error(f"Cache flush error: {e}")
            return False

    def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            return self.client.ping()
        except RedisError:
            return False

    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        return f"{settings.CACHE_KEY_PREFIX}{key}"

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        try:
            info = self.client.info()
            return {
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_connections": info.get("total_connections_received"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0), info.get("keyspace_misses", 0)
                ),
            }
        except RedisError as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0


def cache(
    ttl: int | timedelta | None = None,
    key_prefix: str | None = None,
    key_builder: Callable[..., str] | None = None,
    condition: Callable[..., bool] | None = None,
    namespace: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for caching function results.

    Args:
        ttl: Time to live in seconds or timedelta
        key_prefix: Prefix for cache key
        key_builder: Custom function to build cache key
        condition: Function to determine if result should be cached
        namespace: Cache namespace for invalidation
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Check if caching should be skipped
            if condition and not condition(*args, **kwargs):
                return func(*args, **kwargs)

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = _default_key_builder(
                    func.__name__, key_prefix, namespace, *args, **kwargs
                )

            # Try to get from cache
            cache_manager = CacheManager()
            cached_value = cache_manager.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cast(T, cached_value)

            # Execute function and cache result
            logger.debug(f"Cache miss for key: {cache_key}")
            result = func(*args, **kwargs)

            # Calculate TTL
            if isinstance(ttl, timedelta):
                ttl_seconds = int(ttl.total_seconds())
            else:
                ttl_seconds = ttl

            # Cache the result
            cache_manager.set(cache_key, result, ttl_seconds)

            return result

        # Add cache management methods
        wrapper.cache_clear = lambda: _cache_clear(func.__name__, key_prefix, namespace)  # type: ignore
        wrapper.cache_key = lambda *a, **kw: _default_key_builder(  # type: ignore
            func.__name__, key_prefix, namespace, *a, **kw
        )

        return wrapper

    return decorator


def cache_invalidate(
    patterns: list[str] | str,
    namespace: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to invalidate cache patterns after function execution.

    Args:
        patterns: Cache key patterns to invalidate
        namespace: Cache namespace to invalidate
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            result = func(*args, **kwargs)

            # Invalidate cache patterns
            cache_manager = CacheManager()
            patterns_list = patterns if isinstance(patterns, list) else [patterns]

            for pattern in patterns_list:
                if namespace:
                    pattern = f"{namespace}:{pattern}"
                deleted = cache_manager.delete_pattern(pattern)
                if deleted:
                    logger.debug(
                        f"Invalidated {deleted} cache keys for pattern: {pattern}"
                    )

            return result

        return wrapper

    return decorator


def cached_result(
    model: type[BaseModel],
    ttl: int | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, BaseModel | None]]:
    """
    Decorator for caching Pydantic model results.

    Args:
        model: Pydantic model class
        ttl: Time to live in seconds
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, BaseModel | None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> BaseModel | None:
            cache_key = _default_key_builder(
                func.__name__, model.__name__, None, *args, **kwargs
            )

            cache_manager = CacheManager()
            cached_value = cache_manager.get(cache_key)

            if cached_value is not None:
                logger.debug(f"Cache hit for model {model.__name__}: {cache_key}")
                return model(**cached_value)

            result = func(*args, **kwargs)

            if result:
                if isinstance(result, BaseModel):
                    cache_manager.set(cache_key, result.model_dump(mode="json"), ttl)
                else:
                    cache_manager.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def _default_key_builder(
    func_name: str,
    prefix: str | None,
    namespace: str | None,
    *args: Any,
    **kwargs: Any,
) -> str:
    """Build default cache key from function arguments."""
    key_parts = []

    if namespace:
        key_parts.append(namespace)

    if prefix:
        key_parts.append(prefix)
    else:
        key_parts.append(func_name)

    # Hash arguments for consistent key
    args_str = str(args) + str(sorted(kwargs.items()))
    args_hash = hashlib.md5(args_str.encode()).hexdigest()[:8]
    key_parts.append(args_hash)

    return ":".join(key_parts)


def _cache_clear(
    func_name: str,
    prefix: str | None,
    namespace: str | None,
) -> int:
    """Clear all cache entries for a function."""
    cache_manager = CacheManager()

    key_parts = []
    if namespace:
        key_parts.append(namespace)

    if prefix:
        key_parts.append(prefix)
    else:
        key_parts.append(func_name)

    pattern = ":".join(key_parts) + ":*"
    return cache_manager.delete_pattern(pattern)


# Entity-specific cache utilities
class EntityCache:
    """Cache utilities for domain entities."""

    @staticmethod
    def get_entity_ttl(entity_type: str) -> int:
        """Get TTL for entity type from configuration."""
        return settings.CACHE_ENTITY_TTL.get(entity_type, settings.REDIS_CACHE_TTL)

    @staticmethod
    def entity_key(entity_type: str, entity_id: str | int) -> str:
        """Build cache key for entity."""
        return f"entity:{entity_type}:{entity_id}"

    @staticmethod
    def entity_list_key(entity_type: str, **filters: Any) -> str:
        """Build cache key for entity list."""
        if filters:
            filter_hash = hashlib.md5(
                str(sorted(filters.items())).encode()
            ).hexdigest()[:8]
            return f"entity_list:{entity_type}:{filter_hash}"
        return f"entity_list:{entity_type}:all"

    @staticmethod
    def invalidate_entity(entity_type: str, entity_id: str | int | None = None) -> int:
        """Invalidate entity cache."""
        cache_manager = CacheManager()

        if entity_id:
            # Invalidate specific entity
            key = EntityCache.entity_key(entity_type, entity_id)
            deleted = cache_manager.delete(key)
        else:
            # Invalidate all entities of type
            pattern = f"entity:{entity_type}:*"
            deleted = cache_manager.delete_pattern(pattern)

        # Also invalidate entity lists
        list_pattern = f"entity_list:{entity_type}:*"
        deleted += cache_manager.delete_pattern(list_pattern)

        return deleted

    @staticmethod
    def warm_cache(entity_type: str, entities: list[BaseModel]) -> int:
        """Warm cache with entity data."""
        cache_manager = CacheManager()
        ttl = EntityCache.get_entity_ttl(entity_type)

        count = 0
        for entity in entities:
            if hasattr(entity, "id"):
                key = EntityCache.entity_key(entity_type, entity.id)
                if cache_manager.set(key, entity.model_dump(mode="json"), ttl):
                    count += 1

        return count


# Cache warming utilities
async def warm_cache_on_startup() -> None:
    """Warm cache with frequently accessed data on startup."""
    if not settings.CACHE_WARM_ON_STARTUP:
        return

    logger.info("Starting cache warming...")

    try:
        # This will be implemented when integrating with repositories
        # For now, just test Redis connection
        cache_manager = CacheManager()
        if cache_manager.ping():
            logger.info("Redis cache is available and ready")
        else:
            logger.warning("Redis cache is not available")
    except Exception as e:
        logger.error(f"Error during cache warming: {e}")


# Export main components
__all__ = [
    "CacheManager",
    "cache",
    "cache_invalidate",
    "cached_result",
    "EntityCache",
    "warm_cache_on_startup",
]
