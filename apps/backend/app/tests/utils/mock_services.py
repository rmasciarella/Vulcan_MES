"""
Mock Services and Test Doubles

Comprehensive mocking infrastructure for external dependencies, domain services,
and complex integrations. Provides realistic test doubles for isolation testing.
"""

import random
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.schedule import Schedule, ScheduleAssignment
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.services.optimization_service import (
    OptimizationParameters,
    OptimizationResult,
)
from app.domain.scheduling.services.resource_allocation_service import (
    ResourceAllocation,
)
from app.domain.scheduling.value_objects.duration import Duration
from app.domain.scheduling.value_objects.enums import SkillLevel
from app.tests.database.factories import JobFactory


class MockOptimizationService:
    """Mock optimization service with realistic behavior patterns."""

    def __init__(self, behavior: str = "optimal"):
        """
        Initialize mock optimization service.

        Args:
            behavior: "optimal", "suboptimal", "infeasible", "timeout", "error"
        """
        self.behavior = behavior
        self.optimization_calls = []
        self.performance_metrics = {
            "total_calls": 0,
            "average_duration": 2.5,
            "success_rate": 0.95,
        }

    async def optimize_schedule(
        self,
        job_ids: list[UUID],
        start_time: datetime,
        parameters: OptimizationParameters | None = None,
    ) -> OptimizationResult:
        """Mock schedule optimization with configurable behavior."""
        self.optimization_calls.append(
            {
                "job_ids": job_ids,
                "start_time": start_time,
                "parameters": parameters,
                "timestamp": datetime.utcnow(),
            }
        )
        self.performance_metrics["total_calls"] += 1

        if self.behavior == "optimal":
            return self._create_optimal_result(job_ids, start_time)
        elif self.behavior == "suboptimal":
            return self._create_suboptimal_result(job_ids, start_time)
        elif self.behavior == "infeasible":
            return OptimizationResult(
                status="INFEASIBLE",
                objective_value=None,
                solution_time=5.0,
                message="No feasible solution found with given constraints",
            )
        elif self.behavior == "timeout":
            return OptimizationResult(
                status="TIMEOUT",
                objective_value=None,
                solution_time=300.0,
                message="Optimization timed out after 5 minutes",
            )
        elif self.behavior == "error":
            raise Exception("Mock optimization service error")
        else:
            return self._create_optimal_result(job_ids, start_time)

    def _create_optimal_result(
        self, job_ids: list[UUID], start_time: datetime
    ) -> OptimizationResult:
        """Create an optimal optimization result."""
        # Create a realistic schedule
        schedule = Schedule(
            name=f"Optimized Schedule {datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            planning_horizon=Duration(days=7),
        )

        # Add jobs to schedule
        for job_id in job_ids:
            schedule.add_job(job_id)

        # Create realistic assignments
        current_time = start_time
        for i, job_id in enumerate(job_ids):
            # Simulate 2-3 tasks per job
            task_count = random.randint(2, 3)
            for j in range(task_count):
                assignment = ScheduleAssignment(
                    task_id=uuid4(),
                    machine_id=uuid4(),
                    operator_ids=[uuid4()],
                    start_time=current_time + timedelta(hours=i * 4 + j * 2),
                    end_time=current_time + timedelta(hours=i * 4 + j * 2 + 1.5),
                    setup_duration=Duration(minutes=15),
                    processing_duration=Duration(minutes=75),
                )
                schedule.assignments.append(assignment)

        return OptimizationResult(
            schedule=schedule,
            status="OPTIMAL",
            objective_value=150.0 + random.uniform(-20, 20),
            solution_time=random.uniform(1.0, 5.0),
            gap=0.0,
            iterations=random.randint(50, 200),
            message="Optimal solution found",
        )

    def _create_suboptimal_result(
        self, job_ids: list[UUID], start_time: datetime
    ) -> OptimizationResult:
        """Create a suboptimal optimization result."""
        result = self._create_optimal_result(job_ids, start_time)
        result.status = "FEASIBLE"
        result.objective_value *= 1.15  # 15% worse
        result.gap = 0.12
        result.message = "Good solution found within time limit"
        return result

    def get_performance_stats(self) -> dict[str, Any]:
        """Get mock performance statistics."""
        return {
            **self.performance_metrics,
            "recent_calls": self.optimization_calls[-10:],
        }

    def reset_stats(self):
        """Reset optimization statistics."""
        self.optimization_calls.clear()
        self.performance_metrics["total_calls"] = 0


