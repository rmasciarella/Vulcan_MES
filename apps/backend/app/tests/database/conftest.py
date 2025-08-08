"""
Database Test Configuration and Fixtures

Pytest configuration and fixtures specifically for database tests.
Provides test database setup, cleanup, and utility fixtures.
"""

from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from app.core.db_test import create_test_db, drop_test_db, get_test_session, test_engine
from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import Task
from app.tests.database.factories import (
    JobFactory,
    OperatorAssignmentFactory,
    TaskFactory,
    TestDataBuilder,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup and teardown test database for the session."""
    # Create test database tables
    create_test_db()

    yield

    # Clean up after all tests
    drop_test_db()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Provide a clean database session for each test.

    This fixture creates a new session for each test function and
    ensures cleanup after the test completes.
    """
    with get_test_session() as session:
        # Begin a transaction
        transaction = session.begin()

        try:
            yield session
        finally:
            # Rollback transaction to ensure clean state
            transaction.rollback()


@pytest.fixture(scope="function")
def clean_db() -> Generator[Session, None, None]:
    """
    Provide a completely clean database for tests that need isolation.

    This fixture recreates all tables for maximum isolation.
    """
    # Drop and recreate tables
    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)

    with get_test_session() as session:
        yield session

    # Clean up after test
    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)


@pytest.fixture
def sample_job():
    """Provide a sample job for testing."""
    return JobFactory.create()


@pytest.fixture
def sample_job_with_tasks():
    """Provide a sample job with tasks for testing."""
    return JobFactory.create_with_tasks(task_count=5)


@pytest.fixture
def sample_task():
    """Provide a sample task for testing."""
    return TaskFactory.create()


@pytest.fixture
def sample_ready_task():
    """Provide a ready-to-schedule task for testing."""
    return TaskFactory.create_ready()


@pytest.fixture
def sample_scheduled_task():
    """Provide a scheduled task for testing."""
    return TaskFactory.create_scheduled()


@pytest.fixture
def sample_in_progress_task():
    """Provide an in-progress task for testing."""
    return TaskFactory.create_in_progress()


@pytest.fixture
def sample_completed_task():
    """Provide a completed task for testing."""
    return TaskFactory.create_completed()


@pytest.fixture
def sample_operator_assignment():
    """Provide a sample operator assignment for testing."""
    return OperatorAssignmentFactory.create()


@pytest.fixture
def batch_jobs(request):
    """
    Provide a batch of jobs for testing.

    Usage:
        @pytest.mark.parametrize("batch_jobs", [10], indirect=True)
        def test_with_jobs(batch_jobs):
            assert len(batch_jobs) == 10
    """
    count = getattr(request, "param", 10)
    return JobFactory.create_batch(count)


@pytest.fixture
def workload_scenario():
    """Provide a realistic workload scenario for testing."""
    return TestDataBuilder.create_workload_scenario()


@pytest.fixture
def manufacturing_scenario(request):
    """
    Provide a manufacturing scenario with jobs, tasks, and assignments.

    Usage:
        @pytest.mark.parametrize("manufacturing_scenario", [(5, 3, 2)], indirect=True)
        def test_scenario(manufacturing_scenario):
            jobs, tasks, assignments = manufacturing_scenario
    """
    params = getattr(request, "param", (5, 4, 2))
    job_count, tasks_per_job, operators_per_task = params

    return TestDataBuilder.create_manufacturing_scenario(
        job_count=job_count,
        tasks_per_job=tasks_per_job,
        operators_per_task=operators_per_task,
    )


