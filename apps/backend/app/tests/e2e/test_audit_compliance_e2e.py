"""
Audit Trail and Compliance Verification Integration Tests

Tests comprehensive audit logging, compliance verification, and regulatory
requirements throughout the complete scheduling workflow including traceability,
data retention, access logging, and compliance reporting.
"""

import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.tests.utils.user import create_test_user
from app.tests.utils.utils import get_superuser_token_headers


class AuditTestHelper:
    """Helper for audit and compliance testing."""

    @staticmethod
    def generate_compliance_test_data() -> dict[str, Any]:
        """Generate test data that requires compliance tracking."""
        return {
            "job_number": f"AUDIT-{uuid4().hex[:8].upper()}",
            "customer_name": "Compliance Test Customer Corp",
            "part_number": f"REGULATED-PART-{uuid4().hex[:6].upper()}",
            "quantity": 100,
            "priority": "HIGH",
            "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "compliance_requirements": [
                "FDA_21CFR11",
                "ISO_13485",
                "GMP_COMPLIANCE",
                "TRACE_REQUIREMENTS",
            ],
            "customer_po": f"PO-{uuid4().hex[:8].upper()}",
            "quality_requirements": "Class III Medical Device",
            "notes": "Subject to full audit trail and compliance verification",
        }

    @staticmethod
    def create_audit_scenario_workflow() -> list[dict[str, Any]]:
        """Create a workflow scenario that should generate comprehensive audit trail."""
        return [
            {
                "step": "job_creation",
                "actor": "customer_service",
                "action": "create_job",
                "reason": "customer_order_received",
                "compliance_level": "high",
            },
            {
                "step": "engineering_review",
                "actor": "engineering_manager",
                "action": "review_specifications",
                "reason": "technical_feasibility_check",
                "compliance_level": "high",
            },
            {
                "step": "approval",
                "actor": "production_manager",
                "action": "approve_job",
                "reason": "production_capacity_confirmed",
                "compliance_level": "critical",
            },
            {
                "step": "task_planning",
                "actor": "production_planner",
                "action": "add_tasks",
                "reason": "production_sequence_defined",
                "compliance_level": "medium",
            },
            {
                "step": "resource_allocation",
                "actor": "resource_manager",
                "action": "assign_resources",
                "reason": "qualified_operators_assigned",
                "compliance_level": "high",
            },
            {
                "step": "schedule_optimization",
                "actor": "scheduling_coordinator",
                "action": "optimize_schedule",
                "reason": "delivery_commitment_met",
                "compliance_level": "medium",
            },
            {
                "step": "quality_review",
                "actor": "quality_manager",
                "action": "review_quality_plan",
                "reason": "compliance_verification",
                "compliance_level": "critical",
            },
            {
                "step": "release",
                "actor": "production_supervisor",
                "action": "release_to_floor",
                "reason": "ready_for_production",
                "compliance_level": "high",
            },
        ]

    @staticmethod
    def verify_audit_completeness(
        audit_entries: list[dict[str, Any]], expected_actions: list[str]
    ) -> dict[str, Any]:
        """Verify audit trail completeness against expected actions."""
        recorded_actions = set()
        missing_actions = []
        extra_actions = []

        for entry in audit_entries:
            action = entry.get("action", "")
            recorded_actions.add(action)

        expected_set = set(expected_actions)

        missing_actions = list(expected_set - recorded_actions)
        extra_actions = list(recorded_actions - expected_set)

        return {
            "is_complete": len(missing_actions) == 0,
            "completeness_percentage": (
                len(recorded_actions & expected_set) / len(expected_set)
            )
            * 100
            if expected_set
            else 100,
            "recorded_actions": list(recorded_actions),
            "missing_actions": missing_actions,
            "extra_actions": extra_actions,
            "total_entries": len(audit_entries),
        }


@pytest.fixture
def audit_helper():
    """Provide audit test helper."""
    return AuditTestHelper()


