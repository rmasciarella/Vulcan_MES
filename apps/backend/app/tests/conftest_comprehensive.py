"""
Comprehensive Test Configuration with Test Containers

Enhanced pytest configuration that includes test containers for integration testing
with real databases, Redis, and other external services.
"""

import asyncio
import os
from collections.abc import Generator
from pathlib import Path

import pytest

# Test containers for integration testing
try:
    from testcontainers.compose import DockerCompose
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.core.db import init_db
from app.main import app
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers

# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line("markers", "integration: Integration tests (with database)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (full system)")
    config.addinivalue_line("markers", "performance: Performance and load tests")
    config.addinivalue_line("markers", "security: Security and penetration tests")
    config.addinivalue_line("markers", "slow: Slow tests (may take > 10 seconds)")
    config.addinivalue_line("markers", "containers: Tests requiring test containers")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Get the test file path relative to the tests directory
        test_file = Path(item.fspath).relative_to(Path(__file__).parent)

        # Auto-mark based on directory structure
        if "unit" in str(test_file):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(test_file):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(test_file):
            item.add_marker(pytest.mark.e2e)
        elif "performance" in str(test_file):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        elif "security" in str(test_file):
            item.add_marker(pytest.mark.security)

        # Mark container tests
        if any(
            fixture in item.fixturenames
            for fixture in ["postgres_container", "redis_container", "test_compose"]
        ):
            item.add_marker(pytest.mark.containers)


# ============================================================================
# Test Container Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for integration tests."""
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not available")

    with PostgresContainer("postgres:15") as postgres:
        postgres.with_env("POSTGRES_DB", "testdb")
        postgres.with_env("POSTGRES_USER", "testuser")
        postgres.with_env("POSTGRES_PASSWORD", "testpass")

        # Wait for container to be ready
        postgres.get_connection_url()

        yield {
            "host": postgres.get_container_host_ip(),
            "port": postgres.get_exposed_port(5432),
            "database": "testdb",
            "username": "testuser",
            "password": "testpass",
            "connection_url": postgres.get_connection_url(),
        }


@pytest.fixture(scope="session")
def redis_container():
    """Start a Redis container for caching tests."""
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not available")

    with RedisContainer("redis:7-alpine") as redis:
        yield {
            "host": redis.get_container_host_ip(),
            "port": redis.get_exposed_port(6379),
            "connection_url": redis.get_connection_url(),
        }


@pytest.fixture(scope="session")
def test_compose():
    """Start services using Docker Compose for full integration tests."""
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not available")

    # Path to docker-compose.test.yml
    compose_file = Path(__file__).parent.parent.parent / "docker-compose.test.yml"

    if not compose_file.exists():
        pytest.skip("docker-compose.test.yml not found")

    with DockerCompose(
        str(compose_file.parent), compose_file_name="docker-compose.test.yml"
    ) as compose:
        # Wait for services to be ready
        compose.wait_for("db")

        yield {
            "db_host": compose.get_service_host("db", 5432),
            "db_port": compose.get_service_port("db", 5432),
            "redis_host": compose.get_service_host("redis", 6379)
            if "redis" in compose.services
            else None,
            "redis_port": compose.get_service_port("redis", 6379)
            if "redis" in compose.services
            else None,
        }


# ============================================================================
# Database Fixtures with Test Containers
# ============================================================================


@pytest.fixture(scope="session")
def container_engine(postgres_container):
    """Create database engine using test container."""
    connection_url = postgres_container["connection_url"]
    engine = create_engine(connection_url, echo=False)

    # Create all tables
    SQLModel.metadata.create_all(engine)

    yield engine

    # Cleanup
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def container_db(container_engine) -> Generator[Session, None, None]:
    """Create database session using test container."""
    with Session(container_engine) as session:
        # Initialize with test data if needed
        init_db(session)
        yield session

        # Rollback any changes
        session.rollback()


# ============================================================================
# Enhanced Application Fixtures
# ============================================================================


@pytest.fixture
def test_app():
    """Create test application instance."""
    return app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def container_client(container_engine):
    """Create test client with containerized database."""
    # Override database engine for testing
    original_engine = settings.engine if hasattr(settings, "engine") else None
    settings.engine = container_engine

    try:
        with TestClient(app) as c:
            yield c
    finally:
        # Restore original engine
        if original_engine:
            settings.engine = original_engine


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    """Get superuser token headers."""
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(
    client: TestClient, container_db: Session
) -> dict[str, str]:
    """Get normal user token headers."""
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=container_db
    )


# ============================================================================
# Performance Testing Fixtures
# ============================================================================


@pytest.fixture
def performance_config():
    """Configuration for performance tests."""
    return {
        "max_response_time": 1.0,  # seconds
        "max_memory_usage": 100,  # MB
        "concurrent_users": 10,
        "test_duration": 30,  # seconds
        "ramp_up_time": 5,  # seconds
    }


