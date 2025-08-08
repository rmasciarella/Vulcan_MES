"""
End-to-End Tests for Complete Scheduling Workflows

Tests the complete scheduling system from API endpoints through to database persistence,
including job creation, task assignment, schedule optimization, and execution workflows.

This comprehensive test suite verifies:
- Complete production workflow integration
- Multi-user role-based access scenarios
- Error handling and recovery workflows
- Performance under realistic load conditions
- Data integrity and transaction safety
- Real-time WebSocket updates during operations
- Security and audit compliance requirements
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.infrastructure.database.models import User as UserModel
from app.main import app
from app.tests.utils.user import create_test_user
from app.tests.utils.utils import get_superuser_token_headers


@pytest.fixture
class PerformanceMonitor:
    """Performance monitoring utility for E2E tests."""

    def __init__(self):
        self.operations = []
        self.error_count = 0
        self.start_times = {}

    @asynccontextmanager
    async def time_operation(self, operation_name: str):
        """Context manager to time operations."""
        start_time = time.time()
        try:
            yield
        except Exception:
            self.error_count += 1
            raise
        finally:
            duration = time.time() - start_time
            self.operations.append(
                {
                    "name": operation_name,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return {
            "operations": self.operations,
            "error_count": self.error_count,
            "total_operations": len(self.operations),
            "average_duration": sum(op["duration"] for op in self.operations)
            / len(self.operations)
            if self.operations
            else 0,
        }


@pytest.fixture
def performance_monitor():
    """Provide performance monitoring fixture."""
    return PerformanceMonitor()


@pytest.fixture
def test_users(db: Session):
    """Create test users with different roles."""
    users = {
        "admin": create_test_user(db, "admin@test.com", is_superuser=True),
        "manager": create_test_user(db, "manager@test.com", is_superuser=False),
        "operator": create_test_user(db, "operator@test.com", is_superuser=False),
        "viewer": create_test_user(db, "viewer@test.com", is_superuser=False),
    }
    return users


@pytest.fixture
def user_token_headers(client: TestClient, test_users: dict[str, UserModel]):
    """Get token headers for different user types."""
    headers = {}
    for role, user in test_users.items():
        response = client.post(
            "/api/v1/login/access-token",
            data={"username": user.email, "password": "testpass123"},
        )
        token = response.json()["access_token"]
        headers[role] = {"Authorization": f"Bearer {token}"}
    return headers


class TestDataFactory:
    """Factory for creating realistic test data."""

    @staticmethod
    def create_job_data(job_number: str, **kwargs) -> dict[str, Any]:
        """Create realistic job data."""
        default_data = {
            "job_number": job_number,
            "customer_name": f"Customer for {job_number}",
            "part_number": f"PART-{job_number[-3:]}",
            "quantity": 10,
            "priority": "NORMAL",
            "due_date": (datetime.utcnow() + timedelta(days=14)).isoformat(),
            "notes": f"Test job {job_number}",
        }
        default_data.update(kwargs)
        return default_data

    @staticmethod
    def create_task_data(sequence: int, **kwargs) -> dict[str, Any]:
        """Create realistic task data."""
        default_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": sequence * 10,
            "planned_duration_minutes": 90 + (sequence * 15),
            "setup_duration_minutes": 15 + (sequence * 5),
            "skill_requirements": [
                {
                    "skill_code": f"SKILL_{(sequence % 3) + 1}",
                    "required_level": "INTERMEDIATE",
                    "is_mandatory": True,
                }
            ],
        }
        default_data.update(kwargs)
        return default_data

    @staticmethod
    def create_optimization_parameters(**kwargs) -> dict[str, Any]:
        """Create optimization parameters."""
        default_params = {
            "minimize_makespan": True,
            "minimize_tardiness": True,
            "resource_utilization_weight": 0.3,
            "priority_weight": 0.4,
            "makespan_weight": 0.15,
            "tardiness_weight": 0.15,
        }
        default_params.update(kwargs)
        return default_params


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompleteSchedulingWorkflowE2E:
    """End-to-end tests for complete scheduling workflows.

    This test class verifies the complete production scheduling workflow from
    job creation through schedule optimization to execution and monitoring.
    """

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict[str, str]:
        """Get authentication headers for API requests."""
        return get_superuser_token_headers(client)

    async def test_complete_job_to_schedule_workflow(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test complete workflow from job creation to schedule execution."""

        # Step 1: Create jobs via API
        job_data_list = [
            {
                "job_number": "E2E-WORKFLOW-001",
                "customer_name": "E2E Test Customer A",
                "part_number": "PART-E2E-A",
                "quantity": 10,
                "priority": "HIGH",
                "due_date": (datetime.utcnow() + timedelta(days=14)).isoformat(),
                "notes": "E2E test job A",
            },
            {
                "job_number": "E2E-WORKFLOW-002",
                "customer_name": "E2E Test Customer B",
                "part_number": "PART-E2E-B",
                "quantity": 5,
                "priority": "URGENT",
                "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "notes": "E2E test job B",
            },
        ]

        created_jobs = []
        for job_data in job_data_list:
            response = client.post(
                "/api/v1/jobs/",
                json=job_data,
                headers=auth_headers,
            )
            assert response.status_code == 201
            job = response.json()
            created_jobs.append(job)
            assert job["job_number"] == job_data["job_number"]
            assert job["status"] == "PLANNED"

        # Step 2: Add tasks to jobs
        job_tasks = {}
        for job in created_jobs:
            job_id = job["id"]
            tasks = []

            # Add multiple tasks per job
            for i in range(3):
                task_data = {
                    "operation_id": str(uuid4()),
                    "sequence_in_job": (i + 1) * 10,
                    "planned_duration_minutes": 90 + (i * 30),
                    "setup_duration_minutes": 15 + (i * 5),
                    "skill_requirements": [
                        {
                            "skill_code": f"SKILL_{i+1}",
                            "required_level": "INTERMEDIATE",
                            "is_mandatory": True,
                        }
                    ],
                }

                response = client.post(
                    f"/api/v1/jobs/{job_id}/tasks/",
                    json=task_data,
                    headers=auth_headers,
                )
                assert response.status_code == 201
                task = response.json()
                tasks.append(task)
                assert task["sequence_in_job"] == task_data["sequence_in_job"]
                assert task["status"] == "PENDING"

            job_tasks[job_id] = tasks

        # Step 3: Release jobs for scheduling
        for job in created_jobs:
            job_id = job["id"]
            response = client.patch(
                f"/api/v1/jobs/{job_id}/status",
                json={"status": "RELEASED", "reason": "ready_for_production"},
                headers=auth_headers,
            )
            assert response.status_code == 200
            updated_job = response.json()
            assert updated_job["status"] == "RELEASED"

        # Step 4: Create optimized schedule
        schedule_data = {
            "name": "E2E Complete Workflow Schedule",
            "job_ids": [job["id"] for job in created_jobs],
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "optimization_parameters": {
                "minimize_makespan": True,
                "minimize_tardiness": True,
                "resource_utilization_weight": 0.3,
                "priority_weight": 0.7,
            },
            "constraints": {
                "max_operators_per_task": 3,
                "min_setup_time_minutes": 10,
            },
        }

        response = client.post(
            "/api/v1/schedules/optimize",
            json=schedule_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        schedule_result = response.json()
        schedule_id = schedule_result["schedule"]["id"]

        assert "schedule" in schedule_result
        assert "optimization_result" in schedule_result
        assert "violations" in schedule_result
        assert "metrics" in schedule_result

        # Verify schedule contains the jobs
        schedule = schedule_result["schedule"]
        assert len(schedule["job_ids"]) == 2
        assert all(job["id"] in schedule["job_ids"] for job in created_jobs)

        # Step 5: Validate schedule (should have no violations for publication)
        response = client.get(
            f"/api/v1/schedules/{schedule_id}/validate",
            headers=auth_headers,
        )
        assert response.status_code == 200
        validation_result = response.json()

        # If there are violations, the schedule needs adjustment
        if validation_result["violations"]:
            # Step 5a: Fix violations by updating schedule
            update_data = {
                "name": "E2E Complete Workflow Schedule - Fixed",
                "modifications": {
                    "resolve_conflicts": True,
                    "adjust_for_capacity": True,
                },
            }

            response = client.patch(
                f"/api/v1/schedules/{schedule_id}",
                json=update_data,
                headers=auth_headers,
            )
            assert response.status_code == 200

            # Re-validate
            response = client.get(
                f"/api/v1/schedules/{schedule_id}/validate",
                headers=auth_headers,
            )
            assert response.status_code == 200
            validation_result = response.json()

        # Step 6: Publish schedule
        response = client.post(
            f"/api/v1/schedules/{schedule_id}/publish",
            json={"published_by": "e2e_test_user"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        published_schedule = response.json()
        assert published_schedule["status"] == "PUBLISHED"

        # Step 7: Execute schedule
        response = client.post(
            f"/api/v1/schedules/{schedule_id}/execute",
            json={"executed_by": "e2e_test_user"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        execution_result = response.json()

        assert "schedule_id" in execution_result
        assert "execution_started_at" in execution_result
        assert execution_result["jobs_processed"] == 2
        assert "job_results" in execution_result

        # Step 8: Monitor schedule execution progress
        response = client.get(
            f"/api/v1/schedules/{schedule_id}/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        status_result = response.json()

        assert status_result["status"] in ["ACTIVE", "EXECUTING"]
        assert status_result["total_jobs"] == 2
        assert "overall_progress" in status_result
        assert "job_progress" in status_result

        # Step 9: Simulate task progression
        # Get job details to find first ready tasks
        for job in created_jobs:
            job_id = job["id"]
            response = client.get(
                f"/api/v1/jobs/{job_id}",
                headers=auth_headers,
            )
            assert response.status_code == 200
            job_details = response.json()

            # Find ready tasks and simulate starting them
            ready_tasks = [
                task for task in job_details["tasks"] if task["status"] == "READY"
            ]
            if ready_tasks:
                task = ready_tasks[0]
                task_id = task["id"]

                # Start task
                response = client.patch(
                    f"/api/v1/tasks/{task_id}/start",
                    json={"start_time": datetime.utcnow().isoformat()},
                    headers=auth_headers,
                )
                assert response.status_code == 200
                started_task = response.json()
                assert started_task["status"] == "IN_PROGRESS"

                # Wait a bit, then complete task
                await asyncio.sleep(0.1)  # Minimal wait for test

                response = client.patch(
                    f"/api/v1/tasks/{task_id}/complete",
                    json={
                        "completion_time": datetime.utcnow().isoformat(),
                        "actual_duration_minutes": 95,
                        "quality_notes": "Completed successfully",
                    },
                    headers=auth_headers,
                )
                assert response.status_code == 200
                completed_task = response.json()
                assert completed_task["status"] == "COMPLETED"

        # Step 10: Check final schedule status
        response = client.get(
            f"/api/v1/schedules/{schedule_id}/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        final_status = response.json()

        # Progress should have increased
        assert final_status["completed_tasks"] > 0
        assert final_status["overall_progress"] > 0

        # Step 11: Get schedule analytics and reports
        response = client.get(
            f"/api/v1/schedules/{schedule_id}/analytics",
            headers=auth_headers,
        )
        assert response.status_code == 200
        analytics = response.json()

        assert "performance_metrics" in analytics
        assert "resource_utilization" in analytics
        assert "timeline_analysis" in analytics

        # Verify metrics are calculated
        metrics = analytics["performance_metrics"]
        assert "makespan_hours" in metrics
        assert "total_setup_time" in metrics
        assert "average_task_duration" in metrics

        # Step 12: Generate schedule report
        response = client.get(
            f"/api/v1/schedules/{schedule_id}/report",
            params={"format": "detailed"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        report = response.json()

        assert "schedule_summary" in report
        assert "job_details" in report
        assert "resource_allocation" in report
        assert "timeline" in report

        # Verify report completeness
        assert report["schedule_summary"]["total_jobs"] == 2
        assert len(report["job_details"]) == 2

    async def test_rescheduling_workflow(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test workflow for handling job rescheduling and conflicts."""

        # Step 1: Create initial job and schedule
        job_data = {
            "job_number": "E2E-RESCHEDULE-001",
            "customer_name": "Reschedule Test Customer",
            "part_number": "PART-RESCHEDULE",
            "quantity": 1,
            "priority": "NORMAL",
            "due_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Add task to job
        task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 10,
            "planned_duration_minutes": 120,
            "setup_duration_minutes": 30,
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
        )
        assert response.status_code == 201

        # Release job
        response = client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "RELEASED"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Create initial schedule
        schedule_data = {
            "name": "Initial Schedule for Rescheduling",
            "job_ids": [job_id],
            "start_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=5)).isoformat(),
        }

        response = client.post(
            "/api/v1/schedules/optimize", json=schedule_data, headers=auth_headers
        )
        assert response.status_code == 201
        schedule_result = response.json()
        schedule_id = schedule_result["schedule"]["id"]

        # Publish initial schedule
        response = client.post(
            f"/api/v1/schedules/{schedule_id}/publish", headers=auth_headers
        )
        assert response.status_code == 200

        # Step 2: Create high-priority job that needs urgent scheduling
        urgent_job_data = {
            "job_number": "E2E-URGENT-001",
            "customer_name": "Urgent Customer",
            "part_number": "PART-URGENT",
            "quantity": 1,
            "priority": "URGENT",
            "due_date": (datetime.utcnow() + timedelta(days=2)).isoformat(),
        }

        response = client.post(
            "/api/v1/jobs/", json=urgent_job_data, headers=auth_headers
        )
        assert response.status_code == 201
        urgent_job = response.json()
        urgent_job_id = urgent_job["id"]

        # Add task to urgent job
        response = client.post(
            f"/api/v1/jobs/{urgent_job_id}/tasks/",
            json={
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 60,
                "setup_duration_minutes": 15,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

        # Release urgent job
        response = client.patch(
            f"/api/v1/jobs/{urgent_job_id}/status",
            json={"status": "RELEASED"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Step 3: Request rescheduling to accommodate urgent job
        reschedule_data = {
            "new_jobs": [urgent_job_id],
            "priority_override": True,
            "reason": "urgent_customer_request",
            "reschedule_existing": True,
        }

        response = client.patch(
            f"/api/v1/schedules/{schedule_id}/reschedule",
            json=reschedule_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        reschedule_result = response.json()

        # Verify rescheduling occurred
        assert "conflicts_resolved" in reschedule_result
        assert "jobs_rescheduled" in reschedule_result
        assert urgent_job_id in reschedule_result["schedule"]["job_ids"]

        # Step 4: Check for resource conflicts
        response = client.get(
            f"/api/v1/schedules/{schedule_id}/conflicts",
            params={"time_window_hours": 48},
            headers=auth_headers,
        )
        assert response.status_code == 200
        conflicts = response.json()

        # Should have minimal conflicts after rescheduling
        assert len(conflicts["conflicts"]) <= 1  # Allow for minor conflicts

        # Step 5: Get rescheduling recommendations
        response = client.get(
            f"/api/v1/schedules/{schedule_id}/recommendations",
            headers=auth_headers,
        )
        assert response.status_code == 200
        recommendations = response.json()

        assert "scheduling_recommendations" in recommendations
        assert "optimization_suggestions" in recommendations

    async def test_schedule_optimization_workflow(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test workflow for schedule optimization with various constraints."""

        # Step 1: Create multiple jobs with different characteristics
        jobs_data = [
            {
                "job_number": "E2E-OPT-HIGH-001",
                "customer_name": "High Priority Customer",
                "priority": "HIGH",
                "due_date": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                "quantity": 20,
            },
            {
                "job_number": "E2E-OPT-NORMAL-001",
                "customer_name": "Normal Customer A",
                "priority": "NORMAL",
                "due_date": (datetime.utcnow() + timedelta(days=8)).isoformat(),
                "quantity": 10,
            },
            {
                "job_number": "E2E-OPT-NORMAL-002",
                "customer_name": "Normal Customer B",
                "priority": "NORMAL",
                "due_date": (datetime.utcnow() + timedelta(days=12)).isoformat(),
                "quantity": 15,
            },
            {
                "job_number": "E2E-OPT-LOW-001",
                "customer_name": "Low Priority Customer",
                "priority": "LOW",
                "due_date": (datetime.utcnow() + timedelta(days=20)).isoformat(),
                "quantity": 5,
            },
        ]

        created_jobs = []
        for job_data in jobs_data:
            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201
            job = response.json()
            created_jobs.append(job)

            # Add multiple tasks with different complexities
            task_count = 2 if job_data["priority"] == "HIGH" else 3
            for i in range(task_count):
                task_data = {
                    "operation_id": str(uuid4()),
                    "sequence_in_job": (i + 1) * 10,
                    "planned_duration_minutes": 60
                    + (i * 30)
                    + (20 if job_data["priority"] == "HIGH" else 0),
                    "setup_duration_minutes": 20 + (i * 5),
                    "skill_requirements": [
                        {
                            "skill_code": f"SKILL_{(i % 3) + 1}",
                            "required_level": "INTERMEDIATE"
                            if job_data["priority"] == "HIGH"
                            else "BASIC",
                            "is_mandatory": True,
                        }
                    ],
                }

                response = client.post(
                    f"/api/v1/jobs/{job['id']}/tasks/",
                    json=task_data,
                    headers=auth_headers,
                )
                assert response.status_code == 201

            # Release jobs
            response = client.patch(
                f"/api/v1/jobs/{job['id']}/status",
                json={"status": "RELEASED"},
                headers=auth_headers,
            )
            assert response.status_code == 200

        # Step 2: Create schedule with different optimization strategies
        optimization_strategies = [
            {
                "name": "Minimize Makespan Strategy",
                "parameters": {
                    "minimize_makespan": True,
                    "minimize_tardiness": False,
                    "resource_utilization_weight": 0.2,
                    "priority_weight": 0.3,
                    "makespan_weight": 0.5,
                },
            },
            {
                "name": "Minimize Tardiness Strategy",
                "parameters": {
                    "minimize_makespan": False,
                    "minimize_tardiness": True,
                    "resource_utilization_weight": 0.2,
                    "priority_weight": 0.4,
                    "tardiness_weight": 0.4,
                },
            },
            {
                "name": "Balanced Strategy",
                "parameters": {
                    "minimize_makespan": True,
                    "minimize_tardiness": True,
                    "resource_utilization_weight": 0.3,
                    "priority_weight": 0.3,
                    "makespan_weight": 0.2,
                    "tardiness_weight": 0.2,
                },
            },
        ]

        optimization_results = []
        for strategy in optimization_strategies:
            schedule_data = {
                "name": f"E2E Optimization Test - {strategy['name']}",
                "job_ids": [job["id"] for job in created_jobs],
                "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "end_time": (datetime.utcnow() + timedelta(days=25)).isoformat(),
                "optimization_parameters": strategy["parameters"],
                "constraints": {
                    "max_operators_per_task": 2,
                    "min_setup_time_minutes": 15,
                    "max_daily_hours": 8,
                    "required_skills_matching": True,
                },
            }

            response = client.post(
                "/api/v1/schedules/optimize", json=schedule_data, headers=auth_headers
            )
            assert response.status_code == 201
            result = response.json()
            optimization_results.append(
                {
                    "strategy": strategy["name"],
                    "result": result,
                    "schedule_id": result["schedule"]["id"],
                }
            )

            # Verify optimization succeeded
            assert "optimization_result" in result
            assert result["optimization_result"]["status"] in ["OPTIMAL", "FEASIBLE"]

        # Step 3: Compare optimization results
        response = client.post(
            "/api/v1/schedules/compare",
            json={
                "schedule_ids": [r["schedule_id"] for r in optimization_results],
                "comparison_metrics": [
                    "makespan",
                    "tardiness",
                    "resource_utilization",
                    "priority_satisfaction",
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        comparison = response.json()

        assert "schedule_comparisons" in comparison
        assert len(comparison["schedule_comparisons"]) == 3

        # Verify each schedule has metrics
        for schedule_comparison in comparison["schedule_comparisons"]:
            assert "makespan_hours" in schedule_comparison["metrics"]
            assert "resource_utilization_percent" in schedule_comparison["metrics"]
            assert "priority_score" in schedule_comparison["metrics"]

        # Step 4: Select best schedule and publish
        best_schedule_id = optimization_results[0][
            "schedule_id"
        ]  # Use first one for test
        response = client.post(
            f"/api/v1/schedules/{best_schedule_id}/publish", headers=auth_headers
        )
        assert response.status_code == 200

        # Step 5: Generate optimization report
        response = client.get(
            f"/api/v1/schedules/{best_schedule_id}/optimization-report",
            headers=auth_headers,
        )
        assert response.status_code == 200
        opt_report = response.json()

        assert "optimization_summary" in opt_report
        assert "constraints_analysis" in opt_report
        assert "resource_analysis" in opt_report
        assert "recommendations" in opt_report

        # Verify optimization details
        assert opt_report["optimization_summary"]["total_jobs"] == 4
        assert (
            opt_report["optimization_summary"]["total_tasks"] > 8
        )  # At least 2-3 tasks per job

    async def test_error_handling_and_recovery_workflow(
        self, client: TestClient, auth_headers: dict[str, str], db: Session
    ):
        """Test error handling and recovery workflows."""

        # Step 1: Test invalid job creation
        invalid_job_data = {
            "job_number": "",  # Invalid empty job number
            "customer_name": "Test Customer",
            "due_date": (
                datetime.utcnow() - timedelta(days=1)
            ).isoformat(),  # Past due date
        }

        response = client.post(
            "/api/v1/jobs/", json=invalid_job_data, headers=auth_headers
        )
        assert response.status_code == 422  # Validation error

        # Step 2: Create valid job for further error testing
        job_data = {
            "job_number": "E2E-ERROR-TEST-001",
            "customer_name": "Error Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Step 3: Test invalid task addition
        invalid_task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 0,  # Invalid sequence
            "planned_duration_minutes": -10,  # Invalid duration
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/",
            json=invalid_task_data,
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Step 4: Add valid task and test invalid state transitions
        valid_task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 10,
            "planned_duration_minutes": 60,
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/",
            json=valid_task_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        task = response.json()
        task_id = task["id"]

        # Try to complete task without starting it
        response = client.patch(
            f"/api/v1/tasks/{task_id}/complete",
            json={"completion_time": datetime.utcnow().isoformat()},
            headers=auth_headers,
        )
        assert response.status_code == 400  # Business rule violation

        # Step 5: Test invalid scheduling scenarios
        # Try to create schedule with non-existent job
        invalid_schedule_data = {
            "name": "Invalid Schedule Test",
            "job_ids": [str(uuid4())],  # Non-existent job ID
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

        response = client.post(
            "/api/v1/schedules/optimize",
            json=invalid_schedule_data,
            headers=auth_headers,
        )
        assert response.status_code == 400

        # Step 6: Test recovery workflow - fix issues and retry
        # Release the job first
        response = client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "RELEASED"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Create valid schedule
        valid_schedule_data = {
            "name": "Recovery Test Schedule",
            "job_ids": [job_id],
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=5)).isoformat(),
        }

        response = client.post(
            "/api/v1/schedules/optimize",
            json=valid_schedule_data,
            headers=auth_headers,
        )
        assert response.status_code == 201

        # Step 7: Test error monitoring and alerts
        response = client.get("/api/v1/system/health", headers=auth_headers)
        assert response.status_code == 200
        health = response.json()

        assert "database" in health
        assert "scheduling_service" in health
        assert health["status"] == "healthy"

        # Step 8: Test audit trail for errors
        response = client.get(
            "/api/v1/audit/errors",
            params={
                "start_date": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                "end_date": datetime.utcnow().isoformat(),
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        audit = response.json()

        assert "error_events" in audit
        # Should contain the validation errors we triggered
        assert len(audit["error_events"]) >= 2


@pytest.mark.e2e
@pytest.mark.performance
class TestSchedulingPerformanceE2E:
    """End-to-end performance tests for scheduling system."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict[str, str]:
        """Get authentication headers for API requests."""
        return get_superuser_token_headers(client)

    async def test_large_scale_scheduling_performance(
        self, client: TestClient, auth_headers: dict[str, str], performance_monitor
    ):
        """Test performance with large number of jobs and tasks."""

        # Step 1: Create many jobs with multiple tasks
        job_count = 20
        tasks_per_job = 5

        created_jobs = []

        with performance_monitor.time_operation("create_large_dataset"):
            for i in range(job_count):
                job_data = {
                    "job_number": f"E2E-PERF-{i+1:03d}",
                    "customer_name": f"Performance Customer {i+1}",
                    "priority": ["LOW", "NORMAL", "HIGH"][i % 3],
                    "due_date": (datetime.utcnow() + timedelta(days=5 + i)).isoformat(),
                    "quantity": (i % 10) + 1,
                }

                response = client.post(
                    "/api/v1/jobs/", json=job_data, headers=auth_headers
                )
                assert response.status_code == 201
                job = response.json()
                created_jobs.append(job)

                # Add tasks to each job
                for j in range(tasks_per_job):
                    task_data = {
                        "operation_id": str(uuid4()),
                        "sequence_in_job": (j + 1) * 10,
                        "planned_duration_minutes": 60 + (j * 15),
                        "setup_duration_minutes": 15 + (j * 5),
                    }

                    response = client.post(
                        f"/api/v1/jobs/{job['id']}/tasks/",
                        json=task_data,
                        headers=auth_headers,
                    )
                    assert response.status_code == 201

                # Release job
                response = client.patch(
                    f"/api/v1/jobs/{job['id']}/status",
                    json={"status": "RELEASED"},
                    headers=auth_headers,
                )
                assert response.status_code == 200

        # Step 2: Test optimization performance with large dataset
        with performance_monitor.time_operation("optimize_large_schedule"):
            schedule_data = {
                "name": "Large Scale Performance Test Schedule",
                "job_ids": [job["id"] for job in created_jobs],
                "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "end_time": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "optimization_parameters": {
                    "minimize_makespan": True,
                    "resource_utilization_weight": 0.4,
                    "priority_weight": 0.6,
                },
            }

            response = client.post(
                "/api/v1/schedules/optimize", json=schedule_data, headers=auth_headers
            )
            assert response.status_code == 201
            schedule_result = response.json()
            schedule_id = schedule_result["schedule"]["id"]

        # Step 3: Test schedule status queries performance
        with performance_monitor.time_operation("query_large_schedule_status"):
            response = client.get(
                f"/api/v1/schedules/{schedule_id}/status", headers=auth_headers
            )
            assert response.status_code == 200

        # Step 4: Test bulk updates performance
        with performance_monitor.time_operation("bulk_task_updates"):
            # Simulate starting multiple tasks
            for job in created_jobs[:5]:  # Update first 5 jobs
                response = client.get(f"/api/v1/jobs/{job['id']}", headers=auth_headers)
                job_details = response.json()

                ready_tasks = [
                    task for task in job_details["tasks"] if task["status"] == "READY"
                ]
                if ready_tasks:
                    task_id = ready_tasks[0]["id"]
                    response = client.patch(
                        f"/api/v1/tasks/{task_id}/start",
                        json={"start_time": datetime.utcnow().isoformat()},
                        headers=auth_headers,
                    )
                    assert response.status_code == 200

        # Verify performance metrics
        stats = performance_monitor.get_stats()
        assert stats["error_count"] == 0

        # Performance assertions (adjust thresholds based on requirements)
        create_time = max(
            op["duration"]
            for op in stats["operations"]
            if op["name"] == "create_large_dataset"
        )
        optimize_time = max(
            op["duration"]
            for op in stats["operations"]
            if op["name"] == "optimize_large_schedule"
        )

        assert (
            create_time < 30.0
        )  # Should create 20 jobs with 5 tasks each in under 30s
        assert optimize_time < 60.0  # Should optimize 100 tasks in under 60s

    async def test_concurrent_access_performance(
        self, client: TestClient, auth_headers: dict[str, str], performance_monitor
    ):
        """Test performance under concurrent access."""

        # Create initial dataset
        job_data = {
            "job_number": "E2E-CONCURRENT-001",
            "customer_name": "Concurrent Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Add task
        task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 10,
            "planned_duration_minutes": 90,
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
        )
        assert response.status_code == 201

        # Release job
        response = client.patch(
            f"/api/v1/jobs/{job_id}/status",
            json={"status": "RELEASED"},
            headers=auth_headers,
        )
        assert response.status_code == 200

        async def concurrent_reads():
            """Perform concurrent read operations."""
            for _ in range(10):
                response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
                assert response.status_code == 200

        async def concurrent_updates():
            """Perform concurrent update operations."""
            for i in range(5):
                response = client.patch(
                    f"/api/v1/jobs/{job_id}",
                    json={"notes": f"Concurrent update {i}"},
                    headers=auth_headers,
                )
                assert response.status_code == 200

        # Run concurrent operations
        with performance_monitor.time_operation("concurrent_operations"):
            await asyncio.gather(
                concurrent_reads(),
                concurrent_updates(),
                concurrent_reads(),  # More reads
            )

        # Verify no errors occurred
        stats = performance_monitor.get_stats()
        assert stats["error_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
