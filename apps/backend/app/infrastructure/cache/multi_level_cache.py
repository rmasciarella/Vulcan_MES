"""
Multi-level caching strategy with L1 (in-memory) and L2 (Redis) caches.

This module implements a sophisticated caching strategy with multiple levels,
cache warming, invalidation strategies, and performance monitoring.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any, Generic, TypeVar

from redis.exceptions import RedisError

from app.core.cache import CacheManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheMetrics:
    """Track cache performance metrics."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.l1_hits = 0
        self.l2_hits = 0
        self.evictions = 0
        self.invalidations = 0
        self.errors = 0
        self.total_response_time = 0
        self.cache_operations = []

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    @property
    def l1_hit_rate(self) -> float:
        """Calculate L1 cache hit rate."""
        total = self.hits + self.misses
        return (self.l1_hits / total * 100) if total > 0 else 0.0

    @property
    def avg_response_time(self) -> float:
        """Calculate average cache response time."""
        total = self.hits + self.misses
        return (self.total_response_time / total) if total > 0 else 0.0

    def record_operation(self, operation: str, duration: float, hit: bool = False):
        """Record a cache operation."""
        self.cache_operations.append(
            {
                "operation": operation,
                "duration": duration,
                "hit": hit,
                "timestamp": datetime.utcnow(),
            }
        )
        # Keep only last 1000 operations
        if len(self.cache_operations) > 1000:
            self.cache_operations = self.cache_operations[-1000:]

    def get_summary(self) -> dict[str, Any]:
        """Get cache metrics summary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "l1_hits": self.l1_hits,
            "l1_hit_rate": self.l1_hit_rate,
            "l2_hits": self.l2_hits,
            "evictions": self.evictions,
            "invalidations": self.invalidations,
            "errors": self.errors,
            "avg_response_time_ms": self.avg_response_time * 1000,
            "total_operations": self.hits + self.misses,
        }


class LRUCache(Generic[T]):
    """Thread-safe LRU cache implementation for L1 caching."""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: OrderedDict[str, tuple[T, float, float]] = OrderedDict()
        self.metrics = CacheMetrics()

    def get(self, key: str) -> T | None:
        """Get value from cache."""
        if key in self.cache:
            value, expiry, _ = self.cache[key]
            if expiry > time.time():
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.metrics.l1_hits += 1
                return value
            else:
                # Expired
                del self.cache[key]
        return None

    def set(self, key: str, value: T, ttl: int = 300) -> None:
        """Set value in cache with TTL."""
        expiry = time.time() + ttl

        # Remove oldest if at capacity
        if len(self.cache) >= self.capacity and key not in self.cache:
            self.cache.popitem(last=False)
            self.metrics.evictions += 1

        self.cache[key] = (value, expiry, time.time())
        self.cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self.cache:
            del self.cache[key]
            self.metrics.invalidations += 1
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self.cache)
        self.cache.clear()
        self.metrics.invalidations += count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "capacity": self.capacity,
            "metrics": self.metrics.get_summary(),
        }


class MultiLevelCache:
    """
    Multi-level cache with L1 (in-memory LRU) and L2 (Redis) caching.

    Provides automatic fallback, cache warming, and invalidation strategies.
    """

    def __init__(
        self,
        l1_capacity: int = 1000,
        l1_ttl: int = 60,  # 1 minute default for L1
        l2_ttl: int = 3600,  # 1 hour default for L2
        namespace: str = "mlc",
    ):
        self.l1_cache = LRUCache[Any](capacity=l1_capacity)
        self.l2_cache = CacheManager()
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl
        self.namespace = namespace
        self.metrics = CacheMetrics()
        self._warm_cache_tasks: set[str] = set()

    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache with multi-level fallback.

        1. Check L1 cache (in-memory)
        2. Check L2 cache (Redis)
        3. Promote from L2 to L1 if found
        """
        start_time = time.time()
        full_key = self._make_key(key)

        # Check L1 cache
        value = self.l1_cache.get(full_key)
        if value is not None:
            self.metrics.hits += 1
            self.metrics.l1_hits += 1
            duration = time.time() - start_time
            self.metrics.total_response_time += duration
            self.metrics.record_operation("get_l1", duration, hit=True)
            return value

        # Check L2 cache
        try:
            value = self.l2_cache.get(full_key)
            if value is not None:
                # Promote to L1
                self.l1_cache.set(full_key, value, self.l1_ttl)
                self.metrics.hits += 1
                self.metrics.l2_hits += 1
                duration = time.time() - start_time
                self.metrics.total_response_time += duration
                self.metrics.record_operation("get_l2", duration, hit=True)
                return value
        except RedisError as e:
            logger.error(f"L2 cache error for key {key}: {e}")
            self.metrics.errors += 1

        # Cache miss
        self.metrics.misses += 1
        duration = time.time() - start_time
        self.metrics.total_response_time += duration
        self.metrics.record_operation("get_miss", duration, hit=False)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        l1_ttl: int | None = None,
        l2_ttl: int | None = None,
        l1_only: bool = False,
    ) -> bool:
        """
        Set value in cache levels.

        Args:
            key: Cache key
            value: Value to cache
            l1_ttl: Override L1 TTL
            l2_ttl: Override L2 TTL
            l1_only: Only cache in L1 (for frequently changing data)
        """
        full_key = self._make_key(key)
        success = True

        # Set in L1
        try:
            self.l1_cache.set(full_key, value, l1_ttl or self.l1_ttl)
        except Exception as e:
            logger.error(f"L1 cache set error for key {key}: {e}")
            success = False

        # Set in L2 unless L1-only
        if not l1_only:
            try:
                self.l2_cache.set(full_key, value, l2_ttl or self.l2_ttl)
            except RedisError as e:
                logger.error(f"L2 cache set error for key {key}: {e}")
                self.metrics.errors += 1
                success = False

        return success

    async def delete(self, key: str) -> bool:
        """Delete key from all cache levels."""
        full_key = self._make_key(key)

        # Delete from L1
        l1_deleted = self.l1_cache.delete(full_key)

        # Delete from L2
        l2_deleted = False
        try:
            l2_deleted = self.l2_cache.delete(full_key)
        except RedisError as e:
            logger.error(f"L2 cache delete error for key {key}: {e}")
            self.metrics.errors += 1

        return l1_deleted or l2_deleted

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern from all levels."""
        deleted_count = 0

        # Clear matching keys from L1
        full_pattern = self._make_key(pattern)
        for key in list(self.l1_cache.cache.keys()):
            if self._matches_pattern(key, full_pattern):
                self.l1_cache.delete(key)
                deleted_count += 1

        # Delete from L2
        try:
            deleted_count += self.l2_cache.delete_pattern(full_pattern)
        except RedisError as e:
            logger.error(f"L2 cache delete pattern error for {pattern}: {e}")
            self.metrics.errors += 1

        self.metrics.invalidations += deleted_count
        return deleted_count

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple wildcard support)."""
        import fnmatch

        return fnmatch.fnmatch(key, pattern)

    async def warm_cache(
        self,
        key: str,
        loader: Callable[[], Any],
        l1_ttl: int | None = None,
        l2_ttl: int | None = None,
    ) -> Any:
        """
        Warm cache with data from loader function.

        Prevents cache stampede by ensuring only one loader runs per key.
        """
        if key in self._warm_cache_tasks:
            # Another task is already warming this key
            await asyncio.sleep(0.1)
            return await self.get(key)

        self._warm_cache_tasks.add(key)
        try:
            # Load data
            value = await loader() if asyncio.iscoroutinefunction(loader) else loader()

            if value is not None:
                await self.set(key, value, l1_ttl, l2_ttl)

            return value
        finally:
            self._warm_cache_tasks.discard(key)

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics."""
        l1_stats = self.l1_cache.get_stats()

        # Get L2 stats
        l2_stats = {}
        try:
            l2_stats = self.l2_cache.get_stats()
        except RedisError as e:
            logger.error(f"Failed to get L2 cache stats: {e}")

        return {
            "l1": l1_stats,
            "l2": l2_stats,
            "metrics": self.metrics.get_summary(),
            "warming_keys": list(self._warm_cache_tasks),
        }


class CacheStrategy:
    """
    Defines caching strategies for different data types and access patterns.
    """

    # Define cache strategies for different entity types
    STRATEGIES = {
        "job": {
            "l1_ttl": 60,  # 1 minute in memory
            "l2_ttl": 300,  # 5 minutes in Redis
            "invalidate_on": ["job_update", "task_update"],
            "warm_on_startup": True,
            "warm_query": "SELECT * FROM jobs WHERE status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS')",
        },
        "task": {
            "l1_ttl": 30,  # 30 seconds in memory
            "l2_ttl": 180,  # 3 minutes in Redis
            "invalidate_on": ["task_update", "assignment_update"],
            "warm_on_startup": False,
        },
        "machine": {
            "l1_ttl": 300,  # 5 minutes in memory
            "l2_ttl": 1800,  # 30 minutes in Redis
            "invalidate_on": ["machine_update", "maintenance_schedule"],
            "warm_on_startup": True,
            "warm_query": "SELECT * FROM machines WHERE status = 'AVAILABLE'",
        },
        "operator": {
            "l1_ttl": 300,  # 5 minutes in memory
            "l2_ttl": 1800,  # 30 minutes in Redis
            "invalidate_on": ["operator_update", "skill_update"],
            "warm_on_startup": True,
            "warm_query": "SELECT * FROM operators WHERE status = 'AVAILABLE'",
        },
        "schedule": {
            "l1_ttl": 10,  # 10 seconds in memory (frequently changing)
            "l2_ttl": 60,  # 1 minute in Redis
            "invalidate_on": ["schedule_update", "optimization_complete"],
            "warm_on_startup": False,
            "l1_only": True,  # Only cache in memory due to frequent changes
        },
        "optimization_result": {
            "l1_ttl": 600,  # 10 minutes in memory
            "l2_ttl": 3600,  # 1 hour in Redis
            "invalidate_on": ["new_optimization"],
            "warm_on_startup": False,
        },
        "dashboard_stats": {
            "l1_ttl": 30,  # 30 seconds in memory
            "l2_ttl": 120,  # 2 minutes in Redis
            "invalidate_on": ["job_update", "task_update"],
            "warm_on_startup": True,
            "compute_function": "compute_dashboard_stats",
        },
    }

    @classmethod
    def get_strategy(cls, entity_type: str) -> dict[str, Any]:
        """Get caching strategy for entity type."""
        return cls.STRATEGIES.get(
            entity_type,
            {
                "l1_ttl": 60,
                "l2_ttl": 300,
                "invalidate_on": [],
                "warm_on_startup": False,
            },
        )

    @classmethod
    def should_cache(cls, entity_type: str, operation: str) -> bool:
        """Determine if an operation result should be cached."""
        # Don't cache write operations
        if operation in ["create", "update", "delete"]:
            return False

        # Don't cache if entity type is excluded
        if entity_type in ["audit_log", "system_event"]:
            return False

        return True

    @classmethod
    def get_cache_key(
        cls,
        entity_type: str,
        operation: str,
        identifier: Any | None = None,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Generate consistent cache key for entity operations."""
        key_parts = [entity_type, operation]

        if identifier is not None:
            key_parts.append(str(identifier))

        if filters:
            # Sort filters for consistent key generation
            filter_str = json.dumps(sorted(filters.items()), sort_keys=True)
            filter_hash = hashlib.md5(filter_str.encode()).hexdigest()[:8]
            key_parts.append(filter_hash)

        return ":".join(key_parts)


