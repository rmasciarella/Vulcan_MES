"""
Advanced connection pooling with health checks, monitoring, and failover.

This module provides sophisticated connection pool management for both
database and Redis connections with automatic health checks, failover,
and performance monitoring.
"""

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from threading import Lock, Thread
from typing import Any

import redis
from redis.sentinel import Sentinel
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import DBAPIError, TimeoutError
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """Metrics for connection pool monitoring."""

    connections_created: int = 0
    connections_closed: int = 0
    connections_recycled: int = 0
    connections_failed: int = 0
    checkout_time_total: float = 0
    checkout_count: int = 0
    overflow_created: int = 0
    pool_size_current: int = 0
    pool_size_overflow: int = 0
    wait_time_total: float = 0
    wait_count: int = 0
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    last_health_check: datetime | None = None

    @property
    def avg_checkout_time(self) -> float:
        """Average connection checkout time."""
        return (
            (self.checkout_time_total / self.checkout_count)
            if self.checkout_count > 0
            else 0
        )

    @property
    def avg_wait_time(self) -> float:
        """Average wait time for connection."""
        return (self.wait_time_total / self.wait_count) if self.wait_count > 0 else 0

    @property
    def connection_failure_rate(self) -> float:
        """Connection failure rate."""
        total = self.connections_created + self.connections_failed
        return (self.connections_failed / total * 100) if total > 0 else 0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "connections_created": self.connections_created,
            "connections_closed": self.connections_closed,
            "connections_recycled": self.connections_recycled,
            "connections_failed": self.connections_failed,
            "avg_checkout_time_ms": self.avg_checkout_time * 1000,
            "checkout_count": self.checkout_count,
            "overflow_created": self.overflow_created,
            "pool_size_current": self.pool_size_current,
            "pool_size_overflow": self.pool_size_overflow,
            "avg_wait_time_ms": self.avg_wait_time * 1000,
            "wait_count": self.wait_count,
            "connection_failure_rate": self.connection_failure_rate,
            "health_checks_passed": self.health_checks_passed,
            "health_checks_failed": self.health_checks_failed,
            "last_health_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
        }