class MockConstraintValidationService:
    """Mock constraint validation service with configurable violations."""

    def __init__(self, violation_patterns: list[str] = None):
        """
        Initialize mock constraint validation service.

        Args:
            violation_patterns: List of violation types to simulate
        """
        self.violation_patterns = violation_patterns or []
        self.validation_calls = []

    async def validate_schedule(self, schedule: Schedule) -> list[str]:
        """Mock schedule validation with configurable violations."""
        self.validation_calls.append(
            {
                "schedule_id": schedule.id,
                "job_count": len(schedule.job_ids),
                "assignment_count": len(schedule.assignments),
                "timestamp": datetime.utcnow(),
            }
        )

        violations = []

        # Generate violations based on patterns
        for pattern in self.violation_patterns:
            if pattern == "resource_conflict":
                violations.extend(self._generate_resource_conflicts(schedule))
            elif pattern == "skill_mismatch":
                violations.extend(self._generate_skill_mismatches(schedule))
            elif pattern == "capacity_exceeded":
                violations.extend(self._generate_capacity_violations(schedule))
            elif pattern == "precedence_violation":
                violations.extend(self._generate_precedence_violations(schedule))
            elif pattern == "time_constraint":
                violations.extend(self._generate_time_violations(schedule))

        return violations

    def _generate_resource_conflicts(self, schedule: Schedule) -> list[str]:
        """Generate mock resource conflict violations."""
        conflicts = []
        if len(schedule.assignments) > 5:  # Only for larger schedules
            conflicts.append("Machine M001 has overlapping assignments at 14:00-16:00")
            conflicts.append("Operator O005 double-booked on 2024-01-15")
        return conflicts

    def _generate_skill_mismatches(self, schedule: Schedule) -> list[str]:
        """Generate mock skill mismatch violations."""
        mismatches = []
        if "skill_mismatch" in self.violation_patterns:
            mismatches.append(
                "Task requires WELDING_ADVANCED but operator has WELDING_INTERMEDIATE"
            )
            mismatches.append(
                "No available operators with MACHINING_EXPERT certification"
            )
        return mismatches

    def _generate_capacity_violations(self, schedule: Schedule) -> list[str]:
        """Generate mock capacity violation errors."""
        violations = []
        if len(schedule.assignments) > 10:
            violations.append("Production line capacity exceeded on 2024-01-16")
            violations.append("Warehouse capacity limit reached for PART_A")
        return violations

    def _generate_precedence_violations(self, schedule: Schedule) -> list[str]:
        """Generate mock task precedence violations."""
        violations = []
        if "precedence_violation" in self.violation_patterns:
            violations.append("Task T002 scheduled before prerequisite T001")
            violations.append("Setup operation must complete before processing")
        return violations

    def _generate_time_violations(self, schedule: Schedule) -> list[str]:
        """Generate mock time constraint violations."""
        violations = []
        if "time_constraint" in self.violation_patterns:
            violations.append("Job JOB001 scheduled after due date")
            violations.append("Maintenance window conflict on Machine M003")
        return violations

    def add_violation_pattern(self, pattern: str):
        """Add a violation pattern to simulate."""
        if pattern not in self.violation_patterns:
            self.violation_patterns.append(pattern)

    def remove_violation_pattern(self, pattern: str):
        """Remove a violation pattern."""
        if pattern in self.violation_patterns:
            self.violation_patterns.remove(pattern)

    def get_validation_history(self) -> list[dict[str, Any]]:
        """Get history of validation calls."""
        return self.validation_calls.copy()


