"""
Test Containers Configuration

Provides isolated database containers for integration testing using testcontainers-python.
Ensures true isolation between test runs and environments.
"""

import os
from collections.abc import Generator
from typing import Any

import pytest
from sqlmodel import Session, create_engine
from testcontainers.postgres import PostgresContainer

from app.core.db import init_db
from app.infrastructure.database.models import SQLModel


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Provide isolated PostgreSQL container for testing."""
    # Skip containers if running in CI with existing database
    if os.getenv("CI") and os.getenv("DATABASE_URL"):
        yield None
        return
    
    with PostgresContainer(
        image="postgres:15-alpine",
        user="test_user",
        password="test_password", 
        dbname="test_vulcan",
        port=5432,
        # Optimize for testing speed
        environment={
            "POSTGRES_INITDB_ARGS": "--auth-host=trust",
            "POSTGRES_HOST_AUTH_METHOD": "trust"
        }
    ) as postgres:
        # Wait for container to be ready
        postgres.get_connection_url()
        yield postgres


@pytest.fixture(scope="session")
def container_db_url(postgres_container: PostgresContainer | None) -> str:
    """Get database URL from container or environment."""
    if postgres_container is None:
        # Use existing DATABASE_URL in CI
        return os.getenv("DATABASE_URL", "sqlite:///test.db")
    
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def container_engine(container_db_url: str):
    """Create database engine using container database."""
    engine = create_engine(
        container_db_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        pool_recycle=3600,
        # Optimize connection pool for testing
        pool_size=5,
        max_overflow=10,
    )
    
    # Create tables
    SQLModel.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup
    engine.dispose()


@pytest.fixture(scope="function")
def container_db_session(container_engine) -> Generator[Session, None, None]:
    """Provide isolated database session using container."""
    with Session(container_engine) as session:
        # Initialize with test data
        init_db(session)
        
        # Start transaction for isolation
        transaction = session.begin()
        
        yield session
        
        # Rollback transaction to ensure isolation
        transaction.rollback()


@pytest.fixture
def container_client(container_db_session: Session):
    """FastAPI test client using container database."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db
    
    def get_test_db():
        return container_db_session
    
    app.dependency_overrides[get_db] = get_test_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


class ContainerTestConfig:
    """Configuration for container-based testing."""
    
    # Performance thresholds
    MAX_CONTAINER_STARTUP_TIME = 30.0  # seconds
    MAX_QUERY_TIME = 5.0  # seconds
    
    # Test data limits
    MAX_TEST_JOBS = 1000
    MAX_TEST_TASKS = 5000
    
    # Container resource limits
    POSTGRES_MEMORY_LIMIT = "512m"
    POSTGRES_CPU_LIMIT = 1.0
    
    @classmethod
    def should_use_containers(cls) -> bool:
        """Determine if containers should be used."""
        # Skip containers in certain environments
        if os.getenv("SKIP_CONTAINERS"):
            return False
        
        # Check if Docker is available
        try:
            import docker
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False


@pytest.fixture
def container_test_config():
    """Provide container test configuration."""
    return ContainerTestConfig()


# Markers for container tests
pytest_plugins = []

def pytest_configure(config):
    """Configure container test markers."""
    config.addinivalue_line(
        "markers", "containers: mark test as requiring test containers"
    )
    config.addinivalue_line(
        "markers", "isolated_db: mark test as requiring isolated database"
    )
    config.addinivalue_line(
        "markers", "postgres_only: mark test as PostgreSQL specific"
    )


def pytest_collection_modifyitems(config, items):
    """Skip container tests if containers not available."""
    if not ContainerTestConfig.should_use_containers():
        skip_containers = pytest.mark.skip(
            reason="Docker not available or containers disabled"
        )
        
        for item in items:
            if "containers" in item.keywords:
                item.add_marker(skip_containers)


# Database utility functions for container tests
def create_test_data_bulk(session: Session, job_count: int = 100) -> dict[str, Any]:
    """Create bulk test data efficiently in container database."""
    from app.tests.database.factories import JobFactory, TaskFactory
    
    # Create jobs in batches for efficiency
    batch_size = 50
    created_jobs = []
    
    for i in range(0, job_count, batch_size):
        batch_jobs = []
        for j in range(i, min(i + batch_size, job_count)):
            job = JobFactory.create(job_number=f"CONTAINER_JOB_{j:04d}")
            batch_jobs.append(job)
        
        # Add tasks to each job
        for job in batch_jobs:
            tasks = TaskFactory.create_batch(job.id, count=3)
            for task in tasks:
                job.add_task(task)
        
        created_jobs.extend(batch_jobs)
        
        # Commit batch
        session.add_all(batch_jobs)
        session.commit()
    
    return {
        "jobs": created_jobs,
        "total_jobs": len(created_jobs),
        "total_tasks": len(created_jobs) * 3,
    }


def verify_database_isolation(session: Session) -> bool:
    """Verify that database operations are properly isolated."""
    from app.infrastructure.database.models import Job
    
    # Check that we start with clean database
    job_count = session.query(Job).count()
    return job_count == 0  # Should be 0 due to transaction rollback


class ContainerTestMetrics:
    """Track metrics for container-based testing."""
    
    def __init__(self):
        self.startup_times = []
        self.query_times = []
        self.memory_usage = []
    
    def record_startup_time(self, duration: float):
        """Record container startup time."""
        self.startup_times.append(duration)
    
    def record_query_time(self, duration: float):
        """Record database query time."""
        self.query_times.append(duration)
    
    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance metrics summary."""
        return {
            "startup_times": {
                "count": len(self.startup_times),
                "avg": sum(self.startup_times) / len(self.startup_times) if self.startup_times else 0,
                "max": max(self.startup_times) if self.startup_times else 0,
            },
            "query_times": {
                "count": len(self.query_times),
                "avg": sum(self.query_times) / len(self.query_times) if self.query_times else 0,
                "max": max(self.query_times) if self.query_times else 0,
            },
        }


@pytest.fixture
def container_metrics():
    """Provide container test metrics tracking."""
    return ContainerTestMetrics()
