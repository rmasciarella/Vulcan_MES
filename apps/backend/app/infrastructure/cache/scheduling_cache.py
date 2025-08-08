"""
High-Performance Caching System for Scheduling Data

Implements multi-level caching strategies optimized for scheduling operations,
including task dependencies, resource availability, and solver results.
"""

import asyncio
import hashlib
import json
import pickle
import time
from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import UUID

import numpy as np
import redis.asyncio as redis
from aiocache import Cache, cached
from aiocache.serializers import PickleSerializer

from app.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    size_bytes: int
    created_at: datetime
    last_accessed: datetime
    access_count: int
    ttl_seconds: int
    computation_time_ms: float
    tags: Set[str]


class LRUCache:
    """Thread-safe LRU cache implementation for in-memory caching."""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.current_memory = 0
        self.hits = 0
        self.misses = 0
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                entry = self.cache.pop(key)
                entry.last_accessed = datetime.now()
                entry.access_count += 1
                self.cache[key] = entry
                self.hits += 1
                return entry.value
            
            self.misses += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
        tags: Optional[Set[str]] = None,
        computation_time_ms: float = 0
    ):
        """Set value in cache."""
        async with self.lock:
            # Calculate size
            size_bytes = len(pickle.dumps(value))
            
            # Check if we need to evict entries
            while (
                (len(self.cache) >= self.max_size or 
                 self.current_memory + size_bytes > self.max_memory_bytes)
                and len(self.cache) > 0
            ):
                # Remove least recently used
                oldest_key, oldest_entry = self.cache.popitem(last=False)
                self.current_memory -= oldest_entry.size_bytes
                logger.debug(f"Evicted cache entry: {oldest_key}")
            
            # Add new entry
            entry = CacheEntry(
                key=key,
                value=value,
                size_bytes=size_bytes,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                access_count=0,
                ttl_seconds=ttl_seconds,
                computation_time_ms=computation_time_ms,
                tags=tags or set()
            )
            
            self.cache[key] = entry
            self.current_memory += size_bytes
    
    async def invalidate_by_tags(self, tags: Set[str]) -> int:
        """Invalidate all entries with any of the given tags."""
        async with self.lock:
            keys_to_remove = []
            for key, entry in self.cache.items():
                if entry.tags & tags:  # Intersection
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                entry = self.cache.pop(key)
                self.current_memory -= entry.size_bytes
            
            return len(keys_to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "memory_mb": self.current_memory / 1024 / 1024,
            "max_memory_mb": self.max_memory_bytes / 1024 / 1024,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "avg_access_count": np.mean([e.access_count for e in self.cache.values()]) if self.cache else 0
        }


