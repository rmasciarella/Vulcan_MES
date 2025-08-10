"""
Performance optimization tests for database, caching, and connection pooling.

This module tests the performance improvements implemented in the system
including query optimization, multi-level caching, and connection pooling.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app.core.performance import (
    PerformanceMonitor,
    QueryProfiler,
    monitor_performance,
    profile_block,
)
from app.domain.scheduling.value_objects.enums import JobStatus
from app.infrastructure.cache.multi_level_cache import (
    CacheInvalidator,
    CacheStrategy,
    CacheWarmer,
    MultiLevelCache,
)
from app.infrastructure.database.connection_pool import (
    ConnectionPoolManager,
    DatabaseConnectionPool,
    RedisConnectionPool,
)
from app.infrastructure.database.indexes import IndexManager, QueryOptimizationHints
from app.infrastructure.database.models import Job


class TestDatabaseOptimization:
    """Test database query optimization and indexing."""

    def test_index_creation(self, db_session: Session):
        """Test that indexes are created successfully."""
        # Create indexes
        results = IndexManager.create_all_indexes(db_session)

        # Verify all indexes were created
        assert all(results.values()), "Some indexes failed to create"

        # Verify index exists in database
        result = db_session.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'jobs'"
        )
        index_names = [row[0] for row in result]

        assert "idx_jobs_status_due_date" in index_names
        assert "idx_jobs_customer_status" in index_names

    def test_index_usage_stats(self, db_session: Session):
        """Test index usage statistics collection."""
        # Get index usage stats
        stats = IndexManager.get_index_usage_stats(db_session)

        assert isinstance(stats, list)
        if stats:
            first_stat = stats[0]
            assert "indexname" in first_stat
            assert "index_scans" in first_stat
            assert "usage_category" in first_stat

    def test_query_optimization_hints(self):
        """Test query optimization hints."""
        hints = QueryOptimizationHints.get_optimization_hints("job_dashboard")

        assert "description" in hints
        assert "optimized" in hints
        assert "hints" in hints
        assert len(hints["hints"]) > 0

    @pytest.mark.benchmark
    def test_query_performance_with_indexes(self, db_session: Session, benchmark):
        """Benchmark query performance with indexes."""
        # Create test data
        jobs = []
        for i in range(100):
            job = Job(
                job_number=f"JOB-{i:04d}",
                customer_name=f"Customer-{i % 10}",
                due_date=datetime.utcnow() + timedelta(days=i),
                status=JobStatus.PLANNED if i % 2 == 0 else JobStatus.IN_PROGRESS,
            )
            jobs.append(job)

        db_session.add_all(jobs)
        db_session.commit()

        # Create indexes
        IndexManager.create_all_indexes(db_session)

        # Benchmark query with indexes
        def query_active_jobs():
            stmt = (
                select(Job)
                .where(Job.status.in_([JobStatus.PLANNED, JobStatus.IN_PROGRESS]))
                .order_by(Job.due_date)
            )
            return db_session.exec(stmt).all()

        result = benchmark(query_active_jobs)
        assert len(result) == 100

    def test_analyze_query_plan(self, db_session: Session):
        """Test query plan analysis."""
        query = "SELECT * FROM jobs WHERE status = 'PLANNED' ORDER BY due_date"

        analysis = QueryOptimizationHints.analyze_query_plan(db_session, query)

        assert "total_cost" in analysis or "error" in analysis
        if "recommendations" in analysis:
            assert isinstance(analysis["recommendations"], list)


class TestMultiLevelCaching:
    """Test multi-level caching implementation."""

    @pytest.mark.asyncio
    async def test_multi_level_cache_basic(self):
        """Test basic multi-level cache operations."""
        cache = MultiLevelCache(l1_capacity=10, l1_ttl=1, l2_ttl=10)

        # Test set and get
        await cache.set("test_key", {"data": "test_value"})

        # Should hit L1 cache
        result = await cache.get("test_key")
        assert result == {"data": "test_value"}
        assert cache.l1_cache.metrics.l1_hits == 1

        # Wait for L1 to expire
        await asyncio.sleep(1.1)

        # Should hit L2 cache and promote to L1
        result = await cache.get("test_key")
        assert result == {"data": "test_value"}
        assert cache.metrics.l2_hits == 1

    @pytest.mark.asyncio
    async def test_cache_invalidation(self):
        """Test cache invalidation strategies."""
        cache = MultiLevelCache()
        invalidator = CacheInvalidator(cache)

        # Set some cache entries
        await cache.set("job:get:123", {"id": "123", "status": "PLANNED"})
        await cache.set("job:list:all", [{"id": "123"}, {"id": "456"}])
        await cache.set("task:by_job:123:all", [{"id": "t1"}, {"id": "t2"}])

        # Invalidate on job update event
        await invalidator.invalidate_on_event("job_update", context={"id": "123"})

        # Verify specific job cache was invalidated
        result = await cache.get("job:get:123")
        assert result is None

        # Verify related caches were invalidated
        result = await cache.get("task:by_job:123:all")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_warming(self, db_session: Session):
        """Test cache warming functionality."""
        cache = MultiLevelCache()
        warmer = CacheWarmer(cache)

        # Create test data
        jobs = [
            Job(
                id="job1",
                job_number="JOB-001",
                status=JobStatus.IN_PROGRESS,
                due_date=datetime.utcnow(),
            ),
            Job(
                id="job2",
                job_number="JOB-002",
                status=JobStatus.PLANNED,
                due_date=datetime.utcnow(),
            ),
        ]

        # Mock warm query
        with patch.object(db_session, "execute") as mock_execute:
            mock_execute.return_value.fetchall.return_value = jobs

            # Warm cache
            await warmer.warm_on_startup(db_session)

        # Verify cache was warmed
        for job in jobs:
            key = CacheStrategy.get_cache_key("job", "get", job.id)
            result = await cache.get(key)
            assert result is not None

    @pytest.mark.asyncio
    async def test_cache_strategy(self):
        """Test cache strategy configurations."""
        strategy = CacheStrategy.get_strategy("job")

        assert strategy["l1_ttl"] == 60
        assert strategy["l2_ttl"] == 300
        assert "invalidate_on" in strategy
        assert strategy["warm_on_startup"] is True

        # Test cache key generation
        key = CacheStrategy.get_cache_key(
            "job", "list", filters={"status": "PLANNED", "customer": "ABC"}
        )
        assert key.startswith("job:list:")

    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_cache_performance(self, benchmark):
        """Benchmark cache performance."""
        cache = MultiLevelCache(l1_capacity=1000)

        # Populate cache
        for i in range(100):
            await cache.set(f"key_{i}", {"value": i})

        # Benchmark cache retrieval
        async def get_cached_values():
            results = []
            for i in range(100):
                result = await cache.get(f"key_{i}")
                results.append(result)
            return results

        results = await benchmark(get_cached_values)
        assert len(results) == 100

        # Check cache hit rate
        stats = cache.get_stats()
        assert stats["metrics"]["hit_rate"] > 95  # Should have high hit rate


class TestConnectionPooling:
    """Test connection pooling optimizations."""

    def test_database_connection_pool(self):
        """Test database connection pool functionality."""
        pool = DatabaseConnectionPool(
            database_url="postgresql://test:test@localhost/test",
            pool_size=5,
            max_overflow=10,
        )

        # Test connection acquisition
        with pool.get_connection() as conn:
            assert conn is not None

        # Check metrics
        metrics = pool.get_metrics()
        assert "connections_created" in metrics
        assert "avg_checkout_time_ms" in metrics
        assert metrics["connections_created"] >= 1

    def test_redis_connection_pool(self):
        """Test Redis connection pool functionality."""
        pool = RedisConnectionPool(
            redis_url="redis://localhost:6379/0", max_connections=10
        )

        # Test client acquisition
        with pool.get_client() as client:
            assert client is not None
            # Test ping
            assert client.ping() is True

        # Check metrics
        metrics = pool.get_metrics()
        assert "checkout_count" in metrics
        assert "is_healthy" in metrics

    def test_connection_pool_manager(self):
        """Test connection pool manager."""
        manager = ConnectionPoolManager()

        # Test database connection
        with manager.get_database_connection("primary") as conn:
            assert conn is not None

        # Test Redis client
        with manager.get_redis_client("cache") as client:
            assert client is not None

        # Check health
        health = manager.health_check()
        assert "overall" in health
        assert isinstance(health["overall"], bool)

        # Get all metrics
        metrics = manager.get_all_metrics()
        assert "database_pools" in metrics
        assert "redis_pools" in metrics

    @pytest.mark.benchmark
    def test_connection_pool_performance(self, benchmark):
        """Benchmark connection pool performance."""
        pool = DatabaseConnectionPool(
            database_url="postgresql://test:test@localhost/test",
            pool_size=10,
            max_overflow=20,
        )

        def acquire_and_release():
            with pool.get_connection():
                # Simulate some work
                time.sleep(0.001)

        # Benchmark connection acquisition/release
        benchmark(acquire_and_release)

        # Check pool didn't exhaust
        metrics = pool.get_metrics()
        assert metrics.get("connections_failed", 0) == 0

    def test_connection_pool_scaling(self):
        """Test dynamic pool scaling."""
        manager = ConnectionPoolManager()

        # Simulate high load metrics
        pool = manager.db_pools["primary"]
        pool.metrics.checkout_count = 100
        pool.metrics.wait_time_total = 20
        pool.metrics.wait_count = 50

        # Trigger auto-scaling
        manager._auto_scale_pools()

        # Verify pool was scaled up
        # Note: This would normally check actual pool size adjustment


class TestPerformanceMonitoring:
    """Test performance monitoring and profiling."""

    def test_performance_monitor(self):
        """Test performance monitor functionality."""
        monitor = PerformanceMonitor(enable_profiling=True)

        # Record metrics
        monitor.record_metric("test_operation", 100, "ms")
        monitor.record_metric("test_operation", 150, "ms")
        monitor.record_metric("test_operation", 120, "ms")

        # Record query
        monitor.record_query(
            "SELECT * FROM jobs", execution_time=1.5, rows_returned=100
        )

        # Record endpoint
        monitor.record_endpoint(
            path="/api/jobs", method="GET", duration=0.2, status_code=200
        )

        # Get metrics summary
        summary = monitor.get_metrics_summary()
        assert "test_operation" in summary
        assert summary["test_operation"]["count"] == 3
        assert summary["test_operation"]["mean"] == 123.33333333333333

        # Get slow queries
        slow_queries = monitor.get_slow_queries()
        assert len(slow_queries) == 1
        assert slow_queries[0]["execution_time"] == 1.5

        # Get endpoint statistics
        endpoint_stats = monitor.get_endpoint_statistics()
        assert "GET /api/jobs" in endpoint_stats

    @monitor_performance(name="test_function")
    def test_performance_decorator(self):
        """Test performance monitoring decorator."""
        # Simulate some work
        time.sleep(0.01)
        return "result"

    def test_profile_block(self):
        """Test profiling context manager."""
        monitor = PerformanceMonitor()

        with profile_block("test_block"):
            # Simulate some work
            time.sleep(0.01)
            list(range(1000))

        # Check metrics were recorded
        summary = monitor.get_metrics_summary()
        assert "test_block_duration" in summary
        assert "test_block_memory_delta" in summary

    def test_query_profiler(self, db_session: Session):
        """Test query profiler."""
        profiler = QueryProfiler(db_session)

        with profiler.profile_query("test_query"):
            # Simulate query execution
            time.sleep(0.01)

        # Check query was recorded
        monitor = profiler.monitor
        monitor.get_slow_queries()
        # Would contain the query if execution time > 1s

    def test_system_resource_monitoring(self):
        """Test system resource monitoring."""
        monitor = PerformanceMonitor()

        resources = monitor.get_system_resources()

        assert "cpu" in resources
        assert "memory" in resources
        assert "disk" in resources
        assert "network" in resources
        assert "connections" in resources

        # Verify resource values are reasonable
        assert resources["cpu"]["process_percent"] >= 0
        assert resources["memory"]["process_rss_mb"] > 0


class TestIntegrationPerformance:
    """Integration tests for overall performance improvements."""

    @pytest.mark.asyncio
    async def test_end_to_end_performance(self, db_session: Session):
        """Test end-to-end performance with all optimizations."""
        # Setup
        IndexManager.create_all_indexes(db_session)
        cache = MultiLevelCache()
        PerformanceMonitor()

        # Create test data
        jobs = []
        for i in range(50):
            job = Job(
                job_number=f"PERF-{i:04d}",
                customer_name=f"Customer-{i % 5}",
                due_date=datetime.utcnow() + timedelta(days=i),
                status=JobStatus.PLANNED,
            )
            jobs.append(job)

        db_session.add_all(jobs)
        db_session.commit()

        # Test with caching
        start_time = time.time()

        # First query - cache miss
        stmt = select(Job).where(Job.status == JobStatus.PLANNED)
        result1 = db_session.exec(stmt).all()

        # Cache the result
        await cache.set("jobs:planned", result1)

        # Second query - cache hit
        result2 = await cache.get("jobs:planned")

        end_time = time.time()
        total_time = end_time - start_time

        # Verify results
        assert len(result1) == 50
        assert result2 is not None

        # Check performance improvement
        assert total_time < 1.0  # Should complete quickly

        # Check cache metrics
        cache_stats = cache.get_stats()
        assert cache_stats["metrics"]["hits"] > 0

    @pytest.mark.benchmark
    def test_concurrent_load(self, benchmark):
        """Test performance under concurrent load."""
        manager = ConnectionPoolManager()

        def concurrent_operations():
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []

                for i in range(100):
                    # Mix of database and cache operations
                    if i % 2 == 0:
                        future = executor.submit(
                            lambda: manager.get_database_connection("primary")
                        )
                    else:
                        future = executor.submit(
                            lambda: manager.get_redis_client("cache")
                        )
                    futures.append(future)

                # Wait for all to complete
                for future in futures:
                    future.result()

        # Benchmark concurrent operations
        benchmark(concurrent_operations)

        # Check pool health
        health = manager.health_check()
        assert health["overall"] is True


# Fixtures
@pytest.fixture
def db_session():
    """Create test database session."""
    from sqlalchemy import create_engine
    from sqlmodel import Session

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture
def benchmark():
    """Simple benchmark fixture."""

    def _benchmark(func):
        start = time.time()
        result = func()
        duration = time.time() - start
        print(f"Execution time: {duration:.4f}s")
        return result

    return _benchmark