class MockResourceAllocationService:
    """Mock resource allocation service with realistic resource assignments."""

    def __init__(self, resource_availability: dict[str, float] = None):
        """
        Initialize mock resource allocation service.

        Args:
            resource_availability: Dict mapping resource types to availability (0.0-1.0)
        """
        self.resource_availability = resource_availability or {
            "machines": 0.8,
            "operators": 0.7,
            "tools": 0.9,
        }
        self.allocation_calls = []
        self.available_resources = self._generate_available_resources()

    async def allocate_resources_for_job(
        self, job: Job, start_time: datetime
    ) -> list[ResourceAllocation]:
        """Mock resource allocation for a job."""
        self.allocation_calls.append(
            {
                "job_id": job.id,
                "job_number": job.job_number,
                "start_time": start_time,
                "timestamp": datetime.utcnow(),
            }
        )

        allocations = []
        tasks = job.get_all_tasks()

        for i, task in enumerate(tasks):
            allocation = ResourceAllocation(
                task_id=task.id,
                machine_id=self._allocate_machine(task),
                operator_ids=self._allocate_operators(task),
                start_time=start_time + timedelta(hours=i * 2),
                end_time=start_time + timedelta(hours=i * 2 + 1.5),
                resource_utilization=random.uniform(0.7, 0.95),
                allocation_confidence=random.uniform(0.8, 1.0),
            )
            allocations.append(allocation)

        return allocations

    def _allocate_machine(self, task: Task) -> UUID:
        """Allocate a machine for a task."""
        # Simulate machine selection based on task requirements
        available_machines = list(self.available_resources["machines"].keys())
        if available_machines:
            return random.choice(available_machines)
        return uuid4()

    def _allocate_operators(self, task: Task) -> list[UUID]:
        """Allocate operators for a task."""
        # Simulate operator allocation based on skill requirements
        available_operators = list(self.available_resources["operators"].keys())
        operator_count = random.randint(1, min(3, len(available_operators)))

        if available_operators:
            return random.sample(
                available_operators, min(operator_count, len(available_operators))
            )
        return [uuid4() for _ in range(operator_count)]

    def _generate_available_resources(self) -> dict[str, dict[UUID, dict[str, Any]]]:
        """Generate mock available resources."""
        resources = {
            "machines": {},
            "operators": {},
            "tools": {},
        }

        # Generate machines
        machine_types = ["CNC_MILL", "LATHE", "DRILL_PRESS", "WELDING_STATION"]
        for _i in range(20):
            machine_id = uuid4()
            resources["machines"][machine_id] = {
                "type": random.choice(machine_types),
                "capacity": random.uniform(0.5, 1.0),
                "availability": random.uniform(0.7, 1.0),
                "maintenance_due": datetime.utcnow()
                + timedelta(days=random.randint(1, 90)),
            }

        # Generate operators
        skill_levels = [
            SkillLevel.BASIC,
            SkillLevel.INTERMEDIATE,
            SkillLevel.ADVANCED,
            SkillLevel.EXPERT,
        ]
        for _i in range(50):
            operator_id = uuid4()
            resources["operators"][operator_id] = {
                "skills": {
                    "MACHINING": random.choice(skill_levels),
                    "WELDING": random.choice(skill_levels),
                    "ASSEMBLY": random.choice(skill_levels),
                },
                "availability": random.uniform(0.6, 1.0),
                "shift": random.choice(["DAY", "NIGHT", "SWING"]),
                "hourly_rate": random.uniform(25.0, 75.0),
            }

        return resources

    def set_resource_availability(self, resource_type: str, availability: float):
        """Set availability for a resource type."""
        self.resource_availability[resource_type] = availability

    def get_allocation_history(self) -> list[dict[str, Any]]:
        """Get history of allocation calls."""
        return self.allocation_calls.copy()

    def get_resource_utilization_stats(self) -> dict[str, float]:
        """Get mock resource utilization statistics."""
        return {
            "machine_utilization": random.uniform(0.7, 0.9),
            "operator_utilization": random.uniform(0.6, 0.8),
            "tool_utilization": random.uniform(0.8, 0.95),
            "overall_efficiency": random.uniform(0.75, 0.85),
        }


