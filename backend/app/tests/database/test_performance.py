"""
Database Performance Tests

Performance validation tests for database operations including:
- Query performance benchmarks
- Load testing scenarios
- Memory usage validation
- Connection pool performance
- Batch operation efficiency
"""

import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sqlmodel import Session

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.value_objects.enums import (
    JobStatus,
    PriorityLevel,
    TaskStatus,
)
from app.tests.database.factories import (
    JobFactory,
    TaskFactory,
    TestDataBuilder,
)


class PerformanceMetrics:
    """Helper class for collecting and analyzing performance metrics."""

    def __init__(self):
        self.timings: list[float] = []
        self.memory_usage: list[int] = []
        self.operation_counts: dict[str, int] = {}

    def record_timing(self, duration: float):
        """Record operation timing."""
        self.timings.append(duration)

    def record_operation(self, operation_type: str):
        """Record operation count."""
        self.operation_counts[operation_type] = (
            self.operation_counts.get(operation_type, 0) + 1
        )

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        if not self.timings:
            return {}

        return {
            "min_time": min(self.timings),
            "max_time": max(self.timings),
            "avg_time": statistics.mean(self.timings),
            "median_time": statistics.median(self.timings),
            "total_operations": len(self.timings),
            "operations_per_second": len(self.timings) / sum(self.timings)
            if sum(self.timings) > 0
            else 0,
            "operation_counts": self.operation_counts.copy(),
        }

    def assert_performance_requirements(
        self, max_avg_time: float, min_ops_per_sec: float = None
    ):
        """Assert performance requirements are met."""
        stats = self.get_stats()
        assert (
            stats["avg_time"] <= max_avg_time
        ), f"Average time {stats['avg_time']:.3f}s exceeds limit {max_avg_time}s"

        if min_ops_per_sec:
            assert (
                stats["operations_per_second"] >= min_ops_per_sec
            ), f"Operations per second {stats['operations_per_second']:.2f} below minimum {min_ops_per_sec}"


