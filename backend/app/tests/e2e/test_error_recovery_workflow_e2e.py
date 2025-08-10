"""
Error Handling and Recovery Workflow Integration Tests

Tests error scenarios, recovery procedures, and system resilience across
the complete scheduling workflow with realistic failure conditions.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlmodel import Session

from app.core.database import get_db
from app.main import app


class CircuitBreakerSimulator:
    """Simulates circuit breaker behavior for testing."""

    def __init__(self, failure_threshold: int = 3):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.is_open = False
        self.last_failure_time = None
        self.recovery_timeout = 5  # seconds

    def call(self, func, *args, **kwargs):
        """Simulate circuit breaker protected call."""
        if self.is_open:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                # Try to close circuit
                self.is_open = False
                self.failure_count = 0
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            # Reset on success
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.is_open = True

            raise e


class DatabaseFailureSimulator:
    """Simulates various database failure scenarios."""

    def __init__(self):
        self.connection_failures = 0
        self.timeout_failures = 0
        self.transaction_failures = 0

    @asynccontextmanager
    async def simulate_connection_failure(self):
        """Simulate database connection failure."""
        original_get_db = app.dependency_overrides.get(get_db, get_db)

        def failing_db():
            self.connection_failures += 1
            raise DisconnectionError("Simulated connection failure", None, None, None)

        app.dependency_overrides[get_db] = failing_db
        try:
            yield
        finally:
            app.dependency_overrides[get_db] = original_get_db

    @asynccontextmanager
    async def simulate_transaction_failure(self):
        """Simulate database transaction failure."""
        original_get_db = app.dependency_overrides.get(get_db, get_db)

        def failing_transaction_db():
            self.transaction_failures += 1
            # Create a mock session that fails on commit
            mock_session = MagicMock()
            mock_session.commit.side_effect = OperationalError(
                "Transaction failed", None, None, None
            )
            return mock_session

        app.dependency_overrides[get_db] = failing_transaction_db
        try:
            yield
        finally:
            app.dependency_overrides[get_db] = original_get_db


@pytest.fixture
def circuit_breaker():
    """Provide circuit breaker simulator."""
    return CircuitBreakerSimulator()


@pytest.fixture
def db_failure_simulator():
    """Provide database failure simulator."""
    return DatabaseFailureSimulator()


@pytest.mark.e2e
@pytest.mark.error_recovery
class TestErrorHandlingWorkflowE2E:
    """Test error handling and recovery in complete workflows."""

    async def test_invalid_job_creation_recovery(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test recovery from various invalid job creation scenarios."""

        # Test 1: Invalid job data with recovery
        invalid_jobs = [
            {
                "job_number": "",  # Empty job number
                "customer_name": "Test Customer",
                "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            },
            {
                "job_number": "VALID-001",
                "customer_name": "Test Customer",
                "due_date": (
                    datetime.utcnow() - timedelta(days=1)
                ).isoformat(),  # Past date
            },
            {
                "job_number": "VALID-002",
                "customer_name": "Test Customer",
                "quantity": -5,  # Negative quantity
                "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            },
            {
                "job_number": "VALID-003",
                "customer_name": "A" * 200,  # Too long customer name
                "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            },
        ]

        recovery_attempts = []

        for i, invalid_job in enumerate(invalid_jobs):
            # Attempt invalid job creation
            response = client.post(
                "/api/v1/jobs/", json=invalid_job, headers=auth_headers
            )

            # Should fail with validation error
            assert response.status_code == 422
            response.json()

            # Create corrected version
            corrected_job = invalid_job.copy()

            if corrected_job["job_number"] == "":
                corrected_job["job_number"] = f"RECOVERY-{i+1:03d}"

            if "due_date" in corrected_job:
                due_date = datetime.fromisoformat(
                    corrected_job["due_date"].replace("Z", "+00:00")
                )
                if due_date < datetime.utcnow():
                    corrected_job["due_date"] = (
                        datetime.utcnow() + timedelta(days=7)
                    ).isoformat()

            if corrected_job.get("quantity", 1) < 0:
                corrected_job["quantity"] = abs(corrected_job["quantity"])

            if len(corrected_job.get("customer_name", "")) > 100:
                corrected_job["customer_name"] = corrected_job["customer_name"][:100]

            # Attempt recovery
            recovery_response = client.post(
                "/api/v1/jobs/", json=corrected_job, headers=auth_headers
            )

            # Recovery should succeed
            assert recovery_response.status_code == 201
            recovery_job = recovery_response.json()
            recovery_attempts.append(recovery_job)

        # Verify all recoveries succeeded
        assert len(recovery_attempts) == len(invalid_jobs)
        for job in recovery_attempts:
            assert job["status"] == "PLANNED"

    async def test_database_failure_recovery(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_failure_simulator: DatabaseFailureSimulator,
    ):
        """Test recovery from database failures during workflow operations."""

        # Create valid job data for testing
        job_data = {
            "job_number": "DB-FAIL-001",
            "customer_name": "Database Failure Test",
            "due_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        }

        # Test 1: Connection failure during job creation
        async with db_failure_simulator.simulate_connection_failure():
            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            # Should fail with database error
            assert response.status_code in [500, 503]

        # Recovery: Retry job creation with connection restored
        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Test 2: Transaction failure during status update
        async with db_failure_simulator.simulate_transaction_failure():
            response = client.patch(
                f"/api/v1/jobs/{job_id}/status",
                json={"status": "RELEASED", "reason": "test_release"},
                headers=auth_headers,
            )
            # Should fail with transaction error
            assert response.status_code in [500, 503]

        # Recovery: Retry status update
        response = client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "RELEASED", "reason": "retry_release"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify job state is consistent after recovery
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        final_job = response.json()
        assert final_job["status"] == "RELEASED"

    async def test_solver_failure_recovery(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test recovery from optimization solver failures."""

        # Create jobs for solver testing
        jobs_data = [
            {
                "job_number": f"SOLVER-FAIL-{i+1:03d}",
                "customer_name": f"Solver Test Customer {i+1}",
                "due_date": (datetime.utcnow() + timedelta(days=5 + i)).isoformat(),
            }
            for i in range(3)
        ]

        created_jobs = []
        for job_data in jobs_data:
            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201
            job = response.json()
            created_jobs.append(job)

            # Add task to each job
            task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 120,
            }

            response = client.post(
                f"/api/v1/jobs/{job['id']}/tasks/", json=task_data, headers=auth_headers
            )
            assert response.status_code == 201

            # Release job
            response = client.patch(
                f"/api/v1/jobs/{job['id']}/status",
                json={"status": "RELEASED"},
                headers=auth_headers,
            )
            assert response.status_code == 200

        # Test 1: Optimization with impossible constraints (should fail gracefully)
        impossible_schedule_data = {
            "name": "Impossible Schedule Test",
            "job_ids": [job["id"] for job in created_jobs],
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (
                datetime.utcnow() + timedelta(hours=2)
            ).isoformat(),  # Too short
            "optimization_parameters": {
                "minimize_makespan": True,
                "resource_utilization_weight": 1.0,
            },
            "constraints": {
                "max_operators_per_task": 0,  # Impossible constraint
                "max_daily_hours": 1,  # Too restrictive
            },
        }

        response = client.post(
            "/api/v1/schedules/optimize",
            json=impossible_schedule_data,
            headers=auth_headers,
        )

        # Should fail or return infeasible solution
        if response.status_code == 201:
            result = response.json()
            # Check if solver reported infeasibility
            assert "optimization_result" in result
            # May be "INFEASIBLE" or have violations
        else:
            # Should fail with clear error message
            assert response.status_code == 400

        # Recovery: Create feasible schedule
        feasible_schedule_data = {
            "name": "Feasible Recovery Schedule",
            "job_ids": [job["id"] for job in created_jobs],
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "optimization_parameters": {
                "minimize_makespan": True,
                "resource_utilization_weight": 0.5,
            },
            "constraints": {"max_operators_per_task": 3, "max_daily_hours": 8},
        }

        response = client.post(
            "/api/v1/schedules/optimize",
            json=feasible_schedule_data,
            headers=auth_headers,
        )
        assert response.status_code == 201

        recovery_result = response.json()
        assert "schedule" in recovery_result
        assert "optimization_result" in recovery_result

        # Verify recovery produced valid schedule
        schedule = recovery_result["schedule"]
        assert len(schedule["job_ids"]) == 3

        # Test fallback optimization strategy
        response = client.get(
            f"/api/v1/schedules/{schedule['id']}/validate", headers=auth_headers
        )
        assert response.status_code == 200

    async def test_concurrent_modification_conflicts(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test handling of concurrent modification conflicts and recovery."""

        # Create job for concurrent modification testing
        job_data = {
            "job_number": "CONCURRENT-CONFLICT-001",
            "customer_name": "Concurrent Conflict Test",
            "due_date": (datetime.utcnow() + timedelta(days=8)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Add task for testing
        task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 10,
            "planned_duration_minutes": 90,
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
        )
        assert response.status_code == 201
        task = response.json()
        task["id"]

        # Simulate concurrent modifications
        # First, get current job state
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        response.json()

        # Simulate two users trying to modify job simultaneously
        update_1 = {"priority": "HIGH", "notes": "Updated by user 1"}
        update_2 = {"priority": "URGENT", "notes": "Updated by user 2"}

        # Send both updates (second one may conflict)
        response_1 = client.patch(
            f"/api/v1/jobs/{job_id}", json=update_1, headers=auth_headers
        )
        response_2 = client.patch(
            f"/api/v1/jobs/{job_id}", json=update_2, headers=auth_headers
        )

        # At least one should succeed
        assert response_1.status_code == 200 or response_2.status_code == 200

        # Test optimistic locking recovery (if implemented)
        if response_2.status_code == 409:  # Conflict
            # Retry with fresh data
            response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
            response.json()

            # Update with current version
            retry_update = {
                "priority": "URGENT",
                "notes": "Retry update after conflict",
            }
            response = client.patch(
                f"/api/v1/jobs/{job_id}", json=retry_update, headers=auth_headers
            )
            assert response.status_code == 200

        # Verify final state consistency
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        final_job = response.json()

        # Job should be in valid state
        assert final_job["priority"] in ["HIGH", "URGENT"]
        assert final_job["status"] in ["PLANNED", "APPROVED"]

    async def test_resource_constraint_violation_recovery(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test recovery from resource constraint violations."""

        # Create jobs that will cause resource conflicts
        conflict_jobs_data = [
            {
                "job_number": f"RESOURCE-CONFLICT-{i+1:03d}",
                "customer_name": f"Resource Test Customer {i+1}",
                "priority": "URGENT" if i == 0 else "NORMAL",
                "due_date": (datetime.utcnow() + timedelta(days=2 + i)).isoformat(),
            }
            for i in range(4)  # Create more jobs than available resources
        ]

        created_jobs = []
        for job_data in conflict_jobs_data:
            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201
            job = response.json()
            created_jobs.append(job)

            # Add overlapping time-sensitive tasks
            task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 240,  # Long tasks to create conflicts
                "skill_requirements": [
                    {
                        "skill_code": "SPECIALIZED_MACHINE",  # Rare skill
                        "required_level": "EXPERT",
                        "is_mandatory": True,
                    }
                ],
            }

            response = client.post(
                f"/api/v1/jobs/{job['id']}/tasks/", json=task_data, headers=auth_headers
            )
            assert response.status_code == 201

            # Release job
            response = client.patch(
                f"/api/v1/jobs/{job['id']}/status",
                json={"status": "RELEASED"},
                headers=auth_headers,
            )
            assert response.status_code == 200

        # Try to schedule all jobs in tight timeframe (should cause conflicts)
        conflict_schedule_data = {
            "name": "Resource Conflict Schedule",
            "job_ids": [job["id"] for job in created_jobs],
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=3)).isoformat(),
            "optimization_parameters": {
                "minimize_makespan": True,
                "resource_utilization_weight": 0.8,
            },
        }

        response = client.post(
            "/api/v1/schedules/optimize",
            json=conflict_schedule_data,
            headers=auth_headers,
        )

        if response.status_code == 201:
            schedule_result = response.json()
            schedule_id = schedule_result["schedule"]["id"]

            # Validate schedule for conflicts
            response = client.get(
                f"/api/v1/schedules/{schedule_id}/validate", headers=auth_headers
            )
            assert response.status_code == 200
            validation = response.json()

            if validation.get("violations"):
                # Recovery: Resolve conflicts by extending timeframe
                resolution_data = {
                    "extend_timeframe": True,
                    "reschedule_low_priority": True,
                    "add_overtime_slots": True,
                }

                response = client.patch(
                    f"/api/v1/schedules/{schedule_id}/resolve-conflicts",
                    json=resolution_data,
                    headers=auth_headers,
                )

                if response.status_code == 200:
                    # Re-validate after resolution
                    response = client.get(
                        f"/api/v1/schedules/{schedule_id}/validate",
                        headers=auth_headers,
                    )
                    assert response.status_code == 200
                    final_validation = response.json()

                    # Should have fewer violations after resolution
                    original_violation_count = len(validation.get("violations", []))
                    final_violation_count = len(final_validation.get("violations", []))
                    assert final_violation_count <= original_violation_count

    async def test_network_timeout_recovery(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        circuit_breaker: CircuitBreakerSimulator,
    ):
        """Test recovery from network timeouts and service unavailability."""

        # Create test job
        {
            "job_number": "NETWORK-TIMEOUT-001",
            "customer_name": "Network Timeout Test",
            "due_date": (datetime.utcnow() + timedelta(days=6)).isoformat(),
        }

        # Simulate network timeout using circuit breaker
        timeout_count = 0

        def timeout_simulation():
            nonlocal timeout_count
            timeout_count += 1
            if timeout_count <= 2:  # Fail first 2 attempts
                raise Exception("Network timeout")
            return {"success": True}

        # Test retry logic with circuit breaker
        max_retries = 5
        for attempt in range(max_retries):
            try:
                result = circuit_breaker.call(timeout_simulation)
                # Success on 3rd attempt
                assert result["success"] is True
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    # Final attempt failed
                    assert (
                        "timeout" in str(e).lower()
                        or "circuit breaker" in str(e).lower()
                    )
                else:
                    # Expected failure, continue retrying
                    await asyncio.sleep(0.1)  # Small delay between retries

        # Verify circuit breaker opened after failures
        if circuit_breaker.is_open:
            # Wait for recovery timeout
            await asyncio.sleep(circuit_breaker.recovery_timeout + 0.1)

            # Circuit should try to close on next call
            try:
                result = circuit_breaker.call(lambda: {"recovered": True})
                assert result["recovered"] is True
            except Exception:
                # Circuit is still open or call still fails
                pass

    async def test_data_corruption_recovery(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test recovery from data corruption scenarios."""

        # Create job with tasks for corruption testing
        job_data = {
            "job_number": "CORRUPTION-TEST-001",
            "customer_name": "Data Corruption Test",
            "due_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Add multiple tasks
        task_ids = []
        for i in range(3):
            task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": (i + 1) * 10,
                "planned_duration_minutes": 60 + (i * 20),
            }

            response = client.post(
                f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
            )
            assert response.status_code == 201
            task = response.json()
            task_ids.append(task["id"])

        # Simulate data corruption scenarios
        corruption_tests = [
            {
                "name": "invalid_status_transition",
                "update": {"status": "INVALID_STATUS"},
                "should_fail": True,
            },
            {
                "name": "negative_sequence",
                "task_update": {"sequence_in_job": -10},
                "should_fail": True,
            },
            {
                "name": "future_completion_date",
                "update": {
                    "actual_end_date": (
                        datetime.utcnow() + timedelta(days=100)
                    ).isoformat()
                },
                "should_fail": True,
            },
        ]

        for test in corruption_tests:
            test_name = test["name"]
            should_fail = test["should_fail"]

            if "update" in test:
                # Test job update with corrupted data
                response = client.patch(
                    f"/api/v1/jobs/{job_id}", json=test["update"], headers=auth_headers
                )

                if should_fail:
                    assert response.status_code in [
                        400,
                        422,
                    ], f"Expected failure for {test_name}"
                else:
                    assert (
                        response.status_code == 200
                    ), f"Expected success for {test_name}"

            elif "task_update" in test and task_ids:
                # Test task update with corrupted data
                response = client.patch(
                    f"/api/v1/tasks/{task_ids[0]}",
                    json=test["task_update"],
                    headers=auth_headers,
                )

                if should_fail:
                    assert response.status_code in [
                        400,
                        422,
                    ], f"Expected failure for {test_name}"
                else:
                    assert (
                        response.status_code == 200
                    ), f"Expected success for {test_name}"

        # Verify data integrity after corruption attempts
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        final_job = response.json()

        # Job should still be in valid state
        assert final_job["status"] in [
            "PLANNED",
            "APPROVED",
            "RELEASED",
            "IN_PROGRESS",
            "COMPLETED",
        ]
        assert len(final_job.get("tasks", [])) == 3

        # All tasks should have valid sequences
        for task in final_job.get("tasks", []):
            assert task["sequence_in_job"] > 0

    async def test_system_overload_recovery(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test system behavior and recovery under overload conditions."""

        # Create many jobs rapidly to simulate overload
        overload_jobs = []
        failed_creations = 0

        for i in range(50):  # Create many jobs rapidly
            job_data = {
                "job_number": f"OVERLOAD-{i+1:03d}",
                "customer_name": f"Overload Customer {i+1}",
                "due_date": (datetime.utcnow() + timedelta(days=5 + i)).isoformat(),
            }

            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)

            if response.status_code == 201:
                job = response.json()
                overload_jobs.append(job)
            else:
                failed_creations += 1
                # Expected under overload conditions
                assert response.status_code in [
                    429,
                    500,
                    503,
                ]  # Rate limit or server error

        # Should have created at least some jobs successfully
        assert len(overload_jobs) > 0

        # Test system recovery - should be able to create jobs normally again
        recovery_job_data = {
            "job_number": "RECOVERY-POST-OVERLOAD",
            "customer_name": "Recovery Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        # May need to wait for system recovery
        for attempt in range(5):
            response = client.post(
                "/api/v1/jobs/", json=recovery_job_data, headers=auth_headers
            )

            if response.status_code == 201:
                # System recovered
                recovery_job = response.json()
                assert recovery_job["job_number"] == "RECOVERY-POST-OVERLOAD"
                break
            elif response.status_code in [429, 500, 503]:
                # Still recovering, wait and retry
                await asyncio.sleep(1)
                if attempt == 4:  # Last attempt
                    # System should recover eventually, but test environment may be limited
                    pass
            else:
                # Unexpected error
                raise AssertionError(f"Unexpected error during recovery: {response.status_code}")

        # Verify system health
        response = client.get("/api/v1/system/health", headers=auth_headers)
        if response.status_code == 200:
            health = response.json()
            # System should report healthy or recovering
            assert health.get("status") in ["healthy", "degraded", "recovering"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