@pytest.fixture
def database_stats(db_session: Session):
    """
    Provide database statistics and monitoring utilities.

    Returns a dictionary with database statistics and helper functions.
    """

    def get_table_count(table_name: str) -> int:
        """Get count of records in a table."""
        # In real implementation, would query actual database tables
        return 0

    def get_connection_count() -> int:
        """Get current connection count."""
        result = db_session.execute(
            text("""
            SELECT count(*)
            FROM pg_stat_activity
            WHERE state = 'active'
        """)
        )
        return result.scalar() or 0

    def get_database_size() -> str:
        """Get database size."""
        result = db_session.execute(
            text("""
            SELECT pg_size_pretty(pg_database_size(current_database()))
        """)
        )
        return result.scalar() or "0 bytes"

    def get_lock_count() -> int:
        """Get current lock count."""
        result = db_session.execute(
            text("""
            SELECT count(*)
            FROM pg_locks
            WHERE granted = true
        """)
        )
        return result.scalar() or 0

    return {
        "get_table_count": get_table_count,
        "get_connection_count": get_connection_count,
        "get_database_size": get_database_size,
        "get_lock_count": get_lock_count,
        "session": db_session,
    }


@pytest.fixture
def performance_monitor():
    """
    Provide performance monitoring utilities for tests.

    Returns a context manager for timing operations and collecting metrics.
    """
    import time
    from contextlib import contextmanager

    metrics = {"timings": [], "operations": [], "errors": []}

    @contextmanager
    def time_operation(operation_name: str):
        """Context manager to time an operation."""
        start_time = time.time()
        error = None

        try:
            yield
        except Exception as e:
            error = str(e)
            metrics["errors"].append(
                {"operation": operation_name, "error": error, "timestamp": time.time()}
            )
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time

            metrics["timings"].append(duration)
            metrics["operations"].append(
                {
                    "name": operation_name,
                    "duration": duration,
                    "error": error,
                    "timestamp": end_time,
                }
            )

    def get_stats() -> dict[str, Any]:
        """Get performance statistics."""
        if not metrics["timings"]:
            return {"total_operations": 0}

        timings = metrics["timings"]
        return {
            "total_operations": len(timings),
            "total_time": sum(timings),
            "avg_time": sum(timings) / len(timings),
            "min_time": min(timings),
            "max_time": max(timings),
            "error_count": len(metrics["errors"]),
            "success_rate": (len(timings) - len(metrics["errors"])) / len(timings)
            if timings
            else 0,
            "operations": metrics["operations"].copy(),
            "errors": metrics["errors"].copy(),
        }

    def reset_metrics():
        """Reset all metrics."""
        metrics["timings"].clear()
        metrics["operations"].clear()
        metrics["errors"].clear()

    return {
        "time_operation": time_operation,
        "get_stats": get_stats,
        "reset_metrics": reset_metrics,
        "raw_metrics": metrics,
    }


@pytest.fixture
def transaction_manager(db_session: Session):
    """
    Provide transaction management utilities for tests.

    Allows tests to control transaction boundaries and test rollback scenarios.
    """

    class TransactionManager:
        def __init__(self, session: Session):
            self.session = session
            self._savepoints = []

        def begin_transaction(self):
            """Begin a new transaction."""
            return self.session.begin()

        def create_savepoint(self, name: str = None):
            """Create a savepoint within the current transaction."""
            savepoint = self.session.begin_nested()
            self._savepoints.append(
                {"name": name or f"sp_{len(self._savepoints)}", "savepoint": savepoint}
            )
            return savepoint

        def rollback_to_savepoint(self, name: str = None):
            """Rollback to a specific savepoint."""
            if not self._savepoints:
                return False

            if name:
                # Find specific savepoint
                for i, sp_info in enumerate(self._savepoints):
                    if sp_info["name"] == name:
                        sp_info["savepoint"].rollback()
                        # Remove this and later savepoints
                        self._savepoints = self._savepoints[:i]
                        return True
                return False
            else:
                # Rollback to latest savepoint
                latest = self._savepoints.pop()
                latest["savepoint"].rollback()
                return True

        def commit_savepoint(self, name: str = None):
            """Commit a specific savepoint."""
            if not self._savepoints:
                return False

            if name:
                for i, sp_info in enumerate(self._savepoints):
                    if sp_info["name"] == name:
                        sp_info["savepoint"].commit()
                        self._savepoints.pop(i)
                        return True
                return False
            else:
                latest = self._savepoints.pop()
                latest["savepoint"].commit()
                return True

        def rollback_all(self):
            """Rollback the entire transaction."""
            # Rollback all savepoints first
            for sp_info in reversed(self._savepoints):
                sp_info["savepoint"].rollback()
            self._savepoints.clear()

            # Rollback main transaction
            self.session.rollback()

        def get_savepoint_count(self) -> int:
            """Get number of active savepoints."""
            return len(self._savepoints)

    return TransactionManager(db_session)