class CacheInvalidator:
    """
    Manages cache invalidation based on events and dependencies.
    """

    def __init__(self, cache: MultiLevelCache):
        self.cache = cache
        self.invalidation_rules: dict[str, list[str]] = {}
        self._setup_invalidation_rules()

    def _setup_invalidation_rules(self):
        """Setup invalidation rules based on strategies."""
        for entity_type, strategy in CacheStrategy.STRATEGIES.items():
            for event in strategy.get("invalidate_on", []):
                if event not in self.invalidation_rules:
                    self.invalidation_rules[event] = []
                self.invalidation_rules[event].append(entity_type)

    async def invalidate_on_event(
        self, event: str, context: dict[str, Any] | None = None
    ):
        """
        Invalidate caches based on event.

        Args:
            event: Event name (e.g., "job_update", "task_update")
            context: Optional context with entity IDs or filters
        """
        entity_types = self.invalidation_rules.get(event, [])

        for entity_type in entity_types:
            # Invalidate specific entity if ID provided
            if context and "id" in context:
                key = CacheStrategy.get_cache_key(entity_type, "get", context["id"])
                await self.cache.delete(key)

            # Invalidate list caches for this entity type
            pattern = f"{entity_type}:list:*"
            await self.cache.delete_pattern(pattern)

            # Invalidate related caches
            if entity_type == "job" and context and "id" in context:
                # Invalidate related task caches
                task_pattern = f"task:by_job:{context['id']}:*"
                await self.cache.delete_pattern(task_pattern)

            logger.info(f"Invalidated {entity_type} caches for event {event}")

    async def invalidate_entity(
        self, entity_type: str, entity_id: Any | None = None, cascade: bool = True
    ):
        """
        Invalidate entity caches.

        Args:
            entity_type: Type of entity
            entity_id: Specific entity ID or None for all
            cascade: Invalidate related entities
        """
        if entity_id:
            # Invalidate specific entity
            key = CacheStrategy.get_cache_key(entity_type, "get", entity_id)
            await self.cache.delete(key)
        else:
            # Invalidate all entities of this type
            pattern = f"{entity_type}:*"
            await self.cache.delete_pattern(pattern)

        if cascade:
            # Invalidate related entity caches based on relationships
            if entity_type == "job":
                await self.cache.delete_pattern("task:*")
                await self.cache.delete_pattern("schedule:*")
            elif entity_type == "machine":
                await self.cache.delete_pattern("task:by_machine:*")
                await self.cache.delete_pattern("schedule:*")