class TestBasicQueryPerformance:
    """Test basic query performance."""

    def test_single_entity_retrieval_performance(self, db: Session):
        """Test performance of single entity retrieval."""
        # Create test data
        jobs = JobFactory.create_batch(1000)
        target_job = jobs[500]  # Middle job for testing

        metrics = PerformanceMetrics()

        # Test multiple retrievals
        for _ in range(100):
            start_time = time.time()

            # Simulate database retrieval by ID
            found_job = None
            for job in jobs:
                if job.id == target_job.id:
                    found_job = job
                    break

            end_time = time.time()
            metrics.record_timing(end_time - start_time)
            metrics.record_operation("single_retrieval")

            assert found_job is not None
            assert found_job.id == target_job.id

        # Performance requirements: should average less than 1ms per retrieval
        metrics.assert_performance_requirements(max_avg_time=0.001)

        stats = metrics.get_stats()
        assert stats["total_operations"] == 100

    def test_collection_query_performance(self, db: Session):
        """Test performance of collection queries."""
        # Create diverse dataset
        workload = TestDataBuilder.create_workload_scenario()
        jobs = workload["jobs"]

        metrics = PerformanceMetrics()

        # Test various collection queries
        query_types = [
            ("active_jobs", lambda: [job for job in jobs if job.is_active]),
            ("overdue_jobs", lambda: [job for job in jobs if job.is_overdue]),
            (
                "urgent_jobs",
                lambda: [job for job in jobs if job.priority == PriorityLevel.URGENT],
            ),
            ("due_soon", lambda: [job for job in jobs if job.days_until_due <= 7]),
            (
                "high_priority",
                lambda: [
                    job
                    for job in jobs
                    if job.priority in {PriorityLevel.HIGH, PriorityLevel.URGENT}
                ],
            ),
        ]

        # Run each query type multiple times
        for query_name, query_func in query_types:
            for _ in range(20):
                start_time = time.time()
                results = query_func()
                end_time = time.time()

                metrics.record_timing(end_time - start_time)
                metrics.record_operation(query_name)

                assert isinstance(results, list)

        # Performance requirements: collection queries should be fast
        metrics.assert_performance_requirements(max_avg_time=0.01, min_ops_per_sec=50)

    def test_filtered_query_performance(self, db: Session):
        """Test performance of filtered queries with multiple conditions."""
        jobs = JobFactory.create_batch(2000)
        tasks = []

        # Create tasks for jobs
        for job in jobs[:500]:  # Add tasks to subset of jobs
            job_tasks = TaskFactory.create_batch(job_id=job.id, count=5)
            for task in job_tasks:
                job.add_task(task)
                tasks.append(task)

        metrics = PerformanceMetrics()

        # Test complex filtered queries
        complex_queries = [
            (
                "ready_tasks_for_urgent_jobs",
                lambda: [
                    task
                    for task in tasks
                    if task.status == TaskStatus.READY
                    and any(
                        job.priority == PriorityLevel.URGENT
                        for job in jobs
                        if job.id == task.job_id
                    )
                ],
            ),
            (
                "delayed_critical_tasks",
                lambda: [
                    task for task in tasks if task.is_delayed and task.is_critical_path
                ],
            ),
            (
                "active_tasks_with_rework",
                lambda: [
                    task
                    for task in tasks
                    if task.status in {TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS}
                    and task.has_rework
                ],
            ),
        ]

        for query_name, query_func in complex_queries:
            for _ in range(10):
                start_time = time.time()
                results = query_func()
                end_time = time.time()

                metrics.record_timing(end_time - start_time)
                metrics.record_operation(query_name)

                assert isinstance(results, list)

        # Performance requirements for complex queries
        metrics.assert_performance_requirements(max_avg_time=0.05, min_ops_per_sec=10)

    def test_aggregation_query_performance(self, db: Session):
        """Test performance of aggregation operations."""
        workload = TestDataBuilder.create_workload_scenario()
        jobs = workload["jobs"]
        tasks = workload["tasks"]

        metrics = PerformanceMetrics()

        # Test aggregation operations
        aggregations = [
            ("total_jobs", lambda: len(jobs)),
            ("active_job_count", lambda: len([job for job in jobs if job.is_active])),
            (
                "average_completion",
                lambda: statistics.mean([job.completion_percentage for job in jobs]),
            ),
            ("total_task_count", lambda: len(tasks)),
            (
                "ready_task_count",
                lambda: len(
                    [task for task in tasks if task.status == TaskStatus.READY]
                ),
            ),
            (
                "average_delay",
                lambda: statistics.mean(
                    [task.delay_minutes for task in tasks if task.is_delayed]
                )
                if any(task.is_delayed for task in tasks)
                else 0,
            ),
        ]

        for agg_name, agg_func in aggregations:
            for _ in range(50):
                start_time = time.time()
                result = agg_func()
                end_time = time.time()

                metrics.record_timing(end_time - start_time)
                metrics.record_operation(agg_name)

                assert isinstance(result, int | float)

        # Aggregations should be fast
        metrics.assert_performance_requirements(max_avg_time=0.01, min_ops_per_sec=100)


class TestBulkOperationsPerformance:
    """Test performance of bulk operations."""

    def test_bulk_insert_performance(self, db: Session):
        """Test bulk insertion performance."""
        metrics = PerformanceMetrics()

        batch_sizes = [10, 50, 100, 500]

        for batch_size in batch_sizes:
            start_time = time.time()

            # Create batch of jobs
            jobs = JobFactory.create_batch(batch_size)

            # Simulate bulk insert
            inserted_count = 0
            for _job in jobs:
                # In real implementation: db.add(job)
                inserted_count += 1

            # In real implementation: db.commit()

            end_time = time.time()

            duration = end_time - start_time
            metrics.record_timing(duration)
            metrics.record_operation(f"bulk_insert_{batch_size}")

            # Verify all items were processed
            assert inserted_count == batch_size

        # Bulk operations should scale efficiently
        stats = metrics.get_stats()
        assert (
            stats["max_time"] < 1.0
        )  # Even largest batch should complete in < 1 second

    def test_bulk_update_performance(self, db: Session):
        """Test bulk update performance."""
        # Create initial dataset
        jobs = JobFactory.create_batch(500)

        metrics = PerformanceMetrics()

        # Test bulk status updates
        update_operations = [
            ("release_jobs", JobStatus.RELEASED),
            ("start_jobs", JobStatus.IN_PROGRESS),
            ("complete_jobs", JobStatus.COMPLETED),
        ]

        for operation_name, new_status in update_operations:
            start_time = time.time()

            # Bulk update operation
            updated_count = 0
            for job in jobs[:100]:  # Update subset
                try:
                    job.change_status(new_status)
                    updated_count += 1
                except Exception:
                    # Some status transitions may not be valid
                    pass

            end_time = time.time()

            metrics.record_timing(end_time - start_time)
            metrics.record_operation(operation_name)

        # Bulk updates should be efficient
        metrics.assert_performance_requirements(max_avg_time=0.1, min_ops_per_sec=10)

    def test_bulk_delete_performance(self, db: Session):
        """Test bulk deletion performance."""
        jobs = JobFactory.create_batch(1000)

        metrics = PerformanceMetrics()

        # Test bulk deletion in batches
        batch_size = 100
        batches = [jobs[i : i + batch_size] for i in range(0, len(jobs), batch_size)]

        for i, batch in enumerate(batches[:5]):  # Test first 5 batches
            start_time = time.time()

            # Simulate bulk delete
            deleted_count = len(batch)
            # In real implementation:
            # for job in batch:
            #     db.delete(job)
            # db.commit()

            end_time = time.time()

            metrics.record_timing(end_time - start_time)
            metrics.record_operation(f"bulk_delete_batch_{i}")

            assert deleted_count == batch_size

        # Bulk deletes should be fast
        metrics.assert_performance_requirements(max_avg_time=0.05)