@pytest.fixture
def data_validator():
    """
    Provide data validation utilities for tests.

    Helps validate entity states and relationships in tests.
    """

    def validate_job(job: Job) -> dict[str, Any]:
        """Validate job entity and return validation results."""
        issues = []

        # Basic validation
        if not job.job_number:
            issues.append("Job number is empty")

        if not job.is_valid():
            issues.append("Job fails basic validation")

        # Date validation
        if job.actual_end_date and job.actual_start_date:
            if job.actual_end_date <= job.actual_start_date:
                issues.append("Actual end date is not after start date")

        if job.planned_end_date and job.planned_start_date:
            if job.planned_end_date <= job.planned_start_date:
                issues.append("Planned end date is not after start date")

        # Task validation
        task_sequences = []
        for task in job.get_all_tasks():
            task_sequences.append(task.sequence_in_job)

        if len(task_sequences) != len(set(task_sequences)):
            issues.append("Duplicate task sequences found")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "task_count": job.task_count,
            "completion_percentage": job.completion_percentage,
        }

    def validate_task(task: Task) -> dict[str, Any]:
        """Validate task entity and return validation results."""
        issues = []

        # Basic validation
        if not task.is_valid():
            issues.append("Task fails basic validation")

        # Sequence validation
        if not (1 <= task.sequence_in_job <= 100):
            issues.append(f"Invalid sequence number: {task.sequence_in_job}")

        # Time validation
        if task.actual_end_time and task.actual_start_time:
            if task.actual_end_time <= task.actual_start_time:
                issues.append("Actual end time is not after start time")

        if task.planned_end_time and task.planned_start_time:
            if task.planned_end_time <= task.planned_start_time:
                issues.append("Planned end time is not after start time")

        # Status validation
        if task.status == TaskStatus.COMPLETED and not task.actual_end_time:
            issues.append("Completed task missing actual end time")

        if task.status == TaskStatus.IN_PROGRESS and not task.actual_start_time:
            issues.append("In-progress task missing actual start time")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "status": task.status.value,
            "is_delayed": task.is_delayed,
            "delay_minutes": task.delay_minutes,
        }

    def validate_job_task_relationship(job: Job) -> dict[str, Any]:
        """Validate job-task relationships."""
        issues = []

        # Check that all tasks belong to the job
        for task in job.get_all_tasks():
            if task.job_id != job.id:
                issues.append(f"Task {task.id} has incorrect job_id")

        # Check task sequence uniqueness
        sequences = [task.sequence_in_job for task in job.get_all_tasks()]
        if len(sequences) != len(set(sequences)):
            issues.append("Duplicate task sequences in job")

        # Check completion percentage calculation
        expected_completion = (
            (job.completed_task_count / job.task_count * 100)
            if job.task_count > 0
            else 0
        )
        if abs(job.completion_percentage - expected_completion) > 0.1:
            issues.append(
                f"Completion percentage mismatch: {job.completion_percentage} vs {expected_completion}"
            )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "total_tasks": job.task_count,
            "completed_tasks": job.completed_task_count,
            "ready_tasks": len(job.get_ready_tasks()),
            "active_tasks": len(job.get_active_tasks()),
        }

    return {
        "validate_job": validate_job,
        "validate_task": validate_task,
        "validate_job_task_relationship": validate_job_task_relationship,
    }


# Pytest markers for database tests
pytest.mark.database = pytest.mark.mark(name="database")
pytest.mark.integration = pytest.mark.mark(name="integration")
pytest.mark.performance = pytest.mark.mark(name="performance")
pytest.mark.slow = pytest.mark.mark(name="slow")