class MockWorkflowService:
    """Mock workflow service for task state management."""

    def __init__(self):
        self.workflow_states = {}
        self.transition_calls = []

    async def get_job_workflow_state(self, job_id: UUID) -> dict[str, Any]:
        """Get mock job workflow state."""
        if job_id not in self.workflow_states:
            self.workflow_states[job_id] = {
                "state": "READY",
                "current_task": None,
                "completed_tasks": [],
                "ready_tasks": [uuid4()],
                "blocked_tasks": [],
                "progress_percentage": 0.0,
            }

        return self.workflow_states[job_id].copy()

    async def advance_job_workflow(self, job_id: UUID) -> list[str]:
        """Advance job workflow and return transitions."""
        state = self.workflow_states.get(job_id, {})
        transitions = []

        if state.get("state") == "READY":
            # Start first available task
            ready_tasks = state.get("ready_tasks", [])
            if ready_tasks:
                task_id = ready_tasks[0]
                transitions.append(f"started_task_{task_id}")
                state["current_task"] = task_id
                state["ready_tasks"] = ready_tasks[1:]
                state["state"] = "IN_PROGRESS"

        elif state.get("state") == "IN_PROGRESS":
            # Complete current task and potentially start next
            current_task = state.get("current_task")
            if current_task:
                completed = state.get("completed_tasks", [])
                completed.append(current_task)
                state["completed_tasks"] = completed
                transitions.append(f"completed_task_{current_task}")

                # Check if more tasks available
                ready_tasks = state.get("ready_tasks", [])
                if ready_tasks:
                    next_task = ready_tasks[0]
                    state["current_task"] = next_task
                    state["ready_tasks"] = ready_tasks[1:]
                    transitions.append(f"started_task_{next_task}")
                else:
                    state["current_task"] = None
                    state["state"] = "COMPLETED"

        self.workflow_states[job_id] = state
        self.transition_calls.append(
            {
                "job_id": job_id,
                "transitions": transitions,
                "timestamp": datetime.utcnow(),
            }
        )

        return transitions

    async def get_job_progress(self, job_id: UUID) -> dict[str, Any]:
        """Get job progress information."""
        state = self.workflow_states.get(job_id, {})
        completed_count = len(state.get("completed_tasks", []))
        ready_count = len(state.get("ready_tasks", []))
        total_tasks = (
            completed_count + ready_count + (1 if state.get("current_task") else 0)
        )

        return {
            "job_id": str(job_id),
            "total_tasks": max(total_tasks, 3),  # Minimum 3 tasks for realism
            "completed_tasks": completed_count,
            "in_progress_tasks": 1 if state.get("current_task") else 0,
            "ready_tasks": ready_count,
            "blocked_tasks": len(state.get("blocked_tasks", [])),
            "progress_percentage": (completed_count / max(total_tasks, 1)) * 100,
            "estimated_completion": datetime.utcnow()
            + timedelta(hours=total_tasks * 2),
        }

    def set_job_workflow_state(self, job_id: UUID, state: dict[str, Any]):
        """Manually set job workflow state for testing."""
        self.workflow_states[job_id] = state

    def get_transition_history(self) -> list[dict[str, Any]]:
        """Get history of workflow transitions."""
        return self.transition_calls.copy()


