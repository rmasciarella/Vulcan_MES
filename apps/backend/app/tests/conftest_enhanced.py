"""
Enhanced Test Configuration and Global Fixtures

Extended pytest configuration with comprehensive fixtures for all test types,
markers, and reporting configurations. Provides centralized test infrastructure.
"""

import logging
import sys
from pathlib import Path

import coverage
import pytest
from fastapi.testclient import TestClient

# Import existing configuration
from app.tests.conftest import *  # Import existing fixtures
from app.tests.database.conftest import *  # Import database fixtures

# Import test utilities and mocks
from app.tests.utils.mock_services import MockServiceFactory
from app.tests.utils.test_scenarios import ScenarioManager
from app.tests.utils.utils import get_superuser_token_headers

# Performance monitoring imports
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# Test Configuration
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""

    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "load: Load tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "database: Database tests")
    config.addinivalue_line("markers", "mock: Tests using mocks")
    config.addinivalue_line("markers", "smoke: Smoke tests")
    config.addinivalue_line("markers", "regression: Regression tests")

    # Configure logging for tests
    logging.basicConfig(
        level=logging.INFO if config.getoption("--verbose") else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("tests.log"),
        ],
    )

    # Configure coverage reporting
    if hasattr(config, "_cov") and config._cov:
        config._cov.config.skip_covered = config.getoption("--cov-skip-covered", False)


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file paths."""

    for item in items:
        # Add markers based on file path
        test_file_path = str(item.fspath)

        if "/unit/" in test_file_path or "/test_" in test_file_path:
            item.add_marker(pytest.mark.unit)

        if "/integration/" in test_file_path:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.database)

        if "/e2e/" in test_file_path:
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)

        if "/security/" in test_file_path:
            item.add_marker(pytest.mark.security)

        if "/performance/" in test_file_path:
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)

        if "load" in test_file_path or "stress" in test_file_path:
            item.add_marker(pytest.mark.load)
            item.add_marker(pytest.mark.slow)

        # Mark tests using mock services
        if hasattr(item, "cls") and item.cls and "Mock" in item.cls.__name__:
            item.add_marker(pytest.mark.mock)


def pytest_addoption(parser):
    """Add custom command line options."""

    parser.addoption(
        "--run-slow", action="store_true", default=False, help="Run slow tests"
    )

    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="Run performance tests",
    )

    parser.addoption(
        "--run-load", action="store_true", default=False, help="Run load tests"
    )

    parser.addoption(
        "--run-security", action="store_true", default=False, help="Run security tests"
    )

    parser.addoption(
        "--skip-integration",
        action="store_true",
        default=False,
        help="Skip integration tests",
    )

    parser.addoption(
        "--test-env",
        action="store",
        default="test",
        help="Test environment (test, ci, local)",
    )

    parser.addoption(
        "--cov-skip-covered",
        action="store_true",
        default=False,
        help="Skip covered lines in coverage report",
    )


def pytest_runtest_setup(item):
    """Setup individual test runs with conditional skipping."""

    # Skip slow tests unless explicitly requested
    if item.get_closest_marker("slow") and not item.config.getoption("--run-slow"):
        pytest.skip("Slow test skipped (use --run-slow to run)")

    # Skip performance tests unless explicitly requested
    if item.get_closest_marker("performance") and not item.config.getoption(
        "--run-performance"
    ):
        pytest.skip("Performance test skipped (use --run-performance to run)")

    # Skip load tests unless explicitly requested
    if item.get_closest_marker("load") and not item.config.getoption("--run-load"):
        pytest.skip("Load test skipped (use --run-load to run)")

    # Skip security tests unless explicitly requested
    if item.get_closest_marker("security") and not item.config.getoption(
        "--run-security"
    ):
        pytest.skip("Security test skipped (use --run-security to run)")

    # Skip integration tests if requested
    if item.get_closest_marker("integration") and item.config.getoption(
        "--skip-integration"
    ):
        pytest.skip("Integration test skipped")


@pytest.fixture(scope="session")
def test_environment(request):
    """Get test environment configuration."""
    return {
        "env": request.config.getoption("--test-env"),
        "run_slow": request.config.getoption("--run-slow"),
        "run_performance": request.config.getoption("--run-performance"),
        "run_load": request.config.getoption("--run-load"),
        "run_security": request.config.getoption("--run-security"),
        "skip_integration": request.config.getoption("--skip-integration"),
    }


@pytest.fixture(scope="session")
def coverage_reporter():
    """Coverage reporting fixture."""

    # Initialize coverage if not already done
    cov = coverage.Coverage(
        source=["app"],
        omit=[
            "app/tests/*",
            "app/alembic/*",
            "app/initial_data.py",
            "app/backend_pre_start.py",
            "app/tests_pre_start.py",
            "*/venv/*",
            "*/.venv/*",
        ],
        branch=True,
    )

    cov.start()
    yield cov
    cov.stop()

    # Generate coverage reports
    cov.save()

    # Console report
    print("\n" + "=" * 50)
    print("COVERAGE SUMMARY")
    print("=" * 50)
    cov.report(show_missing=True, skip_covered=False)

    # HTML report
    html_dir = Path("htmlcov")
    cov.html_report(directory=str(html_dir))
    print(f"\nHTML coverage report generated: {html_dir}/index.html")

    # XML report for CI systems
    cov.xml_report(outfile="coverage.xml")
    print("XML coverage report generated: coverage.xml")


@pytest.fixture
def mock_services():
    """Provide mock services for testing."""
    return MockServiceFactory.create_complete_mock_services()


@pytest.fixture
def mock_optimization_service():
    """Provide mock optimization service."""
    return MockServiceFactory.create_optimization_service(behavior="optimal")


@pytest.fixture
def mock_failing_optimization_service():
    """Provide mock optimization service that fails."""
    return MockServiceFactory.create_optimization_service(behavior="error")


@pytest.fixture
def mock_infeasible_optimization_service():
    """Provide mock optimization service that returns infeasible results."""
    return MockServiceFactory.create_optimization_service(behavior="infeasible")


@pytest.fixture
def mock_constraint_service():
    """Provide mock constraint validation service."""
    return MockServiceFactory.create_constraint_validation_service()


@pytest.fixture
def mock_constraint_service_with_violations():
    """Provide mock constraint service with violations."""
    return MockServiceFactory.create_constraint_validation_service(
        violations=["resource_conflict", "skill_mismatch"]
    )


@pytest.fixture
def test_scenario_basic():
    """Provide basic test scenario."""
    return ScenarioManager.create_basic_scenario(job_count=5)


@pytest.fixture
def test_scenario_complex():
    """Provide complex test scenario."""
    return ScenarioManager.create_complex_scenario(job_count=8)


@pytest.fixture
def test_scenario_edge_cases():
    """Provide edge case test scenario."""
    return ScenarioManager.create_edge_case_scenario()


@pytest.fixture
def test_scenario_realistic():
    """Provide realistic test scenario."""
    return ScenarioManager.create_realistic_scenario(job_count=10)


@pytest.fixture
def test_scenario_high_load():
    """Provide high load test scenario."""
    return ScenarioManager.create_high_load_scenario(job_count=50)


@pytest.fixture
def api_client():
    """Enhanced API client for testing."""

    class APITestClient:
        def __init__(self):
            self.client = TestClient(app)
            self.auth_headers = None
            self.request_count = 0
            self.response_times = []

        def authenticate(self):
            """Authenticate and store headers."""
            self.auth_headers = get_superuser_token_headers(self.client)

        def get(self, url, **kwargs):
            """Enhanced GET with metrics."""
            import time

            start_time = time.time()

            headers = kwargs.get("headers", {})
            if self.auth_headers:
                headers.update(self.auth_headers)
            kwargs["headers"] = headers

            response = self.client.get(url, **kwargs)

            self.request_count += 1
            self.response_times.append(time.time() - start_time)

            return response

        def post(self, url, **kwargs):
            """Enhanced POST with metrics."""
            import time

            start_time = time.time()

            headers = kwargs.get("headers", {})
            if self.auth_headers:
                headers.update(self.auth_headers)
            kwargs["headers"] = headers

            response = self.client.post(url, **kwargs)

            self.request_count += 1
            self.response_times.append(time.time() - start_time)

            return response

        def patch(self, url, **kwargs):
            """Enhanced PATCH with metrics."""
            import time

            start_time = time.time()

            headers = kwargs.get("headers", {})
            if self.auth_headers:
                headers.update(self.auth_headers)
            kwargs["headers"] = headers

            response = self.client.patch(url, **kwargs)

            self.request_count += 1
            self.response_times.append(time.time() - start_time)

            return response

        def delete(self, url, **kwargs):
            """Enhanced DELETE with metrics."""
            import time

            start_time = time.time()

            headers = kwargs.get("headers", {})
            if self.auth_headers:
                headers.update(self.auth_headers)
            kwargs["headers"] = headers

            response = self.client.delete(url, **kwargs)

            self.request_count += 1
            self.response_times.append(time.time() - start_time)

            return response

        def get_metrics(self):
            """Get request metrics."""
            if not self.response_times:
                return {"requests": 0, "avg_time": 0}

            return {
                "requests": self.request_count,
                "avg_time": sum(self.response_times) / len(self.response_times),
                "min_time": min(self.response_times),
                "max_time": max(self.response_times),
                "total_time": sum(self.response_times),
            }

    client = APITestClient()
    client.authenticate()
    return client


@pytest.fixture
def system_monitor():
    """System monitoring fixture for performance tests."""
    if not HAS_PSUTIL:
        pytest.skip("psutil not available for system monitoring")

    class SystemMonitor:
        def __init__(self):
            self.initial_memory = psutil.virtual_memory()
            self.initial_cpu = psutil.cpu_percent(interval=1)
            self.measurements = []

        def take_measurement(self):
            """Take a system measurement."""
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)

            measurement = {
                "timestamp": time.time(),
                "memory_percent": memory.percent,
                "memory_available_mb": memory.available / 1024 / 1024,
                "cpu_percent": cpu,
            }

            self.measurements.append(measurement)
            return measurement

        def get_summary(self):
            """Get summary of all measurements."""
            if not self.measurements:
                return {"measurements": 0}

            memory_values = [m["memory_percent"] for m in self.measurements]
            cpu_values = [m["cpu_percent"] for m in self.measurements]

            return {
                "measurements": len(self.measurements),
                "memory_avg": sum(memory_values) / len(memory_values),
                "memory_max": max(memory_values),
                "memory_min": min(memory_values),
                "cpu_avg": sum(cpu_values) / len(cpu_values),
                "cpu_max": max(cpu_values),
                "cpu_min": min(cpu_values),
                "duration": self.measurements[-1]["timestamp"]
                - self.measurements[0]["timestamp"],
            }

    return SystemMonitor()


@pytest.fixture
def test_logger():
    """Test-specific logger."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)

    # Add handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