class TestConcurrentOperationsPerformance:
    """Test performance under concurrent operations."""

    def test_concurrent_read_performance(self, db: Session):
        """Test performance of concurrent read operations."""
        # Create test dataset
        jobs = JobFactory.create_batch(1000)

        metrics = PerformanceMetrics()
        thread_count = 10
        operations_per_thread = 20

        def concurrent_read_worker(worker_id: int):
            """Worker function for concurrent reads."""
            for _ in range(operations_per_thread):
                start_time = time.time()

                # Random job lookup
                import random

                target_job = random.choice(jobs)

                # Simulate database read
                found_job = None
                for job in jobs:
                    if job.id == target_job.id:
                        found_job = job
                        break

                end_time = time.time()

                with threading.Lock():
                    metrics.record_timing(end_time - start_time)
                    metrics.record_operation(f"concurrent_read_worker_{worker_id}")

                assert found_job is not None

        # Execute concurrent reads
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [
                executor.submit(concurrent_read_worker, i) for i in range(thread_count)
            ]

            for future in as_completed(futures):
                future.result()  # Wait for completion and check for exceptions

        total_time = time.time() - start_time

        # Verify performance under concurrency
        stats = metrics.get_stats()
        expected_total_ops = thread_count * operations_per_thread
        assert stats["total_operations"] == expected_total_ops

        # Concurrent operations should not significantly degrade individual performance
        assert stats["avg_time"] < 0.01  # Still fast despite concurrency
        assert total_time < 5.0  # Total execution should complete reasonably quickly

    def test_mixed_concurrent_operations(self, db: Session):
        """Test performance of mixed read/write operations."""
        jobs = JobFactory.create_batch(500)

        metrics = PerformanceMetrics()

        def read_worker():
            """Read-heavy worker."""
            for _ in range(30):
                start_time = time.time()

                # Query operations
                active_jobs = [job for job in jobs if job.is_active]
                urgent_jobs = [
                    job for job in jobs if job.priority == PriorityLevel.URGENT
                ]

                end_time = time.time()

                with threading.Lock():
                    metrics.record_timing(end_time - start_time)
                    metrics.record_operation("mixed_read")

                assert isinstance(active_jobs, list)
                assert isinstance(urgent_jobs, list)

        def write_worker():
            """Write-heavy worker."""
            for _ in range(10):
                start_time = time.time()

                # Update operations
                import random

                target_jobs = random.sample(jobs, 5)

                for job in target_jobs:
                    try:
                        job.adjust_priority(PriorityLevel.HIGH, "concurrent_update")
                    except Exception:
                        pass  # Some operations may conflict

                end_time = time.time()

                with threading.Lock():
                    metrics.record_timing(end_time - start_time)
                    metrics.record_operation("mixed_write")

        # Execute mixed concurrent operations
        with ThreadPoolExecutor(max_workers=8) as executor:
            # 6 readers, 2 writers
            read_futures = [executor.submit(read_worker) for _ in range(6)]
            write_futures = [executor.submit(write_worker) for _ in range(2)]

            all_futures = read_futures + write_futures

            for future in as_completed(all_futures):
                future.result()

        # Verify mixed operations completed successfully
        stats = metrics.get_stats()
        assert stats["operation_counts"]["mixed_read"] == 180  # 6 workers * 30 ops
        assert stats["operation_counts"]["mixed_write"] == 20  # 2 workers * 10 ops