@pytest.fixture
def load_test_data():
    """Generate data for load testing."""

    class LoadTestData:
        @staticmethod
        def generate_jobs(count: int = 1000):
            """Generate job data for load testing."""
            jobs = []
            for i in range(count):
                jobs.append(
                    {
                        "job_number": f"LOAD-TEST-{i:06d}",
                        "customer_name": f"Load Test Customer {i % 100}",
                        "part_number": f"PART-{i % 50:03d}",
                        "quantity": (i % 100) + 1,
                        "priority": ["LOW", "NORMAL", "HIGH", "URGENT"][i % 4],
                        "due_date": f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T12:00:00",
                    }
                )
            return jobs

        @staticmethod
        def generate_concurrent_requests(count: int = 100):
            """Generate requests for concurrent testing."""
            requests = []
            for i in range(count):
                requests.append(
                    {
                        "method": "POST",
                        "url": "/api/v1/scheduling/jobs",
                        "data": {
                            "job_number": f"CONCURRENT-{i:04d}",
                            "customer_name": f"Concurrent Customer {i}",
                            "quantity": 1,
                            "due_date": "2024-06-01T12:00:00",
                        },
                    }
                )
            return requests

    return LoadTestData


# ============================================================================
# Test Environment Configuration
# ============================================================================


@pytest.fixture(scope="session")
def test_environment():
    """Set up test environment variables."""
    # Save original environment
    original_env = dict(os.environ)

    # Set test environment variables
    test_env = {
        "TESTING": "true",
        "DATABASE_URL": "postgresql://testuser:testpass@localhost/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "EMAIL_TEST_USER": "test@example.com",
        "FIRST_SUPERUSER": "admin@example.com",
        "FIRST_SUPERUSER_PASSWORD": "testadminpass",
    }

    os.environ.update(test_env)

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# ============================================================================
# Test Data Management
# ============================================================================


@pytest.fixture
def test_data_manager(container_db):
    """Manage test data creation and cleanup."""

    class TestDataManager:
        def __init__(self, session: Session):
            self.session = session
            self.created_objects = []

        def create_user(self, email: str = "testuser@example.com", **kwargs):
            """Create a test user."""
            from app import crud
            from app.models import UserCreate

            user_data = UserCreate(
                email=email, password="testpass123", full_name="Test User", **kwargs
            )
            user = crud.create_user(self.session, user_create=user_data)
            self.created_objects.append(("user", user.id))
            return user

        def create_jobs(self, count: int = 5):
            """Create test jobs."""
            from app import crud
            from app.models import JobCreate

            jobs = []
            for i in range(count):
                job_data = JobCreate(
                    job_number=f"TEST-JOB-{i:03d}",
                    customer_name=f"Test Customer {i}",
                    quantity=i + 1,
                    due_date="2024-06-01T12:00:00",
                )
                job = crud.create_job(self.session, job_create=job_data)
                jobs.append(job)
                self.created_objects.append(("job", job.id))

            return jobs

        def cleanup(self):
            """Clean up created test data."""
            from app import crud

            for obj_type, obj_id in reversed(self.created_objects):
                try:
                    if obj_type == "user":
                        crud.remove_user(self.session, id=obj_id)
                    elif obj_type == "job":
                        crud.remove_job(self.session, id=obj_id)
                except Exception:
                    pass  # Ignore cleanup errors

            self.created_objects.clear()

    manager = TestDataManager(container_db)
    yield manager
    manager.cleanup()


# ============================================================================
# Event Loop Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Test Utilities
# ============================================================================


@pytest.fixture
def test_utilities():
    """Common test utilities."""

    class TestUtilities:
        @staticmethod
        def assert_response_time(response_time: float, max_time: float = 1.0):
            """Assert response time is within acceptable limits."""
            assert (
                response_time < max_time
            ), f"Response time {response_time}s exceeded limit {max_time}s"

        @staticmethod
        def assert_memory_usage(memory_mb: float, max_memory: float = 100.0):
            """Assert memory usage is within limits."""
            assert (
                memory_mb < max_memory
            ), f"Memory usage {memory_mb}MB exceeded limit {max_memory}MB"

        @staticmethod
        def generate_test_id():
            """Generate unique test ID."""
            import uuid

            return str(uuid.uuid4())[:8]

        @staticmethod
        def wait_for_condition(
            condition_func, timeout: int = 10, interval: float = 0.1
        ):
            """Wait for a condition to become true."""
            import time

            start_time = time.time()

            while time.time() - start_time < timeout:
                if condition_func():
                    return True
                time.sleep(interval)

            return False

    return TestUtilities


# ============================================================================
# Cleanup Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Automatically clean up after each test."""
    yield

    # Perform any necessary cleanup
    # This runs after each test
    pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_after_session():
    """Clean up after entire test session."""
    yield

    # Session-level cleanup
    # Remove any temporary files, stop background processes, etc.
    pass
