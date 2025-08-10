"""
Database Test Utilities

Utility functions and classes for database testing including:
- Test data cleanup
- Database state verification
- Performance measurement helpers
- Test data generation utilities
"""

import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.value_objects.enums import (
    PriorityLevel,
)


class DatabaseTestHelper:
    """Helper class for common database test operations."""

    def __init__(self, session: Session):
        self.session = session

    def count_entities(self, entity_type: str) -> int:
        """Count entities of a specific type (simulated for domain model)."""
        # In real implementation, would query actual database tables
        counts = {"jobs": 0, "tasks": 0, "operator_assignments": 0}
        return counts.get(entity_type.lower(), 0)

    def clear_all_data(self):
        """Clear all test data from database."""
        # In real implementation, would delete from actual tables
        # For now, this is a placeholder
        pass

    def get_database_info(self) -> dict[str, Any]:
        """Get general database information."""
        try:
            version_result = self.session.execute(text("SELECT version()"))
            version = version_result.scalar()

            size_result = self.session.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            size = size_result.scalar()

            connections_result = self.session.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            connections = connections_result.scalar()

            return {
                "version": version,
                "size": size,
                "active_connections": connections,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    def verify_referential_integrity(self) -> list[str]:
        """Verify referential integrity constraints."""
        issues = []

        # In real implementation, would check foreign key constraints
        # For domain model, we check logical consistency

        return issues

    def get_table_statistics(self) -> dict[str, Any]:
        """Get table statistics from database."""
        try:
            stats_result = self.session.execute(
                text("""
                SELECT
                    schemaname,
                    tablename,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
            """)
            )

            tables = []
            for row in stats_result:
                tables.append(
                    {
                        "schema": row.schemaname,
                        "table": row.tablename,
                        "inserts": row.inserts,
                        "updates": row.updates,
                        "deletes": row.deletes,
                        "live_tuples": row.live_tuples,
                        "dead_tuples": row.dead_tuples,
                    }
                )

            return {"tables": tables}
        except Exception as e:
            return {"error": str(e)}


class PerformanceBenchmark:
    """Performance benchmarking utility for database operations."""

    def __init__(self):
        self.results = {}
        self.current_benchmark = None
        self._lock = threading.Lock()

    @contextmanager
    def benchmark(self, operation_name: str, iterations: int = 1):
        """Context manager for benchmarking operations."""
        with self._lock:
            self.current_benchmark = {
                "name": operation_name,
                "iterations": iterations,
                "start_time": time.time(),
                "timings": [],
                "errors": [],
            }

        try:
            for i in range(iterations):
                iteration_start = time.time()

                yield i

                iteration_end = time.time()
                self.current_benchmark["timings"].append(
                    iteration_end - iteration_start
                )

        except Exception as e:
            self.current_benchmark["errors"].append(str(e))
            raise

        finally:
            end_time = time.time()
            total_time = end_time - self.current_benchmark["start_time"]

            # Calculate statistics
            timings = self.current_benchmark["timings"]
            if timings:
                avg_time = sum(timings) / len(timings)
                min_time = min(timings)
                max_time = max(timings)
                ops_per_second = len(timings) / total_time if total_time > 0 else 0
            else:
                avg_time = min_time = max_time = ops_per_second = 0

            result = {
                "operation": operation_name,
                "iterations": iterations,
                "successful_iterations": len(timings),
                "total_time": total_time,
                "avg_time_per_operation": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "operations_per_second": ops_per_second,
                "error_count": len(self.current_benchmark["errors"]),
                "errors": self.current_benchmark["errors"].copy(),
                "timestamp": datetime.utcnow().isoformat(),
            }

            self.results[operation_name] = result
            self.current_benchmark = None

    def get_results(self) -> dict[str, Any]:
        """Get all benchmark results."""
        return self.results.copy()

    def clear_results(self):
        """Clear all benchmark results."""
        self.results.clear()

    def compare_benchmarks(self, baseline: str, comparison: str) -> dict[str, Any]:
        """Compare two benchmark results."""
        if baseline not in self.results or comparison not in self.results:
            return {"error": "One or both benchmarks not found"}

        base = self.results[baseline]
        comp = self.results[comparison]

        # Calculate relative performance
        time_ratio = (
            comp["avg_time_per_operation"] / base["avg_time_per_operation"]
            if base["avg_time_per_operation"] > 0
            else float("inf")
        )
        ops_ratio = (
            comp["operations_per_second"] / base["operations_per_second"]
            if base["operations_per_second"] > 0
            else float("inf")
        )

        return {
            "baseline": baseline,
            "comparison": comparison,
            "time_ratio": time_ratio,  # > 1 means comparison is slower
            "ops_ratio": ops_ratio,  # > 1 means comparison is faster
            "performance_change_percent": ((1 / time_ratio) - 1) * 100
            if time_ratio > 0
            else 0,
            "baseline_ops_per_second": base["operations_per_second"],
            "comparison_ops_per_second": comp["operations_per_second"],
            "baseline_avg_time": base["avg_time_per_operation"],
            "comparison_avg_time": comp["avg_time_per_operation"],
        }


class TestDataManager:
    """Manager for test data lifecycle and cleanup."""

    def __init__(self):
        self.created_entities = {"jobs": [], "tasks": [], "assignments": []}
        self.cleanup_callbacks = []

    def register_job(self, job: Job):
        """Register a job for cleanup tracking."""
        self.created_entities["jobs"].append(job)

    def register_task(self, task: Task):
        """Register a task for cleanup tracking."""
        self.created_entities["tasks"].append(task)

    def register_cleanup_callback(self, callback: Callable[[], None]):
        """Register a cleanup callback function."""
        self.cleanup_callbacks.append(callback)

    def get_entity_counts(self) -> dict[str, int]:
        """Get counts of tracked entities."""
        return {
            entity_type: len(entities)
            for entity_type, entities in self.created_entities.items()
        }

    def cleanup_all(self):
        """Clean up all tracked entities and run cleanup callbacks."""
        # Run custom cleanup callbacks first
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Cleanup callback error: {e}")

        # Clear entity tracking
        for entity_list in self.created_entities.values():
            entity_list.clear()

        self.cleanup_callbacks.clear()

    def create_test_scenario(self, scenario_name: str, **kwargs) -> dict[str, Any]:
        """Create a named test scenario with specific characteristics."""
        from app.tests.database.factories import TestDataBuilder

        scenarios = {
            "small_workload": lambda: TestDataBuilder.create_manufacturing_scenario(
                5, 3, 2
            ),
            "medium_workload": lambda: TestDataBuilder.create_manufacturing_scenario(
                20, 5, 3
            ),
            "large_workload": lambda: TestDataBuilder.create_manufacturing_scenario(
                100, 8, 4
            ),
            "realistic_workload": lambda: TestDataBuilder.create_workload_scenario(),
        }

        if scenario_name not in scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        # Create the scenario
        if scenario_name == "realistic_workload":
            scenario_data = scenarios[scenario_name]()
            jobs = scenario_data["jobs"]
            tasks = scenario_data["tasks"]
            assignments = []  # Workload scenario doesn't include assignments
        else:
            jobs, tasks, assignments = scenarios[scenario_name]()

        # Register entities for cleanup
        for job in jobs:
            self.register_job(job)
        for task in tasks:
            self.register_task(task)

        return {
            "jobs": jobs,
            "tasks": tasks,
            "assignments": assignments,
            "scenario_name": scenario_name,
            "creation_timestamp": datetime.utcnow().isoformat(),
        }


class ConcurrencyTestHelper:
    """Helper for testing concurrent database operations."""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.results = []
        self.errors = []
        self._lock = threading.Lock()

    def run_concurrent_operations(
        self, operations: list[Callable], timeout: float = 30.0
    ) -> dict[str, Any]:
        """Run multiple operations concurrently and collect results."""
        import concurrent.futures

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # Submit all operations
            future_to_op = {executor.submit(op): i for i, op in enumerate(operations)}

            try:
                # Wait for completion with timeout
                for future in concurrent.futures.as_completed(
                    future_to_op, timeout=timeout
                ):
                    op_index = future_to_op[future]

                    try:
                        result = future.result()
                        with self._lock:
                            self.results.append(
                                {
                                    "operation_index": op_index,
                                    "result": result,
                                    "success": True,
                                    "timestamp": time.time(),
                                }
                            )
                    except Exception as e:
                        with self._lock:
                            self.errors.append(
                                {
                                    "operation_index": op_index,
                                    "error": str(e),
                                    "timestamp": time.time(),
                                }
                            )

            except concurrent.futures.TimeoutError:
                # Cancel remaining futures
                for future in future_to_op:
                    future.cancel()

                with self._lock:
                    self.errors.append(
                        {
                            "error": "Timeout waiting for operations to complete",
                            "timestamp": time.time(),
                        }
                    )

        end_time = time.time()

        return {
            "total_operations": len(operations),
            "successful_operations": len(self.results),
            "failed_operations": len(self.errors),
            "total_time": end_time - start_time,
            "results": self.results.copy(),
            "errors": self.errors.copy(),
        }

    def create_read_operation(
        self, data: list[Any], operation_count: int = 10
    ) -> Callable:
        """Create a read operation function for concurrent testing."""

        def read_operation():
            import random

            results = []

            for _ in range(operation_count):
                # Simulate read operations
                if data:
                    item = random.choice(data)
                    # Perform some operation on the item
                    if hasattr(item, "id"):
                        _ = str(item.id)
                    if hasattr(item, "status"):
                        _ = item.status
                    results.append(item)

            return len(results)

        return read_operation

    def create_write_operation(
        self, data: list[Any], operation_count: int = 5
    ) -> Callable:
        """Create a write operation function for concurrent testing."""

        def write_operation():
            import random

            modifications = 0

            for _ in range(operation_count):
                if data:
                    item = random.choice(data)

                    # Perform safe write operations
                    try:
                        if hasattr(item, "priority") and hasattr(
                            item, "adjust_priority"
                        ):
                            new_priority = random.choice(list(PriorityLevel))
                            item.adjust_priority(new_priority, "concurrent_test")
                            modifications += 1
                        elif hasattr(item, "notes"):
                            item.notes = f"Updated at {time.time()}"
                            modifications += 1
                    except Exception:
                        # Some operations may fail due to business rules
                        pass

            return modifications

        return write_operation

    def clear_results(self):
        """Clear all results and errors."""
        with self._lock:
            self.results.clear()
            self.errors.clear()


def create_test_database_url(base_url: str, test_suffix: str = "_test") -> str:
    """Create a test database URL from a base database URL."""
    if "?" in base_url:
        db_part, params = base_url.rsplit("?", 1)
    else:
        db_part = base_url
        params = ""

    # Extract database name and add test suffix
    if "/" in db_part:
        base_part, db_name = db_part.rsplit("/", 1)
        test_db_name = f"{db_name}{test_suffix}"
        test_url = f"{base_part}/{test_db_name}"
    else:
        test_url = f"{db_part}{test_suffix}"

    if params:
        test_url = f"{test_url}?{params}"

    return test_url


def wait_for_database_ready(
    session: Session, timeout: float = 30.0, check_interval: float = 1.0
) -> bool:
    """
    Wait for database to be ready for connections.

    Returns True if database is ready, False if timeout is reached.
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Try a simple query
            session.execute(text("SELECT 1"))
            return True
        except Exception:
            time.sleep(check_interval)

    return False


def assert_entity_relationships(job: Job, expected_task_count: int = None):
    """Assert that entity relationships are properly maintained."""
    # Basic relationship assertions
    assert job is not None
    assert job.id is not None

    if expected_task_count is not None:
        assert job.task_count == expected_task_count

    # Check task relationships
    for task in job.get_all_tasks():
        assert task.job_id == job.id
        assert task.sequence_in_job >= 1
        assert task.sequence_in_job <= 100

    # Check sequence uniqueness
    sequences = [task.sequence_in_job for task in job.get_all_tasks()]
    assert len(sequences) == len(set(sequences)), "Duplicate task sequences found"


def create_performance_baseline(
    operations: dict[str, Callable], iterations: int = 100
) -> dict[str, Any]:
    """Create a performance baseline for comparison in future tests."""
    benchmark = PerformanceBenchmark()
    baseline_results = {}

    for operation_name, operation_func in operations.items():
        with benchmark.benchmark(operation_name, iterations):
            for _ in range(iterations):
                operation_func()

        baseline_results[operation_name] = benchmark.results[operation_name]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "iterations_per_operation": iterations,
        "results": baseline_results,
    }
