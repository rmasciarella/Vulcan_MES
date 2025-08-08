"""
Data Integrity and Transaction Rollback Integration Tests

Tests data consistency, transaction safety, and rollback scenarios across
the complete scheduling system with focus on maintaining data integrity
during complex workflows and failure conditions.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, text


class DatabaseIntegrityChecker:
    """Utility for checking database integrity and constraints."""

    def __init__(self, db: Session):
        self.db = db

    def check_referential_integrity(self) -> dict[str, Any]:
        """Check referential integrity constraints."""
        issues = []

        # Check job-task relationships
        orphaned_tasks = self.db.execute(
            text("""
                SELECT t.id, t.job_id
                FROM tasks t
                LEFT JOIN jobs j ON t.job_id = j.id
                WHERE j.id IS NULL
            """)
        ).fetchall()

        if orphaned_tasks:
            issues.append(
                {
                    "type": "orphaned_tasks",
                    "count": len(orphaned_tasks),
                    "details": [dict(row) for row in orphaned_tasks],
                }
            )

        # Check for duplicate job numbers
        duplicate_jobs = self.db.execute(
            text("""
                SELECT job_number, COUNT(*) as count
                FROM jobs
                GROUP BY job_number
                HAVING COUNT(*) > 1
            """)
        ).fetchall()

        if duplicate_jobs:
            issues.append(
                {
                    "type": "duplicate_job_numbers",
                    "count": len(duplicate_jobs),
                    "details": [dict(row) for row in duplicate_jobs],
                }
            )

        # Check task sequence consistency within jobs
        sequence_issues = self.db.execute(
            text("""
                SELECT j.id as job_id, j.job_number,
                       COUNT(t.id) as task_count,
                       MIN(t.sequence_in_job) as min_seq,
                       MAX(t.sequence_in_job) as max_seq
                FROM jobs j
                LEFT JOIN tasks t ON j.id = t.job_id
                GROUP BY j.id, j.job_number
                HAVING COUNT(t.id) > 0 AND (MIN(t.sequence_in_job) <= 0 OR MAX(t.sequence_in_job) > 100)
            """)
        ).fetchall()

        if sequence_issues:
            issues.append(
                {
                    "type": "invalid_task_sequences",
                    "count": len(sequence_issues),
                    "details": [dict(row) for row in sequence_issues],
                }
            )

        return {
            "is_clean": len(issues) == 0,
            "total_issues": len(issues),
            "issues": issues,
        }

    def check_business_rule_consistency(self) -> dict[str, Any]:
        """Check business rule consistency across entities."""
        violations = []

        # Check for jobs with due dates in the past (for new jobs)
        past_due_new_jobs = self.db.execute(
            text("""
                SELECT id, job_number, due_date, status
                FROM jobs
                WHERE due_date < NOW() AND status IN ('PLANNED', 'APPROVED')
                AND created_at > NOW() - INTERVAL '1 hour'
            """)
        ).fetchall()

        if past_due_new_jobs:
            violations.append(
                {
                    "type": "past_due_new_jobs",
                    "count": len(past_due_new_jobs),
                    "details": [dict(row) for row in past_due_new_jobs],
                }
            )

        # Check for completed jobs without actual_end_date
        incomplete_completed_jobs = self.db.execute(
            text("""
                SELECT id, job_number, status, actual_end_date
                FROM jobs
                WHERE status = 'COMPLETED' AND actual_end_date IS NULL
            """)
        ).fetchall()

        if incomplete_completed_jobs:
            violations.append(
                {
                    "type": "completed_jobs_missing_end_date",
                    "count": len(incomplete_completed_jobs),
                    "details": [dict(row) for row in incomplete_completed_jobs],
                }
            )

        # Check for tasks with invalid durations
        invalid_duration_tasks = self.db.execute(
            text("""
                SELECT id, job_id, planned_duration_minutes, setup_duration_minutes
                FROM tasks
                WHERE planned_duration_minutes <= 0 OR setup_duration_minutes < 0
            """)
        ).fetchall()

        if invalid_duration_tasks:
            violations.append(
                {
                    "type": "invalid_task_durations",
                    "count": len(invalid_duration_tasks),
                    "details": [dict(row) for row in invalid_duration_tasks],
                }
            )

        return {
            "is_consistent": len(violations) == 0,
            "total_violations": len(violations),
            "violations": violations,
        }

    def get_table_counts(self) -> dict[str, int]:
        """Get row counts for all main tables."""
        counts = {}

        # Get all table names
        inspector = inspect(self.db.bind)
        table_names = inspector.get_table_names()

        for table_name in table_names:
            try:
                result = self.db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                counts[table_name] = result.scalar()
            except Exception as e:
                counts[table_name] = f"Error: {str(e)}"

        return counts


class TransactionSimulator:
    """Simulates various transaction scenarios for testing."""

    def __init__(self, db: Session):
        self.db = db

    @asynccontextmanager
    async def simulate_transaction_failure(self, failure_point: str):
        """Simulate transaction failure at specific points."""
        original_commit = self.db.commit
        original_rollback = self.db.rollback

        def failing_commit():
            if failure_point == "commit":
                raise OperationalError("Simulated commit failure", None, None, None)
            return original_commit()

        def failing_rollback():
            if failure_point == "rollback":
                raise OperationalError("Simulated rollback failure", None, None, None)
            return original_rollback()

        self.db.commit = failing_commit
        self.db.rollback = failing_rollback

        try:
            yield
        finally:
            self.db.commit = original_commit
            self.db.rollback = original_rollback


@pytest.fixture
def integrity_checker(db: Session):
    """Provide database integrity checker."""
    return DatabaseIntegrityChecker(db)


@pytest.fixture
def transaction_simulator(db: Session):
    """Provide transaction simulator."""
    return TransactionSimulator(db)


@pytest.mark.e2e
@pytest.mark.data_integrity
class TestDataIntegrityE2E:
    """Test data integrity and transaction safety in workflows."""

    async def test_transaction_atomicity_job_creation(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        integrity_checker: DatabaseIntegrityChecker,
    ):
        """Test that job creation transactions are atomic."""

        # Get initial state
        initial_counts = integrity_checker.get_table_counts()
        integrity_checker.check_referential_integrity()

        # Test successful transaction atomicity
        job_data = {
            "job_number": "ATOMIC-SUCCESS-001",
            "customer_name": "Atomicity Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Verify job was created atomically
        final_counts = integrity_checker.get_table_counts()
        job_count_increase = final_counts.get("jobs", 0) - initial_counts.get("jobs", 0)
        assert job_count_increase == 1, "Exactly one job should be created"

        # Add tasks to test atomic task creation
        tasks_data = [
            {
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 120,
                "setup_duration_minutes": 20,
            },
            {
                "operation_id": str(uuid4()),
                "sequence_in_job": 20,
                "planned_duration_minutes": 90,
                "setup_duration_minutes": 15,
            },
            {
                "operation_id": str(uuid4()),
                "sequence_in_job": 30,
                "planned_duration_minutes": 60,
                "setup_duration_minutes": 10,
            },
        ]

        pre_task_counts = integrity_checker.get_table_counts()

        # Create all tasks
        created_tasks = []
        for task_data in tasks_data:
            response = client.post(
                f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
            )
            assert response.status_code == 201
            task = response.json()
            created_tasks.append(task)

        # Verify all tasks were created atomically
        post_task_counts = integrity_checker.get_table_counts()
        task_count_increase = post_task_counts.get("tasks", 0) - pre_task_counts.get(
            "tasks", 0
        )
        assert task_count_increase == 3, "Exactly three tasks should be created"

        # Verify referential integrity maintained
        final_integrity = integrity_checker.check_referential_integrity()
        assert final_integrity[
            "is_clean"
        ], f"Integrity issues: {final_integrity['issues']}"

        # Verify business rule consistency
        business_consistency = integrity_checker.check_business_rule_consistency()
        assert business_consistency[
            "is_consistent"
        ], f"Business rule violations: {business_consistency['violations']}"

    async def test_transaction_rollback_on_constraint_violation(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        integrity_checker: DatabaseIntegrityChecker,
    ):
        """Test that constraint violations trigger proper rollback."""

        initial_counts = integrity_checker.get_table_counts()

        # Create valid job first
        job_data = {
            "job_number": "ROLLBACK-TEST-001",
            "customer_name": "Rollback Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=8)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Try to create duplicate job (should fail and rollback)
        duplicate_job_data = {
            "job_number": "ROLLBACK-TEST-001",  # Same job number
            "customer_name": "Duplicate Job Customer",
            "due_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
        }

        response = client.post(
            "/api/v1/jobs/", json=duplicate_job_data, headers=auth_headers
        )
        # Should fail due to unique constraint on job_number
        assert response.status_code in [400, 422, 409]

        # Verify no partial data was left behind
        post_failure_counts = integrity_checker.get_table_counts()
        job_count_increase = post_failure_counts.get("jobs", 0) - initial_counts.get(
            "jobs", 0
        )
        assert job_count_increase == 1, "Only the successful job should exist"

        # Test constraint violation with tasks
        # Create task with invalid sequence (should rollback)
        invalid_task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": -5,  # Invalid negative sequence
            "planned_duration_minutes": 60,
        }

        pre_invalid_task_counts = integrity_checker.get_table_counts()

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/",
            json=invalid_task_data,
            headers=auth_headers,
        )
        # Should fail validation
        assert response.status_code in [400, 422]

        # Verify no task was created
        post_invalid_task_counts = integrity_checker.get_table_counts()
        task_count_change = post_invalid_task_counts.get(
            "tasks", 0
        ) - pre_invalid_task_counts.get("tasks", 0)
        assert task_count_change == 0, "No task should be created for invalid data"

        # Verify integrity still maintained
        integrity_check = integrity_checker.check_referential_integrity()
        assert integrity_check[
            "is_clean"
        ], f"Integrity compromised: {integrity_check['issues']}"

    async def test_concurrent_transaction_isolation(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        integrity_checker: DatabaseIntegrityChecker,
    ):
        """Test transaction isolation under concurrent operations."""

        # Create base job for concurrent updates
        job_data = {
            "job_number": "ISOLATION-TEST-001",
            "customer_name": "Isolation Test Customer",
            "quantity": 10,
            "due_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Define concurrent operations that could cause isolation issues
        def update_job_priority(priority: str, notes: str) -> dict[str, Any]:
            """Update job priority and notes."""
            update_data = {
                "priority": priority,
                "notes": f"Updated with priority {priority}: {notes}",
            }

            try:
                response = client.patch(
                    f"/api/v1/jobs/{job_id}", json=update_data, headers=auth_headers
                )
                return {
                    "success": response.status_code == 200,
                    "status": response.status_code,
                    "priority": priority,
                    "response": response.json()
                    if response.status_code == 200
                    else None,
                }
            except Exception as e:
                return {"success": False, "error": str(e), "priority": priority}

        def update_job_quantity(new_quantity: int) -> dict[str, Any]:
            """Update job quantity."""
            update_data = {"quantity": new_quantity}

            try:
                response = client.patch(
                    f"/api/v1/jobs/{job_id}", json=update_data, headers=auth_headers
                )
                return {
                    "success": response.status_code == 200,
                    "status": response.status_code,
                    "quantity": new_quantity,
                    "response": response.json()
                    if response.status_code == 200
                    else None,
                }
            except Exception as e:
                return {"success": False, "error": str(e), "quantity": new_quantity}

        # Execute concurrent updates
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            # Submit concurrent operations
            futures = [
                executor.submit(update_job_priority, "HIGH", "Priority update 1"),
                executor.submit(update_job_priority, "URGENT", "Priority update 2"),
                executor.submit(update_job_quantity, 15),
                executor.submit(update_job_quantity, 20),
                executor.submit(update_job_priority, "NORMAL", "Priority update 3"),
                executor.submit(update_job_quantity, 25),
            ]

            # Collect results
            results = [future.result(timeout=10) for future in futures]

        # Analyze results
        successful_updates = [r for r in results if r["success"]]
        [r for r in results if not r["success"]]

        # At least some updates should succeed
        assert (
            len(successful_updates) >= 3
        ), f"Expected at least 3 successful updates, got {len(successful_updates)}"

        # Verify final state consistency
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        final_job = response.json()

        # Final job should have consistent state
        assert final_job["priority"] in ["LOW", "NORMAL", "HIGH", "URGENT"]
        assert final_job["quantity"] >= 10  # Should be at least original quantity
        assert final_job["job_number"] == "ISOLATION-TEST-001"

        # Check that integrity is maintained
        integrity_check = integrity_checker.check_referential_integrity()
        assert integrity_check[
            "is_clean"
        ], f"Concurrent updates caused integrity issues: {integrity_check['issues']}"

    async def test_cascading_delete_integrity(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        integrity_checker: DatabaseIntegrityChecker,
    ):
        """Test cascading deletes maintain referential integrity."""

        # Create job with multiple tasks
        job_data = {
            "job_number": "CASCADE-DELETE-001",
            "customer_name": "Cascade Delete Test",
            "due_date": (datetime.utcnow() + timedelta(days=9)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Add multiple tasks
        task_ids = []
        for i in range(5):
            task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": (i + 1) * 10,
                "planned_duration_minutes": 60 + (i * 15),
                "setup_duration_minutes": 10 + (i * 2),
            }

            response = client.post(
                f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=auth_headers
            )
            assert response.status_code == 201
            task = response.json()
            task_ids.append(task["id"])

        # Verify tasks were created
        integrity_checker.get_table_counts()
        expected_tasks = 5

        # Get current task count for this job
        job_tasks_response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert job_tasks_response.status_code == 200
        job_with_tasks = job_tasks_response.json()
        actual_task_count = len(job_with_tasks.get("tasks", []))
        assert actual_task_count == expected_tasks

        # Test individual task deletion first
        response = client.delete(f"/api/v1/tasks/{task_ids[0]}", headers=auth_headers)
        # Task deletion endpoint may not exist, so we test what we can
        if response.status_code == 404:
            # Endpoint doesn't exist, skip individual task deletion test
            pass
        elif response.status_code == 200:
            # Verify task was deleted but job remains
            response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
            assert response.status_code == 200
            updated_job = response.json()
            assert len(updated_job.get("tasks", [])) == expected_tasks - 1

        # Test job deletion (should cascade to tasks)
        response = client.delete(f"/api/v1/jobs/{job_id}", headers=auth_headers)

        if response.status_code == 404:
            # Delete endpoint may not exist, test via status change
            response = client.patch(
                f"/api/v1/jobs/{job_id}/status",
                json={"status": "CANCELLED", "reason": "testing_cascade_behavior"},
                headers=auth_headers,
            )
            assert response.status_code == 200
        elif response.status_code == 200:
            # Job was deleted, verify cascading worked
            # Try to access deleted job
            response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
            assert response.status_code == 404, "Job should be deleted"

            # Check that orphaned tasks don't exist
            integrity_check = integrity_checker.check_referential_integrity()
            assert integrity_check[
                "is_clean"
            ], f"Cascading delete left orphaned data: {integrity_check['issues']}"

    async def test_data_consistency_during_schedule_optimization(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        integrity_checker: DatabaseIntegrityChecker,
    ):
        """Test data consistency during complex schedule optimization."""

        # Create multiple jobs for complex optimization
        jobs_data = [
            {
                "job_number": f"CONSISTENCY-{i+1:03d}",
                "customer_name": f"Consistency Customer {i+1}",
                "priority": ["NORMAL", "HIGH", "URGENT"][i % 3],
                "due_date": (datetime.utcnow() + timedelta(days=3 + i)).isoformat(),
            }
            for i in range(8)
        ]

        created_jobs = []
        for job_data in jobs_data:
            response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
            assert response.status_code == 201
            job = response.json()
            created_jobs.append(job)

            # Add tasks with dependencies
            for j in range(3):
                task_data = {
                    "operation_id": str(uuid4()),
                    "sequence_in_job": (j + 1) * 10,
                    "planned_duration_minutes": 90 + (j * 20),
                    "setup_duration_minutes": 15 + (j * 3),
                    "skill_requirements": [
                        {
                            "skill_code": f"SKILL_{j+1}",
                            "required_level": ["BASIC", "INTERMEDIATE", "ADVANCED"][j],
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

            # Release job for scheduling
            response = client.patch(
                f"/api/v1/jobs/{job['id']}/status",
                json={"status": "RELEASED"},
                headers=auth_headers,
            )
            assert response.status_code == 200

        # Check initial integrity
        pre_optimization_integrity = integrity_checker.check_referential_integrity()
        assert pre_optimization_integrity[
            "is_clean"
        ], "Data should be clean before optimization"

        pre_optimization_business = integrity_checker.check_business_rule_consistency()
        assert pre_optimization_business[
            "is_consistent"
        ], "Business rules should be consistent before optimization"

        # Perform complex optimization
        schedule_data = {
            "name": "Data Consistency Test Schedule",
            "job_ids": [job["id"] for job in created_jobs],
            "start_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=15)).isoformat(),
            "optimization_parameters": {
                "minimize_makespan": True,
                "minimize_tardiness": True,
                "resource_utilization_weight": 0.4,
                "priority_weight": 0.6,
            },
            "constraints": {
                "max_operators_per_task": 2,
                "min_setup_time_minutes": 10,
                "required_skills_matching": True,
            },
        }

        response = client.post(
            "/api/v1/schedules/optimize", json=schedule_data, headers=auth_headers
        )

        if response.status_code == 201:
            schedule_result = response.json()
            schedule_id = schedule_result["schedule"]["id"]

            # Check integrity after optimization
            post_optimization_integrity = (
                integrity_checker.check_referential_integrity()
            )
            assert post_optimization_integrity[
                "is_clean"
            ], f"Optimization broke referential integrity: {post_optimization_integrity['issues']}"

            post_optimization_business = (
                integrity_checker.check_business_rule_consistency()
            )
            assert post_optimization_business[
                "is_consistent"
            ], f"Optimization violated business rules: {post_optimization_business['violations']}"

            # Verify schedule data consistency
            response = client.get(
                f"/api/v1/schedules/{schedule_id}", headers=auth_headers
            )
            assert response.status_code == 200
            schedule = response.json()

            # All original jobs should be in the schedule
            assert len(schedule["job_ids"]) == len(created_jobs)
            assert set(schedule["job_ids"]) == {job["id"] for job in created_jobs}

            # Validate schedule
            response = client.get(
                f"/api/v1/schedules/{schedule_id}/validate", headers=auth_headers
            )
            if response.status_code == 200:
                validation = response.json()
                # Should have minimal violations for a well-formed dataset
                violation_count = len(validation.get("violations", []))
                assert (
                    violation_count <= 2
                ), f"Too many violations in optimized schedule: {violation_count}"

        else:
            # Optimization failed, but data should still be consistent
            post_failed_optimization_integrity = (
                integrity_checker.check_referential_integrity()
            )
            assert post_failed_optimization_integrity[
                "is_clean"
            ], f"Failed optimization left integrity issues: {post_failed_optimization_integrity['issues']}"

    async def test_audit_trail_consistency(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        integrity_checker: DatabaseIntegrityChecker,
    ):
        """Test that audit trail maintains consistency during operations."""

        # Create job with audit tracking
        job_data = {
            "job_number": "AUDIT-CONSISTENCY-001",
            "customer_name": "Audit Test Customer",
            "created_by": "test_user",
            "due_date": (datetime.utcnow() + timedelta(days=6)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Track operations that should be audited
        operations = [
            {
                "action": "status_change",
                "data": {"status": "APPROVED", "reason": "manager_approval"},
            },
            {
                "action": "priority_change",
                "data": {"priority": "HIGH", "reason": "customer_request"},
            },
            {"action": "schedule_update", "data": {"notes": "Scheduled for next week"}},
        ]

        # Perform operations
        for operation in operations:
            response = client.patch(
                f"/api/v1/jobs/{job_id}", json=operation["data"], headers=auth_headers
            )
            # Operations may or may not succeed based on business rules
            # but they should not break data consistency

        # Check audit trail consistency (if audit endpoints exist)
        response = client.get(f"/api/v1/audit/job/{job_id}", headers=auth_headers)

        if response.status_code == 200:
            audit_log = response.json()

            # Verify audit entries are consistent
            assert "entries" in audit_log
            entries = audit_log["entries"]

            # Should have at least creation entry
            assert len(entries) >= 1

            # Each entry should have required fields
            for entry in entries:
                assert "timestamp" in entry
                assert "action" in entry
                assert "entity_type" in entry
                assert "entity_id" in entry

                # Timestamps should be in order
                if len(entries) > 1:
                    timestamps = [entry["timestamp"] for entry in entries]
                    sorted_timestamps = sorted(timestamps)
                    assert (
                        timestamps == sorted_timestamps
                    ), "Audit entries should be in chronological order"

        elif response.status_code == 404:
            # Audit endpoint doesn't exist, verify at least basic consistency
            pass

        # Verify overall integrity remains intact
        final_integrity = integrity_checker.check_referential_integrity()
        assert final_integrity[
            "is_clean"
        ], f"Audit operations broke integrity: {final_integrity['issues']}"

    async def test_data_recovery_after_partial_failure(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db: Session,
        integrity_checker: DatabaseIntegrityChecker,
    ):
        """Test data recovery and cleanup after partial transaction failures."""

        integrity_checker.get_table_counts()

        # Create job successfully
        job_data = {
            "job_number": "RECOVERY-TEST-001",
            "customer_name": "Recovery Test Customer",
            "due_date": (datetime.utcnow() + timedelta(days=8)).isoformat(),
        }

        response = client.post("/api/v1/jobs/", json=job_data, headers=auth_headers)
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Simulate partial failure scenario
        # Create valid task first
        valid_task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 10,
            "planned_duration_minutes": 120,
            "setup_duration_minutes": 20,
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/", json=valid_task_data, headers=auth_headers
        )
        assert response.status_code == 201
        valid_task = response.json()

        # Now try to create invalid task (should not affect valid one)
        invalid_task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 0,  # Invalid sequence
            "planned_duration_minutes": -50,  # Invalid duration
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/",
            json=invalid_task_data,
            headers=auth_headers,
        )
        assert response.status_code in [400, 422]  # Should fail validation

        # Verify valid data still exists and invalid data was not persisted
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        job_with_tasks = response.json()

        # Should still have the valid task
        tasks = job_with_tasks.get("tasks", [])
        assert len(tasks) == 1
        assert tasks[0]["id"] == valid_task["id"]
        assert tasks[0]["sequence_in_job"] == 10

        # Test recovery by fixing the invalid data
        corrected_task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 20,  # Valid sequence
            "planned_duration_minutes": 90,  # Valid duration
            "setup_duration_minutes": 15,
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/",
            json=corrected_task_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        response.json()

        # Verify recovery successful
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        final_job = response.json()

        final_tasks = final_job.get("tasks", [])
        assert len(final_tasks) == 2
        task_sequences = [task["sequence_in_job"] for task in final_tasks]
        assert set(task_sequences) == {10, 20}

        # Verify overall system integrity
        final_integrity = integrity_checker.check_referential_integrity()
        assert final_integrity[
            "is_clean"
        ], f"Recovery left integrity issues: {final_integrity['issues']}"

        final_business_consistency = integrity_checker.check_business_rule_consistency()
        assert final_business_consistency[
            "is_consistent"
        ], f"Recovery violated business rules: {final_business_consistency['violations']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
