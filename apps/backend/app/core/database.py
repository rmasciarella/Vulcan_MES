"""Enhanced database configuration with read replicas and connection pooling."""

import logging
import time
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event, pool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


# Connection pool configuration
POOL_CONFIG = {
    "pool_size": settings.DATABASE_POOL_SIZE,
    "max_overflow": settings.DATABASE_POOL_SIZE * 2,
    "pool_timeout": 30,
    "pool_recycle": settings.DATABASE_POOL_RECYCLE,
    "pool_pre_ping": settings.DATABASE_POOL_PRE_PING,
    "echo_pool": settings.ENVIRONMENT == "local",
}


# Create primary (write) engine
primary_engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    poolclass=pool.QueuePool,
    **POOL_CONFIG,
)

# Create read replica engine if configured
read_replica_engine: Engine | None = None
if settings.SQLALCHEMY_READ_REPLICA_URI:
    read_replica_engine = create_engine(
        str(settings.SQLALCHEMY_READ_REPLICA_URI),
        poolclass=pool.QueuePool,
        **POOL_CONFIG,
    )
    logger.info("Read replica database configured")


# Create async engines for async operations
async_primary_engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI).replace(
        "postgresql+psycopg://", "postgresql+asyncpg://"
    ),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_POOL_SIZE * 2,
    pool_timeout=30,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
    echo_pool=settings.ENVIRONMENT == "local",
)

async_read_replica_engine: Any | None = None
if settings.SQLALCHEMY_READ_REPLICA_URI:
    async_read_replica_engine = create_async_engine(
        str(settings.SQLALCHEMY_READ_REPLICA_URI).replace(
            "postgresql+psycopg://", "postgresql+asyncpg://"
        ),
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_POOL_SIZE * 2,
        pool_timeout=30,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
        echo_pool=settings.ENVIRONMENT == "local",
    )


# Session factories
PrimarySessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=primary_engine,
    class_=Session,
    expire_on_commit=False,
)

ReadReplicaSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=read_replica_engine or primary_engine,
    class_=Session,
    expire_on_commit=False,
)

AsyncPrimarySessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_primary_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

AsyncReadReplicaSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_read_replica_engine or async_primary_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Performance monitoring for slow queries
if settings.PERFORMANCE_LOG_SLOW_QUERIES:

    @event.listens_for(Engine, "before_cursor_execute", propagate=True)
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(time.time())
        if settings.ENVIRONMENT == "local":
            logger.debug(f"Query: {statement[:100]}...")

    @event.listens_for(Engine, "after_cursor_execute", propagate=True)
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - conn.info["query_start_time"].pop(-1)
        if total_time > settings.PERFORMANCE_SLOW_QUERY_THRESHOLD:
            logger.warning(
                f"Slow query detected ({total_time:.2f}s): {statement[:200]}...",
                extra={
                    "duration": total_time,
                    "query": statement[:500],
                    "parameters": str(parameters)[:200] if parameters else None,
                },
            )


# Database session management
def get_primary_db() -> Generator[Session, None, None]:
    """Get primary database session for write operations."""
    db = PrimarySessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_read_db() -> Generator[Session, None, None]:
    """Get read replica database session for read-only operations."""
    db = ReadReplicaSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_primary_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async primary database session for write operations."""
    async with AsyncPrimarySessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Alias for backward compatibility
async_session = get_async_primary_db


async def get_async_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Get async read replica database session for read-only operations."""
    async with AsyncReadReplicaSessionLocal() as session:
        try:
            yield session
        finally:
            pass