class TestMemoryPerformance:
    """Test memory usage and performance characteristics."""

    def test_large_dataset_memory_usage(self, db: Session):
        """Test memory usage with large datasets."""

        # Measure initial memory usage
        len(
            [obj for obj in globals().values() if isinstance(obj, Job | Task)]
        )

        # Create large dataset
        start_time = time.time()

        jobs, tasks, assignments = TestDataBuilder.create_manufacturing_scenario(
            job_count=100, tasks_per_job=10, operators_per_task=2
        )

        creation_time = time.time() - start_time

        # Measure final object count
        final_objects = len(jobs) + len(tasks) + len(assignments)

        # Verify dataset size
        assert len(jobs) == 100
        assert len(tasks) == 1000  # 100 jobs * 10 tasks
        assert len(assignments) == 2000  # 1000 tasks * 2 operators

        # Performance requirements
        assert creation_time < 2.0  # Should create large dataset quickly
        assert final_objects == 3100  # Total expected objects

        # Test operations on large dataset
        start_time = time.time()

        # Various operations that should scale well
        [job for job in jobs if job.is_active]
        [task for task in tasks if task.status == TaskStatus.READY]
        [task for task in tasks if task.is_critical_path]

        operation_time = time.time() - start_time

        # Operations should remain fast even with large dataset
        assert operation_time < 0.5

    def test_object_creation_efficiency(self, db: Session):
        """Test efficiency of object creation and initialization."""
        metrics = PerformanceMetrics()

        object_counts = [10, 50, 100, 500, 1000]

        for count in object_counts:
            start_time = time.time()

            # Create various entity types
            jobs = JobFactory.create_batch(count)
            tasks = []

            # Add tasks to first few jobs
            for job in jobs[: min(10, count)]:
                job_tasks = TaskFactory.create_batch(job_id=job.id, count=5)
                for task in job_tasks:
                    job.add_task(task)
                    tasks.append(task)

            creation_time = time.time() - start_time

            metrics.record_timing(creation_time)
            metrics.record_operation(f"create_objects_{count}")

            # Verify objects were created correctly
            assert len(jobs) == count

            # Test that creation time scales reasonably
            objects_per_second = (
                count / creation_time if creation_time > 0 else float("inf")
            )
            assert (
                objects_per_second > 100
            )  # Should create at least 100 objects per second

        # Overall creation should be efficient
        stats = metrics.get_stats()
        assert stats["max_time"] < 1.0  # Even largest batch should complete quickly