class SchedulingCache:
    """Multi-level caching system optimized for scheduling data."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        enable_l1: bool = True,
        enable_l2: bool = True,
        enable_l3: bool = False
    ):
        # L1: In-memory LRU cache (fastest, smallest)
        self.l1_cache = LRUCache(max_size=500, max_memory_mb=50) if enable_l1 else None
        
        # L2: Local Redis cache (fast, medium size)
        self.l2_cache = None
        if enable_l2 and redis_url:
            self.l2_cache = Cache(
                Cache.REDIS,
                endpoint=redis_url,
                namespace="scheduling",
                serializer=PickleSerializer(),
                ttl=3600
            )
        
        # L3: Distributed cache (slower, largest)
        self.l3_cache = None  # Could be implemented with Redis Cluster or similar
        
        # Cache key patterns for different data types
        self.key_patterns = {
            "schedule": "schedule:{schedule_id}:v{version}",
            "job": "job:{job_id}",
            "task": "task:{task_id}",
            "dependencies": "deps:job:{job_id}",
            "resource_availability": "resource:{resource_id}:avail:{date}",
            "solver_result": "solver:{hash}",
            "critical_path": "critical_path:{schedule_id}",
            "utilization": "utilization:{resource_id}:{date_range}"
        }
        
        # Cache statistics
        self.stats = defaultdict(lambda: {"hits": 0, "misses": 0, "saves": 0})
        
        # Computation cache for expensive operations
        self.computation_cache: Dict[str, Tuple[Any, float]] = {}
    
    def _generate_key(self, pattern: str, **kwargs) -> str:
        """Generate cache key from pattern."""
        return pattern.format(**kwargs)
    
    def _hash_solver_input(self, jobs: List[Any], constraints: Dict) -> str:
        """Generate hash for solver input to cache results."""
        # Create deterministic hash of solver input
        input_data = {
            "jobs": [str(j.id) for j in jobs],
            "constraints": constraints
        }
        
        serialized = json.dumps(input_data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    async def get_schedule(
        self,
        schedule_id: UUID,
        version: int = None
    ) -> Optional[Any]:
        """Get schedule from cache."""
        key = self._generate_key(
            self.key_patterns["schedule"],
            schedule_id=schedule_id,
            version=version or "latest"
        )
        
        # Try L1 cache first
        if self.l1_cache:
            value = await self.l1_cache.get(key)
            if value:
                self.stats["schedule"]["hits"] += 1
                return value
        
        # Try L2 cache
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value:
                self.stats["schedule"]["misses"] += 1
                # Promote to L1
                if self.l1_cache:
                    await self.l1_cache.set(key, value, ttl_seconds=300)
                return value
        
        self.stats["schedule"]["misses"] += 1
        return None
    
    async def set_schedule(
        self,
        schedule_id: UUID,
        schedule: Any,
        version: int = None,
        ttl_seconds: int = 3600
    ):
        """Cache schedule data."""
        key = self._generate_key(
            self.key_patterns["schedule"],
            schedule_id=schedule_id,
            version=version or "latest"
        )
        
        tags = {f"schedule:{schedule_id}", "schedule"}
        
        # Save to L1
        if self.l1_cache:
            await self.l1_cache.set(key, schedule, ttl_seconds=ttl_seconds, tags=tags)
        
        # Save to L2
        if self.l2_cache:
            await self.l2_cache.set(key, schedule, ttl=ttl_seconds)
        
        self.stats["schedule"]["saves"] += 1
    
    async def get_task_dependencies(self, job_id: UUID) -> Optional[Dict]:
        """Get cached task dependencies for a job."""
        key = self._generate_key(self.key_patterns["dependencies"], job_id=job_id)
        
        if self.l1_cache:
            value = await self.l1_cache.get(key)
            if value:
                self.stats["dependencies"]["hits"] += 1
                return value
        
        self.stats["dependencies"]["misses"] += 1
        return None
    
    async def set_task_dependencies(
        self,
        job_id: UUID,
        dependencies: Dict,
        ttl_seconds: int = 7200
    ):
        """Cache task dependencies."""
        key = self._generate_key(self.key_patterns["dependencies"], job_id=job_id)
        
        if self.l1_cache:
            await self.l1_cache.set(
                key,
                dependencies,
                ttl_seconds=ttl_seconds,
                tags={f"job:{job_id}", "dependencies"}
            )
        
        self.stats["dependencies"]["saves"] += 1
    
    async def get_resource_availability(
        self,
        resource_id: UUID,
        date: datetime
    ) -> Optional[List[Tuple[datetime, datetime]]]:
        """Get cached resource availability."""
        key = self._generate_key(
            self.key_patterns["resource_availability"],
            resource_id=resource_id,
            date=date.date().isoformat()
        )
        
        if self.l1_cache:
            value = await self.l1_cache.get(key)
            if value:
                self.stats["resource_availability"]["hits"] += 1
                return value
        
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value:
                self.stats["resource_availability"]["misses"] += 1
                return value
        
        self.stats["resource_availability"]["misses"] += 1
        return None
    
    async def set_resource_availability(
        self,
        resource_id: UUID,
        date: datetime,
        availability: List[Tuple[datetime, datetime]],
        ttl_seconds: int = 1800
    ):
        """Cache resource availability."""
        key = self._generate_key(
            self.key_patterns["resource_availability"],
            resource_id=resource_id,
            date=date.date().isoformat()
        )
        
        tags = {f"resource:{resource_id}", "availability", date.date().isoformat()}
        
        if self.l1_cache:
            await self.l1_cache.set(key, availability, ttl_seconds=ttl_seconds, tags=tags)
        
        if self.l2_cache:
            await self.l2_cache.set(key, availability, ttl=ttl_seconds)
        
        self.stats["resource_availability"]["saves"] += 1
    
    async def get_solver_result(
        self,
        jobs: List[Any],
        constraints: Dict
    ) -> Optional[Any]:
        """Get cached solver result for given input."""
        hash_key = self._hash_solver_input(jobs, constraints)
        key = self._generate_key(self.key_patterns["solver_result"], hash=hash_key)
        
        # Solver results are expensive, check all cache levels
        if self.l1_cache:
            value = await self.l1_cache.get(key)
            if value:
                self.stats["solver"]["hits"] += 1
                logger.info(f"Solver cache hit: {hash_key}")
                return value
        
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value:
                self.stats["solver"]["hits"] += 1
                logger.info(f"Solver L2 cache hit: {hash_key}")
                # Promote to L1
                if self.l1_cache:
                    await self.l1_cache.set(key, value, ttl_seconds=600)
                return value
        
        self.stats["solver"]["misses"] += 1
        return None
    
    async def set_solver_result(
        self,
        jobs: List[Any],
        constraints: Dict,
        result: Any,
        computation_time_ms: float,
        ttl_seconds: int = 1800
    ):
        """Cache solver result."""
        hash_key = self._hash_solver_input(jobs, constraints)
        key = self._generate_key(self.key_patterns["solver_result"], hash=hash_key)
        
        tags = {"solver", f"jobs:{len(jobs)}"}
        
        # Cache in both levels for expensive computations
        if self.l1_cache:
            await self.l1_cache.set(
                key,
                result,
                ttl_seconds=ttl_seconds,
                tags=tags,
                computation_time_ms=computation_time_ms
            )
        
        if self.l2_cache:
            await self.l2_cache.set(key, result, ttl=ttl_seconds)
        
        self.stats["solver"]["saves"] += 1
        logger.info(
            f"Cached solver result: {hash_key}, "
            f"computation_time: {computation_time_ms:.2f}ms"
        )
    
    async def get_critical_path(self, schedule_id: UUID) -> Optional[Dict]:
        """Get cached critical path for schedule."""
        key = self._generate_key(
            self.key_patterns["critical_path"],
            schedule_id=schedule_id
        )
        
        if self.l1_cache:
            value = await self.l1_cache.get(key)
            if value:
                self.stats["critical_path"]["hits"] += 1
                return value
        
        self.stats["critical_path"]["misses"] += 1
        return None
    
    async def set_critical_path(
        self,
        schedule_id: UUID,
        critical_path: Dict,
        ttl_seconds: int = 600
    ):
        """Cache critical path calculation."""
        key = self._generate_key(
            self.key_patterns["critical_path"],
            schedule_id=schedule_id
        )
        
        if self.l1_cache:
            await self.l1_cache.set(
                key,
                critical_path,
                ttl_seconds=ttl_seconds,
                tags={f"schedule:{schedule_id}", "critical_path"}
            )
        
        self.stats["critical_path"]["saves"] += 1
    
    async def invalidate_schedule_cache(self, schedule_id: UUID):
        """Invalidate all cache entries related to a schedule."""
        tags = {f"schedule:{schedule_id}"}
        
        invalidated = 0
        if self.l1_cache:
            invalidated += await self.l1_cache.invalidate_by_tags(tags)
        
        # For L2 cache, we'd need to track keys or use Redis tags
        if self.l2_cache:
            # Invalidate known patterns
            patterns = [
                self._generate_key(
                    self.key_patterns["schedule"],
                    schedule_id=schedule_id,
                    version="*"
                ),
                self._generate_key(
                    self.key_patterns["critical_path"],
                    schedule_id=schedule_id
                )
            ]
            
            for pattern in patterns:
                try:
                    await self.l2_cache.delete(pattern)
                    invalidated += 1
                except Exception as e:
                    logger.error(f"Error invalidating L2 cache: {e}")
        
        logger.info(f"Invalidated {invalidated} cache entries for schedule {schedule_id}")
        return invalidated
    
    async def invalidate_job_cache(self, job_id: UUID):
        """Invalidate all cache entries related to a job."""
        tags = {f"job:{job_id}"}
        
        invalidated = 0
        if self.l1_cache:
            invalidated += await self.l1_cache.invalidate_by_tags(tags)
        
        logger.info(f"Invalidated {invalidated} cache entries for job {job_id}")
        return invalidated
    
    async def warm_cache(
        self,
        schedule_id: UUID,
        jobs: List[Any],
        resources: List[Any]
    ):
        """Pre-warm cache with frequently accessed data."""
        logger.info(f"Warming cache for schedule {schedule_id}")
        
        warm_tasks = []
        
        # Warm job dependencies
        for job in jobs[:10]:  # Limit to avoid overwhelming
            if hasattr(job, 'get_dependencies'):
                deps = await job.get_dependencies()
                warm_tasks.append(
                    self.set_task_dependencies(job.id, deps)
                )
        
        # Warm resource availability
        today = datetime.now().date()
        for resource in resources[:10]:
            for days_ahead in range(7):
                date = today + timedelta(days=days_ahead)
                if hasattr(resource, 'get_availability'):
                    avail = await resource.get_availability(date)
                    warm_tasks.append(
                        self.set_resource_availability(
                            resource.id,
                            datetime.combine(date, datetime.min.time()),
                            avail
                        )
                    )
        
        # Execute warming tasks concurrently
        if warm_tasks:
            await asyncio.gather(*warm_tasks, return_exceptions=True)
        
        logger.info(f"Cache warming completed for schedule {schedule_id}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        stats = {
            "overall": {
                "total_hits": sum(s["hits"] for s in self.stats.values()),
                "total_misses": sum(s["misses"] for s in self.stats.values()),
                "total_saves": sum(s["saves"] for s in self.stats.values())
            },
            "by_type": dict(self.stats)
        }
        
        if self.l1_cache:
            stats["l1_cache"] = self.l1_cache.get_stats()
        
        # Calculate hit rates
        for key, values in stats["by_type"].items():
            total = values["hits"] + values["misses"]
            values["hit_rate"] = (values["hits"] / total * 100) if total > 0 else 0
        
        overall_total = stats["overall"]["total_hits"] + stats["overall"]["total_misses"]
        stats["overall"]["hit_rate"] = (
            (stats["overall"]["total_hits"] / overall_total * 100)
            if overall_total > 0 else 0
        )
        
        return stats


class CachingDecorator:
    """Decorator for caching expensive scheduling operations."""
    
    def __init__(self, cache: SchedulingCache):
        self.cache = cache
    
    def cached_operation(
        self,
        cache_type: str,
        ttl_seconds: int = 3600,
        key_func: Optional[Callable] = None
    ):
        """Decorator to cache function results."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    cache_key = f"{cache_type}:{func.__name__}:{str(args)}:{str(kwargs)}"
                
                # Try to get from cache
                if cache_type == "solver":
                    # Special handling for solver results
                    if len(args) >= 2:
                        result = await self.cache.get_solver_result(args[0], args[1])
                        if result:
                            return result
                
                # Execute function and measure time
                start_time = time.perf_counter()
                result = await func(*args, **kwargs)
                computation_time_ms = (time.perf_counter() - start_time) * 1000
                
                # Cache result
                if cache_type == "solver" and len(args) >= 2:
                    await self.cache.set_solver_result(
                        args[0],
                        args[1],
                        result,
                        computation_time_ms,
                        ttl_seconds
                    )
                
                return result
            
            return wrapper
        return decorator


# Global cache instance (to be initialized with configuration)
scheduling_cache: Optional[SchedulingCache] = None


def init_scheduling_cache(
    redis_url: Optional[str] = None,
    enable_l1: bool = True,
    enable_l2: bool = True
) -> SchedulingCache:
    """Initialize global scheduling cache."""
    global scheduling_cache
    scheduling_cache = SchedulingCache(
        redis_url=redis_url,
        enable_l1=enable_l1,
        enable_l2=enable_l2
    )
    logger.info("Scheduling cache initialized")
    return scheduling_cache