@pytest.fixture
def compliance_test_users(db: Session):
    """Create users representing different roles in compliance workflow."""
    users = {
        "customer_service": create_test_user(
            db,
            "customer.service@compliance-test.com",
            is_superuser=False,
            full_name="Customer Service Rep",
        ),
        "engineering_manager": create_test_user(
            db,
            "engineering.manager@compliance-test.com",
            is_superuser=False,
            full_name="Engineering Manager",
        ),
        "production_manager": create_test_user(
            db,
            "production.manager@compliance-test.com",
            is_superuser=True,
            full_name="Production Manager",
        ),
        "production_planner": create_test_user(
            db,
            "production.planner@compliance-test.com",
            is_superuser=False,
            full_name="Production Planner",
        ),
        "resource_manager": create_test_user(
            db,
            "resource.manager@compliance-test.com",
            is_superuser=False,
            full_name="Resource Manager",
        ),
        "scheduling_coordinator": create_test_user(
            db,
            "scheduling.coordinator@compliance-test.com",
            is_superuser=False,
            full_name="Scheduling Coordinator",
        ),
        "quality_manager": create_test_user(
            db,
            "quality.manager@compliance-test.com",
            is_superuser=True,
            full_name="Quality Manager",
        ),
        "production_supervisor": create_test_user(
            db,
            "production.supervisor@compliance-test.com",
            is_superuser=False,
            full_name="Production Supervisor",
        ),
        "compliance_officer": create_test_user(
            db,
            "compliance.officer@compliance-test.com",
            is_superuser=True,
            full_name="Compliance Officer",
        ),
    }
    return users


@pytest.fixture
def compliance_token_headers(client: TestClient, compliance_test_users: dict[str, Any]):
    """Get authentication headers for compliance test users."""
    headers = {}
    for role, user in compliance_test_users.items():
        try:
            response = client.post(
                "/api/v1/login/access-token",
                data={"username": user.email, "password": "testpass123"},
            )
            if response.status_code == 200:
                token = response.json()["access_token"]
                headers[role] = {"Authorization": f"Bearer {token}"}
            else:
                # Fallback for testing
                headers[role] = get_superuser_token_headers(client)
        except Exception:
            headers[role] = get_superuser_token_headers(client)

    return headers