class MockExternalAPIService:
    """Mock external API service for testing integrations."""

    def __init__(self, response_delay: float = 0.1, failure_rate: float = 0.05):
        """
        Initialize mock external API service.

        Args:
            response_delay: Simulated response delay in seconds
            failure_rate: Probability of API call failure (0.0-1.0)
        """
        self.response_delay = response_delay
        self.failure_rate = failure_rate
        self.api_calls = []

    async def get_machine_status(self, machine_id: UUID) -> dict[str, Any]:
        """Mock machine status API call."""
        await self._simulate_delay()
        self._record_api_call("get_machine_status", {"machine_id": machine_id})

        if random.random() < self.failure_rate:
            raise Exception("Mock API failure: Machine status service unavailable")

        return {
            "machine_id": str(machine_id),
            "status": random.choice(["IDLE", "RUNNING", "MAINTENANCE", "ERROR"]),
            "utilization": random.uniform(0.3, 0.9),
            "last_maintenance": datetime.utcnow()
            - timedelta(days=random.randint(1, 30)),
            "next_maintenance": datetime.utcnow()
            + timedelta(days=random.randint(1, 60)),
            "error_count": random.randint(0, 5),
            "efficiency": random.uniform(0.8, 0.98),
        }

    async def get_operator_availability(self, operator_id: UUID) -> dict[str, Any]:
        """Mock operator availability API call."""
        await self._simulate_delay()
        self._record_api_call("get_operator_availability", {"operator_id": operator_id})

        if random.random() < self.failure_rate:
            raise Exception("Mock API failure: Operator service unavailable")

        return {
            "operator_id": str(operator_id),
            "available": random.choice([True, False]),
            "shift_start": datetime.utcnow().replace(
                hour=8, minute=0, second=0, microsecond=0
            ),
            "shift_end": datetime.utcnow().replace(
                hour=17, minute=0, second=0, microsecond=0
            ),
            "current_task": str(uuid4()) if random.random() > 0.5 else None,
            "skills": ["MACHINING", "WELDING", "ASSEMBLY"][: random.randint(1, 3)],
            "performance_rating": random.uniform(0.8, 1.0),
        }

    async def submit_work_order(self, work_order: dict[str, Any]) -> dict[str, Any]:
        """Mock work order submission API call."""
        await self._simulate_delay()
        self._record_api_call("submit_work_order", work_order)

        if random.random() < self.failure_rate:
            raise Exception("Mock API failure: Work order service unavailable")

        return {
            "work_order_id": str(uuid4()),
            "status": "SUBMITTED",
            "estimated_start": datetime.utcnow()
            + timedelta(hours=random.randint(1, 24)),
            "estimated_completion": datetime.utcnow()
            + timedelta(days=random.randint(1, 7)),
            "assigned_resources": {
                "machine_id": str(uuid4()),
                "operator_ids": [str(uuid4()) for _ in range(random.randint(1, 3))],
            },
            "priority": random.choice(["LOW", "NORMAL", "HIGH", "URGENT"]),
        }

    async def get_inventory_levels(self, part_numbers: list[str]) -> dict[str, Any]:
        """Mock inventory levels API call."""
        await self._simulate_delay()
        self._record_api_call("get_inventory_levels", {"part_numbers": part_numbers})

        if random.random() < self.failure_rate:
            raise Exception("Mock API failure: Inventory service unavailable")

        inventory = {}
        for part_number in part_numbers:
            inventory[part_number] = {
                "available_quantity": random.randint(0, 1000),
                "reserved_quantity": random.randint(0, 100),
                "reorder_level": random.randint(50, 200),
                "lead_time_days": random.randint(1, 30),
                "supplier": f"Supplier_{random.randint(1, 10)}",
                "unit_cost": random.uniform(10.0, 1000.0),
            }

        return inventory

    async def _simulate_delay(self):
        """Simulate API response delay."""
        import asyncio

        await asyncio.sleep(self.response_delay)

    def _record_api_call(self, endpoint: str, params: Any):
        """Record API call for testing verification."""
        self.api_calls.append(
            {
                "endpoint": endpoint,
                "params": params,
                "timestamp": datetime.utcnow(),
            }
        )

    def set_failure_rate(self, rate: float):
        """Set API failure rate for testing."""
        self.failure_rate = max(0.0, min(1.0, rate))

    def get_api_call_history(self) -> list[dict[str, Any]]:
        """Get history of API calls."""
        return self.api_calls.copy()

    def reset_call_history(self):
        """Reset API call history."""
        self.api_calls.clear()


