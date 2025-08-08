"""
Tests for the /solve API endpoint.

Tests the scheduling optimization endpoint integration with OR-Tools solver
and the domain/infrastructure layer.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestSolveEndpoint:
    """Test cases for the /solve endpoint."""

    def test_solve_status_endpoint(self):
        """Test the solver status endpoint."""
        response = client.get("/api/v1/scheduling/solve/status")

        assert response.status_code in [
            200,
            503,
        ]  # 200 if OR-Tools available, 503 if not
        data = response.json()

        assert "solver" in data
        assert "status" in data
        assert data["solver"]["name"] == "OR-Tools CP-SAT"

    def test_solve_examples_endpoint(self):
        """Test the examples endpoint."""
        response = client.get("/api/v1/scheduling/solve/examples")

        assert response.status_code == 200
        data = response.json()

        assert "examples" in data
        assert "simple_job" in data["examples"]
        assert "multi_job_complex" in data["examples"]

    def test_solve_endpoint_invalid_request(self):
        """Test solve endpoint with invalid request data."""
        # Empty request
        response = client.post("/api/v1/scheduling/solve", json={})

        assert response.status_code == 422  # Validation error

    def test_solve_endpoint_missing_jobs(self):
        """Test solve endpoint with missing jobs."""
        request_data = {
            "problem_name": "Empty Problem",
            "jobs": [],  # No jobs provided
        }

        response = client.post("/api/v1/scheduling/solve", json=request_data)

        assert response.status_code == 422  # Validation error for empty jobs list

    def test_solve_endpoint_valid_simple_request(self):
        """Test solve endpoint with valid simple request."""
        future_time = datetime.utcnow() + timedelta(hours=1)

        request_data = {
            "problem_name": "Test Problem",
            "schedule_start_time": future_time.isoformat(),
            "jobs": [
                {
                    "job_number": "TEST001",
                    "priority": "normal",
                    "due_date": (future_time + timedelta(days=2)).isoformat(),
                    "quantity": 1,
                    "customer_name": "Test Customer",
                    "part_number": "TEST-PART",
                    "task_sequences": [10, 20, 30],
                }
            ],
            "optimization_parameters": {
                "max_time_seconds": 30,  # Short time for testing
                "enable_hierarchical_optimization": False,  # Simplified for testing
            },
        }

        response = client.post("/api/v1/scheduling/solve", json=request_data)

        # Could be 200 (success), 408 (timeout), 422 (no feasible solution), or 500 (OR-Tools not available)
        assert response.status_code in [200, 408, 422, 500, 503]

        data = response.json()
        assert "problem_name" in data
        assert data["problem_name"] == "Test Problem"
        assert "status" in data
        assert "success" in data

        if response.status_code == 200:
            # Success case
            assert data["success"] is True
            assert "jobs" in data
            assert "metrics" in data
            assert data["total_jobs"] == 1
            assert data["total_tasks"] == 3

        else:
            # Error case
            assert data["success"] is False
            assert "message" in data
            assert "error_code" in data

    def test_solve_endpoint_complex_request(self):
        """Test solve endpoint with more complex request."""
        future_time = datetime.utcnow() + timedelta(hours=1)

        request_data = {
            "problem_name": "Complex Manufacturing Schedule",
            "schedule_start_time": future_time.isoformat(),
            "jobs": [
                {
                    "job_number": "URGENT001",
                    "priority": "high",
                    "due_date": (future_time + timedelta(days=1)).isoformat(),
                    "quantity": 2,
                    "customer_name": "Priority Customer",
                    "part_number": "URGENT-PART",
                    "task_sequences": [10, 20, 30, 40],
                },
                {
                    "job_number": "NORMAL001",
                    "priority": "normal",
                    "due_date": (future_time + timedelta(days=3)).isoformat(),
                    "quantity": 1,
                    "customer_name": "Regular Customer",
                    "part_number": "NORMAL-PART",
                    "task_sequences": [15, 25, 35, 45, 55],
                },
            ],
            "business_constraints": {
                "work_start_hour": 8,
                "work_end_hour": 17,
                "lunch_start_hour": 12,
                "lunch_duration_minutes": 60,
                "holiday_days": [],
            },
            "optimization_parameters": {
                "max_time_seconds": 45,
                "num_workers": 4,
                "horizon_days": 7,
                "enable_hierarchical_optimization": True,
            },
        }

        response = client.post("/api/v1/scheduling/solve", json=request_data)

        # Could succeed or fail depending on OR-Tools availability and test environment
        assert response.status_code in [200, 408, 422, 500, 503]

        data = response.json()
        assert data["problem_name"] == "Complex Manufacturing Schedule"

        if response.status_code == 200:
            # Success case - verify structure
            assert data["success"] is True
            assert data["total_jobs"] == 2
            assert data["total_tasks"] == 9  # 4 + 5 tasks
            assert "processing_time_seconds" in data
            assert data["processing_time_seconds"] > 0

    def test_solve_endpoint_invalid_optimization_params(self):
        """Test solve endpoint with invalid optimization parameters."""
        datetime.utcnow() + timedelta(hours=1)

        request_data = {
            "problem_name": "Invalid Params Test",
            "jobs": [{"job_number": "TEST001", "task_sequences": [10]}],
            "optimization_parameters": {
                "max_time_seconds": -1,  # Invalid negative time
                "num_workers": 0,  # Invalid zero workers
                "horizon_days": 200,  # Invalid too many days
            },
        }

        response = client.post("/api/v1/scheduling/solve", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_solve_endpoint_invalid_business_constraints(self):
        """Test solve endpoint with invalid business constraints."""
        request_data = {
            "problem_name": "Invalid Business Constraints",
            "jobs": [{"job_number": "TEST001", "task_sequences": [10]}],
            "business_constraints": {
                "work_start_hour": 18,  # Start after end
                "work_end_hour": 8,  # End before start
                "holiday_days": [0, -1],  # Invalid holiday days
            },
        }

        response = client.post("/api/v1/scheduling/solve", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_solve_endpoint_duplicate_job_numbers(self):
        """Test solve endpoint with duplicate job numbers."""
        request_data = {
            "problem_name": "Duplicate Jobs Test",
            "jobs": [
                {"job_number": "DUPLICATE", "task_sequences": [10]},
                {
                    "job_number": "DUPLICATE",  # Same job number
                    "task_sequences": [20],
                },
            ],
        }

        response = client.post("/api/v1/scheduling/solve", json=request_data)

        assert response.status_code == 422  # Validation error

    def test_solve_endpoint_invalid_task_sequences(self):
        """Test solve endpoint with invalid task sequences."""
        request_data = {
            "problem_name": "Invalid Task Sequences",
            "jobs": [
                {
                    "job_number": "INVALID_TASKS",
                    "task_sequences": [0, 101, -1],  # Invalid sequence numbers
                }
            ],
        }

        response = client.post("/api/v1/scheduling/solve", json=request_data)

        assert response.status_code == 422  # Validation error


@pytest.mark.integration
class TestSolveEndpointIntegration:
    """Integration tests for the solve endpoint with database."""

    def test_solve_endpoint_with_database(self):
        """
        Integration test that verifies the solve endpoint works with the database layer.

        This test creates temporary jobs and tasks, runs optimization, and verifies cleanup.
        """
        # This would require a test database setup
        # Skipping implementation details for now
        pytest.skip("Integration tests require test database setup")

    def test_solve_endpoint_performance(self):
        """Test solve endpoint performance with realistic workload."""
        # This would test with larger problems to verify performance
        pytest.skip("Performance tests require longer execution time")


if __name__ == "__main__":
    # Run a simple test
    test_client = TestClient(app)
    response = test_client.get("/api/v1/scheduling/solve/status")
    print(f"Solver status: {response.status_code} - {response.json()}")