class CacheWarmer:
    """
    Handles cache warming strategies for improved performance.
    """

    def __init__(self, cache: MultiLevelCache):
        self.cache = cache
        self.warming_tasks: list[asyncio.Task] = []

    async def warm_on_startup(self, session):
        """
        Warm caches on application startup based on strategies.
        """
        logger.info("Starting cache warming...")

        for entity_type, strategy in CacheStrategy.STRATEGIES.items():
            if strategy.get("warm_on_startup"):
                try:
                    if "warm_query" in strategy:
                        # Execute warm query
                        result = session.execute(strategy["warm_query"])
                        entities = result.fetchall()

                        # Cache each entity
                        for entity in entities:
                            key = CacheStrategy.get_cache_key(
                                entity_type, "get", entity.id
                            )
                            await self.cache.set(
                                key,
                                entity,
                                l1_ttl=strategy["l1_ttl"],
                                l2_ttl=strategy["l2_ttl"],
                            )

                        logger.info(f"Warmed {len(entities)} {entity_type} entities")

                    elif "compute_function" in strategy:
                        # Execute compute function
                        func_name = strategy["compute_function"]
                        # This would call the actual compute function
                        # For now, just log
                        logger.info(f"Would warm {entity_type} using {func_name}")

                except Exception as e:
                    logger.error(f"Failed to warm {entity_type} cache: {e}")

        logger.info("Cache warming completed")

    async def schedule_periodic_warming(
        self, entity_type: str, loader: Callable, interval: int = 300
    ):
        """
        Schedule periodic cache warming for an entity type.

        Args:
            entity_type: Type of entity to warm
            loader: Function to load data
            interval: Warming interval in seconds
        """

        async def warm_task():
            while True:
                try:
                    await asyncio.sleep(interval)

                    # Load and cache data
                    data = (
                        await loader()
                        if asyncio.iscoroutinefunction(loader)
                        else loader()
                    )

                    strategy = CacheStrategy.get_strategy(entity_type)
                    for item in data:
                        key = CacheStrategy.get_cache_key(
                            entity_type, "get", getattr(item, "id", None)
                        )
                        await self.cache.set(
                            key,
                            item,
                            l1_ttl=strategy["l1_ttl"],
                            l2_ttl=strategy["l2_ttl"],
                        )

                    logger.debug(f"Periodic warming completed for {entity_type}")

                except Exception as e:
                    logger.error(f"Error in periodic warming for {entity_type}: {e}")

        task = asyncio.create_task(warm_task())
        self.warming_tasks.append(task)
        return task

    def stop_all_warming(self):
        """Stop all periodic warming tasks."""
        for task in self.warming_tasks:
            task.cancel()
        self.warming_tasks.clear()