class DatabaseConnectionPool:
    """
    Advanced database connection pool with health monitoring and failover.
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 20,
        max_overflow: int = 40,
        pool_timeout: float = 30.0,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo_pool: bool = False,
    ):
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping
        self.echo_pool = echo_pool

        self.metrics = PoolMetrics()
        self.health_check_interval = 30  # seconds
        self.health_check_thread: Thread | None = None
        self.is_healthy = True
        self._lock = Lock()

        # Create engine with custom pool
        self.engine = self._create_engine()
        self._setup_event_listeners()

        # Start health check thread
        self._start_health_check()

    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with optimized pool configuration."""

        # Choose pool class based on configuration
        if settings.ENVIRONMENT == "production":
            poolclass = QueuePool
        elif settings.ENVIRONMENT == "testing":
            poolclass = StaticPool
        else:
            poolclass = QueuePool

        return create_engine(
            self.database_url,
            poolclass=poolclass,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=self.pool_pre_ping,
            echo_pool=self.echo_pool,
            connect_args={
                "server_settings": {
                    "jit": "off",  # Disable JIT for consistent performance
                    "application_name": f"vulcan_engine_{settings.ENVIRONMENT}",
                },
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",  # 30 second statement timeout
            },
        )

    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for monitoring."""

        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Track connection creation."""
            with self._lock:
                self.metrics.connections_created += 1

            # Set connection parameters
            with dbapi_conn.cursor() as cursor:
                # Set work_mem for better sorting performance
                cursor.execute("SET work_mem = '32MB'")
                # Set random_page_cost for SSD optimization
                cursor.execute("SET random_page_cost = 1.1")

        @event.listens_for(self.engine, "close")
        def receive_close(dbapi_conn, connection_record):
            """Track connection closing."""
            with self._lock:
                self.metrics.connections_closed += 1

        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Track connection checkout."""
            connection_record.info["checkout_time"] = time.time()
            with self._lock:
                self.metrics.checkout_count += 1

        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            """Track connection checkin."""
            if "checkout_time" in connection_record.info:
                checkout_duration = (
                    time.time() - connection_record.info["checkout_time"]
                )
                with self._lock:
                    self.metrics.checkout_time_total += checkout_duration
                del connection_record.info["checkout_time"]

        @event.listens_for(self.engine.pool, "connect")
        def pool_connect(dbapi_conn, connection_record):
            """Handle pool connection events."""
            connection_record.info["connect_time"] = time.time()

        @event.listens_for(self.engine.pool, "invalidate")
        def pool_invalidate(dbapi_conn, connection_record, exception):
            """Handle connection invalidation."""
            with self._lock:
                self.metrics.connections_failed += 1
            logger.warning(f"Connection invalidated: {exception}")

    def _start_health_check(self):
        """Start background health check thread."""

        def health_check_loop():
            while True:
                try:
                    time.sleep(self.health_check_interval)
                    self._perform_health_check()
                except Exception as e:
                    logger.error(f"Health check error: {e}")

        self.health_check_thread = Thread(target=health_check_loop, daemon=True)
        self.health_check_thread.start()

    def _perform_health_check(self):
        """Perform health check on connection pool."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.scalar()

            with self._lock:
                self.is_healthy = True
                self.metrics.health_checks_passed += 1
                self.metrics.last_health_check = datetime.utcnow()

                # Update pool metrics
                pool_impl = self.engine.pool
                self.metrics.pool_size_current = pool_impl.size()
                self.metrics.pool_size_overflow = pool_impl.overflow()

        except Exception as e:
            with self._lock:
                self.is_healthy = False
                self.metrics.health_checks_failed += 1
                self.metrics.last_health_check = datetime.utcnow()
            logger.error(f"Database health check failed: {e}")

    @contextmanager
    def get_connection(self, timeout: float | None = None):
        """
        Get a database connection with timeout and retry logic.

        Args:
            timeout: Connection timeout in seconds
        """
        time.time()
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                # Record wait time if pool is exhausted
                wait_start = time.time()

                # Get connection with timeout
                if timeout:
                    conn = self.engine.connect().execution_options(timeout=timeout)
                else:
                    conn = self.engine.connect()

                wait_time = time.time() - wait_start
                if wait_time > 0.1:  # Only record significant waits
                    with self._lock:
                        self.metrics.wait_time_total += wait_time
                        self.metrics.wait_count += 1

                yield conn
                conn.close()
                return

            except (TimeoutError, DBAPIError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    with self._lock:
                        self.metrics.connections_failed += 1
                    raise

                # Exponential backoff
                time.sleep(0.1 * (2**retry_count))
                logger.warning(f"Connection attempt {retry_count} failed: {e}")

    def adjust_pool_size(self, new_size: int, new_overflow: int):
        """
        Dynamically adjust pool size based on load.

        Args:
            new_size: New pool size
            new_overflow: New max overflow
        """
        try:
            # Recreate engine with new pool configuration
            self.pool_size = new_size
            self.max_overflow = new_overflow

            old_engine = self.engine
            self.engine = self._create_engine()
            self._setup_event_listeners()

            # Dispose old engine
            old_engine.dispose()

            logger.info(
                f"Adjusted pool size to {new_size} with overflow {new_overflow}"
            )

        except Exception as e:
            logger.error(f"Failed to adjust pool size: {e}")

    def get_metrics(self) -> dict[str, Any]:
        """Get current pool metrics."""
        with self._lock:
            metrics = self.metrics.to_dict()

        # Add current pool stats
        try:
            pool_impl = self.engine.pool
            metrics.update(
                {
                    "pool_size": pool_impl.size(),
                    "checked_in": pool_impl.checkedin(),
                    "checked_out": pool_impl.checkedout(),
                    "overflow": pool_impl.overflow(),
                    "total": pool_impl.size() + pool_impl.overflow(),
                    "is_healthy": self.is_healthy,
                }
            )
        except Exception as e:
            logger.error(f"Failed to get pool stats: {e}")

        return metrics

    def close(self):
        """Close the connection pool."""
        self.engine.dispose()
        logger.info("Database connection pool closed")


class RedisConnectionPool:
    """
    Advanced Redis connection pool with Sentinel support and health monitoring.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        sentinels: list[tuple] | None = None,
        service_name: str = "mymaster",
        max_connections: int = 100,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30,
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.sentinels = sentinels
        self.service_name = service_name
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_on_timeout = retry_on_timeout
        self.health_check_interval = health_check_interval

        self.metrics = PoolMetrics()
        self.is_healthy = True
        self._lock = Lock()

        # Create connection pool
        if sentinels:
            self.pool = self._create_sentinel_pool()
        else:
            self.pool = self._create_standard_pool()

        # Create Redis client
        self.client = redis.Redis(connection_pool=self.pool)

        # Start health monitoring
        self._start_health_monitoring()

    def _create_standard_pool(self) -> redis.ConnectionPool:
        """Create standard Redis connection pool."""
        return redis.ConnectionPool.from_url(
            self.redis_url,
            max_connections=self.max_connections,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            retry_on_timeout=self.retry_on_timeout,
            decode_responses=True,
        )

    def _create_sentinel_pool(self) -> redis.sentinel.SentinelConnectionPool:
        """Create Redis Sentinel connection pool for HA."""
        sentinel = Sentinel(
            self.sentinels,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
        )

        return sentinel.master_for(
            self.service_name,
            connection_pool_kwargs={
                "max_connections": self.max_connections,
                "retry_on_timeout": self.retry_on_timeout,
                "decode_responses": True,
            },
        )

    def _start_health_monitoring(self):
        """Start background health monitoring."""

        def monitor_loop():
            while True:
                try:
                    time.sleep(self.health_check_interval)
                    self._check_health()
                except Exception as e:
                    logger.error(f"Redis health check error: {e}")

        monitor_thread = Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

    def _check_health(self):
        """Check Redis connection health."""
        try:
            start_time = time.time()
            self.client.ping()
            response_time = time.time() - start_time

            with self._lock:
                self.is_healthy = True
                self.metrics.health_checks_passed += 1
                self.metrics.last_health_check = datetime.utcnow()

            # Log if response time is high
            if response_time > 0.1:
                logger.warning(f"Redis high response time: {response_time:.3f}s")

        except redis.RedisError as e:
            with self._lock:
                self.is_healthy = False
                self.metrics.health_checks_failed += 1
                self.metrics.last_health_check = datetime.utcnow()
            logger.error(f"Redis health check failed: {e}")

    @contextmanager
    def get_client(self, retry: bool = True) -> redis.Redis:
        """
        Get Redis client with retry logic.

        Args:
            retry: Enable retry on failure
        """
        max_retries = 3 if retry else 1
        retry_count = 0

        while retry_count < max_retries:
            try:
                start_time = time.time()

                # Test connection
                self.client.ping()

                with self._lock:
                    self.metrics.checkout_count += 1
                    self.metrics.checkout_time_total += time.time() - start_time

                yield self.client
                return

            except redis.RedisError as e:
                retry_count += 1

                with self._lock:
                    self.metrics.connections_failed += 1

                if retry_count >= max_retries:
                    raise

                # Exponential backoff
                time.sleep(0.1 * (2**retry_count))
                logger.warning(f"Redis connection attempt {retry_count} failed: {e}")

    def get_pipeline(self, transaction: bool = True) -> redis.client.Pipeline:
        """Get Redis pipeline for batch operations."""
        return self.client.pipeline(transaction=transaction)

    def get_metrics(self) -> dict[str, Any]:
        """Get current pool metrics."""
        with self._lock:
            metrics = self.metrics.to_dict()

        # Add pool-specific stats
        try:
            pool_stats = {
                "created_connections": self.pool.created_connections,
                "available_connections": len(self.pool._available_connections),
                "in_use_connections": len(self.pool._in_use_connections),
                "max_connections": self.pool.max_connections,
                "is_healthy": self.is_healthy,
            }
            metrics.update(pool_stats)
        except Exception as e:
            logger.error(f"Failed to get Redis pool stats: {e}")

        return metrics

    def close(self):
        """Close the connection pool."""
        self.pool.disconnect()
        logger.info("Redis connection pool closed")


class ConnectionPoolManager:
    """
    Manages all connection pools with automatic scaling and monitoring.
    """

    def __init__(self):
        self.db_pools: dict[str, DatabaseConnectionPool] = {}
        self.redis_pools: dict[str, RedisConnectionPool] = {}
        self.metrics_history: list[dict[str, Any]] = []
        self.auto_scale_enabled = True
        self._lock = Lock()

        # Initialize default pools
        self._initialize_default_pools()

        # Start monitoring
        self._start_monitoring()

    def _initialize_default_pools(self):
        """Initialize default connection pools."""
        # Primary database pool
        self.db_pools["primary"] = DatabaseConnectionPool(
            database_url=str(settings.SQLALCHEMY_DATABASE_URI),
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_POOL_SIZE * 2,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
        )

        # Read replica pool if configured
        if settings.DATABASE_READ_REPLICA_URL:
            self.db_pools["read_replica"] = DatabaseConnectionPool(
                database_url=settings.DATABASE_READ_REPLICA_URL,
                pool_size=settings.DATABASE_POOL_SIZE,
                max_overflow=settings.DATABASE_POOL_SIZE * 2,
                pool_recycle=settings.DATABASE_POOL_RECYCLE,
                pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
            )

        # Redis pools
        self.redis_pools["cache"] = RedisConnectionPool(
            redis_url=settings.REDIS_URL, max_connections=settings.REDIS_MAX_CONNECTIONS
        )

        # Separate pool for Celery if needed
        if settings.CELERY_BROKER_URL:
            self.redis_pools["celery"] = RedisConnectionPool(
                redis_url=settings.CELERY_BROKER_URL,
                max_connections=50,  # Lower limit for Celery
            )

    def _start_monitoring(self):
        """Start pool monitoring and auto-scaling."""

        def monitor_loop():
            while True:
                try:
                    time.sleep(60)  # Check every minute
                    self._collect_metrics()

                    if self.auto_scale_enabled:
                        self._auto_scale_pools()

                except Exception as e:
                    logger.error(f"Pool monitoring error: {e}")

        monitor_thread = Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

    def _collect_metrics(self):
        """Collect metrics from all pools."""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "database_pools": {},
            "redis_pools": {},
        }

        # Collect database pool metrics
        for name, pool in self.db_pools.items():
            metrics["database_pools"][name] = pool.get_metrics()

        # Collect Redis pool metrics
        for name, pool in self.redis_pools.items():
            metrics["redis_pools"][name] = pool.get_metrics()

        with self._lock:
            self.metrics_history.append(metrics)
            # Keep only last 100 entries
            if len(self.metrics_history) > 100:
                self.metrics_history = self.metrics_history[-100:]

    def _auto_scale_pools(self):
        """Auto-scale pools based on metrics."""
        for name, pool in self.db_pools.items():
            metrics = pool.get_metrics()

            # Scale up if high utilization
            utilization = metrics.get("checked_out", 0) / max(
                metrics.get("pool_size", 1), 1
            )

            if utilization > 0.8 and metrics.get("avg_wait_time_ms", 0) > 100:
                # Scale up by 25%
                new_size = min(int(pool.pool_size * 1.25), 100)  # Cap at 100
                new_overflow = min(int(pool.max_overflow * 1.25), 200)  # Cap at 200

                if new_size > pool.pool_size:
                    logger.info(
                        f"Scaling up {name} pool: {pool.pool_size} -> {new_size}"
                    )
                    pool.adjust_pool_size(new_size, new_overflow)

            elif utilization < 0.3 and pool.pool_size > 10:
                # Scale down by 20%
                new_size = max(int(pool.pool_size * 0.8), 10)  # Min 10
                new_overflow = max(int(pool.max_overflow * 0.8), 20)  # Min 20

                if new_size < pool.pool_size:
                    logger.info(
                        f"Scaling down {name} pool: {pool.pool_size} -> {new_size}"
                    )
                    pool.adjust_pool_size(new_size, new_overflow)

    def get_database_connection(
        self, pool_name: str = "primary", timeout: float | None = None
    ):
        """Get database connection from specified pool."""
        pool = self.db_pools.get(pool_name)
        if not pool:
            raise ValueError(f"Database pool '{pool_name}' not found")

        return pool.get_connection(timeout)

    def get_redis_client(self, pool_name: str = "cache", retry: bool = True):
        """Get Redis client from specified pool."""
        pool = self.redis_pools.get(pool_name)
        if not pool:
            raise ValueError(f"Redis pool '{pool_name}' not found")

        return pool.get_client(retry)

    def get_all_metrics(self) -> dict[str, Any]:
        """Get metrics for all pools."""
        return {
            "database_pools": {
                name: pool.get_metrics() for name, pool in self.db_pools.items()
            },
            "redis_pools": {
                name: pool.get_metrics() for name, pool in self.redis_pools.items()
            },
            "metrics_history": self.metrics_history[-10:]
            if self.metrics_history
            else [],
        }

    def health_check(self) -> dict[str, bool]:
        """Check health of all pools."""
        health = {}

        for name, pool in self.db_pools.items():
            health[f"db_{name}"] = pool.is_healthy

        for name, pool in self.redis_pools.items():
            health[f"redis_{name}"] = pool.is_healthy

        health["overall"] = all(health.values())
        return health

    def close_all(self):
        """Close all connection pools."""
        for pool in self.db_pools.values():
            pool.close()

        for pool in self.redis_pools.values():
            pool.close()

        logger.info("All connection pools closed")


# Global connection pool manager instance
_pool_manager: ConnectionPoolManager | None = None


def get_pool_manager() -> ConnectionPoolManager:
    """Get or create the global connection pool manager."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = ConnectionPoolManager()
    return _pool_manager


# Export components
__all__ = [
    "DatabaseConnectionPool",
    "RedisConnectionPool",
    "ConnectionPoolManager",
    "get_pool_manager",
    "PoolMetrics",
]
