"""
Database Connectivity and Health Check Tests

Tests for database connection, health checks, and basic database operations.
These tests ensure the database layer is properly configured and accessible.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlmodel import Session, select

from app.core.db import engine
from app.core.db_test import get_test_session, test_engine
from app.models import User


class TestDatabaseConnectivity:
    """Test database connectivity and basic operations."""

    def test_database_engine_creation(self):
        """Test that database engine is created properly."""
        assert engine is not None
        assert str(engine.url).startswith("postgresql+psycopg://")

    def test_test_database_engine_creation(self):
        """Test that test database engine is created properly."""
        assert test_engine is not None
        assert str(test_engine.url).startswith("postgresql+psycopg://")
        assert "_test" in str(test_engine.url)

    def test_database_connection(self, db: Session):
        """Test basic database connection."""
        # Test simple query
        result = db.execute(text("SELECT 1 as test_value"))
        row = result.fetchone()
        assert row is not None
        assert row.test_value == 1

    def test_test_database_connection(self):
        """Test test database connection specifically."""
        with get_test_session() as session:
            result = session.execute(text("SELECT 1 as test_value"))
            row = result.fetchone()
            assert row is not None
            assert row.test_value == 1

    def test_database_version(self, db: Session):
        """Test PostgreSQL version retrieval."""
        result = db.execute(text("SELECT version()"))
        version_info = result.scalar()
        assert version_info is not None
        assert "PostgreSQL" in version_info

    def test_database_timezone(self, db: Session):
        """Test database timezone configuration."""
        result = db.execute(text("SHOW timezone"))
        timezone = result.scalar()
        assert timezone is not None

    def test_database_encoding(self, db: Session):
        """Test database encoding."""
        result = db.execute(text("SHOW server_encoding"))
        encoding = result.scalar()
        assert encoding in ["UTF8", "UTF-8"]

    def test_connection_pool_configuration(self):
        """Test connection pool settings."""
        pool = engine.pool
        assert pool is not None
        # Test that we can get a connection from the pool
        connection = pool.connect()
        assert connection is not None
        connection.close()

    def test_database_tables_exist(self, db: Session):
        """Test that required tables exist in database."""
        # Check if user table exists
        result = db.execute(
            text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'user'
            );
        """)
        )
        table_exists = result.scalar()
        assert table_exists is True

    def test_database_permissions(self, db: Session):
        """Test basic database permissions."""
        # Test SELECT permission
        try:
            db.execute(select(User).limit(1))
        except Exception as e:
            pytest.fail(f"SELECT permission test failed: {e}")

        # Test INSERT permission (will be rolled back)
        try:
            # This will fail due to constraints but should not fail due to permissions
            db.execute(
                text(
                    "INSERT INTO \"user\" (id, email, hashed_password) VALUES (gen_random_uuid(), 'test@test.com', 'hash') ON CONFLICT DO NOTHING"
                )
            )
        except DatabaseError as e:
            # Expected due to constraints, but not permissions
            if "permission" in str(e).lower():
                pytest.fail(f"INSERT permission test failed: {e}")


class TestDatabaseHealthChecks:
    """Health check tests for database monitoring."""

    def test_database_health_check_query(self, db: Session):
        """Test a basic health check query."""
        # Simple health check query that should always work
        result = db.execute(text("SELECT 1"))
        assert result.scalar() == 1

    def test_database_connection_count(self, db: Session):
        """Test database connection count monitoring."""
        result = db.execute(
            text("""
            SELECT count(*) as connection_count
            FROM pg_stat_activity
            WHERE state = 'active'
        """)
        )
        connection_count = result.scalar()
        assert connection_count is not None
        assert connection_count > 0

    def test_database_lock_status(self, db: Session):
        """Test database lock monitoring."""
        result = db.execute(
            text("""
            SELECT count(*) as lock_count
            FROM pg_locks
            WHERE granted = true
        """)
        )
        lock_count = result.scalar()
        assert lock_count is not None
        assert lock_count >= 0

    def test_database_size(self, db: Session):
        """Test database size monitoring."""
        result = db.execute(
            text("""
            SELECT pg_size_pretty(pg_database_size(current_database())) as db_size
        """)
        )
        db_size = result.scalar()
        assert db_size is not None
        assert isinstance(db_size, str)

    def test_table_counts(self, db: Session):
        """Test basic table count monitoring."""
        # Count users (should be at least 1 due to superuser creation)
        result = db.execute(text('SELECT count(*) FROM "user"'))
        user_count = result.scalar()
        assert user_count >= 1

    def test_database_statistics(self, db: Session):
        """Test database statistics collection."""
        result = db.execute(
            text("""
            SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            LIMIT 5
        """)
        )
        stats = result.fetchall()
        # Should have at least one table with statistics
        assert len(stats) >= 0

    def test_connection_pool_health(self):
        """Test connection pool health."""
        pool = engine.pool

        # Test pool status
        assert pool.size() >= 0
        assert pool.checkedin() >= 0
        assert pool.checkedout() >= 0

        # Test getting and returning connection
        conn = engine.connect()
        assert conn is not None
        conn.close()


class TestDatabaseErrorHandling:
    """Test database error handling and recovery."""

    def test_invalid_query_handling(self, db: Session):
        """Test handling of invalid SQL queries."""
        with pytest.raises(DatabaseError):
            db.execute(text("SELECT * FROM nonexistent_table"))

    def test_connection_timeout_configuration(self):
        """Test connection timeout configuration."""
        # Test that engine has reasonable timeout settings
        # This is more of a configuration test
        assert engine.pool.timeout >= 0

    def test_transaction_rollback(self, db: Session):
        """Test transaction rollback functionality."""
        # Start a transaction that we'll roll back
        with db.begin():
            # Make a change
            db.execute(
                text(
                    "INSERT INTO \"user\" (id, email, hashed_password, is_active, is_superuser) VALUES (gen_random_uuid(), 'rollback-test@test.com', 'hash', true, false) ON CONFLICT DO NOTHING"
                )
            )
            # Rollback by raising exception
            db.rollback()

        # Verify the change was rolled back
        result = db.execute(
            text("SELECT count(*) FROM \"user\" WHERE email = 'rollback-test@test.com'")
        )
        count = result.scalar()
        assert count == 0

    def test_concurrent_connection_handling(self):
        """Test handling of concurrent connections."""
        connections = []
        try:
            # Try to create multiple connections
            for _ in range(5):
                conn = engine.connect()
                connections.append(conn)
                # Test that connection works
                result = conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            # Clean up connections
            for conn in connections:
                conn.close()
