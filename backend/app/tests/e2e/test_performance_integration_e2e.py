"""
Performance Integration Tests for Large-Scale Scenarios

Tests system performance under realistic production loads including:
- Large-scale job and task creation
- Complex scheduling optimization
- Concurrent user access patterns
- Memory usage and resource efficiency
- Database performance under load
"""

import asyncio
import gc
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import psutil
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, text


class PerformanceMetrics:
    """Tracks performance metrics during tests."""

    def __init__(self):
        self.operation_times = {}
        self.memory_usage = []
        self.cpu_usage = []
        self.database_queries = []
        self.start_time = None
        self.end_time = None

    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.memory_usage.append(psutil.virtual_memory().percent)
        self.cpu_usage.append(psutil.cpu_percent(interval=None))

    def end_monitoring(self):
        """End performance monitoring."""
        self.end_time = time.time()
        self.memory_usage.append(psutil.virtual_memory().percent)
        self.cpu_usage.append(psutil.cpu_percent(interval=None))

    def record_operation(self, operation_name: str, duration: float):
        """Record operation timing."""
        if operation_name not in self.operation_times:
            self.operation_times[operation_name] = []
        self.operation_times[operation_name].append(duration)

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        total_time = (
            self.end_time - self.start_time if self.end_time and self.start_time else 0
        )

        operation_stats = {}
        for op_name, times in self.operation_times.items():
            operation_stats[op_name] = {
                "count": len(times),
                "total_time": sum(times),
                "avg_time": statistics.mean(times),
                "min_time": min(times),
                "max_time": max(times),
                "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            }

        return {
            "total_duration": total_time,
            "memory_usage": {
                "min": min(self.memory_usage) if self.memory_usage else 0,
                "max": max(self.memory_usage) if self.memory_usage else 0,
                "avg": statistics.mean(self.memory_usage) if self.memory_usage else 0,
            },
            "cpu_usage": {
                "min": min(self.cpu_usage) if self.cpu_usage else 0,
                "max": max(self.cpu_usage) if self.cpu_usage else 0,
                "avg": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
            },
            "operations": operation_stats,
            "database_queries": len(self.database_queries),
        }


class LoadTestDataGenerator:
    """Generates realistic load test data."""

    @staticmethod
    def generate_job_batch(batch_size: int, batch_id: str) -> list[dict[str, Any]]:
        """Generate a batch of realistic job data."""
        jobs = []

        priorities = ["LOW", "NORMAL", "HIGH", "URGENT"]
        customers = [
            "Automotive Corp",
            "Aerospace Inc",
            "Electronics Ltd",
            "Medical Devices Co",
            "Defense Contractor",
            "Tech Startup",
        ]

        for i in range(batch_size):
            job = {
                "job_number": f"{batch_id}-{i+1:04d}",
                "customer_name": customers[i % len(customers)],
                "part_number": f"PART-{batch_id}-{i+1:04d}",
                "quantity": (i % 50) + 1,  # 1-50 parts
                "priority": priorities[i % len(priorities)],
                "due_date": (
                    datetime.utcnow() + timedelta(days=1 + (i % 30))
                ).isoformat(),
                "notes": f"Load test job {i+1} in batch {batch_id}",
            }
            jobs.append(job)

        return jobs

    @staticmethod
    def generate_task_batch(
        job_count: int, tasks_per_job: int
    ) -> list[list[dict[str, Any]]]:
        """Generate batches of tasks for jobs."""
        skill_codes = [
            "MACHINING",
            "ASSEMBLY",
            "WELDING",
            "QUALITY_CHECK",
            "PACKAGING",
            "INSPECTION",
        ]
        skill_levels = ["BASIC", "INTERMEDIATE", "ADVANCED", "EXPERT"]

        job_tasks = []

        for job_idx in range(job_count):
            job_task_list = []

            for task_idx in range(tasks_per_job):
                task = {
                    "operation_id": str(uuid4()),
                    "sequence_in_job": (task_idx + 1) * 10,
                    "planned_duration_minutes": 60 + (task_idx * 30) + (job_idx % 60),
                    "setup_duration_minutes": 15 + (task_idx * 5),
                    "skill_requirements": [
                        {
                            "skill_code": skill_codes[task_idx % len(skill_codes)],
                            "required_level": skill_levels[
                                task_idx % len(skill_levels)
                            ],
                            "is_mandatory": task_idx < 2,  # First 2 tasks mandatory
                        }
                    ],
                }
                job_task_list.append(task)

            job_tasks.append(job_task_list)

        return job_tasks


@pytest.fixture
def performance_metrics():
    """Provide performance metrics tracker."""
    return PerformanceMetrics()


@pytest.fixture
def load_data_generator():
    """Provide load test data generator."""
    return LoadTestDataGenerator()


@pytest.mark.e2e
@pytest.mark.performance
class TestPerformanceIntegrationE2E:
    """Performance tests for large-scale production scenarios."""

    async def test_large_scale_job_creation_performance(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        performance_metrics: PerformanceMetrics,
        load_data_generator: LoadTestDataGenerator,
    ):
        """Test performance of creating large numbers of jobs."""

        performance_metrics.start_monitoring()

        # Test parameters
        job_batches = 5
        jobs_per_batch = 50
        total_jobs = job_batches * jobs_per_batch

        created_jobs = []

        # Create jobs in batches
        for batch_idx in range(job_batches):
            batch_id = f"PERF-BATCH-{batch_idx+1}"
            job_batch = load_data_generator.generate_job_batch(jobs_per_batch, batch_id)

            batch_start_time = time.time()

            # Create jobs in batch
            batch_jobs = []
            for job_data in job_batch:
                job_start_time = time.time()

                response = client.post(
                    "/api/v1/jobs/", json=job_data, headers=auth_headers
                )

                job_creation_time = time.time() - job_start_time
                performance_metrics.record_operation("job_creation", job_creation_time)

                if response.status_code == 201:
                    job = response.json()
                    batch_jobs.append(job)
                    created_jobs.append(job)
                else:
                    # Track failures but continue test
                    performance_metrics.record_operation(
                        "job_creation_failed", job_creation_time
                    )

            batch_duration = time.time() - batch_start_time
            performance_metrics.record_operation("batch_creation", batch_duration)

            # Monitor memory after each batch
            current_memory = psutil.virtual_memory().percent
            performance_metrics.memory_usage.append(current_memory)

            print(
                f"Batch {batch_idx+1}: Created {len(batch_jobs)}/{jobs_per_batch} jobs in {batch_duration:.2f}s"
            )

        performance_metrics.end_monitoring()

        # Verify creation results
        assert (
            len(created_jobs) >= total_jobs * 0.95
        ), "Should create at least 95% of jobs successfully"

        # Performance assertions
        stats = performance_metrics.get_summary()

        # Job creation should average under 0.5 seconds per job
        avg_job_time = stats["operations"]["job_creation"]["avg_time"]
        assert (
            avg_job_time < 0.5
        ), f"Average job creation time {avg_job_time:.3f}s exceeds threshold"

        # Batch creation should scale linearly
        avg_batch_time = stats["operations"]["batch_creation"]["avg_time"]
        expected_max_batch_time = jobs_per_batch * 0.5  # Allow 0.5s per job
        assert (
            avg_batch_time < expected_max_batch_time
        ), f"Batch creation time {avg_batch_time:.2f}s too slow"

        # Memory usage should not grow excessively
        memory_growth = max(stats["memory_usage"]["max"]) - min(
            stats["memory_usage"]["min"]
        )
        assert memory_growth < 20, f"Memory usage grew by {memory_growth}% during test"

        print(f"Performance Summary: {stats}")

        return created_jobs

    async def test_complex_scheduling_optimization_performance(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        performance_metrics: PerformanceMetrics,
        load_data_generator: LoadTestDataGenerator,
    ):
        """Test optimization performance with complex scheduling scenarios."""

        performance_metrics.start_monitoring()

        # Create complex dataset for optimization
        job_count = 30
        tasks_per_job = 4

        # Generate and create jobs
        job_batch = load_data_generator.generate_job_batch(job_count, "OPT-PERF")
        task_batches = load_data_generator.generate_task_batch(job_count, tasks_per_job)

        created_jobs = []

        job_creation_start = time.time()

        for i, job_data in enumerate(job_batch):
            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201

            job = response.json()
            created_jobs.append(job)
            job_id = job["id"]

            # Add tasks to job
            for task_data in task_batches[i]:
                response = client.post(
                    f"/api/v1/jobs/{job_id}/tasks/",
                    json=task_data,
                    headers=auth_headers,
                )
                assert response.status_code == 201

            # Release job for scheduling
            response = client.patch(
                f"/api/v1/jobs/{job_id}/status",
                json={"status": "RELEASED"},
                headers=auth_headers,
            )
            assert response.status_code == 200

        job_creation_time = time.time() - job_creation_start
        performance_metrics.record_operation("dataset_creation", job_creation_time)

        # Test different optimization strategies
        optimization_strategies = [
            {
                "name": "Makespan Optimization",
                "parameters": {
                    "minimize_makespan": True,
                    "minimize_tardiness": False,
                    "resource_utilization_weight": 0.3,
                    "makespan_weight": 0.7,
                },
            },
            {
                "name": "Balanced Optimization",
                "parameters": {
                    "minimize_makespan": True,
                    "minimize_tardiness": True,
                    "resource_utilization_weight": 0.4,
                    "priority_weight": 0.3,
                    "makespan_weight": 0.15,
                    "tardiness_weight": 0.15,
                },
            },
            {
                "name": "Resource-Focused Optimization",
                "parameters": {
                    "minimize_makespan": False,
                    "minimize_tardiness": True,
                    "resource_utilization_weight": 0.7,
                    "tardiness_weight": 0.3,
                },
            },
        ]

        optimization_results = []

        for strategy in optimization_strategies:
            strategy_name = strategy["name"]

            schedule_data = {
                "name": f"Performance Test - {strategy_name}",
                "job_ids": [job["id"] for job in created_jobs],
                "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "end_time": (datetime.utcnow() + timedelta(days=20)).isoformat(),
                "optimization_parameters": strategy["parameters"],
                "constraints": {
                    "max_operators_per_task": 3,
                    "min_setup_time_minutes": 15,
                    "max_daily_hours": 10,
                    "required_skills_matching": True,
                },
            }

            optimization_start = time.time()

            response = client.post(
                "/api/v1/schedules/optimize", json=schedule_data, headers=auth_headers
            )

            optimization_time = time.time() - optimization_start
            performance_metrics.record_operation(
                f"optimization_{strategy_name}", optimization_time
            )

            if response.status_code == 201:
                result = response.json()
                optimization_results.append(
                    {
                        "strategy": strategy_name,
                        "optimization_time": optimization_time,
                        "result": result,
                        "schedule_id": result["schedule"]["id"],
                    }
                )

                # Track memory usage after optimization
                performance_metrics.memory_usage.append(psutil.virtual_memory().percent)

                print(f"{strategy_name}: Optimized in {optimization_time:.2f}s")
            else:
                print(
                    f"{strategy_name}: Optimization failed with status {response.status_code}"
                )

        performance_metrics.end_monitoring()

        # Performance assertions
        assert (
            len(optimization_results) >= 2
        ), "At least 2 optimization strategies should succeed"

        # Each optimization should complete within reasonable time
        for result in optimization_results:
            opt_time = result["optimization_time"]
            assert (
                opt_time < 30.0
            ), f"{result['strategy']} took {opt_time:.2f}s (>30s threshold)"

        # Memory usage should be controlled
        stats = performance_metrics.get_summary()
        max_memory = stats["memory_usage"]["max"]
        assert max_memory < 80, f"Memory usage {max_memory}% exceeds 80% threshold"

        print(f"Optimization Performance Summary: {stats}")

        return optimization_results

    async def test_concurrent_user_load_performance(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        performance_metrics: PerformanceMetrics,
    ):
        """Test system performance under concurrent user load."""

        performance_metrics.start_monitoring()

        # Create base dataset for concurrent operations
        base_jobs = []
        for i in range(10):
            job_data = {
                "job_number": f"CONCURRENT-BASE-{i+1:03d}",
                "customer_name": f"Concurrent Customer {i+1}",
                "due_date": (datetime.utcnow() + timedelta(days=5 + i)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            if response.status_code == 201:
                job = response.json()
                base_jobs.append(job)

        # Define concurrent operations
        def concurrent_job_creation(worker_id: int, job_count: int):
            """Worker function for concurrent job creation."""
            results = {"created": 0, "failed": 0, "times": []}

            for i in range(job_count):
                job_data = {
                    "job_number": f"WORKER-{worker_id}-{i+1:03d}",
                    "customer_name": f"Worker {worker_id} Customer {i+1}",
                    "due_date": (datetime.utcnow() + timedelta(days=3 + i)).isoformat(),
                }

                start_time = time.time()
                try:
                    response = client.post(
                        "/api/v1/jobs/", json=job_data, headers=auth_headers
                    )
                    duration = time.time() - start_time
                    results["times"].append(duration)

                    if response.status_code == 201:
                        results["created"] += 1
                    else:
                        results["failed"] += 1

                except Exception:
                    results["failed"] += 1
                    results["times"].append(time.time() - start_time)

            return results

        def concurrent_job_queries(worker_id: int, query_count: int):
            """Worker function for concurrent job queries."""
            results = {"successful": 0, "failed": 0, "times": []}

            for i in range(query_count):
                if not base_jobs:
                    continue

                job = base_jobs[i % len(base_jobs)]
                job_id = job["id"]

                start_time = time.time()
                try:
                    response = client.get(
                        f"/api/v1/jobs/{job_id}", headers=auth_headers
                    )
                    duration = time.time() - start_time
                    results["times"].append(duration)

                    if response.status_code == 200:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1

                except Exception:
                    results["failed"] += 1
                    results["times"].append(time.time() - start_time)

            return results

        def concurrent_status_updates(worker_id: int, update_count: int):
            """Worker function for concurrent status updates."""
            results = {"updated": 0, "failed": 0, "times": []}

            for i in range(update_count):
                if not base_jobs:
                    continue

                job = base_jobs[i % len(base_jobs)]
                job_id = job["id"]

                update_data = {
                    "notes": f"Updated by worker {worker_id} at {datetime.now()}"
                }

                start_time = time.time()
                try:
                    response = client.patch(
                        f"/api/v1/jobs/{job_id}", json=update_data, headers=auth_headers
                    )
                    duration = time.time() - start_time
                    results["times"].append(duration)

                    if response.status_code == 200:
                        results["updated"] += 1
                    else:
                        results["failed"] += 1

                except Exception:
                    results["failed"] += 1
                    results["times"].append(time.time() - start_time)

            return results

        # Execute concurrent load test
        num_workers = 8
        operations_per_worker = 15

        load_test_start = time.time()

        with ThreadPoolExecutor(max_workers=num_workers * 3) as executor:
            # Submit concurrent tasks
            futures = []

            # Job creation workers
            for worker_id in range(num_workers):
                future = executor.submit(
                    concurrent_job_creation, worker_id, operations_per_worker
                )
                futures.append(("creation", worker_id, future))

            # Query workers
            for worker_id in range(num_workers):
                future = executor.submit(
                    concurrent_job_queries, worker_id, operations_per_worker * 2
                )
                futures.append(("query", worker_id, future))

            # Update workers
            for worker_id in range(num_workers // 2):
                future = executor.submit(
                    concurrent_status_updates, worker_id, operations_per_worker
                )
                futures.append(("update", worker_id, future))

            # Collect results
            all_results = {}
            for operation_type, worker_id, future in futures:
                try:
                    result = future.result(timeout=60)  # 60 second timeout
                    if operation_type not in all_results:
                        all_results[operation_type] = []
                    all_results[operation_type].append(result)

                    # Record operation times
                    for op_time in result.get("times", []):
                        performance_metrics.record_operation(
                            f"concurrent_{operation_type}", op_time
                        )

                except Exception as e:
                    print(f"Worker {worker_id} ({operation_type}) failed: {e}")

        load_test_duration = time.time() - load_test_start
        performance_metrics.record_operation("full_load_test", load_test_duration)

        performance_metrics.end_monitoring()

        # Analyze results
        total_operations = 0
        successful_operations = 0

        for operation_type, results_list in all_results.items():
            for result in results_list:
                if operation_type == "creation":
                    total_operations += result["created"] + result["failed"]
                    successful_operations += result["created"]
                elif operation_type == "query":
                    total_operations += result["successful"] + result["failed"]
                    successful_operations += result["successful"]
                elif operation_type == "update":
                    total_operations += result["updated"] + result["failed"]
                    successful_operations += result["updated"]

        success_rate = (
            (successful_operations / total_operations) * 100
            if total_operations > 0
            else 0
        )

        # Performance assertions
        assert (
            success_rate >= 85
        ), f"Success rate {success_rate:.1f}% below 85% threshold"
        assert (
            load_test_duration < 120
        ), f"Load test took {load_test_duration:.2f}s (>120s threshold)"

        # Response time assertions
        stats = performance_metrics.get_summary()
        for operation_type in [
            "concurrent_creation",
            "concurrent_query",
            "concurrent_update",
        ]:
            if operation_type in stats["operations"]:
                avg_time = stats["operations"][operation_type]["avg_time"]
                max_time = stats["operations"][operation_type]["max_time"]

                assert (
                    avg_time < 2.0
                ), f"{operation_type} avg time {avg_time:.3f}s exceeds 2s"
                assert (
                    max_time < 10.0
                ), f"{operation_type} max time {max_time:.3f}s exceeds 10s"

        print(
            f"Load Test Results: {success_rate:.1f}% success rate, {total_operations} total operations"
        )
        print(f"Load Test Performance: {stats}")

        return all_results

    async def test_memory_usage_under_load(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        performance_metrics: PerformanceMetrics,
    ):
        """Test memory usage patterns under sustained load."""

        performance_metrics.start_monitoring()

        # Monitor initial memory
        initial_memory = psutil.virtual_memory().percent
        peak_memory = initial_memory

        # Create sustained load with memory monitoring
        load_iterations = 10
        jobs_per_iteration = 25

        for iteration in range(load_iterations):
            iteration_start = time.time()

            # Create jobs
            for i in range(jobs_per_iteration):
                job_data = {
                    "job_number": f"MEMORY-{iteration+1:02d}-{i+1:03d}",
                    "customer_name": f"Memory Test Customer {i+1}",
                    "quantity": (i % 20) + 1,
                    "due_date": (datetime.utcnow() + timedelta(days=2 + i)).isoformat(),
                }

                response = client.post(
                    "/api/v1/jobs/", json=job_data, headers=auth_headers
                )
                if response.status_code != 201:
                    print(f"Job creation failed in iteration {iteration+1}, job {i+1}")

            # Monitor memory after each iteration
            current_memory = psutil.virtual_memory().percent
            performance_metrics.memory_usage.append(current_memory)
            peak_memory = max(peak_memory, current_memory)

            # Force garbage collection to test memory cleanup
            gc.collect()
            post_gc_memory = psutil.virtual_memory().percent
            performance_metrics.memory_usage.append(post_gc_memory)

            iteration_time = time.time() - iteration_start
            performance_metrics.record_operation(
                "memory_test_iteration", iteration_time
            )

            print(
                f"Iteration {iteration+1}: Memory {current_memory:.1f}% -> {post_gc_memory:.1f}% after GC"
            )

            # Small delay between iterations
            await asyncio.sleep(0.5)

        performance_metrics.end_monitoring()

        # Memory analysis
        final_memory = psutil.virtual_memory().percent
        memory_growth = final_memory - initial_memory
        peak_growth = peak_memory - initial_memory

        stats = performance_metrics.get_summary()

        # Memory assertions
        assert (
            memory_growth < 15
        ), f"Memory grew by {memory_growth:.1f}% (>15% threshold)"
        assert (
            peak_growth < 25
        ), f"Peak memory growth {peak_growth:.1f}% (>25% threshold)"

        # Ensure garbage collection is effective
        memory_after_gc = [
            performance_metrics.memory_usage[i]
            for i in range(1, len(performance_metrics.memory_usage), 2)
        ]
        memory_before_gc = [
            performance_metrics.memory_usage[i]
            for i in range(0, len(performance_metrics.memory_usage), 2)
        ]

        if len(memory_after_gc) > 0 and len(memory_before_gc) > 0:
            avg_gc_reduction = statistics.mean(
                [
                    before - after
                    for before, after in zip(
                        memory_before_gc[1:], memory_after_gc, strict=False
                    )
                ]
            )
            assert (
                avg_gc_reduction >= 0
            ), "Garbage collection should reduce or maintain memory usage"

        print(
            f"Memory Test Results: {memory_growth:.1f}% growth, {peak_growth:.1f}% peak growth"
        )
        print(f"Memory Performance: {stats}")

    async def test_database_performance_under_load(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        performance_metrics: PerformanceMetrics,
    ):
        """Test database performance under high query load."""

        performance_metrics.start_monitoring()

        # Create test dataset
        test_jobs = []
        for i in range(100):
            job_data = {
                "job_number": f"DB-PERF-{i+1:03d}",
                "customer_name": f"DB Performance Customer {i+1}",
                "due_date": (
                    datetime.utcnow() + timedelta(days=1 + (i % 30))
                ).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            if response.status_code == 201:
                job = response.json()
                test_jobs.append(job)

        print(f"Created {len(test_jobs)} test jobs for database performance testing")

        # Test different query patterns
        query_patterns = [
            {
                "name": "individual_job_queries",
                "operation": lambda: client.get(
                    f"/api/v1/jobs/{test_jobs[0]['id']}", headers=auth_headers
                ),
                "iterations": 100,
            },
            {
                "name": "job_list_queries",
                "operation": lambda: client.get("/api/v1/jobs/", headers=auth_headers),
                "iterations": 50,
            },
            {
                "name": "filtered_job_queries",
                "operation": lambda: client.get(
                    "/api/v1/jobs/?status=PLANNED&limit=20", headers=auth_headers
                ),
                "iterations": 30,
            },
            {
                "name": "job_status_updates",
                "operation": lambda: client.patch(
                    f"/api/v1/jobs/{test_jobs[len(test_jobs)//2]['id']}",
                    json={"notes": f"Updated at {time.time()}"},
                    headers=auth_headers,
                ),
                "iterations": 20,
            },
        ]

        # Execute query patterns
        for pattern in query_patterns:
            pattern_name = pattern["name"]
            operation = pattern["operation"]
            iterations = pattern["iterations"]

            pattern_start_time = time.time()
            successful_queries = 0

            for i in range(iterations):
                query_start_time = time.time()

                try:
                    response = operation()
                    query_time = time.time() - query_start_time
                    performance_metrics.record_operation(pattern_name, query_time)

                    if response.status_code == 200:
                        successful_queries += 1

                except Exception:
                    query_time = time.time() - query_start_time
                    performance_metrics.record_operation(
                        f"{pattern_name}_failed", query_time
                    )

            pattern_duration = time.time() - pattern_start_time
            success_rate = (successful_queries / iterations) * 100

            print(
                f"{pattern_name}: {success_rate:.1f}% success rate in {pattern_duration:.2f}s"
            )

        # Test database connection pool under load
        concurrent_db_queries = 20

        def execute_db_query(query_id: int):
            """Execute direct database query."""
            try:
                query_start = time.time()

                # Simple query to test connection pool
                result = db.execute(text("SELECT COUNT(*) FROM jobs"))
                count = result.scalar()

                query_time = time.time() - query_start
                return {
                    "query_id": query_id,
                    "success": True,
                    "time": query_time,
                    "count": count,
                }

            except Exception as e:
                query_time = time.time() - query_start
                return {
                    "query_id": query_id,
                    "success": False,
                    "time": query_time,
                    "error": str(e),
                }

        # Execute concurrent database queries
        db_test_start = time.time()

        with ThreadPoolExecutor(max_workers=concurrent_db_queries) as executor:
            db_futures = [
                executor.submit(execute_db_query, i)
                for i in range(concurrent_db_queries)
            ]
            db_results = [future.result(timeout=10) for future in db_futures]

        time.time() - db_test_start

        # Analyze database results
        successful_db_queries = len([r for r in db_results if r["success"]])
        len([r for r in db_results if not r["success"]])

        if successful_db_queries > 0:
            db_query_times = [r["time"] for r in db_results if r["success"]]
            avg_db_time = statistics.mean(db_query_times)
            max_db_time = max(db_query_times)

            for db_time in db_query_times:
                performance_metrics.record_operation("direct_db_query", db_time)
        else:
            avg_db_time = 0
            max_db_time = 0

        performance_metrics.end_monitoring()

        # Database performance assertions
        stats = performance_metrics.get_summary()

        # API query performance
        for pattern in query_patterns:
            pattern_name = pattern["name"]
            if pattern_name in stats["operations"]:
                avg_time = stats["operations"][pattern_name]["avg_time"]
                assert (
                    avg_time < 1.0
                ), f"{pattern_name} avg time {avg_time:.3f}s exceeds 1s"

        # Database connection performance
        db_success_rate = (successful_db_queries / concurrent_db_queries) * 100
        assert (
            db_success_rate >= 90
        ), f"DB success rate {db_success_rate:.1f}% below 90%"

        if avg_db_time > 0:
            assert (
                avg_db_time < 0.1
            ), f"Direct DB query avg time {avg_db_time:.3f}s exceeds 0.1s"
            assert (
                max_db_time < 1.0
            ), f"Direct DB query max time {max_db_time:.3f}s exceeds 1s"

        print(
            f"Database Performance: API queries successful, DB success rate {db_success_rate:.1f}%"
        )
        print(f"Database Stats: {stats}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