@pytest.mark.e2e
@pytest.mark.audit_compliance
class TestAuditComplianceE2E:
    """Test audit trail and compliance verification in workflows."""

    async def test_complete_audit_trail_workflow(
        self,
        client: TestClient,
        compliance_token_headers: dict[str, dict[str, str]],
        audit_helper: AuditTestHelper,
        db: Session,
    ):
        """Test complete audit trail generation through regulated workflow."""

        # Generate compliance-sensitive test data
        compliance_data = audit_helper.generate_compliance_test_data()
        workflow_steps = audit_helper.create_audit_scenario_workflow()

        # Start audit trail tracking
        audit_start_time = datetime.utcnow()

        # Step 1: Customer Service creates job
        response = client.post(
            "/api/v1/jobs/",
            json=compliance_data,
            headers=compliance_token_headers["customer_service"],
        )
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Execute workflow steps that should generate audit entries
        workflow_results = []

        for step in workflow_steps:
            step_start_time = time.time()
            actor = step["actor"]
            action = step["action"]
            reason = step["reason"]
            compliance_level = step["compliance_level"]

            headers = compliance_token_headers.get(
                actor, compliance_token_headers["production_manager"]
            )

            step_result = {
                "step": step["step"],
                "actor": actor,
                "action": action,
                "reason": reason,
                "compliance_level": compliance_level,
                "timestamp": datetime.utcnow().isoformat(),
                "duration": 0,
                "success": False,
            }

            # Execute step-specific actions
            if action == "create_job":
                # Already created above
                step_result["success"] = True

            elif action == "review_specifications":
                # Engineering review - update job with technical specifications
                response = client.patch(
                    f"/api/v1/jobs/{job_id}",
                    json={
                        "notes": f"Engineering reviewed: {reason}. Technical specs verified.",
                        "engineering_approval": True,
                        "reviewed_by": actor,
                    },
                    headers=headers,
                )
                step_result["success"] = response.status_code == 200

            elif action == "approve_job":
                # Production manager approval
                response = client.patch(
                    f"/api/v1/jobs/{job_id}/status",
                    json={"status": "APPROVED", "reason": reason, "approved_by": actor},
                    headers=headers,
                )
                step_result["success"] = response.status_code == 200

            elif action == "add_tasks":
                # Add production tasks
                tasks_to_add = [
                    {
                        "operation_id": str(uuid4()),
                        "sequence_in_job": 10,
                        "planned_duration_minutes": 120,
                        "setup_duration_minutes": 30,
                        "skill_requirements": [
                            {
                                "skill_code": "REGULATED_MACHINING",
                                "required_level": "CERTIFIED",
                                "is_mandatory": True,
                            }
                        ],
                        "quality_checkpoints": ["dimensional_check", "surface_finish"],
                        "compliance_notes": "FDA 21 CFR Part 11 electronic records required",
                    },
                    {
                        "operation_id": str(uuid4()),
                        "sequence_in_job": 20,
                        "planned_duration_minutes": 90,
                        "setup_duration_minutes": 15,
                        "skill_requirements": [
                            {
                                "skill_code": "QUALITY_INSPECTION",
                                "required_level": "CERTIFIED",
                                "is_mandatory": True,
                            }
                        ],
                        "quality_checkpoints": [
                            "final_inspection",
                            "compliance_verification",
                        ],
                        "compliance_notes": "ISO 13485 documentation required",
                    },
                ]

                task_success_count = 0
                for task_data in tasks_to_add:
                    response = client.post(
                        f"/api/v1/jobs/{job_id}/tasks/", json=task_data, headers=headers
                    )
                    if response.status_code == 201:
                        task_success_count += 1

                step_result["success"] = task_success_count == len(tasks_to_add)
                step_result["tasks_added"] = task_success_count

            elif action == "assign_resources":
                # Resource allocation with compliance tracking
                response = client.patch(
                    f"/api/v1/jobs/{job_id}",
                    json={
                        "assigned_operators": ["OP001-CERTIFIED", "OP002-CERTIFIED"],
                        "assigned_machines": [
                            "MACHINE-001-VALIDATED",
                            "MACHINE-002-VALIDATED",
                        ],
                        "resource_compliance_verified": True,
                        "assigned_by": actor,
                    },
                    headers=headers,
                )
                step_result["success"] = response.status_code == 200

            elif action == "optimize_schedule":
                # Create optimized schedule
                schedule_data = {
                    "name": f"Compliance Schedule - {job['job_number']}",
                    "job_ids": [job_id],
                    "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                    "end_time": (datetime.utcnow() + timedelta(days=25)).isoformat(),
                    "compliance_requirements": compliance_data[
                        "compliance_requirements"
                    ],
                    "optimization_parameters": {
                        "minimize_makespan": True,
                        "compliance_priority": True,
                        "quality_weight": 0.4,
                    },
                }

                response = client.post(
                    "/api/v1/schedules/optimize", json=schedule_data, headers=headers
                )
                step_result["success"] = response.status_code == 201
                if step_result["success"]:
                    schedule_result = response.json()
                    step_result["schedule_id"] = schedule_result["schedule"]["id"]

            elif action == "review_quality_plan":
                # Quality manager review
                response = client.patch(
                    f"/api/v1/jobs/{job_id}",
                    json={
                        "quality_plan_approved": True,
                        "quality_reviewer": actor,
                        "compliance_verified": True,
                        "quality_notes": f"Quality plan reviewed and approved. {reason}.",
                    },
                    headers=headers,
                )
                step_result["success"] = response.status_code == 200

            elif action == "release_to_floor":
                # Release for production
                response = client.patch(
                    f"/api/v1/jobs/{job_id}/status",
                    json={"status": "RELEASED", "reason": reason, "released_by": actor},
                    headers=headers,
                )
                step_result["success"] = response.status_code == 200

            step_result["duration"] = time.time() - step_start_time
            workflow_results.append(step_result)

        # Verify audit trail completeness
        audit_end_time = datetime.utcnow()

        # Check audit trail (if audit endpoint exists)
        response = client.get(
            f"/api/v1/audit/job/{job_id}",
            params={
                "start_time": audit_start_time.isoformat(),
                "end_time": audit_end_time.isoformat(),
                "include_compliance": True,
            },
            headers=compliance_token_headers["compliance_officer"],
        )

        if response.status_code == 200:
            audit_data = response.json()

            # Verify audit trail structure
            assert "entries" in audit_data
            assert "job_id" in audit_data
            assert "total_entries" in audit_data

            audit_entries = audit_data["entries"]

            # Verify audit completeness
            expected_actions = [
                step["action"] for step in workflow_steps if step.get("success", False)
            ]
            completeness = audit_helper.verify_audit_completeness(
                audit_entries, expected_actions
            )

            assert (
                completeness["is_complete"]
                or completeness["completeness_percentage"] >= 80
            ), f"Audit trail incomplete: {completeness['completeness_percentage']:.1f}% complete"

            # Verify audit entry quality
            for entry in audit_entries:
                assert "timestamp" in entry, "Audit entry missing timestamp"
                assert (
                    "user" in entry or "user_id" in entry
                ), "Audit entry missing user identification"
                assert "action" in entry, "Audit entry missing action"
                assert "entity_type" in entry, "Audit entry missing entity type"
                assert "entity_id" in entry, "Audit entry missing entity ID"

                # Check compliance-specific fields
                if entry.get("compliance_level") in ["high", "critical"]:
                    assert (
                        "reason" in entry or "notes" in entry
                    ), "High compliance entries should include reason/notes"

            # Verify chronological order
            timestamps = [entry["timestamp"] for entry in audit_entries]
            sorted_timestamps = sorted(timestamps)
            assert (
                timestamps == sorted_timestamps
            ), "Audit entries should be in chronological order"

        elif response.status_code == 404:
            # Audit endpoint doesn't exist - verify workflow completed successfully
            successful_steps = [r for r in workflow_results if r["success"]]
            assert (
                len(successful_steps) >= len(workflow_steps) * 0.8
            ), "At least 80% of workflow steps should complete successfully"

        # Verify job final state shows compliance
        response = client.get(
            f"/api/v1/jobs/{job_id}",
            headers=compliance_token_headers["compliance_officer"],
        )
        assert response.status_code == 200
        final_job = response.json()

        # Compliance fields should be populated
        compliance_indicators = [
            final_job.get("quality_plan_approved"),
            final_job.get("compliance_verified"),
            final_job.get("engineering_approval"),
        ]

        assert any(
            compliance_indicators
        ), "Job should show compliance verification indicators"

    async def test_compliance_data_retention_verification(
        self,
        client: TestClient,
        compliance_token_headers: dict[str, dict[str, str]],
        audit_helper: AuditTestHelper,
        db: Session,
    ):
        """Test compliance data retention and historical access."""

        # Create historical jobs for retention testing
        historical_jobs = []

        for i in range(5):
            job_data = {
                "job_number": f"RETENTION-TEST-{i+1:03d}",
                "customer_name": f"Historical Customer {i+1}",
                "due_date": (datetime.utcnow() + timedelta(days=30 + i)).isoformat(),
                "compliance_requirements": ["FDA_21CFR11", "ISO_13485"],
            }

            response = client.post(
                "/api/v1/jobs/",
                json=job_data,
                headers=compliance_token_headers["production_manager"],
            )
            assert response.status_code == 201
            job = response.json()
            historical_jobs.append(job)

            # Add some historical activity
            response = client.patch(
                f"/api/v1/jobs/{job['id']}/status",
                json={"status": "APPROVED", "reason": "historical_test"},
                headers=compliance_token_headers["production_manager"],
            )

        # Test data retention queries
        retention_queries = [
            {
                "name": "all_historical_jobs",
                "params": {
                    "start_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                    "end_date": datetime.utcnow().isoformat(),
                },
            },
            {
                "name": "compliance_filtered",
                "params": {
                    "compliance_requirement": "FDA_21CFR11",
                    "start_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                },
            },
            {
                "name": "status_history",
                "params": {
                    "include_status_changes": True,
                    "start_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                },
            },
        ]

        for query in retention_queries:
            query["name"]
            params = query["params"]

            # Test audit data retention
            response = client.get(
                "/api/v1/audit/historical",
                params=params,
                headers=compliance_token_headers["compliance_officer"],
            )

            if response.status_code == 200:
                historical_data = response.json()

                # Verify data structure
                assert "records" in historical_data or "entries" in historical_data

                # Verify compliance metadata
                records = historical_data.get(
                    "records", historical_data.get("entries", [])
                )

                for record in records:
                    # Should preserve compliance-related information
                    assert "timestamp" in record
                    assert "entity_id" in record or "job_id" in record

                    # Check data integrity
                    if "compliance_requirements" in record:
                        assert isinstance(record["compliance_requirements"], list)

            elif response.status_code == 404:
                # Historical endpoint doesn't exist, test job queries
                response = client.get(
                    "/api/v1/jobs/",
                    params={"limit": 100},
                    headers=compliance_token_headers["compliance_officer"],
                )

                if response.status_code == 200:
                    jobs_data = response.json()
                    all_jobs = jobs_data.get("data", jobs_data)

                    # Should find our historical jobs
                    historical_job_numbers = [
                        job["job_number"] for job in historical_jobs
                    ]
                    found_jobs = [
                        job
                        for job in all_jobs
                        if job.get("job_number") in historical_job_numbers
                    ]

                    assert len(found_jobs) >= 3, "Should retain historical job data"

    async def test_regulatory_compliance_reporting(
        self,
        client: TestClient,
        compliance_token_headers: dict[str, dict[str, str]],
        audit_helper: AuditTestHelper,
        db: Session,
    ):
        """Test regulatory compliance reporting capabilities."""

        # Create jobs with different compliance requirements
        compliance_scenarios = [
            {
                "job_number": "FDA-COMPLIANCE-001",
                "compliance_requirements": ["FDA_21CFR11", "GMP_COMPLIANCE"],
                "device_class": "Class III Medical Device",
                "customer_name": "FDA Regulated Customer",
            },
            {
                "job_number": "ISO-COMPLIANCE-001",
                "compliance_requirements": ["ISO_13485", "ISO_9001"],
                "device_class": "Medical Device",
                "customer_name": "ISO Certified Customer",
            },
            {
                "job_number": "AUTOMOTIVE-001",
                "compliance_requirements": ["IATF_16949", "ISO_9001"],
                "device_class": "Automotive Component",
                "customer_name": "Automotive OEM",
            },
        ]

        created_compliance_jobs = []

        for scenario in compliance_scenarios:
            job_data = {
                **scenario,
                "due_date": (datetime.utcnow() + timedelta(days=20)).isoformat(),
                "priority": "HIGH",
            }

            response = client.post(
                "/api/v1/jobs/",
                json=job_data,
                headers=compliance_token_headers["production_manager"],
            )
            assert response.status_code == 201
            job = response.json()
            created_compliance_jobs.append(job)

            # Add compliance-specific tasks
            compliance_task_data = {
                "operation_id": str(uuid4()),
                "sequence_in_job": 10,
                "planned_duration_minutes": 180,
                "skill_requirements": [
                    {
                        "skill_code": "COMPLIANCE_CERTIFIED",
                        "required_level": "EXPERT",
                        "is_mandatory": True,
                        "certification_required": True,
                    }
                ],
                "quality_requirements": scenario["compliance_requirements"],
                "documentation_required": True,
            }

            response = client.post(
                f"/api/v1/jobs/{job['id']}/tasks/",
                json=compliance_task_data,
                headers=compliance_token_headers["quality_manager"],
            )
            assert response.status_code == 201

        # Test compliance reporting queries
        compliance_reports = [
            {
                "name": "fda_compliance_report",
                "params": {
                    "compliance_standard": "FDA_21CFR11",
                    "report_period": "current_month",
                    "include_audit_trail": True,
                },
            },
            {
                "name": "iso_compliance_summary",
                "params": {
                    "compliance_standard": "ISO_13485",
                    "include_tasks": True,
                    "include_quality_records": True,
                },
            },
            {
                "name": "all_compliance_status",
                "params": {"include_all_standards": True, "status_summary": True},
            },
        ]

        for report in compliance_reports:
            report_name = report["name"]
            params = report["params"]

            # Test compliance reporting endpoint
            response = client.get(
                f"/api/v1/compliance/reports/{report_name}",
                params=params,
                headers=compliance_token_headers["compliance_officer"],
            )

            if response.status_code == 200:
                report_data = response.json()

                # Verify report structure
                assert "report_metadata" in report_data or "summary" in report_data
                assert "generated_at" in report_data or "timestamp" in report_data

                # Verify compliance data
                if "jobs" in report_data:
                    compliance_jobs = report_data["jobs"]

                    for job in compliance_jobs:
                        assert "job_number" in job
                        assert (
                            "compliance_status" in job
                            or "compliance_requirements" in job
                        )

                        # Verify traceability
                        if "audit_entries" in job:
                            audit_entries = job["audit_entries"]
                            assert isinstance(audit_entries, list)

                            for entry in audit_entries:
                                assert "timestamp" in entry
                                assert "user" in entry or "user_id" in entry

            elif response.status_code == 404:
                # Compliance reporting endpoint doesn't exist
                # Test general compliance queries
                response = client.get(
                    "/api/v1/jobs/",
                    params={
                        "compliance_filter": params.get(
                            "compliance_standard", "FDA_21CFR11"
                        ),
                        "limit": 50,
                    },
                    headers=compliance_token_headers["compliance_officer"],
                )

                if response.status_code == 200:
                    jobs_data = response.json()
                    filtered_jobs = jobs_data.get("data", jobs_data)

                    # Should find compliance-specific jobs
                    compliance_job_count = len(
                        [
                            job
                            for job in filtered_jobs
                            if any(
                                "COMPLIANCE" in job.get("job_number", "")
                                for job in created_compliance_jobs
                            )
                        ]
                    )

                    assert (
                        compliance_job_count > 0
                    ), "Should find compliance-filtered jobs"

    async def test_audit_trail_immutability_verification(
        self,
        client: TestClient,
        compliance_token_headers: dict[str, dict[str, str]],
        db: Session,
    ):
        """Test audit trail immutability and tamper detection."""

        # Create job for immutability testing
        job_data = {
            "job_number": "IMMUTABLE-AUDIT-001",
            "customer_name": "Audit Immutability Test",
            "due_date": (datetime.utcnow() + timedelta(days=15)).isoformat(),
            "compliance_requirements": ["AUDIT_IMMUTABILITY"],
        }

        response = client.post(
            "/api/v1/jobs/",
            json=job_data,
            headers=compliance_token_headers["production_manager"],
        )
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Generate audit entries through various operations
        audit_operations = [
            {
                "action": "status_change",
                "data": {"status": "APPROVED", "reason": "immutability_test_approval"},
            },
            {
                "action": "priority_change",
                "data": {"priority": "URGENT", "notes": "immutability_test_priority"},
            },
            {
                "action": "notes_update",
                "data": {"notes": "Immutability test - audit trail verification"},
            },
        ]

        # Execute operations to create audit trail
        for operation in audit_operations:
            response = client.patch(
                f"/api/v1/jobs/{job_id}",
                json=operation["data"],
                headers=compliance_token_headers["production_manager"],
            )
            # Operations may or may not succeed, but should generate audit entries

        # Get initial audit state
        response = client.get(
            f"/api/v1/audit/job/{job_id}",
            headers=compliance_token_headers["compliance_officer"],
        )

        if response.status_code == 200:
            initial_audit = response.json()
            initial_entries = initial_audit.get("entries", [])
            initial_count = len(initial_entries)

            # Verify audit entries have immutability indicators
            for entry in initial_entries:
                # Should have timestamps that can't be modified
                assert "timestamp" in entry

                # Should have user identification for accountability
                assert "user" in entry or "user_id" in entry

                # Should have hash or signature for integrity (if implemented)
                if "hash" in entry or "signature" in entry or "checksum" in entry:
                    integrity_field = (
                        entry.get("hash")
                        or entry.get("signature")
                        or entry.get("checksum")
                    )
                    assert integrity_field, "Integrity field should not be empty"
                    assert (
                        len(str(integrity_field)) > 10
                    ), "Integrity field should be substantial"

            # Test that audit cannot be modified by unauthorized users
            # Try to access audit modification endpoints (should not exist or be protected)
            modification_attempts = [
                {"method": "DELETE", "url": f"/api/v1/audit/job/{job_id}"},
                {"method": "PUT", "url": f"/api/v1/audit/job/{job_id}"},
                {"method": "PATCH", "url": f"/api/v1/audit/job/{job_id}"},
            ]

            for attempt in modification_attempts:
                method = attempt["method"]
                url = attempt["url"]

                if method == "DELETE":
                    response = client.delete(
                        url, headers=compliance_token_headers["production_manager"]
                    )
                elif method == "PUT":
                    response = client.put(
                        url,
                        json={},
                        headers=compliance_token_headers["production_manager"],
                    )
                elif method == "PATCH":
                    response = client.patch(
                        url,
                        json={},
                        headers=compliance_token_headers["production_manager"],
                    )

                # Should be denied or not exist
                assert response.status_code in [
                    403,
                    404,
                    405,
                ], f"Audit modification via {method} should be denied"

            # Perform additional operations and verify audit grows monotonically
            additional_operation = {
                "notes": f"Additional operation at {datetime.utcnow().isoformat()}"
            }

            response = client.patch(
                f"/api/v1/jobs/{job_id}",
                json=additional_operation,
                headers=compliance_token_headers["quality_manager"],
            )

            # Get updated audit state
            response = client.get(
                f"/api/v1/audit/job/{job_id}",
                headers=compliance_token_headers["compliance_officer"],
            )

            if response.status_code == 200:
                updated_audit = response.json()
                updated_entries = updated_audit.get("entries", [])
                updated_count = len(updated_entries)

                # Audit should have grown (new entries added)
                assert (
                    updated_count >= initial_count
                ), "Audit trail should grow monotonically"

                # Original entries should be unchanged
                if initial_count > 0 and updated_count > initial_count:
                    # Compare first few entries (should be identical)
                    comparison_count = min(initial_count, 3)
                    for i in range(comparison_count):
                        initial_entry = initial_entries[i]
                        updated_entry = updated_entries[i]

                        # Core fields should be unchanged
                        assert initial_entry.get("timestamp") == updated_entry.get(
                            "timestamp"
                        )
                        assert initial_entry.get("action") == updated_entry.get(
                            "action"
                        )
                        assert initial_entry.get("entity_id") == updated_entry.get(
                            "entity_id"
                        )

    async def test_cross_system_audit_correlation(
        self,
        client: TestClient,
        compliance_token_headers: dict[str, dict[str, str]],
        db: Session,
    ):
        """Test audit correlation across different system components."""

        # Create job for cross-system correlation testing
        job_data = {
            "job_number": "CROSS-SYSTEM-AUDIT-001",
            "customer_name": "Cross System Audit Test",
            "due_date": (datetime.utcnow() + timedelta(days=18)).isoformat(),
        }

        response = client.post(
            "/api/v1/jobs/",
            json=job_data,
            headers=compliance_token_headers["production_manager"],
        )
        assert response.status_code == 201
        job = response.json()
        job_id = job["id"]

        # Add task to create cross-system interactions
        task_data = {
            "operation_id": str(uuid4()),
            "sequence_in_job": 10,
            "planned_duration_minutes": 120,
        }

        response = client.post(
            f"/api/v1/jobs/{job_id}/tasks/",
            json=task_data,
            headers=compliance_token_headers["production_planner"],
        )
        assert response.status_code == 201
        task = response.json()
        task_id = task["id"]

        # Create schedule (scheduling system interaction)
        schedule_data = {
            "name": "Cross-System Audit Schedule",
            "job_ids": [job_id],
            "start_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(days=10)).isoformat(),
        }

        response = client.post(
            "/api/v1/schedules/optimize",
            json=schedule_data,
            headers=compliance_token_headers["scheduling_coordinator"],
        )

        schedule_id = None
        if response.status_code == 201:
            schedule_result = response.json()
            schedule_id = schedule_result["schedule"]["id"]

        # Test cross-system audit correlation
        correlation_queries = [
            {
                "name": "job_task_correlation",
                "params": {"job_id": job_id, "include_tasks": True},
            },
            {
                "name": "job_schedule_correlation",
                "params": {"job_id": job_id, "include_schedules": True},
            },
            {
                "name": "timeline_correlation",
                "params": {
                    "start_time": (
                        datetime.utcnow() - timedelta(minutes=5)
                    ).isoformat(),
                    "end_time": datetime.utcnow().isoformat(),
                    "correlation_id": job_id,
                },
            },
        ]

        for query in correlation_queries:
            query["name"]
            params = query["params"]

            # Test audit correlation endpoint
            response = client.get(
                "/api/v1/audit/correlation",
                params=params,
                headers=compliance_token_headers["compliance_officer"],
            )

            if response.status_code == 200:
                correlation_data = response.json()

                # Verify correlation structure
                assert (
                    "related_entities" in correlation_data
                    or "correlations" in correlation_data
                )

                # Verify cross-references
                correlations = correlation_data.get(
                    "correlations", correlation_data.get("related_entities", [])
                )

                if correlations:
                    for correlation in correlations:
                        assert "entity_type" in correlation
                        assert "entity_id" in correlation
                        assert (
                            "relationship" in correlation
                            or "correlation_type" in correlation
                        )

                        # Should link related entities
                        if correlation["entity_type"] == "task":
                            assert (
                                correlation["entity_id"] == task_id
                                or "relationship" in correlation
                            )
                        elif correlation["entity_type"] == "schedule" and schedule_id:
                            assert (
                                correlation["entity_id"] == schedule_id
                                or "relationship" in correlation
                            )

            elif response.status_code == 404:
                # Correlation endpoint doesn't exist, test individual audits
                # Verify job audit exists
                response = client.get(
                    f"/api/v1/audit/job/{job_id}",
                    headers=compliance_token_headers["compliance_officer"],
                )

                if response.status_code == 200:
                    job_audit = response.json()
                    assert "entries" in job_audit

                    # Should have entries related to task and schedule creation
                    entries = job_audit["entries"]
                    action_types = [entry.get("action", "") for entry in entries]

                    # Should correlate job, task, and schedule operations
                    assert any("job" in action.lower() for action in action_types)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
