"""Load testing scenarios using Locust."""

import random
from datetime import datetime, timedelta

from locust import HttpUser, between, events, task


class SchedulingAPIUser(HttpUser):
    """Load test user for Scheduling API endpoints."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Initialize user session."""
        # Login or get auth token
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Store some IDs for later use
        self.job_ids = []
        self.schedule_ids = []
        self.operator_ids = []

    @task(10)
    def create_job(self):
        """Create a new job (high frequency)."""
        job_data = {
            "name": f"Job_{random.randint(1000, 9999)}",
            "priority": random.randint(1, 10),
            "due_date": (
                datetime.now() + timedelta(days=random.randint(1, 30))
            ).isoformat(),
            "tasks": [
                {
                    "name": f"Task_{i}",
                    "duration": random.randint(30, 180),
                    "skill_required": random.choice(
                        ["welding", "machining", "assembly"]
                    ),
                    "skill_level": random.randint(1, 3),
                }
                for i in range(random.randint(5, 20))
            ],
        }

        with self.client.post(
            "/api/v1/jobs",
            json=job_data,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                response.success()
                data = response.json()
                if "id" in data:
                    self.job_ids.append(data["id"])
                    # Keep only last 100 IDs
                    self.job_ids = self.job_ids[-100:]
            else:
                response.failure(f"Failed to create job: {response.status_code}")

    @task(15)
    def get_job(self):
        """Get job details (very high frequency)."""
        if not self.job_ids:
            return

        job_id = random.choice(self.job_ids)

        with self.client.get(
            f"/api/v1/jobs/{job_id}",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Remove non-existent job
                self.job_ids.remove(job_id)
                response.failure("Job not found")
            else:
                response.failure(f"Failed to get job: {response.status_code}")

    @task(8)
    def list_jobs(self):
        """List jobs with filters (high frequency)."""
        params = {}

        # Random filters
        if random.random() > 0.5:
            params["status"] = random.choice(
                ["pending", "scheduled", "in_progress", "completed"]
            )
        if random.random() > 0.5:
            params["priority"] = random.randint(1, 10)

        params["limit"] = random.choice([10, 20, 50])
        params["offset"] = random.randint(0, 100)

        with self.client.get(
            "/api/v1/jobs",
            params=params,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to list jobs: {response.status_code}")

    @task(5)
    def schedule_job(self):
        """Schedule a job (medium frequency)."""
        if not self.job_ids:
            return

        job_id = random.choice(self.job_ids)

        schedule_data = {
            "job_id": job_id,
            "optimization_level": random.choice(["quick", "normal", "thorough"]),
            "constraints": {
                "max_makespan": random.randint(5, 20) * 24 * 60,  # Days to minutes
                "prefer_operators": random.sample(
                    self.operator_ids, min(3, len(self.operator_ids))
                )
                if self.operator_ids
                else [],
            },
        }

        with self.client.post(
            "/api/v1/schedules",
            json=schedule_data,
            headers=self.headers,
            catch_response=True,
            timeout=30,  # Scheduling can take time
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
                data = response.json()
                if "id" in data:
                    self.schedule_ids.append(data["id"])
                    self.schedule_ids = self.schedule_ids[-50:]
            else:
                response.failure(f"Failed to schedule job: {response.status_code}")

    @task(3)
    def optimize_schedule(self):
        """Optimize existing schedule (low frequency)."""
        if not self.schedule_ids:
            return

        schedule_id = random.choice(self.schedule_ids)

        optimize_data = {
            "focus": random.choice(["cost", "makespan", "balanced"]),
            "max_iterations": random.randint(100, 1000),
        }

        with self.client.post(
            f"/api/v1/schedules/{schedule_id}/optimize",
            json=optimize_data,
            headers=self.headers,
            catch_response=True,
            timeout=60,  # Optimization can take longer
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to optimize schedule: {response.status_code}")

    @task(10)
    def get_schedule(self):
        """Get schedule details (high frequency)."""
        if not self.schedule_ids:
            return

        schedule_id = random.choice(self.schedule_ids)

        with self.client.get(
            f"/api/v1/schedules/{schedule_id}",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                self.schedule_ids.remove(schedule_id)
                response.failure("Schedule not found")
            else:
                response.failure(f"Failed to get schedule: {response.status_code}")

    @task(7)
    def list_operators(self):
        """List available operators (medium frequency)."""
        params = {
            "available": True,
            "limit": 50,
        }

        if random.random() > 0.5:
            params["skill"] = random.choice(["welding", "machining", "assembly"])

        with self.client.get(
            "/api/v1/operators",
            params=params,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                data = response.json()
                if isinstance(data, list):
                    self.operator_ids = [op.get("id") for op in data if "id" in op]
            else:
                response.failure(f"Failed to list operators: {response.status_code}")

    @task(2)
    def get_metrics(self):
        """Get performance metrics (low frequency)."""
        with self.client.get(
            "/api/v1/metrics/performance",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get metrics: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check endpoint (very low frequency)."""
        with self.client.get(
            "/health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


class AdminUser(HttpUser):
    """Load test user for admin operations."""

    wait_time = between(5, 10)  # Admins make fewer requests

    def on_start(self):
        """Initialize admin session."""
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Add admin auth token here
        }

    @task(3)
    def generate_report(self):
        """Generate performance report."""
        report_data = {
            "type": random.choice(["daily", "weekly", "monthly"]),
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
        }

        with self.client.post(
            "/api/v1/reports/generate",
            json=report_data,
            headers=self.headers,
            catch_response=True,
            timeout=30,
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Failed to generate report: {response.status_code}")

    @task(2)
    def export_data(self):
        """Export schedule data."""
        params = {
            "format": random.choice(["json", "csv", "excel"]),
            "include_details": True,
        }

        with self.client.get(
            "/api/v1/exports/schedules",
            params=params,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to export data: {response.status_code}")

    @task(1)
    def system_stats(self):
        """Get system statistics."""
        with self.client.get(
            "/api/v1/admin/stats",
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get system stats: {response.status_code}")


class MixedLoadUser(HttpUser):
    """Mixed load pattern simulating real usage."""

    tasks = [SchedulingAPIUser, AdminUser]
    wait_time = between(0.5, 5)


# Event handlers for custom metrics
@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    response,
    context,
    exception,
    **kwargs,
):
    """Custom request event handler."""
    if exception:
        print(f"Request failed: {name} - {exception}")
    elif response_time > 1000:  # Log slow requests (>1s)
        print(f"Slow request: {name} - {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test environment."""
    print("Load test starting...")
    print(f"Target host: {environment.host}")
    print(
        f"Total users: {environment.runner.target_user_count if environment.runner else 'N/A'}"
    )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Clean up test environment."""
    print("\nLoad test completed!")

    # Print summary statistics
    if environment.runner and environment.runner.stats:
        stats = environment.runner.stats
        print(f"\nTotal requests: {stats.total.num_requests}")
        print(f"Total failures: {stats.total.num_failures}")
        print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
        print(f"Min response time: {stats.total.min_response_time:.2f}ms")
        print(f"Max response time: {stats.total.max_response_time:.2f}ms")

        # Print percentiles
        if stats.total.response_times:
            print(
                f"Median response time: {stats.total.get_response_time_percentile(0.5):.2f}ms"
            )
            print(
                f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms"
            )
            print(
                f"99th percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms"
            )


# Custom load test scenarios
class StressTestUser(SchedulingAPIUser):
    """Stress test with aggressive request pattern."""

    wait_time = between(0.1, 0.5)  # Very short wait times


class SpikeTestUser(SchedulingAPIUser):
    """Spike test to simulate sudden traffic increase."""

    wait_time = between(0.1, 1)

    @task(50)
    def burst_requests(self):
        """Generate burst of requests."""
        for _ in range(10):
            self.get_job()


class EnduranceTestUser(SchedulingAPIUser):
    """Endurance test for long-running scenarios."""

    wait_time = between(2, 5)

    def on_start(self):
        """Initialize with more data for long test."""
        super().on_start()
        # Pre-populate with more IDs
        for _ in range(100):
            self.create_job()


# Configuration for different test scenarios
TEST_SCENARIOS = {
    "normal": {
        "users": 100,
        "spawn_rate": 10,
        "run_time": "5m",
        "user_class": SchedulingAPIUser,
    },
    "stress": {
        "users": 500,
        "spawn_rate": 50,
        "run_time": "10m",
        "user_class": StressTestUser,
    },
    "spike": {
        "users": 1000,
        "spawn_rate": 100,
        "run_time": "5m",
        "user_class": SpikeTestUser,
    },
    "endurance": {
        "users": 50,
        "spawn_rate": 5,
        "run_time": "1h",
        "user_class": EnduranceTestUser,
    },
    "mixed": {
        "users": 200,
        "spawn_rate": 20,
        "run_time": "15m",
        "user_class": MixedLoadUser,
    },
}


if __name__ == "__main__":
    # Example: Run load test programmatically
    pass

    # For debugging single user
    # run_single_user(SchedulingAPIUser)