@pytest.fixture
def temp_test_data_dir(tmp_path):
    """Provide temporary directory for test data."""
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()

    # Create subdirectories
    (test_data_dir / "exports").mkdir()
    (test_data_dir / "imports").mkdir()
    (test_data_dir / "logs").mkdir()
    (test_data_dir / "reports").mkdir()

    return test_data_dir


@pytest.fixture
def async_test_runner():
    """Fixture for running async tests with proper event loop."""

    async def run_async_test(coro):
        """Run async coroutine in test context."""
        return await coro

    return run_async_test


# Test reporting hooks
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Generate test execution summary."""

    if not hasattr(terminalreporter, "stats"):
        return

    stats = terminalreporter.stats

    # Count test results by marker
    marker_stats = {}
    for test_result in ["passed", "failed", "error", "skipped"]:
        if test_result in stats:
            for report in stats[test_result]:
                if hasattr(report, "keywords"):
                    for marker in report.keywords:
                        if marker.startswith("test_") or marker in [
                            "unit",
                            "integration",
                            "e2e",
                            "security",
                            "performance",
                            "load",
                            "slow",
                            "database",
                        ]:
                            continue

                        if marker not in marker_stats:
                            marker_stats[marker] = {
                                "passed": 0,
                                "failed": 0,
                                "error": 0,
                                "skipped": 0,
                            }

                        marker_stats[marker][test_result] += 1

    # Print summary by test type
    if marker_stats:
        terminalreporter.write_sep("=", "Test Summary by Type")
        for marker, counts in marker_stats.items():
            if any(counts.values()):
                total = sum(counts.values())
                terminalreporter.write_line(
                    f"{marker.capitalize():12}: {total:3} total "
                    f"({counts['passed']:2} passed, {counts['failed']:2} failed, "
                    f"{counts['error']:2} error, {counts['skipped']:2} skipped)"
                )

    # Performance summary if performance tests were run
    if config.getoption("--run-performance"):
        terminalreporter.write_sep("=", "Performance Test Summary")
        terminalreporter.write_line(
            "Performance test results available in test output above."
        )
        terminalreporter.write_line(
            "Check htmlcov/index.html for detailed coverage report."
        )


def pytest_sessionstart(session):
    """Session start hook."""
    print("\n" + "=" * 60)
    print("VULCAN ENGINE COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print(f"Test session started at: {datetime.utcnow().isoformat()}")
    print(f"Python version: {sys.version}")
    print(f"Test environment: {session.config.getoption('--test-env')}")

    # Print enabled test types
    enabled_types = []
    if session.config.getoption("--run-slow"):
        enabled_types.append("slow")
    if session.config.getoption("--run-performance"):
        enabled_types.append("performance")
    if session.config.getoption("--run-load"):
        enabled_types.append("load")
    if session.config.getoption("--run-security"):
        enabled_types.append("security")

    if enabled_types:
        print(f"Special test types enabled: {', '.join(enabled_types)}")

    print("=" * 60)


def pytest_sessionfinish(session, exitstatus):
    """Session finish hook."""
    print("\n" + "=" * 60)
    print("TEST SESSION COMPLETED")
    print(f"Session finished at: {datetime.utcnow().isoformat()}")
    print(f"Exit status: {exitstatus}")

    # Generate final reports
    if exitstatus == 0:
        print("✅ All tests passed successfully!")
    else:
        print("❌ Some tests failed. Check output above for details.")

    print("=" * 60)


# Import datetime for session hooks
import time
from datetime import datetime
