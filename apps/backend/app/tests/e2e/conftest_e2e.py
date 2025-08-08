"""
End-to-End Test Configuration

Provides comprehensive test fixtures, utilities, and configuration for
complete end-to-end workflow integration tests.
"""

import asyncio
import time
from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from app.core.database import get_db
from app.core.db import init_db
from app.main import app
from app.tests.utils.utils import get_superuser_token_headers


class E2ETestConfig:
    """Configuration for end-to-end tests."""

    # Test database settings
    TEST_DATABASE_URL = "sqlite:///./test_e2e.db"

    # Performance test thresholds
    MAX_JOB_CREATION_TIME = 2.0  # seconds
    MAX_SCHEDULE_OPTIMIZATION_TIME = 30.0  # seconds
    MAX_CONCURRENT_OPERATIONS = 50

    # Security test settings
    TOKEN_EXPIRY_BUFFER = 60  # seconds
    MAX_LOGIN_ATTEMPTS = 5

    # Compliance test settings
    AUDIT_RETENTION_DAYS = 2555  # 7 years in days
    REQUIRED_COMPLIANCE_FIELDS = [
        "timestamp",
        "user",
        "action",
        "entity_type",
        "entity_id",
    ]

    # WebSocket test settings
    WS_CONNECTION_TIMEOUT = 5.0
    WS_MESSAGE_TIMEOUT = 3.0

    # Data integrity test settings
    TRANSACTION_TIMEOUT = 10.0
    MAX_ROLLBACK_TIME = 5.0


@pytest.fixture(scope="session")
def e2e_config():
    """Provide E2E test configuration."""
    return E2ETestConfig()