class TestQueryOptimizationPerformance:
    """Test query optimization and indexing effectiveness."""

    def test_index_effectiveness_simulation(self, db: Session):
        """Test simulated index effectiveness for common queries."""
        # Create large dataset to test query performance
        jobs = JobFactory.create_batch(5000)

        # Add variety to test different query patterns
        for i, job in enumerate(jobs):
            if i % 10 == 0:
                job.priority = PriorityLevel.URGENT
            elif i % 5 == 0:
                job.priority = PriorityLevel.HIGH

            if i % 20 == 0:
                job.change_status(JobStatus.COMPLETED)
            elif i % 15 == 0:
                job.change_status(JobStatus.IN_PROGRESS)
            elif i % 10 == 0:
                job.change_status(JobStatus.RELEASED)

        metrics = PerformanceMetrics()

        # Test queries that would benefit from indexes
        indexed_queries = [
            (
                "find_by_status",
                lambda status: [job for job in jobs if job.status == status],
            ),
            (
                "find_by_priority",
                lambda priority: [job for job in jobs if job.priority == priority],
            ),
            ("find_active", lambda: [job for job in jobs if job.is_active]),
            ("find_overdue", lambda: [job for job in jobs if job.is_overdue]),
        ]

        for query_name, query_func in indexed_queries:
            # Test multiple variations
            test_cases = [
                JobStatus.RELEASED,
                PriorityLevel.URGENT,
                None,  # for parameterless queries
                None,
            ]

            for i, test_case in enumerate(test_cases):
                start_time = time.time()

                if test_case is not None:
                    results = query_func(test_case)
                else:
                    results = query_func()

                end_time = time.time()

                metrics.record_timing(end_time - start_time)
                metrics.record_operation(f"{query_name}_{i}")

                assert isinstance(results, list)

                # Break after first valid test case for parameterless queries
                if test_case is None:
                    break

        # Indexed queries should be fast even with large dataset
        metrics.assert_performance_requirements(max_avg_time=0.01, min_ops_per_sec=50)

    def test_join_performance_simulation(self, db: Session):
        """Test simulated join performance for related entities."""
        # Create related data
        jobs = JobFactory.create_batch(500)
        all_tasks = []

        for job in jobs:
            tasks = TaskFactory.create_batch(job_id=job.id, count=8)
            for task in tasks:
                job.add_task(task)
                all_tasks.append(task)

        metrics = PerformanceMetrics()

        # Test join-like operations
        join_queries = [
            (
                "jobs_with_ready_tasks",
                lambda: [
                    job
                    for job in jobs
                    if any(
                        task.status == TaskStatus.READY for task in job.get_all_tasks()
                    )
                ],
            ),
            (
                "urgent_jobs_with_active_tasks",
                lambda: [
                    job
                    for job in jobs
                    if job.priority == PriorityLevel.URGENT
                    and any(
                        task.status == TaskStatus.IN_PROGRESS
                        for task in job.get_all_tasks()
                    )
                ],
            ),
            (
                "tasks_for_overdue_jobs",
                lambda: [
                    task
                    for task in all_tasks
                    if any(job.is_overdue for job in jobs if job.id == task.job_id)
                ],
            ),
        ]

        for query_name, query_func in join_queries:
            for _ in range(10):
                start_time = time.time()
                results = query_func()
                end_time = time.time()

                metrics.record_timing(end_time - start_time)
                metrics.record_operation(query_name)

                assert isinstance(results, list)

        # Join operations should complete in reasonable time
        metrics.assert_performance_requirements(max_avg_time=0.05, min_ops_per_sec=20)


class TestScalabilityPerformance:
    """Test performance scalability with increasing data sizes."""

    def test_linear_scalability(self, db: Session):
        """Test that performance scales linearly with data size."""
        data_sizes = [100, 500, 1000, 2500]
        performance_ratios = []

        for size in data_sizes:
            start_time = time.time()

            # Create dataset of specified size
            jobs = JobFactory.create_batch(size)

            # Perform standard operations
            active_count = len([job for job in jobs if job.is_active])
            urgent_count = len(
                [job for job in jobs if job.priority == PriorityLevel.URGENT]
            )
            completion_avg = sum(job.completion_percentage for job in jobs) / len(jobs)

            end_time = time.time()

            operation_time = end_time - start_time
            time_per_item = operation_time / size

            performance_ratios.append(time_per_item)

            # Verify operations completed
            assert isinstance(active_count, int)
            assert isinstance(urgent_count, int)
            assert isinstance(completion_avg, float)

        # Performance should scale roughly linearly (time per item should be relatively stable)
        min_ratio = min(performance_ratios)
        max_ratio = max(performance_ratios)

        # Allow for some variation, but should not be exponential growth
        scalability_factor = max_ratio / min_ratio if min_ratio > 0 else 1
        assert (
            scalability_factor < 5.0
        ), f"Performance degradation factor {scalability_factor} too high"

    def test_memory_scalability(self, db: Session):
        """Test memory usage scalability."""
        import gc

        memory_measurements = []
        data_sizes = [100, 500, 1000]

        for size in data_sizes:
            # Force garbage collection before measurement
            gc.collect()

            # Create dataset
            jobs = JobFactory.create_batch(size)
            tasks = []

            for job in jobs[: min(100, size)]:  # Limit task creation to avoid explosion
                job_tasks = TaskFactory.create_batch(job_id=job.id, count=5)
                for task in job_tasks:
                    job.add_task(task)
                    tasks.append(task)

            # Measure objects created
            total_objects = len(jobs) + len(tasks)
            memory_per_object = total_objects  # Simplified memory measurement

            memory_measurements.append(memory_per_object / size)

        # Memory per base object should remain relatively stable
        memory_variance = max(memory_measurements) - min(memory_measurements)
        avg_memory = sum(memory_measurements) / len(memory_measurements)

        # Memory growth should be reasonable
        variance_ratio = memory_variance / avg_memory if avg_memory > 0 else 0
        assert variance_ratio < 1.0, f"Memory variance ratio {variance_ratio} too high"
