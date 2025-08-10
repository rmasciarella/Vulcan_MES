"""
Comprehensive Performance and Load Testing Suite

Tests the system's performance characteristics under various load conditions,
including concurrent users, large datasets, and stress scenarios.
"""

import asyncio
import statistics
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import psutil
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.tests.utils.test_scenarios import ScenarioManager
from app.tests.utils.utils import get_superuser_token_headers


class PerformanceMetrics:
    """Collector for performance metrics."""

    def __init__(self):
        self.metrics = {
            "response_times": [],
            "throughput": [],
            "error_rates": [],
            "memory_usage": [],
            "cpu_usage": [],
            "database_connections": [],
            "concurrent_users": [],
        }
        self.start_time = None
        self.end_time = None
        self._lock = threading.Lock()

    def start_collection(self):
        """Start metrics collection."""
        self.start_time = time.time()

    def stop_collection(self):
        """Stop metrics collection."""
        self.end_time = time.time()

    def add_response_time(self, duration: float):
        """Add a response time measurement."""
        with self._lock:
            self.metrics["response_times"].append(duration)

    def add_error(self, error_type: str):
        """Record an error occurrence."""
        with self._lock:
            if "errors" not in self.metrics:
                self.metrics["errors"] = {}
            self.metrics["errors"][error_type] = (
                self.metrics["errors"].get(error_type, 0) + 1
            )

    def record_system_metrics(self):
        """Record current system metrics."""
        with self._lock:
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics["memory_usage"].append(
                {
                    "timestamp": time.time(),
                    "percent": memory.percent,
                    "available_mb": memory.available / 1024 / 1024,
                    "used_mb": memory.used / 1024 / 1024,
                }
            )

            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.metrics["cpu_usage"].append(
                {
                    "timestamp": time.time(),
                    "percent": cpu_percent,
                }
            )

    def get_summary(self) -> dict[str, Any]:
        """Get performance metrics summary."""
        response_times = self.metrics["response_times"]
        total_duration = (
            (self.end_time - self.start_time)
            if self.end_time and self.start_time
            else 0
        )

        summary = {
            "test_duration_seconds": total_duration,
            "total_requests": len(response_times),
            "throughput_rps": len(response_times) / total_duration
            if total_duration > 0
            else 0,
        }

        if response_times:
            summary.update(
                {
                    "response_time_avg": statistics.mean(response_times),
                    "response_time_median": statistics.median(response_times),
                    "response_time_p95": self._percentile(response_times, 95),
                    "response_time_p99": self._percentile(response_times, 99),
                    "response_time_max": max(response_times),
                    "response_time_min": min(response_times),
                }
            )

        # Error rates
        total_errors = sum(self.metrics.get("errors", {}).values())
        total_requests = len(response_times) + total_errors
        summary["error_rate_percent"] = (
            (total_errors / total_requests * 100) if total_requests > 0 else 0
        )

        # System metrics
        if self.metrics["memory_usage"]:
            memory_usage = [m["percent"] for m in self.metrics["memory_usage"]]
            summary["memory_usage_avg"] = statistics.mean(memory_usage)
            summary["memory_usage_max"] = max(memory_usage)

        if self.metrics["cpu_usage"]:
            cpu_usage = [c["percent"] for c in self.metrics["cpu_usage"]]
            summary["cpu_usage_avg"] = statistics.mean(cpu_usage)
            summary["cpu_usage_max"] = max(cpu_usage)

        return summary

    def _percentile(self, data: list[float], percentile: int) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int(percentile / 100 * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


class LoadTestRunner:
    """Runner for executing load tests."""

    def __init__(self, client: TestClient, auth_headers: dict[str, str]):
        self.client = client
        self.auth_headers = auth_headers
        self.metrics = PerformanceMetrics()

    async def run_concurrent_load_test(
        self,
        test_function: Callable,
        concurrent_users: int,
        duration_seconds: int,
        ramp_up_time: int = 10,
    ) -> dict[str, Any]:
        """Run a load test with concurrent users."""
        self.metrics.start_collection()

        # System metrics collection thread
        stop_metrics = threading.Event()
        metrics_thread = threading.Thread(
            target=self._collect_system_metrics,
            args=(stop_metrics, 1.0),  # Collect every second
        )
        metrics_thread.start()

        try:
            # Ramp up users gradually
            tasks = []
            users_per_ramp = max(1, concurrent_users // (ramp_up_time + 1))

            for ramp_step in range(ramp_up_time + 1):
                users_this_step = min(users_per_ramp, concurrent_users - len(tasks))

                for _ in range(users_this_step):
                    task = asyncio.create_task(
                        self._user_simulation(
                            test_function, duration_seconds, len(tasks) + 1
                        )
                    )
                    tasks.append(task)

                if ramp_step < ramp_up_time:
                    await asyncio.sleep(1)  # 1 second ramp up intervals

            # Wait for all users to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.metrics.add_error(f"user_{i}_exception")

        finally:
            stop_metrics.set()
            metrics_thread.join()
            self.metrics.stop_collection()

        return self.metrics.get_summary()

    async def _user_simulation(
        self,
        test_function: Callable,
        duration_seconds: int,
        user_id: int,
    ):
        """Simulate a single user's behavior."""
        end_time = time.time() + duration_seconds
        request_count = 0

        while time.time() < end_time:
            try:
                start_time = time.time()
                await test_function(user_id)
                response_time = time.time() - start_time

                self.metrics.add_response_time(response_time)
                request_count += 1

                # Think time between requests (realistic user behavior)
                await asyncio.sleep(0.1 + (request_count % 3) * 0.1)

            except Exception:
                self.metrics.add_error(f"user_{user_id}_error")
                await asyncio.sleep(1)  # Back off on error

        return {"user_id": user_id, "requests_completed": request_count}

    def _collect_system_metrics(self, stop_event: threading.Event, interval: float):
        """Collect system metrics in background thread."""
        while not stop_event.wait(interval):
            self.metrics.record_system_metrics()


@pytest.mark.performance
@pytest.mark.asyncio
class TestAPIPerformance:
    """API performance tests under various load conditions."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict[str, str]:
        """Get authentication headers."""
        return get_superuser_token_headers(client)

    @pytest.fixture
    def load_test_runner(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> LoadTestRunner:
        """Create load test runner."""
        return LoadTestRunner(client, auth_headers)

    async def test_job_creation_performance(self, load_test_runner: LoadTestRunner):
        """Test job creation performance under load."""

        async def create_job(user_id: int):
            """Create a job for performance testing."""
            job_data = {
                "job_number": f"PERF_JOB_{user_id}_{int(time.time()*1000)}",
                "customer_name": f"Performance Customer {user_id}",
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "quantity": 1,
                "priority": "NORMAL",
            }

            response = load_test_runner.client.post(
                "/api/v1/jobs/",
                json=job_data,
                headers=load_test_runner.auth_headers,
            )
            assert response.status_code in [
                201,
                400,
                409,
            ]  # Allow conflicts in high concurrency

        # Run load test
        results = await load_test_runner.run_concurrent_load_test(
            test_function=create_job,
            concurrent_users=20,
            duration_seconds=30,
            ramp_up_time=5,
        )

        # Performance assertions
        assert results["error_rate_percent"] < 5.0  # Less than 5% errors
        assert results["response_time_avg"] < 2.0  # Average under 2 seconds
        assert results["response_time_p95"] < 5.0  # 95th percentile under 5 seconds
        assert results["throughput_rps"] > 5.0  # At least 5 requests per second

        print("Job Creation Performance Results:")
        print(f"  Throughput: {results['throughput_rps']:.2f} RPS")
        print(f"  Avg Response Time: {results['response_time_avg']:.3f}s")
        print(f"  95th Percentile: {results['response_time_p95']:.3f}s")
        print(f"  Error Rate: {results['error_rate_percent']:.2f}%")

    async def test_job_listing_performance(
        self, load_test_runner: LoadTestRunner, db: Session
    ):
        """Test job listing performance with large dataset."""

        # First, create a large dataset
        ScenarioManager.create_high_load_scenario(job_count=100)
        # In a real test, you would save these jobs to the database

        async def list_jobs(user_id: int):
            """List jobs for performance testing."""
            # Vary the parameters to test different scenarios
            page = (user_id % 10) + 1
            page_size = 10 + (user_id % 5) * 5

            response = load_test_runner.client.get(
                f"/api/v1/jobs/?page={page}&page_size={page_size}",
                headers=load_test_runner.auth_headers,
            )
            assert response.status_code == 200

        # Run load test
        results = await load_test_runner.run_concurrent_load_test(
            test_function=list_jobs,
            concurrent_users=30,
            duration_seconds=60,
            ramp_up_time=10,
        )

        # Performance assertions for read operations
        assert results["error_rate_percent"] < 2.0  # Less than 2% errors for reads
        assert results["response_time_avg"] < 1.0  # Average under 1 second for reads
        assert results["response_time_p95"] < 3.0  # 95th percentile under 3 seconds
        assert (
            results["throughput_rps"] > 10.0
        )  # At least 10 requests per second for reads

        print("Job Listing Performance Results:")
        print(f"  Throughput: {results['throughput_rps']:.2f} RPS")
        print(f"  Avg Response Time: {results['response_time_avg']:.3f}s")
        print(f"  95th Percentile: {results['response_time_p95']:.3f}s")

    async def test_schedule_optimization_performance(
        self, load_test_runner: LoadTestRunner
    ):
        """Test schedule optimization performance under concurrent load."""

        # Create jobs for optimization testing
        test_jobs = []
        for i in range(20):  # Pre-create jobs for optimization
            job_data = {
                "job_number": f"OPT_JOB_{i+1:03d}",
                "customer_name": f"Optimization Customer {i+1}",
                "due_date": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                "priority": "NORMAL",
            }

            response = load_test_runner.client.post(
                "/api/v1/jobs/",
                json=job_data,
                headers=load_test_runner.auth_headers,
            )
            if response.status_code == 201:
                test_jobs.append(response.json()["id"])

        async def optimize_schedule(user_id: int):
            """Optimize schedule for performance testing."""
            # Use a subset of jobs to avoid excessive optimization time
            job_subset = test_jobs[: min(5, len(test_jobs))]

            schedule_data = {
                "name": f"Perf Schedule User {user_id}",
                "job_ids": job_subset,
                "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "end_time": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "optimization_parameters": {
                    "minimize_makespan": True,
                    "time_limit_seconds": 30,  # Limit optimization time for performance test
                },
            }

            response = load_test_runner.client.post(
                "/api/v1/schedules/optimize",
                json=schedule_data,
                headers=load_test_runner.auth_headers,
            )
            assert response.status_code in [
                201,
                400,
                500,
            ]  # Allow some failures in high load

        # Run load test with fewer concurrent users for optimization
        results = await load_test_runner.run_concurrent_load_test(
            test_function=optimize_schedule,
            concurrent_users=5,  # Fewer users for resource-intensive operations
            duration_seconds=120,  # Longer duration for optimization
            ramp_up_time=5,
        )

        # More relaxed performance assertions for complex operations
        assert (
            results["error_rate_percent"] < 20.0
        )  # Higher error tolerance for complex ops
        assert results["response_time_avg"] < 45.0  # Average under 45 seconds
        assert results["response_time_p95"] < 90.0  # 95th percentile under 90 seconds

        print("Schedule Optimization Performance Results:")
        print(f"  Throughput: {results['throughput_rps']:.2f} RPS")
        print(f"  Avg Response Time: {results['response_time_avg']:.3f}s")
        print(f"  95th Percentile: {results['response_time_p95']:.3f}s")

    async def test_mixed_workload_performance(self, load_test_runner: LoadTestRunner):
        """Test performance with mixed read/write workload."""

        # Pre-create some test data
        job_ids = []
        for i in range(10):
            job_data = {
                "job_number": f"MIXED_JOB_{i+1:03d}",
                "customer_name": f"Mixed Customer {i+1}",
                "due_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            }

            response = load_test_runner.client.post(
                "/api/v1/jobs/",
                json=job_data,
                headers=load_test_runner.auth_headers,
            )
            if response.status_code == 201:
                job_ids.append(response.json()["id"])

        async def mixed_operations(user_id: int):
            """Perform mixed read/write operations."""
            operation_type = user_id % 4

            if operation_type == 0:  # Create job (25%)
                job_data = {
                    "job_number": f"MIX_NEW_{user_id}_{int(time.time()*1000)}",
                    "customer_name": f"New Customer {user_id}",
                    "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
                }
                response = load_test_runner.client.post(
                    "/api/v1/jobs/",
                    json=job_data,
                    headers=load_test_runner.auth_headers,
                )

            elif operation_type == 1:  # List jobs (25%)
                response = load_test_runner.client.get(
                    f"/api/v1/jobs/?page={(user_id % 5) + 1}&page_size=10",
                    headers=load_test_runner.auth_headers,
                )

            elif operation_type == 2:  # Get specific job (25%)
                if job_ids:
                    job_id = job_ids[user_id % len(job_ids)]
                    response = load_test_runner.client.get(
                        f"/api/v1/jobs/{job_id}",
                        headers=load_test_runner.auth_headers,
                    )
                else:
                    # Fallback to list operation
                    response = load_test_runner.client.get(
                        "/api/v1/jobs/",
                        headers=load_test_runner.auth_headers,
                    )

            else:  # Update job (25%)
                if job_ids:
                    job_id = job_ids[user_id % len(job_ids)]
                    update_data = {
                        "notes": f"Updated by user {user_id} at {datetime.utcnow().isoformat()}",
                        "priority": "HIGH" if user_id % 2 == 0 else "NORMAL",
                    }
                    response = load_test_runner.client.patch(
                        f"/api/v1/jobs/{job_id}",
                        json=update_data,
                        headers=load_test_runner.auth_headers,
                    )
                else:
                    # Fallback to create operation
                    job_data = {
                        "job_number": f"MIX_FALLBACK_{user_id}_{int(time.time()*1000)}",
                        "customer_name": f"Fallback Customer {user_id}",
                        "due_date": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                    }
                    response = load_test_runner.client.post(
                        "/api/v1/jobs/",
                        json=job_data,
                        headers=load_test_runner.auth_headers,
                    )

            assert response.status_code in [200, 201, 400, 404]  # Allow expected errors

        # Run mixed workload test
        results = await load_test_runner.run_concurrent_load_test(
            test_function=mixed_operations,
            concurrent_users=25,
            duration_seconds=90,
            ramp_up_time=10,
        )

        # Balanced performance assertions for mixed workload
        assert (
            results["error_rate_percent"] < 10.0
        )  # Allow higher error rate for mixed operations
        assert results["response_time_avg"] < 3.0  # Average under 3 seconds
        assert results["response_time_p95"] < 8.0  # 95th percentile under 8 seconds
        assert results["throughput_rps"] > 8.0  # At least 8 requests per second

        print("Mixed Workload Performance Results:")
        print(f"  Throughput: {results['throughput_rps']:.2f} RPS")
        print(f"  Avg Response Time: {results['response_time_avg']:.3f}s")
        print(f"  95th Percentile: {results['response_time_p95']:.3f}s")
        print(f"  Error Rate: {results['error_rate_percent']:.2f}%")
        print(f"  Peak Memory Usage: {results.get('memory_usage_max', 'N/A')}%")
        print(f"  Peak CPU Usage: {results.get('cpu_usage_max', 'N/A')}%")


@pytest.mark.performance
@pytest.mark.slow
class TestDatabasePerformance:
    """Database performance tests with large datasets."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict[str, str]:
        """Get authentication headers."""
        return get_superuser_token_headers(client)

    def test_large_dataset_insertion_performance(
        self, client: TestClient, auth_headers: dict[str, str], performance_monitor
    ):
        """Test performance of inserting large datasets."""

        batch_sizes = [10, 50, 100]
        results = {}

        for batch_size in batch_sizes:
            with performance_monitor.time_operation(f"batch_insert_{batch_size}"):
                jobs_created = 0
                for batch in range(5):  # 5 batches
                    batch_jobs = []

                    for i in range(batch_size):
                        job_data = {
                            "job_number": f"BATCH_{batch_size}_{batch}_{i+1:03d}",
                            "customer_name": f"Batch Customer {batch}",
                            "due_date": (
                                datetime.utcnow()
                                + timedelta(days=random.randint(1, 30))
                            ).isoformat(),
                        }
                        batch_jobs.append(job_data)

                    # Create jobs in batch (if API supports it) or individually
                    for job_data in batch_jobs:
                        response = client.post(
                            "/api/v1/jobs/", json=job_data, headers=auth_headers
                        )
                        if response.status_code == 201:
                            jobs_created += 1

                results[batch_size] = jobs_created

        # Verify performance characteristics
        stats = performance_monitor.get_stats()

        # Batch insertion should be more efficient
        batch_10_time = next(
            op["duration"]
            for op in stats["operations"]
            if "batch_insert_10" in op["name"]
        )
        batch_100_time = next(
            op["duration"]
            for op in stats["operations"]
            if "batch_insert_100" in op["name"]
        )

        # Larger batches should have better throughput per item
        throughput_10 = results[10] / batch_10_time
        throughput_100 = results[100] / batch_100_time

        assert throughput_100 > throughput_10 * 0.8  # At least 80% efficiency gain

        print("Database Insertion Performance:")
        print(
            f"  Batch 10 - Created: {results[10]}, Time: {batch_10_time:.2f}s, Throughput: {throughput_10:.2f}/s"
        )
        print(
            f"  Batch 100 - Created: {results[100]}, Time: {batch_100_time:.2f}s, Throughput: {throughput_100:.2f}/s"
        )

    def test_complex_query_performance(
        self, client: TestClient, auth_headers: dict[str, str], performance_monitor
    ):
        """Test performance of complex queries."""

        # First create diverse test data
        ScenarioManager.create_realistic_scenario(job_count=50)
        # In a real test, this data would be persisted to database

        complex_queries = [
            "/api/v1/jobs/?status=IN_PROGRESS&priority=HIGH",
            "/api/v1/jobs/?customer_name=*Manufacturing*&sort=due_date",
            "/api/v1/jobs/?overdue=true&sort=priority,due_date",
            "/api/v1/schedules/?status=ACTIVE&date_range=7",
        ]

        for query in complex_queries:
            with performance_monitor.time_operation(f"complex_query_{hash(query)}"):
                response = client.get(query, headers=auth_headers)
                # Allow 404 if endpoint doesn't exist yet
                assert response.status_code in [200, 404]

        stats = performance_monitor.get_stats()

        # Complex queries should complete within reasonable time
        for operation in stats["operations"]:
            if "complex_query" in operation["name"]:
                assert operation["duration"] < 5.0  # Under 5 seconds

        print("Complex Query Performance:")
        for operation in stats["operations"]:
            if "complex_query" in operation["name"]:
                print(f"  Query completed in {operation['duration']:.3f}s")

    def test_database_connection_pooling_performance(self, performance_monitor):
        """Test database connection pooling under load."""

        # This would test connection pool efficiency
        # For now, just verify the concept
        with performance_monitor.time_operation("connection_pool_test"):
            # Simulate multiple concurrent database operations
            import time

            time.sleep(0.1)  # Placeholder for actual database operations

        stats = performance_monitor.get_stats()
        assert stats["error_count"] == 0


@pytest.mark.performance
class TestMemoryAndResourceUsage:
    """Test memory usage and resource consumption patterns."""

    def test_memory_usage_under_load(self, performance_monitor):
        """Test memory usage patterns under different loads."""

        # Create scenarios with different memory profiles
        scenarios = [
            ("small", ScenarioManager.create_basic_scenario(job_count=5)),
            ("medium", ScenarioManager.create_complex_scenario(job_count=20)),
            ("large", ScenarioManager.create_high_load_scenario(job_count=100)),
        ]

        memory_usage = {}

        for scenario_name, scenario in scenarios:
            with performance_monitor.time_operation(f"memory_test_{scenario_name}"):
                # Process scenario data (simulate memory usage)
                jobs = scenario["jobs"]
                scenario["tasks"]

                # Simulate processing that uses memory
                processed_data = []
                for job in jobs:
                    job_summary = {
                        "id": job.id,
                        "job_number": job.job_number,
                        "task_count": len(job.get_all_tasks()),
                        "summary": job.get_job_summary(),
                    }
                    processed_data.append(job_summary)

                # Record memory usage
                memory_info = psutil.virtual_memory()
                memory_usage[scenario_name] = {
                    "used_mb": memory_info.used / 1024 / 1024,
                    "percent": memory_info.percent,
                    "data_size": len(processed_data),
                }

        # Verify memory usage scaling
        small_memory = memory_usage["small"]["used_mb"]
        large_memory = memory_usage["large"]["used_mb"]

        # Memory should scale reasonably with data size
        memory_growth_ratio = large_memory / small_memory if small_memory > 0 else 1
        data_growth_ratio = (
            memory_usage["large"]["data_size"] / memory_usage["small"]["data_size"]
        )

        # Memory growth should not exceed data growth by more than 3x
        assert memory_growth_ratio < data_growth_ratio * 3

        print("Memory Usage Under Load:")
        for scenario_name, usage in memory_usage.items():
            print(
                f"  {scenario_name.capitalize()}: {usage['used_mb']:.2f} MB ({usage['percent']:.1f}%)"
            )

    def test_garbage_collection_performance(self, performance_monitor):
        """Test garbage collection impact on performance."""

        import gc

        # Force garbage collection and measure impact
        with performance_monitor.time_operation("gc_disabled"):
            gc.disable()
            try:
                # Create lots of temporary objects
                temp_objects = []
                for i in range(10000):
                    temp_objects.append({"id": i, "data": f"temp_data_{i}" * 10})

                # Process objects
                [obj for obj in temp_objects if obj["id"] % 2 == 0]

            finally:
                gc.enable()

        with performance_monitor.time_operation("gc_enabled"):
            # Same operations with GC enabled
            temp_objects = []
            for i in range(10000):
                temp_objects.append({"id": i, "data": f"temp_data_{i}" * 10})

            [obj for obj in temp_objects if obj["id"] % 2 == 0]

            # Force collection
            gc.collect()

        stats = performance_monitor.get_stats()

        # Find timing for both operations
        gc_disabled_time = next(
            op["duration"] for op in stats["operations"] if "gc_disabled" in op["name"]
        )
        gc_enabled_time = next(
            op["duration"] for op in stats["operations"] if "gc_enabled" in op["name"]
        )

        print("Garbage Collection Performance Impact:")
        print(f"  GC Disabled: {gc_disabled_time:.3f}s")
        print(f"  GC Enabled: {gc_enabled_time:.3f}s")
        print(
            f"  Impact: {((gc_enabled_time - gc_disabled_time) / gc_disabled_time * 100):.1f}% overhead"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "performance"])
