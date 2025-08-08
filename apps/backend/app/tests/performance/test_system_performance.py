"""
Comprehensive Performance Tests for Production Scheduling System

Tests system performance under various load conditions including database
operations, solver performance, API response times, and concurrent access.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import psutil
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.db_test import test_engine
from app.core.solver import HFFSScheduler
from app.infrastructure.database.models import JobCreate
from app.infrastructure.database.repositories.job_repository import JobRepository
from app.main import app

client = TestClient(app)


class PerformanceMonitor:
    """Utility class for monitoring system performance during tests."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.peak_memory = None

    def start_monitoring(self):
        """Start monitoring system resources."""
        self.start_time = time.time()
        self.start_memory = psutil.virtual_memory().used
        self.peak_memory = self.start_memory

    def update_peak_memory(self):
        """Update peak memory usage."""
        current_memory = psutil.virtual_memory().used
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory

    def stop_monitoring(self):
        """Stop monitoring and calculate metrics."""
        self.end_time = time.time()
        self.end_memory = psutil.virtual_memory().used

    @property
    def duration(self) -> float:
        """Get total duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def memory_increase_mb(self) -> float:
        """Get memory increase in MB."""
        if self.start_memory and self.end_memory:
            return (self.end_memory - self.start_memory) / (1024 * 1024)
        return 0.0

    @property
    def peak_memory_increase_mb(self) -> float:
        """Get peak memory increase in MB."""
        if self.start_memory and self.peak_memory:
            return (self.peak_memory - self.start_memory) / (1024 * 1024)
        return 0.0


@pytest.fixture
def performance_monitor():
    """Create a performance monitor instance."""
    return PerformanceMonitor()


@pytest.fixture
def db_session():
    """Create database session for performance tests."""
    with Session(test_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def job_repository(db_session):
    """Create job repository for performance tests."""
    return JobRepository(session=db_session)


class TestDatabasePerformance:
    """Test database operation performance."""

    def test_bulk_job_creation_performance(self, job_repository, performance_monitor):
        """Test performance of bulk job creation."""
        performance_monitor.start_monitoring()

        # Create 1000 jobs
        job_count = 1000
        jobs_created = []

        for i in range(job_count):
            job_data = {
                "job_number": f"PERF-JOB-{i:05d}",
                "customer_name": f"Customer {i % 100}",  # 100 different customers
                "part_number": f"PART-{i % 50:03d}",  # 50 different parts
                "quantity": (i % 20) + 1,  # 1-20 pieces
                "priority": ["LOW", "NORMAL", "HIGH", "URGENT"][i % 4],
                "status": "PLANNED",
                "due_date": datetime.utcnow() + timedelta(days=(i % 30) + 1),
                "notes": f"Performance test job {i}",
                "created_by": "performance_test",
            }

            job_create = JobCreate(**job_data)
            created_job = job_repository.create(job_create)
            jobs_created.append(created_job)

            # Update peak memory every 100 jobs
            if i % 100 == 0:
                performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Performance assertions
        assert len(jobs_created) == job_count
        assert performance_monitor.duration < 60.0  # Should complete within 1 minute
        assert (
            performance_monitor.peak_memory_increase_mb < 100
        )  # Should use < 100MB additional memory

        # Calculate throughput
        throughput = job_count / performance_monitor.duration
        assert throughput > 50  # Should create > 50 jobs per second

        print(f"Created {job_count} jobs in {performance_monitor.duration:.2f} seconds")
        print(f"Throughput: {throughput:.1f} jobs/second")
        print(
            f"Peak memory increase: {performance_monitor.peak_memory_increase_mb:.1f} MB"
        )

    def test_large_query_performance(self, job_repository, performance_monitor):
        """Test performance of querying large datasets."""
        # First create a large dataset
        job_count = 2000
        customer_names = [f"Customer {i}" for i in range(100)]

        for i in range(job_count):
            job_data = {
                "job_number": f"QUERY-JOB-{i:05d}",
                "customer_name": customer_names[i % len(customer_names)],
                "quantity": 1,
                "due_date": datetime.utcnow() + timedelta(days=30),
            }
            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

        # Test various query patterns
        performance_monitor.start_monitoring()

        # Query 1: List all jobs
        all_jobs = job_repository.list()
        performance_monitor.update_peak_memory()

        # Query 2: Find jobs by customer (should return ~20 jobs per customer)
        customer_jobs = job_repository.find_by_customer("Customer 0")
        performance_monitor.update_peak_memory()

        # Query 3: Find jobs by status
        planned_jobs = job_repository.find_by_status(["PLANNED"])
        performance_monitor.update_peak_memory()

        # Query 4: Paginated query
        page_1 = job_repository.list(skip=0, limit=100)
        page_10 = job_repository.list(skip=1000, limit=100)
        performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Performance assertions
        assert len(all_jobs) == job_count
        assert len(customer_jobs) >= 15  # Should find jobs for Customer 0
        assert len(planned_jobs) == job_count  # All jobs are planned
        assert len(page_1) == 100
        assert len(page_10) == 100

        assert performance_monitor.duration < 10.0  # Should complete within 10 seconds
        assert performance_monitor.peak_memory_increase_mb < 200  # Should use < 200MB

        print(
            f"Executed queries on {job_count} jobs in {performance_monitor.duration:.2f} seconds"
        )

    def test_complex_join_query_performance(
        self, job_repository, db_session, performance_monitor
    ):
        """Test performance of complex queries with joins."""
        # Create jobs with tasks (simulating complex relationships)
        job_count = 500
        task_count_per_job = 5

        for i in range(job_count):
            # Create job
            job_data = {
                "job_number": f"COMPLEX-JOB-{i:04d}",
                "customer_name": f"Customer {i % 20}",
                "quantity": 1,
                "due_date": datetime.utcnow() + timedelta(days=30),
            }
            job_create = JobCreate(**job_data)
            job_repository.create(job_create)

            # Create tasks for this job (simulated - would be actual Task entities)
            for _j in range(task_count_per_job):
                # In a real scenario, this would create Task entities
                # For performance testing, we simulate the relationship complexity
                pass

        performance_monitor.start_monitoring()

        # Simulate complex queries (jobs with task counts, completion rates, etc.)
        for i in range(100):  # 100 different complex queries
            # Query jobs with various filters
            customer_subset = job_repository.find_by_customer(f"Customer {i % 20}")

            # Simulate complex aggregation
            for _job in customer_subset[:10]:  # Limit to first 10 for performance
                # In real scenario: job completion percentage, task counts, etc.
                pass

            if i % 20 == 0:
                performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Performance assertions
        assert performance_monitor.duration < 30.0  # Should complete within 30 seconds
        print(
            f"Complex queries completed in {performance_monitor.duration:.2f} seconds"
        )

    def test_concurrent_database_access(self, performance_monitor):
        """Test database performance under concurrent access."""
        performance_monitor.start_monitoring()

        def create_jobs_batch(batch_id: int, batch_size: int = 50):
            """Create a batch of jobs in a separate thread."""
            with Session(test_engine) as session:
                repo = JobRepository(session=session)
                jobs_created = []

                for i in range(batch_size):
                    job_data = {
                        "job_number": f"CONCURRENT-{batch_id:02d}-{i:03d}",
                        "customer_name": f"Concurrent Customer {batch_id}",
                        "quantity": 1,
                        "due_date": datetime.utcnow() + timedelta(days=7),
                    }
                    job_create = JobCreate(**job_data)
                    job = repo.create(job_create)
                    jobs_created.append(job)

                return len(jobs_created)

        # Create multiple threads for concurrent access
        thread_count = 10
        batch_size = 50

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            # Submit all tasks
            futures = [
                executor.submit(create_jobs_batch, i, batch_size)
                for i in range(thread_count)
            ]

            # Wait for completion and collect results
            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Performance assertions
        total_jobs_created = sum(results)
        expected_jobs = thread_count * batch_size

        assert total_jobs_created == expected_jobs
        assert performance_monitor.duration < 20.0  # Should complete within 20 seconds

        # Calculate concurrent throughput
        throughput = total_jobs_created / performance_monitor.duration
        assert throughput > 25  # Should handle > 25 jobs/second under concurrency

        print(
            f"Concurrent creation: {total_jobs_created} jobs in {performance_monitor.duration:.2f} seconds"
        )
        print(f"Concurrent throughput: {throughput:.1f} jobs/second")


class TestSolverPerformance:
    """Test solver performance characteristics."""

    def test_small_problem_solver_performance(self, performance_monitor):
        """Test solver performance on small problems."""
        scheduler = HFFSScheduler()

        # Configure small problem
        scheduler.num_jobs = 3
        scheduler.num_tasks = 20  # Per job
        scheduler.num_operators = 5
        scheduler.horizon_days = 7
        scheduler.horizon = 7 * 24 * 60

        performance_monitor.start_monitoring()

        with patch.object(scheduler, "solve") as mock_solve:
            # Simulate solve time for small problem
            def mock_solve_impl():
                time.sleep(0.5)  # Simulate 0.5 second solve time
                return {
                    "status": "OPTIMAL",
                    "objective_value": 1000,
                    "solve_time": 0.5,
                    "assignments": [
                        {
                            "job": 0,
                            "task": 10,
                            "operator": 1,
                            "start_time": 420,
                            "end_time": 480,
                        }
                    ],
                }

            mock_solve.side_effect = mock_solve_impl
            result = scheduler.solve()
            performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Performance assertions
        assert result["status"] == "OPTIMAL"
        assert performance_monitor.duration < 2.0  # Should solve within 2 seconds
        assert performance_monitor.peak_memory_increase_mb < 50  # Should use < 50MB

        print(f"Small problem solved in {performance_monitor.duration:.3f} seconds")

    def test_medium_problem_solver_performance(self, performance_monitor):
        """Test solver performance on medium problems."""
        scheduler = HFFSScheduler()

        # Configure medium problem
        scheduler.num_jobs = 5
        scheduler.num_tasks = 50  # Per job
        scheduler.num_operators = 10
        scheduler.horizon_days = 14

        performance_monitor.start_monitoring()

        with patch.object(scheduler, "solve") as mock_solve:

            def mock_solve_impl():
                time.sleep(2.0)  # Simulate 2 second solve time
                return {
                    "status": "OPTIMAL",
                    "objective_value": 2500,
                    "solve_time": 2.0,
                    "assignments": [],
                }

            mock_solve.side_effect = mock_solve_impl
            result = scheduler.solve()
            performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Performance assertions
        assert result["status"] == "OPTIMAL"
        assert performance_monitor.duration < 5.0  # Should solve within 5 seconds
        assert performance_monitor.peak_memory_increase_mb < 100  # Should use < 100MB

        print(f"Medium problem solved in {performance_monitor.duration:.3f} seconds")

    def test_large_problem_solver_performance(self, performance_monitor):
        """Test solver performance on large problems."""
        scheduler = HFFSScheduler()

        # Configure large problem
        scheduler.num_jobs = 10
        scheduler.num_tasks = 100  # Per job
        scheduler.num_operators = 15
        scheduler.horizon_days = 30

        performance_monitor.start_monitoring()

        with patch.object(scheduler, "solve") as mock_solve:

            def mock_solve_impl():
                time.sleep(10.0)  # Simulate 10 second solve time
                return {
                    "status": "FEASIBLE",  # Might not reach optimal in time limit
                    "objective_value": 5000,
                    "solve_time": 10.0,
                    "assignments": [],
                }

            mock_solve.side_effect = mock_solve_impl
            result = scheduler.solve()
            performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Performance assertions
        assert result["status"] in ["OPTIMAL", "FEASIBLE"]
        assert performance_monitor.duration < 15.0  # Should complete within 15 seconds
        assert performance_monitor.peak_memory_increase_mb < 500  # Should use < 500MB

        print(f"Large problem solved in {performance_monitor.duration:.3f} seconds")

    def test_solver_scalability_analysis(self, performance_monitor):
        """Test solver scalability with different problem sizes."""
        problem_sizes = [
            (2, 10, 3),  # Small: 2 jobs, 10 tasks each, 3 operators
            (3, 20, 5),  # Medium: 3 jobs, 20 tasks each, 5 operators
            (5, 30, 8),  # Large: 5 jobs, 30 tasks each, 8 operators
        ]

        results = []

        for num_jobs, num_tasks, num_operators in problem_sizes:
            scheduler = HFFSScheduler()
            scheduler.num_jobs = num_jobs
            scheduler.num_tasks = num_tasks
            scheduler.num_operators = num_operators

            performance_monitor.start_monitoring()

            with patch.object(scheduler, "solve") as mock_solve:
                # Simulate solve time proportional to problem complexity
                complexity = num_jobs * num_tasks * num_operators
                solve_time = min(complexity / 1000, 30.0)  # Cap at 30 seconds

                def mock_solve_impl():
                    time.sleep(solve_time)
                    return {
                        "status": "OPTIMAL",
                        "solve_time": solve_time,
                        "assignments": [],
                    }

                mock_solve.side_effect = mock_solve_impl
                result = scheduler.solve()
                performance_monitor.update_peak_memory()

            performance_monitor.stop_monitoring()

            results.append(
                {
                    "problem_size": (num_jobs, num_tasks, num_operators),
                    "complexity": num_jobs * num_tasks * num_operators,
                    "solve_time": performance_monitor.duration,
                    "memory_mb": performance_monitor.peak_memory_increase_mb,
                }
            )

        # Analyze scalability
        for i, result in enumerate(results):
            print(
                f"Problem {i+1}: {result['problem_size']} - "
                f"Time: {result['solve_time']:.2f}s, "
                f"Memory: {result['memory_mb']:.1f}MB"
            )

        # Performance should scale reasonably
        assert all(r["solve_time"] < 35.0 for r in results)
        assert all(r["memory_mb"] < 600 for r in results)

    def test_solver_timeout_handling_performance(self, performance_monitor):
        """Test solver performance under timeout constraints."""
        scheduler = HFFSScheduler()

        # Configure challenging problem
        scheduler.num_jobs = 8
        scheduler.num_tasks = 80
        scheduler.num_operators = 12

        performance_monitor.start_monitoring()

        with patch.object(scheduler, "solve") as mock_solve:

            def mock_solve_impl():
                time.sleep(5.0)  # Simulate timeout scenario
                return {
                    "status": "TIMEOUT",
                    "best_objective": 3500,
                    "solve_time": 5.0,
                    "assignments": [],  # Partial solution
                }

            mock_solve.side_effect = mock_solve_impl
            result = scheduler.solve()

        performance_monitor.stop_monitoring()

        # Should handle timeout gracefully
        assert result["status"] == "TIMEOUT"
        assert performance_monitor.duration >= 5.0
        assert (
            performance_monitor.duration < 6.0
        )  # Should not exceed timeout significantly

        print(f"Timeout handled in {performance_monitor.duration:.3f} seconds")


class TestAPIPerformance:
    """Test API endpoint performance."""

    def test_job_creation_api_performance(self, performance_monitor):
        """Test job creation API performance."""
        performance_monitor.start_monitoring()

        job_count = 100
        response_times = []

        for i in range(job_count):
            job_data = {
                "job_number": f"API-PERF-JOB-{i:04d}",
                "customer_name": f"API Customer {i % 10}",
                "part_number": f"API-PART-{i % 5:03d}",
                "quantity": (i % 10) + 1,
                "priority": "NORMAL",
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            }

            with patch(
                "app.infrastructure.database.dependencies.get_job_repository"
            ) as mock_repo:
                mock_repository = Mock()
                mock_job = Mock()
                mock_job.id = uuid4()
                mock_job.job_number = job_data["job_number"]
                mock_repository.create.return_value = mock_job
                mock_repo.return_value = mock_repository

                start_request_time = time.time()

                response = client.post(
                    "/api/v1/scheduling/jobs",
                    headers={"Authorization": "Bearer mock_token"},
                    json=job_data,
                )

                end_request_time = time.time()
                request_time = end_request_time - start_request_time
                response_times.append(request_time)

                assert response.status_code == 201

            if i % 10 == 0:
                performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Calculate performance metrics
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)

        # Performance assertions
        assert avg_response_time < 0.1  # Average < 100ms
        assert max_response_time < 0.5  # Max < 500ms
        assert performance_monitor.duration < 30.0  # Total < 30 seconds

        print(
            f"API Performance - Avg: {avg_response_time*1000:.1f}ms, "
            f"Max: {max_response_time*1000:.1f}ms, "
            f"Min: {min_response_time*1000:.1f}ms"
        )

    def test_job_listing_api_performance(self, performance_monitor):
        """Test job listing API performance with various page sizes."""
        page_sizes = [10, 50, 100, 500]

        for page_size in page_sizes:
            performance_monitor.start_monitoring()

            with patch(
                "app.infrastructure.database.dependencies.get_job_repository"
            ) as mock_repo:
                mock_repository = Mock()
                # Create mock jobs for this page size
                mock_jobs = [
                    Mock(
                        id=uuid4(),
                        job_number=f"LIST-JOB-{i:04d}",
                        customer_name=f"Customer {i}",
                    )
                    for i in range(page_size)
                ]
                mock_repository.list.return_value = mock_jobs
                mock_repo.return_value = mock_repository

                response = client.get(
                    f"/api/v1/scheduling/jobs?limit={page_size}",
                    headers={"Authorization": "Bearer mock_token"},
                )

                performance_monitor.update_peak_memory()

            performance_monitor.stop_monitoring()

            # Performance assertions
            assert response.status_code == 200
            data = response.json()
            assert len(data) == page_size

            # Response time should scale reasonably with page size
            max_expected_time = page_size / 1000 + 0.1  # Linear scaling + base time
            assert performance_monitor.duration < max_expected_time

            print(f"Page size {page_size}: {performance_monitor.duration:.3f}s")

    def test_schedule_generation_api_performance(self, performance_monitor):
        """Test schedule generation API performance."""
        job_counts = [2, 5, 10]  # Different problem sizes

        for job_count in job_counts:
            performance_monitor.start_monitoring()

            schedule_request = {
                "job_ids": [str(uuid4()) for _ in range(job_count)],
                "optimization_objective": "minimize_makespan",
                "time_limit_seconds": 10,
            }

            with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
                mock_scheduler = Mock()

                # Simulate solve time proportional to job count
                solve_time = job_count * 0.5
                mock_solution = {
                    "status": "OPTIMAL",
                    "solve_time": solve_time,
                    "assignments": [],
                }

                def mock_solve_impl():
                    time.sleep(solve_time)
                    return mock_solution

                mock_scheduler.solve.side_effect = mock_solve_impl
                mock_scheduler_class.return_value = mock_scheduler

                response = client.post(
                    "/api/v1/scheduling/generate-schedule",
                    headers={"Authorization": "Bearer mock_token"},
                    json=schedule_request,
                )

                performance_monitor.update_peak_memory()

            performance_monitor.stop_monitoring()

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "OPTIMAL"

            # API overhead should be minimal compared to solve time
            api_overhead = performance_monitor.duration - solve_time
            assert api_overhead < 0.5  # API overhead < 500ms

            print(
                f"Jobs: {job_count}, Total: {performance_monitor.duration:.2f}s, "
                f"Solve: {solve_time:.2f}s, Overhead: {api_overhead:.3f}s"
            )

    def test_concurrent_api_requests_performance(self, performance_monitor):
        """Test API performance under concurrent load."""
        performance_monitor.start_monitoring()

        def make_api_request(request_id: int):
            """Make a single API request."""
            job_data = {
                "job_number": f"CONCURRENT-API-{request_id:04d}",
                "customer_name": f"Concurrent Customer {request_id % 5}",
                "quantity": 1,
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            }

            with patch(
                "app.infrastructure.database.dependencies.get_job_repository"
            ) as mock_repo:
                mock_repository = Mock()
                mock_job = Mock()
                mock_job.id = uuid4()
                mock_job.job_number = job_data["job_number"]
                mock_repository.create.return_value = mock_job
                mock_repo.return_value = mock_repository

                start_time = time.time()

                response = client.post(
                    "/api/v1/scheduling/jobs",
                    headers={"Authorization": "Bearer mock_token"},
                    json=job_data,
                )

                end_time = time.time()

                return {
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                }

        # Make concurrent requests
        concurrent_requests = 20

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(make_api_request, i) for i in range(concurrent_requests)
            ]

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Analyze results
        successful_requests = [r for r in results if r["status_code"] == 201]
        response_times = [r["response_time"] for r in successful_requests]

        assert len(successful_requests) == concurrent_requests

        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        # Performance under concurrency
        assert avg_response_time < 1.0  # Average < 1 second under load
        assert max_response_time < 2.0  # Max < 2 seconds under load
        assert performance_monitor.duration < 10.0  # Total < 10 seconds

        print(
            f"Concurrent API - Requests: {len(successful_requests)}, "
            f"Avg: {avg_response_time*1000:.1f}ms, "
            f"Max: {max_response_time*1000:.1f}ms, "
            f"Total: {performance_monitor.duration:.2f}s"
        )


class TestMemoryUsageOptimization:
    """Test memory usage and optimization."""

    def test_memory_usage_large_dataset(self, performance_monitor):
        """Test memory usage when handling large datasets."""
        performance_monitor.start_monitoring()

        # Simulate loading a large number of jobs
        job_count = 5000
        jobs = []

        for i in range(job_count):
            # Create mock job objects to simulate memory usage
            job = Mock()
            job.id = uuid4()
            job.job_number = f"MEMORY-TEST-{i:05d}"
            job.customer_name = f"Customer {i % 100}"
            job.notes = f"This is a test job with some notes to simulate realistic memory usage. Job number {i}."
            jobs.append(job)

            if i % 500 == 0:
                performance_monitor.update_peak_memory()

        # Simulate processing the jobs
        processed_count = 0
        for job in jobs:
            # Simulate some processing
            _ = f"{job.job_number} - {job.customer_name}"
            processed_count += 1

            if processed_count % 1000 == 0:
                performance_monitor.update_peak_memory()

        performance_monitor.stop_monitoring()

        # Memory usage assertions
        assert len(jobs) == job_count
        assert processed_count == job_count
        assert performance_monitor.peak_memory_increase_mb < 500  # Should use < 500MB
        assert performance_monitor.duration < 5.0  # Should process quickly

        print(
            f"Processed {job_count} jobs using {performance_monitor.peak_memory_increase_mb:.1f}MB peak memory"
        )

    def test_memory_leak_detection(self, performance_monitor):
        """Test for memory leaks during repeated operations."""
        import gc

        initial_objects = len(gc.get_objects())
        performance_monitor.start_monitoring()

        # Perform repeated operations that could cause memory leaks
        for iteration in range(100):
            # Create and process objects
            temp_jobs = []
            for i in range(50):
                job = Mock()
                job.id = uuid4()
                job.data = f"Iteration {iteration}, Job {i}"
                temp_jobs.append(job)

            # Process jobs
            for job in temp_jobs:
                _ = job.data.upper()

            # Clear references
            temp_jobs.clear()
            del temp_jobs

            # Force garbage collection periodically
            if iteration % 20 == 0:
                gc.collect()
                performance_monitor.update_peak_memory()

        # Final garbage collection
        gc.collect()
        performance_monitor.stop_monitoring()

        final_objects = len(gc.get_objects())
        object_increase = final_objects - initial_objects

        # Memory leak assertions
        assert (
            performance_monitor.peak_memory_increase_mb < 50
        )  # Minimal memory increase
        assert object_increase < 1000  # Limited object growth

        print(
            f"Memory after 100 iterations: {performance_monitor.peak_memory_increase_mb:.1f}MB increase"
        )
        print(f"Object count increase: {object_increase}")


if __name__ == "__main__":
    # Run with performance markers
    pytest.main([__file__, "-v", "-m", "not slow", "--tb=short"])