class MockServiceFactory:
    """Factory for creating configured mock services."""

    @staticmethod
    def create_optimization_service(
        behavior: str = "optimal",
    ) -> MockOptimizationService:
        """Create a mock optimization service."""
        return MockOptimizationService(behavior=behavior)

    @staticmethod
    def create_constraint_validation_service(
        violations: list[str] = None,
    ) -> MockConstraintValidationService:
        """Create a mock constraint validation service."""
        return MockConstraintValidationService(violation_patterns=violations or [])

    @staticmethod
    def create_resource_allocation_service(
        availability: dict[str, float] = None,
    ) -> MockResourceAllocationService:
        """Create a mock resource allocation service."""
        return MockResourceAllocationService(resource_availability=availability)

    @staticmethod
    def create_workflow_service() -> MockWorkflowService:
        """Create a mock workflow service."""
        return MockWorkflowService()

    @staticmethod
    def create_external_api_service(
        failure_rate: float = 0.05,
    ) -> MockExternalAPIService:
        """Create a mock external API service."""
        return MockExternalAPIService(failure_rate=failure_rate)

    @staticmethod
    def create_complete_mock_services(
        optimization_behavior: str = "optimal",
        constraint_violations: list[str] = None,
        resource_availability: dict[str, float] = None,
        api_failure_rate: float = 0.05,
    ) -> dict[str, Any]:
        """Create a complete set of mock services for testing."""
        return {
            "optimization_service": MockServiceFactory.create_optimization_service(
                optimization_behavior
            ),
            "constraint_validation_service": MockServiceFactory.create_constraint_validation_service(
                constraint_violations
            ),
            "resource_allocation_service": MockServiceFactory.create_resource_allocation_service(
                resource_availability
            ),
            "workflow_service": MockServiceFactory.create_workflow_service(),
            "external_api_service": MockServiceFactory.create_external_api_service(
                api_failure_rate
            ),
        }


# Utility functions for creating mock data patterns


def create_mock_job_scenario(
    job_count: int = 5,
    with_tasks: bool = True,
    priority_distribution: dict[str, float] = None,
) -> list[Job]:
    """Create a realistic scenario of mock jobs."""
    priority_dist = priority_distribution or {
        "LOW": 0.2,
        "NORMAL": 0.5,
        "HIGH": 0.2,
        "URGENT": 0.1,
    }

    jobs = []
    for i in range(job_count):
        # Select priority based on distribution
        rand = random.random()
        cumulative = 0
        priority = "NORMAL"
        for prio, prob in priority_dist.items():
            cumulative += prob
            if rand <= cumulative:
                priority = prio
                break

        if with_tasks:
            job = JobFactory.create_with_tasks(
                task_count=random.randint(2, 5),
                job_number=f"MOCK_JOB_{i+1:03d}",
                priority=priority,
            )
        else:
            job = JobFactory.create(
                job_number=f"MOCK_JOB_{i+1:03d}",
                priority=priority,
            )

        jobs.append(job)

    return jobs


def create_mock_production_scenario() -> dict[str, Any]:
    """Create a complete mock production scenario."""
    jobs = create_mock_job_scenario(job_count=10, with_tasks=True)

    # Create mock schedules
    schedules = []
    for i in range(3):
        schedule = Schedule(
            name=f"Mock Schedule {i+1}",
            planning_horizon=Duration(days=7),
        )

        # Add subset of jobs to each schedule
        job_subset = jobs[i * 3 : (i + 1) * 3] if i * 3 < len(jobs) else jobs[-3:]
        for job in job_subset:
            schedule.add_job(job.id)

        schedules.append(schedule)

    return {
        "jobs": jobs,
        "schedules": schedules,
        "total_tasks": sum(job.task_count for job in jobs),
        "scenario_type": "production_test",
    }


if __name__ == "__main__":
    # Example usage of mock services

    # Create mock services
    services = MockServiceFactory.create_complete_mock_services(
        optimization_behavior="optimal",
        constraint_violations=["resource_conflict"],
        api_failure_rate=0.1,
    )

    print("Mock services created:")
    for name, service in services.items():
        print(f"- {name}: {type(service).__name__}")

    # Create mock scenario
    scenario = create_mock_production_scenario()
    print("\nMock scenario created:")
    print(f"- Jobs: {len(scenario['jobs'])}")
    print(f"- Schedules: {len(scenario['schedules'])}")
    print(f"- Total tasks: {scenario['total_tasks']}")