@pytest.fixture(scope="session")
def e2e_test_engine():
    """Create test database engine for E2E tests."""
    engine = create_engine(
        E2ETestConfig.TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(scope="session")
def e2e_test_db(e2e_test_engine) -> Generator[Session, None, None]:
    """Create test database session for E2E tests."""
    from app.infrastructure.database.models import SQLModel

    # Create tables
    SQLModel.metadata.create_all(e2e_test_engine)

    with Session(e2e_test_engine) as session:
        init_db(session)
        yield session

    # Clean up
    SQLModel.metadata.drop_all(e2e_test_engine)


@pytest.fixture(scope="function")
def e2e_client(e2e_test_db: Session) -> TestClient:
    """Create test client with E2E database."""

    def get_test_db():
        return e2e_test_db

    app.dependency_overrides[get_db] = get_test_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


class E2ETestDataFactory:
    """Factory for creating comprehensive E2E test data."""

    @staticmethod
    def create_realistic_production_scenario() -> dict[str, Any]:
        """Create realistic production scenario with multiple jobs, customers, and constraints."""
        customers = [
            "Automotive Solutions Inc",
            "Aerospace Dynamics Corp",
            "Medical Device Systems",
            "Electronics Manufacturing Co",
            "Defense Contractors Ltd",
            "Consumer Products Group",
        ]

        part_types = [
            "Engine Component",
            "Flight Control Part",
            "Medical Implant",
            "Circuit Board",
            "Tactical Equipment",
            "Consumer Device",
        ]

        priorities = ["LOW", "NORMAL", "HIGH", "URGENT"]

        scenario_id = uuid4().hex[:8].upper()

        jobs = []
        for i in range(15):  # Create 15 jobs for comprehensive testing
            customer = customers[i % len(customers)]
            part_type = part_types[i % len(part_types)]
            priority = priorities[i % len(priorities)]

            job = {
                "job_number": f"E2E-{scenario_id}-{i+1:03d}",
                "customer_name": customer,
                "part_number": f"{part_type.replace(' ', '').upper()}-{i+1:03d}",
                "quantity": (i % 50) + 1,
                "priority": priority,
                "due_date": (
                    datetime.utcnow() + timedelta(days=3 + (i * 2))
                ).isoformat(),
                "notes": f"E2E test job for {customer} - {part_type}",
                "customer_po": f"PO-{scenario_id}-{i+1:03d}",
            }
            jobs.append(job)

        return {
            "scenario_id": scenario_id,
            "jobs": jobs,
            "total_jobs": len(jobs),
            "customers": list(set(customers)),
            "expected_duration_days": 33,  # Based on due dates
        }

    @staticmethod
    def create_task_templates() -> list[dict[str, Any]]:
        """Create realistic task templates for different operation types."""
        return [
            {
                "name": "Precision Machining",
                "base_duration": 120,
                "setup_duration": 30,
                "skill_requirements": [
                    {
                        "skill_code": "CNC_MACHINING",
                        "required_level": "INTERMEDIATE",
                        "is_mandatory": True,
                    }
                ],
                "quality_checkpoints": [
                    "dimensional_inspection",
                    "surface_finish_check",
                ],
            },
            {
                "name": "Assembly Operation",
                "base_duration": 90,
                "setup_duration": 15,
                "skill_requirements": [
                    {
                        "skill_code": "ASSEMBLY",
                        "required_level": "BASIC",
                        "is_mandatory": True,
                    }
                ],
                "quality_checkpoints": ["torque_verification", "fit_check"],
            },
            {
                "name": "Quality Inspection",
                "base_duration": 60,
                "setup_duration": 10,
                "skill_requirements": [
                    {
                        "skill_code": "QUALITY_CONTROL",
                        "required_level": "ADVANCED",
                        "is_mandatory": True,
                    }
                ],
                "quality_checkpoints": ["final_inspection", "compliance_verification"],
            },
            {
                "name": "Welding Operation",
                "base_duration": 150,
                "setup_duration": 25,
                "skill_requirements": [
                    {
                        "skill_code": "CERTIFIED_WELDING",
                        "required_level": "EXPERT",
                        "is_mandatory": True,
                    }
                ],
                "quality_checkpoints": ["weld_inspection", "penetrant_testing"],
            },
            {
                "name": "Packaging",
                "base_duration": 30,
                "setup_duration": 5,
                "skill_requirements": [
                    {
                        "skill_code": "PACKAGING",
                        "required_level": "BASIC",
                        "is_mandatory": False,
                    }
                ],
                "quality_checkpoints": ["package_integrity", "labeling_verification"],
            },
        ]

    @staticmethod
    def create_optimization_scenarios() -> list[dict[str, Any]]:
        """Create different optimization scenarios for testing."""
        return [
            {
                "name": "Minimize Makespan",
                "description": "Optimize for shortest total completion time",
                "parameters": {
                    "minimize_makespan": True,
                    "minimize_tardiness": False,
                    "resource_utilization_weight": 0.2,
                    "makespan_weight": 0.8,
                },
                "expected_improvement": "20-30% reduction in total time",
            },
            {
                "name": "Minimize Tardiness",
                "description": "Optimize for on-time delivery",
                "parameters": {
                    "minimize_makespan": False,
                    "minimize_tardiness": True,
                    "priority_weight": 0.4,
                    "tardiness_weight": 0.6,
                },
                "expected_improvement": "90%+ on-time delivery rate",
            },
            {
                "name": "Balanced Optimization",
                "description": "Balance all objectives",
                "parameters": {
                    "minimize_makespan": True,
                    "minimize_tardiness": True,
                    "resource_utilization_weight": 0.3,
                    "priority_weight": 0.3,
                    "makespan_weight": 0.2,
                    "tardiness_weight": 0.2,
                },
                "expected_improvement": "Overall improvement across metrics",
            },
            {
                "name": "Resource Utilization Focus",
                "description": "Maximize resource efficiency",
                "parameters": {
                    "minimize_makespan": False,
                    "minimize_tardiness": False,
                    "resource_utilization_weight": 0.8,
                    "efficiency_weight": 0.2,
                },
                "expected_improvement": "85%+ resource utilization",
            },
        ]


@pytest.fixture
def e2e_data_factory():
    """Provide E2E test data factory."""
    return E2ETestDataFactory()


class E2EPerformanceMonitor:
    """Monitor performance metrics during E2E tests."""

    def __init__(self):
        self.metrics = {
            "operation_times": {},
            "memory_usage": [],
            "cpu_usage": [],
            "database_operations": [],
            "network_requests": [],
            "errors": [],
        }
        self.start_time = None

    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()

        # Try to get system metrics
        try:
            import psutil

            self.metrics["memory_usage"].append(psutil.virtual_memory().percent)
            self.metrics["cpu_usage"].append(psutil.cpu_percent(interval=None))
        except ImportError:
            # psutil not available, continue without system metrics
            pass

    def stop_monitoring(self):
        """Stop performance monitoring."""
        if self.start_time:
            total_time = time.time() - self.start_time
            self.record_operation("total_test_duration", total_time)

        try:
            import psutil

            self.metrics["memory_usage"].append(psutil.virtual_memory().percent)
            self.metrics["cpu_usage"].append(psutil.cpu_percent(interval=None))
        except ImportError:
            pass

    def record_operation(
        self, operation_name: str, duration: float, metadata: dict = None
    ):
        """Record operation timing."""
        if operation_name not in self.metrics["operation_times"]:
            self.metrics["operation_times"][operation_name] = []

        self.metrics["operation_times"][operation_name].append(
            {"duration": duration, "timestamp": time.time(), "metadata": metadata or {}}
        )

    def record_error(self, error_type: str, error_message: str, context: dict = None):
        """Record error occurrence."""
        self.metrics["errors"].append(
            {
                "type": error_type,
                "message": error_message,
                "timestamp": time.time(),
                "context": context or {},
            }
        )

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        summary = {
            "total_operations": sum(
                len(ops) for ops in self.metrics["operation_times"].values()
            ),
            "total_errors": len(self.metrics["errors"]),
            "operation_summary": {},
            "system_usage": {},
        }

        # Summarize operation times
        for op_name, operations in self.metrics["operation_times"].items():
            durations = [op["duration"] for op in operations]
            if durations:
                summary["operation_summary"][op_name] = {
                    "count": len(durations),
                    "total_time": sum(durations),
                    "avg_time": sum(durations) / len(durations),
                    "min_time": min(durations),
                    "max_time": max(durations),
                }

        # System usage summary
        if self.metrics["memory_usage"]:
            summary["system_usage"]["memory"] = {
                "min": min(self.metrics["memory_usage"]),
                "max": max(self.metrics["memory_usage"]),
                "avg": sum(self.metrics["memory_usage"])
                / len(self.metrics["memory_usage"]),
            }

        if self.metrics["cpu_usage"]:
            summary["system_usage"]["cpu"] = {
                "min": min(self.metrics["cpu_usage"]),
                "max": max(self.metrics["cpu_usage"]),
                "avg": sum(self.metrics["cpu_usage"]) / len(self.metrics["cpu_usage"]),
            }

        return summary

    @asynccontextmanager
    async def monitor_operation(self, operation_name: str, metadata: dict = None):
        """Context manager for monitoring operations."""
        start_time = time.time()
        try:
            yield
        except Exception as e:
            self.record_error(operation_name, str(e), metadata)
            raise
        finally:
            duration = time.time() - start_time
            self.record_operation(operation_name, duration, metadata)


@pytest.fixture
def performance_monitor():
    """Provide performance monitor for E2E tests."""
    return E2EPerformanceMonitor()


class E2ETestOrchestrator:
    """Orchestrates complex E2E test workflows."""

    def __init__(self, client: TestClient, auth_headers: dict[str, str]):
        self.client = client
        self.auth_headers = auth_headers
        self.created_entities = {"jobs": [], "tasks": [], "schedules": [], "users": []}

    async def create_complete_workflow_scenario(
        self, scenario_data: dict[str, Any], performance_monitor: E2EPerformanceMonitor
    ) -> dict[str, Any]:
        """Create complete workflow scenario with all entities."""

        workflow_results = {
            "scenario_id": scenario_data["scenario_id"],
            "created_jobs": [],
            "created_tasks": [],
            "created_schedules": [],
            "performance_metrics": {},
            "workflow_success": False,
        }

        try:
            # Phase 1: Create jobs
            async with performance_monitor.monitor_operation("bulk_job_creation"):
                for job_data in scenario_data["jobs"]:
                    response = self.client.post(
                        "/api/v1/jobs/", json=job_data, headers=self.auth_headers
                    )

                    if response.status_code == 201:
                        job = response.json()
                        workflow_results["created_jobs"].append(job)
                        self.created_entities["jobs"].append(job)

            # Phase 2: Add tasks to jobs
            async with performance_monitor.monitor_operation("bulk_task_creation"):
                task_templates = E2ETestDataFactory.create_task_templates()

                for job in workflow_results["created_jobs"]:
                    job_id = job["id"]

                    # Add 2-4 tasks per job based on complexity
                    task_count = min(4, len(task_templates))
                    for i in range(task_count):
                        template = task_templates[i]

                        task_data = {
                            "operation_id": str(uuid4()),
                            "sequence_in_job": (i + 1) * 10,
                            "planned_duration_minutes": template["base_duration"]
                            + (i * 15),
                            "setup_duration_minutes": template["setup_duration"],
                            "skill_requirements": template["skill_requirements"],
                            "quality_checkpoints": template.get(
                                "quality_checkpoints", []
                            ),
                        }

                        response = self.client.post(
                            f"/api/v1/jobs/{job_id}/tasks/",
                            json=task_data,
                            headers=self.auth_headers,
                        )

                        if response.status_code == 201:
                            task = response.json()
                            workflow_results["created_tasks"].append(task)
                            self.created_entities["tasks"].append(task)

            # Phase 3: Release jobs for scheduling
            async with performance_monitor.monitor_operation("bulk_job_release"):
                for job in workflow_results["created_jobs"]:
                    response = self.client.patch(
                        f"/api/v1/jobs/{job['id']}/status",
                        json={"status": "RELEASED", "reason": "e2e_workflow_test"},
                        headers=self.auth_headers,
                    )
                    # Continue even if some releases fail

            # Phase 4: Create optimized schedules
            async with performance_monitor.monitor_operation("schedule_optimization"):
                optimization_scenarios = (
                    E2ETestDataFactory.create_optimization_scenarios()
                )

                for scenario in optimization_scenarios[
                    :2
                ]:  # Test 2 optimization strategies
                    schedule_data = {
                        "name": f"E2E {scenario['name']} - {scenario_data['scenario_id']}",
                        "job_ids": [
                            job["id"] for job in workflow_results["created_jobs"]
                        ],
                        "start_time": (
                            datetime.utcnow() + timedelta(hours=1)
                        ).isoformat(),
                        "end_time": (
                            datetime.utcnow()
                            + timedelta(days=scenario_data["expected_duration_days"])
                        ).isoformat(),
                        "optimization_parameters": scenario["parameters"],
                    }

                    response = self.client.post(
                        "/api/v1/schedules/optimize",
                        json=schedule_data,
                        headers=self.auth_headers,
                    )

                    if response.status_code == 201:
                        schedule_result = response.json()
                        workflow_results["created_schedules"].append(
                            schedule_result["schedule"]
                        )
                        self.created_entities["schedules"].append(
                            schedule_result["schedule"]
                        )

            workflow_results["workflow_success"] = True
            workflow_results["performance_metrics"] = (
                performance_monitor.get_performance_summary()
            )

        except Exception as e:
            performance_monitor.record_error("workflow_creation", str(e))
            workflow_results["workflow_error"] = str(e)

        return workflow_results

    async def cleanup_entities(self):
        """Clean up created entities."""
        # Clean up in reverse order of creation
        for schedule in self.created_entities["schedules"]:
            try:
                self.client.delete(
                    f"/api/v1/schedules/{schedule['id']}", headers=self.auth_headers
                )
            except Exception:
                pass

        for job in self.created_entities["jobs"]:
            try:
                self.client.delete(
                    f"/api/v1/jobs/{job['id']}", headers=self.auth_headers
                )
            except Exception:
                pass


@pytest.fixture
def test_orchestrator(e2e_client: TestClient):
    """Provide test orchestrator for complex E2E workflows."""
    auth_headers = get_superuser_token_headers(e2e_client)
    orchestrator = E2ETestOrchestrator(e2e_client, auth_headers)

    yield orchestrator

    # Cleanup after test
    asyncio.create_task(orchestrator.cleanup_entities())


# Test collection and execution helpers
def pytest_collection_modifyitems(config, items):
    """Modify test collection for E2E tests."""
    # Add markers for different test categories
    for item in items:
        # Mark E2E tests
        if "e2e" in item.nodeid:
            item.add_marker(pytest.mark.e2e)

        # Mark slow tests
        if any(
            keyword in item.name.lower()
            for keyword in ["performance", "load", "stress"]
        ):
            item.add_marker(pytest.mark.slow)

        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)


def pytest_configure(config):
    """Configure pytest for E2E tests."""
    # Register custom markers
    config.addinivalue_line("markers", "e2e: mark test as end-to-end integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "security: mark test as security test")
    config.addinivalue_line(
        "markers", "audit_compliance: mark test as audit/compliance test"
    )
    config.addinivalue_line("markers", "websocket: mark test as WebSocket test")
    config.addinivalue_line(
        "markers", "data_integrity: mark test as data integrity test"
    )


# Performance test configuration
@pytest.fixture(scope="session")
def performance_thresholds():
    """Define performance thresholds for E2E tests."""
    return {
        "job_creation_max_time": 2.0,
        "task_creation_max_time": 1.0,
        "schedule_optimization_max_time": 30.0,
        "concurrent_operations_min_success_rate": 0.85,
        "memory_usage_max_increase": 20.0,  # percent
        "response_time_99th_percentile": 5.0,  # seconds
    }
