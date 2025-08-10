"""
Comprehensive API Endpoint Tests for Scheduling Operations

Tests all scheduling API endpoints including CRUD operations, authentication,
authorization, error handling, and workflow scenarios.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domain.scheduling.value_objects.enums import JobStatus, TaskStatus
from app.infrastructure.database.repositories.base import (
    DatabaseError,
    EntityNotFoundError,
)
from app.main import app

client = TestClient(app)


@pytest.fixture
def auth_headers():
    """Mock authentication headers."""
    return {"Authorization": "Bearer mock_token"}


@pytest.fixture
def superuser_headers():
    """Mock superuser authentication headers."""
    return {"Authorization": "Bearer superuser_token"}


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "job_number": "TEST-JOB-001",
        "customer_name": "Test Customer Corp",
        "part_number": "PART-TEST-001",
        "quantity": 10,
        "priority": "NORMAL",
        "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        "notes": "Test job for API testing",
        "created_by": "test_user",
    }


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        "operation_id": str(uuid4()),
        "sequence_in_job": 10,
        "planned_duration_minutes": 120,
        "setup_duration_minutes": 15,
        "skill_requirements": [
            {"skill_type": "MACHINING", "minimum_level": "PROFICIENT"}
        ],
        "machine_options": [
            {
                "machine_id": str(uuid4()),
                "efficiency_factor": 1.0,
                "setup_time_minutes": 10,
            }
        ],
    }


class TestSchedulingDataEndpoints:
    """Test scheduling data retrieval endpoints."""

    def test_get_scheduling_data_success(self, auth_headers):
        """Test successful retrieval of scheduling data summary."""
        with patch(
            "app.infrastructure.database.dependencies.get_repository_container"
        ) as mock_container:
            # Mock repository responses
            mock_repos = Mock()
            mock_repos.jobs.find_active_jobs.return_value = [
                Mock(job_number="JOB-001"),
                Mock(job_number="JOB-002"),
            ]
            mock_repos.jobs.find_overdue.return_value = []
            mock_repos.tasks.find_ready_tasks.return_value = [Mock(), Mock(), Mock()]
            mock_repos.tasks.find_scheduled_tasks.return_value = [Mock()]
            mock_repos.tasks.find_active_tasks.return_value = [Mock(), Mock()]
            mock_repos.tasks.find_critical_path_tasks.return_value = [Mock()]
            mock_repos.tasks.find_delayed_tasks.return_value = []
            mock_repos.machines.find_available.return_value = [Mock(), Mock(), Mock()]
            mock_repos.operators.find_available.return_value = [
                Mock(),
                Mock(),
                Mock(),
                Mock(),
            ]
            mock_repos.resources.get_resource_summary.return_value = {
                "total_capacity": 100,
                "utilized_capacity": 75,
            }

            mock_container.return_value = mock_repos

            response = client.get("/api/v1/scheduling/data", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()

            assert data["message"] == "Scheduling data retrieved successfully"
            assert "data" in data

            scheduling_data = data["data"]
            assert "timestamp" in scheduling_data
            assert "jobs" in scheduling_data
            assert "tasks" in scheduling_data
            assert "resources" in scheduling_data
            assert "constraints" in scheduling_data

            # Verify job data
            assert scheduling_data["jobs"]["active_count"] == 2
            assert scheduling_data["jobs"]["overdue_count"] == 0
            assert "JOB-001" in scheduling_data["jobs"]["job_numbers"]

            # Verify task data
            assert scheduling_data["tasks"]["ready_count"] == 3
            assert scheduling_data["tasks"]["scheduled_count"] == 1
            assert scheduling_data["tasks"]["active_count"] == 2

            # Verify resource data
            assert scheduling_data["resources"]["available_machines"] == 3
            assert scheduling_data["resources"]["available_operators"] == 4

            # Verify constraints
            assert scheduling_data["constraints"]["critical_path_tasks"] == 1
            assert scheduling_data["constraints"]["delayed_tasks"] == 0

    def test_get_scheduling_data_unauthorized(self):
        """Test scheduling data access without authentication."""
        response = client.get("/api/v1/scheduling/data")
        assert response.status_code == 401

    def test_get_scheduling_data_database_error(self, auth_headers):
        """Test handling of database errors."""
        with patch(
            "app.infrastructure.database.dependencies.get_repository_container"
        ) as mock_container:
            mock_repos = Mock()
            mock_repos.jobs.find_active_jobs.side_effect = DatabaseError(
                "Database connection failed"
            )
            mock_container.return_value = mock_repos

            response = client.get("/api/v1/scheduling/data", headers=auth_headers)

            assert response.status_code == 500
            data = response.json()
            assert "Database connection failed" in data["detail"]

    def test_get_scheduling_data_empty_database(self, auth_headers):
        """Test scheduling data with empty database."""
        with patch(
            "app.infrastructure.database.dependencies.get_repository_container"
        ) as mock_container:
            mock_repos = Mock()
            # All repository methods return empty lists
            mock_repos.jobs.find_active_jobs.return_value = []
            mock_repos.jobs.find_overdue.return_value = []
            mock_repos.tasks.find_ready_tasks.return_value = []
            mock_repos.tasks.find_scheduled_tasks.return_value = []
            mock_repos.tasks.find_active_tasks.return_value = []
            mock_repos.tasks.find_critical_path_tasks.return_value = []
            mock_repos.tasks.find_delayed_tasks.return_value = []
            mock_repos.machines.find_available.return_value = []
            mock_repos.operators.find_available.return_value = []
            mock_repos.resources.get_resource_summary.return_value = {
                "total_capacity": 0,
                "utilized_capacity": 0,
            }

            mock_container.return_value = mock_repos

            response = client.get("/api/v1/scheduling/data", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()

            scheduling_data = data["data"]
            assert scheduling_data["jobs"]["active_count"] == 0
            assert scheduling_data["tasks"]["ready_count"] == 0
            assert scheduling_data["resources"]["available_machines"] == 0


class TestJobManagementEndpoints:
    """Test job management API endpoints."""

    def test_create_job_success(self, auth_headers, sample_job_data):
        """Test successful job creation."""
        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            created_job = Mock()
            created_job.id = uuid4()
            created_job.job_number = sample_job_data["job_number"]
            created_job.customer_name = sample_job_data["customer_name"]
            created_job.status = JobStatus.PLANNED
            created_job.created_at = datetime.utcnow()

            mock_repository.create.return_value = created_job
            mock_repo.return_value = mock_repository

            response = client.post(
                "/api/v1/scheduling/jobs", headers=auth_headers, json=sample_job_data
            )

            assert response.status_code == 201
            data = response.json()

            assert data["job_number"] == sample_job_data["job_number"]
            assert data["customer_name"] == sample_job_data["customer_name"]
            assert data["status"] == JobStatus.PLANNED.value

    def test_create_job_validation_error(self, auth_headers):
        """Test job creation with validation errors."""
        invalid_job_data = {
            "job_number": "",  # Invalid: empty
            "due_date": "invalid-date",  # Invalid: bad format
            "quantity": -1,  # Invalid: negative
        }

        response = client.post(
            "/api/v1/scheduling/jobs", headers=auth_headers, json=invalid_job_data
        )

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

        # Should contain validation errors for multiple fields
        errors = data["detail"]
        error_fields = [error["loc"][-1] for error in errors if "loc" in error]
        assert "job_number" in error_fields
        assert "due_date" in error_fields
        assert "quantity" in error_fields

    def test_create_job_duplicate_job_number(self, auth_headers, sample_job_data):
        """Test creating job with duplicate job number."""
        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_repository.create.side_effect = DatabaseError("Duplicate job number")
            mock_repo.return_value = mock_repository

            response = client.post(
                "/api/v1/scheduling/jobs", headers=auth_headers, json=sample_job_data
            )

            assert response.status_code == 400
            data = response.json()
            assert "Duplicate job number" in data["detail"]

    def test_get_job_by_id_success(self, auth_headers):
        """Test successful job retrieval by ID."""
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_job = Mock()
            mock_job.id = job_id
            mock_job.job_number = "TEST-JOB-001"
            mock_job.customer_name = "Test Customer"
            mock_job.status = JobStatus.PLANNED

            mock_repository.get.return_value = mock_job
            mock_repo.return_value = mock_repository

            response = client.get(
                f"/api/v1/scheduling/jobs/{job_id}", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == str(job_id)
            assert data["job_number"] == "TEST-JOB-001"
            assert data["customer_name"] == "Test Customer"

    def test_get_job_by_id_not_found(self, auth_headers):
        """Test job retrieval for non-existent ID."""
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_repository.get.return_value = None
            mock_repo.return_value = mock_repository

            response = client.get(
                f"/api/v1/scheduling/jobs/{job_id}", headers=auth_headers
            )

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_update_job_success(self, auth_headers):
        """Test successful job update."""
        job_id = uuid4()
        update_data = {
            "customer_name": "Updated Customer",
            "priority": "HIGH",
            "notes": "Updated notes",
        }

        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            updated_job = Mock()
            updated_job.id = job_id
            updated_job.customer_name = update_data["customer_name"]
            updated_job.priority = update_data["priority"]
            updated_job.notes = update_data["notes"]
            updated_job.updated_at = datetime.utcnow()

            mock_repository.update.return_value = updated_job
            mock_repo.return_value = mock_repository

            response = client.put(
                f"/api/v1/scheduling/jobs/{job_id}",
                headers=auth_headers,
                json=update_data,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["customer_name"] == update_data["customer_name"]
            assert data["priority"] == update_data["priority"]
            assert data["notes"] == update_data["notes"]

    def test_update_job_not_found(self, auth_headers):
        """Test updating non-existent job."""
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_repository.update.side_effect = EntityNotFoundError("Job not found")
            mock_repo.return_value = mock_repository

            response = client.put(
                f"/api/v1/scheduling/jobs/{job_id}",
                headers=auth_headers,
                json={"customer_name": "Updated Customer"},
            )

            assert response.status_code == 404

    def test_delete_job_success(self, superuser_headers):
        """Test successful job deletion."""
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_repository.delete.return_value = True
            mock_repo.return_value = mock_repository

            response = client.delete(
                f"/api/v1/scheduling/jobs/{job_id}", headers=superuser_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert "deleted successfully" in data["message"]

    def test_delete_job_not_found(self, superuser_headers):
        """Test deleting non-existent job."""
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_repository.delete.return_value = False
            mock_repo.return_value = mock_repository

            response = client.delete(
                f"/api/v1/scheduling/jobs/{job_id}", headers=superuser_headers
            )

            assert response.status_code == 404

    def test_delete_job_unauthorized(self, auth_headers):
        """Test job deletion without superuser permissions."""
        job_id = uuid4()

        response = client.delete(
            f"/api/v1/scheduling/jobs/{job_id}", headers=auth_headers
        )

        # Should require superuser permissions
        assert response.status_code in [401, 403]

    def test_list_jobs_success(self, auth_headers):
        """Test successful job listing."""
        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_jobs = [
                Mock(id=uuid4(), job_number="JOB-001", customer_name="Customer A"),
                Mock(id=uuid4(), job_number="JOB-002", customer_name="Customer B"),
                Mock(id=uuid4(), job_number="JOB-003", customer_name="Customer C"),
            ]
            mock_repository.list.return_value = mock_jobs
            mock_repo.return_value = mock_repository

            response = client.get("/api/v1/scheduling/jobs", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()

            assert len(data) == 3
            assert data[0]["job_number"] == "JOB-001"
            assert data[1]["job_number"] == "JOB-002"
            assert data[2]["job_number"] == "JOB-003"

    def test_list_jobs_with_pagination(self, auth_headers):
        """Test job listing with pagination."""
        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_jobs = [
                Mock(
                    id=uuid4(), job_number=f"JOB-{i:03d}", customer_name=f"Customer {i}"
                )
                for i in range(5)
            ]
            mock_repository.list.return_value = mock_jobs[:2]  # First 2 jobs
            mock_repo.return_value = mock_repository

            response = client.get(
                "/api/v1/scheduling/jobs?skip=0&limit=2", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_list_jobs_by_status(self, auth_headers):
        """Test job listing filtered by status."""
        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_jobs = [
                Mock(id=uuid4(), job_number="JOB-001", status=JobStatus.PLANNED),
                Mock(id=uuid4(), job_number="JOB-002", status=JobStatus.RELEASED),
            ]
            mock_repository.find_by_status.return_value = mock_jobs
            mock_repo.return_value = mock_repository

            response = client.get(
                "/api/v1/scheduling/jobs?status=PLANNED,RELEASED", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2


class TestTaskManagementEndpoints:
    """Test task management API endpoints."""

    def test_create_task_success(self, auth_headers, sample_task_data):
        """Test successful task creation."""
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_task_repository"
        ) as mock_repo:
            mock_repository = Mock()
            created_task = Mock()
            created_task.id = uuid4()
            created_task.job_id = job_id
            created_task.sequence_in_job = sample_task_data["sequence_in_job"]
            created_task.status = TaskStatus.PENDING

            mock_repository.create.return_value = created_task
            mock_repo.return_value = mock_repository

            task_data = sample_task_data.copy()
            task_data["job_id"] = str(job_id)

            response = client.post(
                "/api/v1/scheduling/tasks", headers=auth_headers, json=task_data
            )

            assert response.status_code == 201
            data = response.json()

            assert data["job_id"] == str(job_id)
            assert data["sequence_in_job"] == sample_task_data["sequence_in_job"]
            assert data["status"] == TaskStatus.PENDING.value

    def test_create_task_invalid_job_id(self, auth_headers, sample_task_data):
        """Test task creation with invalid job ID."""
        task_data = sample_task_data.copy()
        task_data["job_id"] = "invalid-uuid"

        response = client.post(
            "/api/v1/scheduling/tasks", headers=auth_headers, json=task_data
        )

        assert response.status_code == 422  # Validation error

    def test_get_task_by_id_success(self, auth_headers):
        """Test successful task retrieval."""
        task_id = uuid4()
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_task_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_task = Mock()
            mock_task.id = task_id
            mock_task.job_id = job_id
            mock_task.sequence_in_job = 10
            mock_task.status = TaskStatus.PENDING

            mock_repository.get.return_value = mock_task
            mock_repo.return_value = mock_repository

            response = client.get(
                f"/api/v1/scheduling/tasks/{task_id}", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == str(task_id)
            assert data["job_id"] == str(job_id)
            assert data["sequence_in_job"] == 10

    def test_update_task_status_success(self, auth_headers):
        """Test successful task status update."""
        task_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_task_repository"
        ) as mock_repo:
            mock_repository = Mock()
            updated_task = Mock()
            updated_task.id = task_id
            updated_task.status = TaskStatus.READY

            mock_repository.update_status.return_value = updated_task
            mock_repo.return_value = mock_repository

            response = client.patch(
                f"/api/v1/scheduling/tasks/{task_id}/status",
                headers=auth_headers,
                json={"status": "READY"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == TaskStatus.READY.value

    def test_get_tasks_by_job_success(self, auth_headers):
        """Test retrieving tasks for a specific job."""
        job_id = uuid4()

        with patch(
            "app.infrastructure.database.dependencies.get_task_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_tasks = [
                Mock(
                    id=uuid4(),
                    job_id=job_id,
                    sequence_in_job=10,
                    status=TaskStatus.PENDING,
                ),
                Mock(
                    id=uuid4(),
                    job_id=job_id,
                    sequence_in_job=20,
                    status=TaskStatus.READY,
                ),
                Mock(
                    id=uuid4(),
                    job_id=job_id,
                    sequence_in_job=30,
                    status=TaskStatus.SCHEDULED,
                ),
            ]
            mock_repository.find_by_job_id.return_value = mock_tasks
            mock_repo.return_value = mock_repository

            response = client.get(
                f"/api/v1/scheduling/jobs/{job_id}/tasks", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data) == 3
            # Should be ordered by sequence
            sequences = [task["sequence_in_job"] for task in data]
            assert sequences == [10, 20, 30]

    def test_get_ready_tasks_success(self, auth_headers):
        """Test retrieving ready tasks for scheduling."""
        with patch(
            "app.infrastructure.database.dependencies.get_task_repository"
        ) as mock_repo:
            mock_repository = Mock()
            mock_tasks = [
                Mock(
                    id=uuid4(),
                    job_id=uuid4(),
                    sequence_in_job=10,
                    status=TaskStatus.READY,
                ),
                Mock(
                    id=uuid4(),
                    job_id=uuid4(),
                    sequence_in_job=20,
                    status=TaskStatus.READY,
                ),
            ]
            mock_repository.find_ready_tasks.return_value = mock_tasks
            mock_repo.return_value = mock_repository

            response = client.get(
                "/api/v1/scheduling/tasks/ready", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data) == 2
            for task in data:
                assert task["status"] == TaskStatus.READY.value


class TestScheduleOperationEndpoints:
    """Test schedule operation endpoints."""

    def test_generate_schedule_success(self, auth_headers):
        """Test successful schedule generation."""
        schedule_request = {
            "job_ids": [str(uuid4()), str(uuid4())],
            "optimization_objective": "minimize_makespan",
            "time_limit_seconds": 300,
            "consider_skill_requirements": True,
        }

        with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
            mock_scheduler = Mock()
            mock_solution = {
                "status": "OPTIMAL",
                "objective_value": 1200,
                "makespan": 2880,  # 2 days
                "assignments": [
                    {
                        "job": 0,
                        "task": 10,
                        "operator": 1,
                        "start_time": 420,
                        "end_time": 480,
                    },
                    {
                        "job": 1,
                        "task": 10,
                        "operator": 2,
                        "start_time": 480,
                        "end_time": 540,
                    },
                ],
                "solve_time": 15.5,
            }
            mock_scheduler.solve.return_value = mock_solution
            mock_scheduler_class.return_value = mock_scheduler

            response = client.post(
                "/api/v1/scheduling/generate-schedule",
                headers=auth_headers,
                json=schedule_request,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "OPTIMAL"
            assert data["objective_value"] == 1200
            assert data["makespan"] == 2880
            assert len(data["assignments"]) == 2
            assert data["solve_time"] == 15.5

            # Verify scheduler was called with correct parameters
            mock_scheduler.solve.assert_called_once()

    def test_generate_schedule_infeasible(self, auth_headers):
        """Test schedule generation when problem is infeasible."""
        schedule_request = {
            "job_ids": [str(uuid4())],
            "optimization_objective": "minimize_makespan",
        }

        with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
            mock_scheduler = Mock()
            mock_solution = {
                "status": "INFEASIBLE",
                "reason": "Due dates too tight for task requirements",
            }
            mock_scheduler.solve.return_value = mock_solution
            mock_scheduler_class.return_value = mock_scheduler

            response = client.post(
                "/api/v1/scheduling/generate-schedule",
                headers=auth_headers,
                json=schedule_request,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "INFEASIBLE"
            assert "reason" in data

    def test_generate_schedule_timeout(self, auth_headers):
        """Test schedule generation with timeout."""
        schedule_request = {
            "job_ids": [str(uuid4())],
            "time_limit_seconds": 1,  # Very short timeout
        }

        with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
            mock_scheduler = Mock()
            mock_solution = {
                "status": "TIMEOUT",
                "best_objective": 1500,
                "solve_time": 1.0,
                "assignments": [],
            }
            mock_scheduler.solve.return_value = mock_solution
            mock_scheduler_class.return_value = mock_scheduler

            response = client.post(
                "/api/v1/scheduling/generate-schedule",
                headers=auth_headers,
                json=schedule_request,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "TIMEOUT"
            assert data["solve_time"] >= 1.0

    def test_validate_schedule_success(self, auth_headers):
        """Test successful schedule validation."""
        schedule_data = {
            "assignments": [
                {
                    "task_id": str(uuid4()),
                    "operator_id": str(uuid4()),
                    "machine_id": str(uuid4()),
                    "start_time": "2024-01-01T08:00:00",
                    "end_time": "2024-01-01T10:00:00",
                }
            ]
        }

        with patch(
            "app.domain.scheduling.services.constraint_validation_service.ConstraintValidationService"
        ) as mock_service:
            mock_validator = Mock()
            mock_validator.validate_schedule.return_value = []  # No violations
            mock_service.return_value = mock_validator

            response = client.post(
                "/api/v1/scheduling/validate-schedule",
                headers=auth_headers,
                json=schedule_data,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["is_valid"] is True
            assert data["violations"] == []
            assert data["message"] == "Schedule is valid"

    def test_validate_schedule_with_violations(self, auth_headers):
        """Test schedule validation with constraint violations."""
        schedule_data = {
            "assignments": [
                {
                    "task_id": str(uuid4()),
                    "operator_id": str(uuid4()),
                    "machine_id": str(uuid4()),
                    "start_time": "2024-01-01T18:00:00",  # Outside business hours
                    "end_time": "2024-01-01T20:00:00",
                }
            ]
        }

        with patch(
            "app.domain.scheduling.services.constraint_validation_service.ConstraintValidationService"
        ) as mock_service:
            mock_validator = Mock()
            mock_validator.validate_schedule.return_value = [
                "Task scheduled outside business hours (18:00-20:00)"
            ]
            mock_service.return_value = mock_validator

            response = client.post(
                "/api/v1/scheduling/validate-schedule",
                headers=auth_headers,
                json=schedule_data,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["is_valid"] is False
            assert len(data["violations"]) == 1
            assert "outside business hours" in data["violations"][0]


class TestSchedulingWorkflowEndpoints:
    """Test complete scheduling workflow scenarios."""

    def test_complete_scheduling_workflow(
        self, auth_headers, sample_job_data, sample_task_data
    ):
        """Test complete workflow from job creation to scheduling."""
        # Step 1: Create job
        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_job_repo:
            mock_repository = Mock()
            created_job = Mock()
            job_id = uuid4()
            created_job.id = job_id
            created_job.job_number = sample_job_data["job_number"]
            created_job.status = JobStatus.PLANNED

            mock_repository.create.return_value = created_job
            mock_job_repo.return_value = mock_repository

            job_response = client.post(
                "/api/v1/scheduling/jobs", headers=auth_headers, json=sample_job_data
            )

            assert job_response.status_code == 201

        # Step 2: Add tasks to job
        with patch(
            "app.infrastructure.database.dependencies.get_task_repository"
        ) as mock_task_repo:
            mock_repository = Mock()
            task_data = sample_task_data.copy()
            task_data["job_id"] = str(job_id)

            created_task = Mock()
            created_task.id = uuid4()
            created_task.job_id = job_id
            created_task.status = TaskStatus.PENDING

            mock_repository.create.return_value = created_task
            mock_task_repo.return_value = mock_repository

            task_response = client.post(
                "/api/v1/scheduling/tasks", headers=auth_headers, json=task_data
            )

            assert task_response.status_code == 201

        # Step 3: Generate schedule
        with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
            mock_scheduler = Mock()
            mock_solution = {
                "status": "OPTIMAL",
                "assignments": [
                    {
                        "job": 0,
                        "task": 10,
                        "operator": 1,
                        "start_time": 420,
                        "end_time": 480,
                    }
                ],
                "solve_time": 5.0,
            }
            mock_scheduler.solve.return_value = mock_solution
            mock_scheduler_class.return_value = mock_scheduler

            schedule_request = {
                "job_ids": [str(job_id)],
                "optimization_objective": "minimize_makespan",
            }

            schedule_response = client.post(
                "/api/v1/scheduling/generate-schedule",
                headers=auth_headers,
                json=schedule_request,
            )

            assert schedule_response.status_code == 200
            schedule_data = schedule_response.json()
            assert schedule_data["status"] == "OPTIMAL"

    def test_rush_order_workflow(self, auth_headers, sample_job_data):
        """Test rush order handling workflow."""
        # Create rush order with tight deadline
        rush_job_data = sample_job_data.copy()
        rush_job_data["job_number"] = "RUSH-ORDER-001"
        rush_job_data["priority"] = "URGENT"
        rush_job_data["due_date"] = (
            datetime.utcnow() + timedelta(days=1)
        ).isoformat()  # Tomorrow!

        with patch(
            "app.infrastructure.database.dependencies.get_job_repository"
        ) as mock_repo:
            mock_repository = Mock()
            created_job = Mock()
            created_job.id = uuid4()
            created_job.job_number = rush_job_data["job_number"]
            created_job.priority = "URGENT"
            created_job.status = JobStatus.PLANNED

            mock_repository.create.return_value = created_job
            mock_repo.return_value = mock_repository

            response = client.post(
                "/api/v1/scheduling/jobs", headers=auth_headers, json=rush_job_data
            )

            assert response.status_code == 201
            data = response.json()
            assert data["priority"] == "URGENT"

    def test_schedule_optimization_comparison(self, auth_headers):
        """Test comparing different optimization objectives."""
        job_ids = [str(uuid4()), str(uuid4())]

        objectives = ["minimize_makespan", "minimize_tardiness", "minimize_cost"]
        results = {}

        for objective in objectives:
            with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
                mock_scheduler = Mock()

                # Mock different results for different objectives
                if objective == "minimize_makespan":
                    mock_solution = {
                        "status": "OPTIMAL",
                        "makespan": 2000,
                        "tardiness": 100,
                    }
                elif objective == "minimize_tardiness":
                    mock_solution = {
                        "status": "OPTIMAL",
                        "makespan": 2200,
                        "tardiness": 50,
                    }
                else:  # minimize_cost
                    mock_solution = {
                        "status": "OPTIMAL",
                        "makespan": 2100,
                        "cost": 1500,
                    }

                mock_scheduler.solve.return_value = mock_solution
                mock_scheduler_class.return_value = mock_scheduler

                schedule_request = {
                    "job_ids": job_ids,
                    "optimization_objective": objective,
                }

                response = client.post(
                    "/api/v1/scheduling/generate-schedule",
                    headers=auth_headers,
                    json=schedule_request,
                )

                assert response.status_code == 200
                results[objective] = response.json()

        # Verify different objectives produce different results
        assert (
            results["minimize_makespan"]["makespan"]
            < results["minimize_tardiness"]["makespan"]
        )
        assert (
            results["minimize_tardiness"]["tardiness"]
            < results["minimize_makespan"]["tardiness"]
        )


class TestSchedulingErrorHandling:
    """Test error handling in scheduling endpoints."""

    def test_invalid_json_request(self, auth_headers):
        """Test handling of invalid JSON requests."""
        response = client.post(
            "/api/v1/scheduling/jobs",
            headers=auth_headers,
            data="invalid json",  # Not JSON
        )

        assert response.status_code == 422

    def test_missing_required_fields(self, auth_headers):
        """Test handling of missing required fields."""
        incomplete_job_data = {
            "customer_name": "Test Customer"
            # Missing required fields: job_number, due_date
        }

        response = client.post(
            "/api/v1/scheduling/jobs", headers=auth_headers, json=incomplete_job_data
        )

        assert response.status_code == 422
        data = response.json()

        # Should specify which fields are missing
        error_detail = str(data["detail"])
        assert "job_number" in error_detail or "due_date" in error_detail

    def test_solver_exception_handling(self, auth_headers):
        """Test handling of solver exceptions."""
        schedule_request = {"job_ids": [str(uuid4())]}

        with patch("app.core.solver.HFFSScheduler") as mock_scheduler_class:
            mock_scheduler = Mock()
            mock_scheduler.solve.side_effect = Exception("Solver crashed unexpectedly")
            mock_scheduler_class.return_value = mock_scheduler

            response = client.post(
                "/api/v1/scheduling/generate-schedule",
                headers=auth_headers,
                json=schedule_request,
            )

            assert response.status_code == 500
            data = response.json()
            assert "internal server error" in data["detail"].lower()

    def test_large_request_handling(self, auth_headers):
        """Test handling of very large requests."""
        # Create request with many job IDs
        large_request = {
            "job_ids": [str(uuid4()) for _ in range(1000)],  # 1000 jobs
            "optimization_objective": "minimize_makespan",
        }

        # Should either handle gracefully or return appropriate error
        response = client.post(
            "/api/v1/scheduling/generate-schedule",
            headers=auth_headers,
            json=large_request,
            timeout=5.0,  # Short timeout
        )

        # Should either succeed or return appropriate error code
        assert response.status_code in [200, 400, 413, 500, 504]

    def test_concurrent_request_handling(self, auth_headers, sample_job_data):
        """Test handling of concurrent requests."""
        import threading
        import time

        responses = []

        def create_job():
            job_data = sample_job_data.copy()
            job_data["job_number"] = f"CONCURRENT-{threading.current_thread().ident}"

            with patch(
                "app.infrastructure.database.dependencies.get_job_repository"
            ) as mock_repo:
                mock_repository = Mock()
                created_job = Mock()
                created_job.id = uuid4()
                created_job.job_number = job_data["job_number"]

                # Simulate database delay
                time.sleep(0.1)
                mock_repository.create.return_value = created_job
                mock_repo.return_value = mock_repository

                response = client.post(
                    "/api/v1/scheduling/jobs", headers=auth_headers, json=job_data
                )
                responses.append(response.status_code)

        # Create multiple threads
        threads = [threading.Thread(target=create_job) for _ in range(3)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All requests should complete successfully (or with known error codes)
        assert len(responses) == 3
        assert all(code in [200, 201, 400, 500] for code in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
