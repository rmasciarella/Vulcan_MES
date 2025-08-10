"""
Database Testing Package

Comprehensive database testing suite for the Vulcan Engine backend.

This package provides:
- Database connectivity and health check tests
- SQLModel entity validation tests
- Repository CRUD operation tests
- Integration tests for full workflows
- Error handling and exception tests
- Performance and load testing
- Test data factories and utilities

Test Categories:
- Unit Tests: Individual model and repository method testing
- Integration Tests: Full database workflow testing
- Performance Tests: Query performance and scalability
- Error Tests: Exception handling and recovery

Usage:
    # Run all database tests
    pytest app/tests/database/

    # Run specific test categories
    pytest app/tests/database/ -m "connectivity"
    pytest app/tests/database/ -m "performance"
    pytest app/tests/database/ -m "integration"

    # Run with coverage
    pytest app/tests/database/ --cov=app.domain --cov=app.core.db

Test Structure:
- test_connectivity.py: Database connection and health tests
- test_models.py: SQLModel entity validation tests
- test_repositories.py: Repository CRUD operation tests
- test_integration.py: End-to-end workflow tests
- test_error_handling.py: Error scenario and recovery tests
- test_performance.py: Performance benchmarking tests
- factories.py: Test data creation utilities
- conftest.py: Test configuration and fixtures
- test_utils.py: Testing helper utilities
"""

from .factories import (
    JobFactory,
    OperatorAssignmentFactory,
    TaskFactory,
    TestDataBuilder,
)
from .test_utils import (
    ConcurrencyTestHelper,
    DatabaseTestHelper,
    PerformanceBenchmark,
    TestDataManager,
    assert_entity_relationships,
    create_performance_baseline,
    create_test_database_url,
    wait_for_database_ready,
)

__all__ = [
    # Factories
    "JobFactory",
    "TaskFactory",
    "OperatorAssignmentFactory",
    "TestDataBuilder",
    # Utilities
    "DatabaseTestHelper",
    "PerformanceBenchmark",
    "TestDataManager",
    "ConcurrencyTestHelper",
    "create_test_database_url",
    "wait_for_database_ready",
    "assert_entity_relationships",
    "create_performance_baseline",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "Vulcan Engine Team"
__description__ = "Comprehensive database testing suite"