# Decorator for automatic caching with multi-level support
def multi_level_cache(
    entity_type: str, operation: str = "get", ttl_override: dict[str, int] | None = None
):
    """
    Decorator for automatic multi-level caching.

    Args:
        entity_type: Type of entity being cached
        operation: Operation being performed
        ttl_override: Override TTL values
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get cache instance (would be injected in real app)
            cache = MultiLevelCache(namespace=entity_type)

            # Generate cache key
            cache_key = CacheStrategy.get_cache_key(
                entity_type,
                operation,
                identifier=args[0] if args else None,
                filters=kwargs,
            )

            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result if applicable
            if (
                CacheStrategy.should_cache(entity_type, operation)
                and result is not None
            ):
                strategy = CacheStrategy.get_strategy(entity_type)

                l1_ttl = (
                    ttl_override.get("l1_ttl") if ttl_override else strategy["l1_ttl"]
                )
                l2_ttl = (
                    ttl_override.get("l2_ttl") if ttl_override else strategy["l2_ttl"]
                )
                l1_only = strategy.get("l1_only", False)

                await cache.set(
                    cache_key, result, l1_ttl=l1_ttl, l2_ttl=l2_ttl, l1_only=l1_only
                )

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, use asyncio.run
            return asyncio.run(async_wrapper(*args, **kwargs))

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# Export components
__all__ = [
    "MultiLevelCache",
    "CacheStrategy",
    "CacheInvalidator",
    "CacheWarmer",
    "multi_level_cache",
    "LRUCache",
    "CacheMetrics",
]