@contextmanager
def get_db_session(read_only: bool = False) -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Args:
        read_only: Use read replica if available
    """
    if read_only and read_replica_engine:
        db = ReadReplicaSessionLocal()
    else:
        db = PrimarySessionLocal()

    try:
        yield db
        if not read_only:
            db.commit()
    except Exception:
        if not read_only:
            db.rollback()
        raise
    finally:
        db.close()


# Connection pool monitoring
def get_pool_status() -> dict[str, Any]:
    """Get connection pool status and metrics."""
    status = {
        "primary": {
            "size": primary_engine.pool.size(),
            "checked_in": primary_engine.pool.checkedin(),
            "checked_out": primary_engine.pool.checkedout(),
            "overflow": primary_engine.pool.overflow(),
            "total": primary_engine.pool.size() + primary_engine.pool.overflow(),
        }
    }

    if read_replica_engine:
        status["read_replica"] = {
            "size": read_replica_engine.pool.size(),
            "checked_in": read_replica_engine.pool.checkedin(),
            "checked_out": read_replica_engine.pool.checkedout(),
            "overflow": read_replica_engine.pool.overflow(),
            "total": read_replica_engine.pool.size()
            + read_replica_engine.pool.overflow(),
        }

    return status


def close_all_connections() -> None:
    """Close all database connections."""
    primary_engine.dispose()
    if read_replica_engine:
        read_replica_engine.dispose()
    logger.info("All database connections closed")


# Database health check
def check_database_health() -> dict[str, Any]:
    """Check database health and connectivity."""
    health = {
        "primary": {"connected": False, "response_time": None},
        "read_replica": {"connected": False, "response_time": None},
    }

    # Check primary
    try:
        import time

        start = time.time()
        with primary_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        health["primary"]["connected"] = True
        health["primary"]["response_time"] = time.time() - start
    except Exception as e:
        logger.error(f"Primary database health check failed: {e}")
        health["primary"]["error"] = str(e)

    # Check read replica
    if read_replica_engine:
        try:
            start = time.time()
            with read_replica_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            health["read_replica"]["connected"] = True
            health["read_replica"]["response_time"] = time.time() - start
        except Exception as e:
            logger.error(f"Read replica health check failed: {e}")
            health["read_replica"]["error"] = str(e)

    return health


# Query optimization utilities
class QueryOptimizer:
    """Utilities for query optimization."""

    @staticmethod
    def explain_query(query: str, session: Session) -> str:
        """Get query execution plan."""
        result = session.execute(f"EXPLAIN ANALYZE {query}")
        return "\n".join(row[0] for row in result)

    @staticmethod
    def analyze_table(table_name: str, session: Session) -> None:
        """Update table statistics for query optimization."""
        session.execute(f"ANALYZE {table_name}")
        session.commit()

    @staticmethod
    def vacuum_table(table_name: str, session: Session, full: bool = False) -> None:
        """Vacuum table to reclaim space and update visibility map."""
        vacuum_type = "VACUUM FULL" if full else "VACUUM"
        session.execute(f"{vacuum_type} {table_name}")
        session.commit()

    @staticmethod
    def get_table_stats(table_name: str, session: Session) -> dict[str, Any]:
        """Get table statistics."""
        result = session.execute(
            f"""
            SELECT
                pg_size_pretty(pg_total_relation_size('{table_name}')) as total_size,
                pg_size_pretty(pg_relation_size('{table_name}')) as table_size,
                pg_size_pretty(pg_indexes_size('{table_name}')) as indexes_size,
                n_live_tup as live_rows,
                n_dead_tup as dead_rows,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
            WHERE schemaname = 'public' AND tablename = '{table_name}'
            """
        )
        row = result.fetchone()
        if row:
            return {
                "total_size": row[0],
                "table_size": row[1],
                "indexes_size": row[2],
                "live_rows": row[3],
                "dead_rows": row[4],
                "last_vacuum": row[5],
                "last_autovacuum": row[6],
                "last_analyze": row[7],
                "last_autoanalyze": row[8],
            }
        return {}


# Transaction utilities
class TransactionManager:
    """Manage database transactions with retry logic."""

    @staticmethod
    def with_retry(
        func: Callable,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> Any:
        """Execute function with retry on database errors."""
        import time

        from sqlalchemy.exc import DatabaseError, OperationalError

        for attempt in range(max_retries):
            try:
                return func()
            except (OperationalError, DatabaseError) as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                time.sleep(retry_delay * (2**attempt))  # Exponential backoff

        raise RuntimeError("Max retries exceeded")

    @staticmethod
    @contextmanager
    def savepoint(session: Session, name: str = "sp1"):
        """Create a savepoint for nested transactions."""
        session.begin_nested()
        try:
            yield
            session.commit()
        except Exception:
            session.rollback()
            raise


# Export main components
__all__ = [
    "primary_engine",
    "read_replica_engine",
    "async_primary_engine",
    "async_read_replica_engine",
    "get_primary_db",
    "get_read_db",
    "get_async_primary_db",
    "get_async_read_db",
    "get_db_session",
    "get_pool_status",
    "close_all_connections",
    "check_database_health",
    "QueryOptimizer",
    "TransactionManager",
]
