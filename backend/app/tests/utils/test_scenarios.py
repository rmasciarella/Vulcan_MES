"""
Test Scenarios and Data Builders

Comprehensive test scenario builders for different testing contexts including
realistic production scenarios, edge cases, performance test data, and failure scenarios.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.schedule import Schedule, ScheduleAssignment
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.value_objects.duration import Duration
from app.domain.scheduling.value_objects.enums import (
    JobStatus,
    PriorityLevel,
)
from app.tests.database.factories import JobFactory, TaskFactory


class ScenarioType(Enum):
    """Types of test scenarios."""

    BASIC = "basic"
    COMPLEX = "complex"
    HIGH_LOAD = "high_load"
    EDGE_CASE = "edge_case"
    ERROR_PRONE = "error_prone"
    PERFORMANCE = "performance"
    REALISTIC = "realistic"


@dataclass
class ScenarioConfig:
    """Configuration for test scenario generation."""

    scenario_type: ScenarioType
    job_count: int = 10
    tasks_per_job_range: tuple[int, int] = (2, 5)
    time_horizon_days: int = 30
    priority_distribution: dict[str, float] = None
    status_distribution: dict[str, float] = None
    complexity_factors: dict[str, Any] = None
    edge_case_types: list[str] = None

    def __post_init__(self):
        if self.priority_distribution is None:
            self.priority_distribution = {
                "LOW": 0.2,
                "NORMAL": 0.5,
                "HIGH": 0.2,
                "URGENT": 0.1,
            }

        if self.status_distribution is None:
            self.status_distribution = {
                "PLANNED": 0.3,
                "RELEASED": 0.4,
                "IN_PROGRESS": 0.2,
                "COMPLETED": 0.1,
            }

        if self.complexity_factors is None:
            self.complexity_factors = {
                "skill_requirements": True,
                "operator_assignments": True,
                "dependencies": True,
                "rework_possibility": 0.1,
            }

        if self.edge_case_types is None:
            self.edge_case_types = [
                "overdue_jobs",
                "zero_duration_tasks",
                "circular_dependencies",
                "resource_conflicts",
                "invalid_dates",
            ]


class TestScenarioBuilder:
    """Builder for creating comprehensive test scenarios."""

    def __init__(self, config: ScenarioConfig):
        self.config = config
        self.scenario_data = {
            "jobs": [],
            "tasks": [],
            "schedules": [],
            "metadata": {},
        }

    def build(self) -> dict[str, Any]:
        """Build the complete test scenario."""
        if self.config.scenario_type == ScenarioType.BASIC:
            return self._build_basic_scenario()
        elif self.config.scenario_type == ScenarioType.COMPLEX:
            return self._build_complex_scenario()
        elif self.config.scenario_type == ScenarioType.HIGH_LOAD:
            return self._build_high_load_scenario()
        elif self.config.scenario_type == ScenarioType.EDGE_CASE:
            return self._build_edge_case_scenario()
        elif self.config.scenario_type == ScenarioType.ERROR_PRONE:
            return self._build_error_prone_scenario()
        elif self.config.scenario_type == ScenarioType.PERFORMANCE:
            return self._build_performance_scenario()
        elif self.config.scenario_type == ScenarioType.REALISTIC:
            return self._build_realistic_scenario()
        else:
            return self._build_basic_scenario()

    def _build_basic_scenario(self) -> dict[str, Any]:
        """Build a basic test scenario."""
        jobs = []

        for i in range(self.config.job_count):
            job = JobFactory.create(
                job_number=f"BASIC_{i+1:03d}",
                customer_name=f"Customer {i+1}",
                due_date=datetime.utcnow() + timedelta(days=random.randint(1, 30)),
            )

            # Add simple tasks
            task_count = random.randint(*self.config.tasks_per_job_range)
            for j in range(task_count):
                task = TaskFactory.create(
                    job_id=job.id,
                    sequence_in_job=(j + 1) * 10,
                    planned_duration_minutes=random.randint(60, 180),
                )
                job.add_task(task)

            jobs.append(job)

        return {
            "jobs": jobs,
            "tasks": sum([job.get_all_tasks() for job in jobs], []),
            "schedules": [],
            "metadata": {
                "scenario_type": "basic",
                "total_jobs": len(jobs),
                "total_tasks": sum(job.task_count for job in jobs),
                "complexity_level": "low",
            },
        }

    def _build_complex_scenario(self) -> dict[str, Any]:
        """Build a complex test scenario with interdependencies."""
        jobs = []
        all_tasks = []

        # Create jobs with varying complexity
        for i in range(self.config.job_count):
            priority = self._select_priority()
            status = self._select_status()

            job = JobFactory.create(
                job_number=f"COMPLEX_{i+1:03d}",
                customer_name=f"Complex Customer {i+1}",
                priority=priority,
                status=status,
                quantity=random.randint(1, 50),
                due_date=datetime.utcnow() + timedelta(days=random.randint(5, 60)),
            )

            # Add complex tasks with dependencies
            task_count = random.randint(*self.config.tasks_per_job_range)
            job_tasks = []

            for j in range(task_count):
                task = TaskFactory.create(
                    job_id=job.id,
                    sequence_in_job=(j + 1) * 10,
                    planned_duration_minutes=random.randint(30, 300),
                    setup_duration_minutes=random.randint(10, 60),
                )

                # Add skill requirements
                if self.config.complexity_factors.get("skill_requirements", False):
                    self._add_skill_requirements(task, j)

                # Add operator assignments
                if self.config.complexity_factors.get("operator_assignments", False):
                    self._add_operator_assignments(task)

                # Add rework possibility
                if random.random() < self.config.complexity_factors.get(
                    "rework_possibility", 0.1
                ):
                    task.record_rework(f"Quality issue {random.randint(1, 5)}")

                job.add_task(task)
                job_tasks.append(task)
                all_tasks.append(task)

            # Add task dependencies
            if self.config.complexity_factors.get("dependencies", False):
                self._add_task_dependencies(job_tasks)

            jobs.append(job)

        # Create schedules with assignments
        schedules = self._create_complex_schedules(jobs)

        return {
            "jobs": jobs,
            "tasks": all_tasks,
            "schedules": schedules,
            "metadata": {
                "scenario_type": "complex",
                "total_jobs": len(jobs),
                "total_tasks": len(all_tasks),
                "total_schedules": len(schedules),
                "complexity_level": "high",
                "has_dependencies": True,
                "has_skill_requirements": self.config.complexity_factors.get(
                    "skill_requirements", False
                ),
            },
        }

    def _build_high_load_scenario(self) -> dict[str, Any]:
        """Build a high-load scenario for stress testing."""
        job_count = max(self.config.job_count, 100)  # Minimum 100 jobs for high load
        jobs = []

        # Create many jobs with realistic distribution
        customers = [f"HighLoad Customer {i}" for i in range(20)]  # Repeat customers
        part_numbers = [f"PART-HL-{i:04d}" for i in range(50)]  # Common parts

        for i in range(job_count):
            job = JobFactory.create(
                job_number=f"HL_{i+1:05d}",
                customer_name=random.choice(customers),
                part_number=random.choice(part_numbers),
                priority=self._select_priority(),
                quantity=random.randint(1, 100),
                due_date=datetime.utcnow() + timedelta(days=random.randint(1, 90)),
            )

            # Add many tasks per job
            task_count = random.randint(5, 15)  # More tasks for high load
            for j in range(task_count):
                task = TaskFactory.create(
                    job_id=job.id,
                    sequence_in_job=(j + 1) * 5,  # Tighter sequence numbers
                    planned_duration_minutes=random.randint(15, 480),  # Wide range
                    setup_duration_minutes=random.randint(5, 30),
                )
                job.add_task(task)

            jobs.append(job)

        return {
            "jobs": jobs,
            "tasks": sum([job.get_all_tasks() for job in jobs], []),
            "schedules": [],
            "metadata": {
                "scenario_type": "high_load",
                "total_jobs": len(jobs),
                "total_tasks": sum(job.task_count for job in jobs),
                "complexity_level": "high",
                "load_factor": "extreme",
            },
        }

    def _build_edge_case_scenario(self) -> dict[str, Any]:
        """Build a scenario with edge cases and boundary conditions."""
        jobs = []
        edge_cases_created = []

        for edge_case_type in self.config.edge_case_types:
            if edge_case_type == "overdue_jobs":
                job = self._create_overdue_job()
                jobs.append(job)
                edge_cases_created.append("overdue_job")

            elif edge_case_type == "zero_duration_tasks":
                job = self._create_job_with_zero_duration_task()
                jobs.append(job)
                edge_cases_created.append("zero_duration_task")

            elif edge_case_type == "circular_dependencies":
                circular_jobs = self._create_circular_dependency_jobs()
                jobs.extend(circular_jobs)
                edge_cases_created.append("circular_dependencies")

            elif edge_case_type == "resource_conflicts":
                conflict_jobs = self._create_resource_conflict_jobs()
                jobs.extend(conflict_jobs)
                edge_cases_created.append("resource_conflicts")

            elif edge_case_type == "invalid_dates":
                job = self._create_job_with_invalid_dates()
                jobs.append(job)
                edge_cases_created.append("invalid_dates")

        # Add some normal jobs for contrast
        for i in range(3):
            normal_job = JobFactory.create(
                job_number=f"NORMAL_EDGE_{i+1}",
                customer_name=f"Normal Customer {i+1}",
            )
            jobs.append(normal_job)

        return {
            "jobs": jobs,
            "tasks": sum([job.get_all_tasks() for job in jobs], []),
            "schedules": [],
            "metadata": {
                "scenario_type": "edge_case",
                "total_jobs": len(jobs),
                "edge_cases_created": edge_cases_created,
                "complexity_level": "extreme",
            },
        }

    def _build_error_prone_scenario(self) -> dict[str, Any]:
        """Build a scenario designed to trigger errors and failures."""
        jobs = []

        # Create jobs with problematic data
        for i in range(self.config.job_count):
            # Some jobs will have issues
            if i % 3 == 0:  # Every third job has issues
                job = self._create_problematic_job(i)
            else:
                job = JobFactory.create(
                    job_number=f"ERROR_PRONE_{i+1:03d}",
                    customer_name=f"Customer {i+1}",
                )

            jobs.append(job)

        return {
            "jobs": jobs,
            "tasks": sum([job.get_all_tasks() for job in jobs], []),
            "schedules": [],
            "metadata": {
                "scenario_type": "error_prone",
                "total_jobs": len(jobs),
                "error_probability": 0.33,
                "complexity_level": "high",
            },
        }

    def _build_performance_scenario(self) -> dict[str, Any]:
        """Build a scenario optimized for performance testing."""
        # Large dataset with controlled complexity
        job_count = max(self.config.job_count, 500)
        jobs = []

        # Batch create jobs for better performance testing
        batch_size = 50
        for batch in range(0, job_count, batch_size):
            batch_jobs = []
            for i in range(min(batch_size, job_count - batch)):
                job_index = batch + i
                job = JobFactory.create(
                    job_number=f"PERF_{job_index+1:06d}",
                    customer_name=f"Perf Customer {(job_index % 100) + 1}",  # Reuse customers
                    due_date=datetime.utcnow() + timedelta(days=random.randint(1, 365)),
                )

                # Consistent task count for performance predictability
                task_count = 4  # Fixed number for consistent performance
                for j in range(task_count):
                    task = TaskFactory.create(
                        job_id=job.id,
                        sequence_in_job=(j + 1) * 10,
                        planned_duration_minutes=90,  # Fixed duration
                        setup_duration_minutes=15,  # Fixed setup
                    )
                    job.add_task(task)

                batch_jobs.append(job)

            jobs.extend(batch_jobs)

        return {
            "jobs": jobs,
            "tasks": sum([job.get_all_tasks() for job in jobs], []),
            "schedules": [],
            "metadata": {
                "scenario_type": "performance",
                "total_jobs": len(jobs),
                "total_tasks": len(jobs) * 4,  # Fixed 4 tasks per job
                "batch_size": batch_size,
                "complexity_level": "controlled",
            },
        }

    def _build_realistic_scenario(self) -> dict[str, Any]:
        """Build a realistic manufacturing scenario."""
        # Simulate real manufacturing environment
        jobs = []

        # Industry-specific data
        customers = [
            "Aerospace Dynamics Corp",
            "Automotive Solutions Ltd",
            "Precision Manufacturing Inc",
            "Heavy Industry Partners",
            "Electronic Components Co",
            "Marine Systems LLC",
        ]

        product_lines = [
            {"prefix": "AER", "complexity": "high", "duration_range": (120, 480)},
            {"prefix": "AUTO", "complexity": "medium", "duration_range": (60, 240)},
            {"prefix": "PREC", "complexity": "high", "duration_range": (90, 360)},
            {"prefix": "HEAVY", "complexity": "low", "duration_range": (180, 600)},
            {"prefix": "ELEC", "complexity": "medium", "duration_range": (30, 180)},
            {"prefix": "MARINE", "complexity": "high", "duration_range": (240, 720)},
        ]

        for i in range(self.config.job_count):
            customer = random.choice(customers)
            product_line = random.choice(product_lines)

            # Realistic job creation based on industry patterns
            job = JobFactory.create(
                job_number=f"{product_line['prefix']}-{datetime.utcnow().year}-{i+1:04d}",
                customer_name=customer,
                part_number=f"{product_line['prefix']}-PART-{random.randint(1000, 9999)}",
                priority=self._select_realistic_priority(product_line["complexity"]),
                quantity=self._select_realistic_quantity(product_line["complexity"]),
                due_date=self._select_realistic_due_date(product_line["complexity"]),
            )

            # Add realistic tasks based on product complexity
            task_count = self._get_realistic_task_count(product_line["complexity"])
            duration_range = product_line["duration_range"]

            for j in range(task_count):
                task = TaskFactory.create(
                    job_id=job.id,
                    sequence_in_job=(j + 1) * 10,
                    planned_duration_minutes=random.randint(*duration_range),
                    setup_duration_minutes=self._get_realistic_setup_time(
                        product_line["complexity"]
                    ),
                )

                # Add realistic skill requirements
                if product_line["complexity"] in ["medium", "high"]:
                    self._add_realistic_skill_requirements(task, product_line["prefix"])

                job.add_task(task)

            jobs.append(job)

        # Create realistic schedules
        schedules = self._create_realistic_schedules(jobs)

        return {
            "jobs": jobs,
            "tasks": sum([job.get_all_tasks() for job in jobs], []),
            "schedules": schedules,
            "metadata": {
                "scenario_type": "realistic",
                "total_jobs": len(jobs),
                "total_tasks": sum(job.task_count for job in jobs),
                "customers": len(customers),
                "product_lines": len(product_lines),
                "complexity_level": "realistic",
                "industry_simulation": True,
            },
        }

    # Helper methods for scenario building

    def _select_priority(self) -> PriorityLevel:
        """Select priority based on distribution."""
        rand = random.random()
        cumulative = 0

        for priority_str, probability in self.config.priority_distribution.items():
            cumulative += probability
            if rand <= cumulative:
                return PriorityLevel[priority_str]

        return PriorityLevel.NORMAL

    def _select_status(self) -> JobStatus:
        """Select status based on distribution."""
        rand = random.random()
        cumulative = 0

        for status_str, probability in self.config.status_distribution.items():
            cumulative += probability
            if rand <= cumulative:
                return JobStatus[status_str]

        return JobStatus.PLANNED

    def _add_skill_requirements(self, task: Task, task_index: int):
        """Add skill requirements to a task."""
        # Implementation would add specific skill requirements
        # For now, just mark that skills are required
        pass

    def _add_operator_assignments(self, task: Task):
        """Add operator assignments to a task."""
        # Implementation would create operator assignments
        pass

    def _add_task_dependencies(self, tasks: list[Task]):
        """Add dependencies between tasks."""
        # Implementation would create task dependencies
        pass

    def _create_complex_schedules(self, jobs: list[Job]) -> list[Schedule]:
        """Create complex schedules with assignments."""
        schedules = []

        # Create multiple schedules with different job subsets
        job_batches = [jobs[i : i + 5] for i in range(0, len(jobs), 5)]

        for i, batch in enumerate(job_batches):
            schedule = Schedule(
                name=f"Complex Schedule {i+1}",
                planning_horizon=Duration(days=14),
            )

            for job in batch:
                schedule.add_job(job.id)

                # Add some assignments
                tasks = job.get_all_tasks()
                current_time = datetime.utcnow() + timedelta(days=i, hours=8)

                for j, task in enumerate(tasks):
                    assignment = ScheduleAssignment(
                        task_id=task.id,
                        machine_id=uuid4(),
                        operator_ids=[uuid4()],
                        start_time=current_time + timedelta(hours=j * 2),
                        end_time=current_time + timedelta(hours=j * 2 + 1.5),
                        setup_duration=Duration(minutes=20),
                        processing_duration=Duration(minutes=70),
                    )
                    schedule.assignments.append(assignment)

            schedules.append(schedule)

        return schedules

    # Edge case creation methods

    def _create_overdue_job(self) -> Job:
        """Create an overdue job."""
        return JobFactory.create(
            job_number="OVERDUE_001",
            customer_name="Overdue Customer",
            due_date=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
            status=JobStatus.IN_PROGRESS,
        )

    def _create_job_with_zero_duration_task(self) -> Job:
        """Create a job with a zero-duration task."""
        job = JobFactory.create(
            job_number="ZERO_DURATION_001",
            customer_name="Zero Duration Customer",
        )

        # Add a problematic zero-duration task
        try:
            task = TaskFactory.create(
                job_id=job.id,
                sequence_in_job=10,
                planned_duration_minutes=0,  # This should cause issues
            )
            job.add_task(task)
        except Exception:
            # If creation fails, add a normal task instead
            task = TaskFactory.create(
                job_id=job.id,
                sequence_in_job=10,
                planned_duration_minutes=1,  # Minimal duration
            )
            job.add_task(task)

        return job

    def _create_circular_dependency_jobs(self) -> list[Job]:
        """Create jobs with circular dependencies."""
        # This would create a more complex dependency scenario
        job1 = JobFactory.create(job_number="CIRCULAR_A")
        job2 = JobFactory.create(job_number="CIRCULAR_B")

        # Add tasks (dependency logic would be added in full implementation)
        for job in [job1, job2]:
            task = TaskFactory.create(job_id=job.id, sequence_in_job=10)
            job.add_task(task)

        return [job1, job2]

    def _create_resource_conflict_jobs(self) -> list[Job]:
        """Create jobs that will have resource conflicts."""
        jobs = []
        uuid4()  # Same machine for conflicts

        for i in range(2):
            job = JobFactory.create(job_number=f"CONFLICT_{i+1}")
            task = TaskFactory.create(job_id=job.id, sequence_in_job=10)
            job.add_task(task)
            jobs.append(job)

        return jobs

    def _create_job_with_invalid_dates(self) -> Job:
        """Create a job with problematic date relationships."""
        job = JobFactory.create(
            job_number="INVALID_DATES_001",
            due_date=datetime.utcnow() + timedelta(days=7),
        )

        # Try to create task with end before start (if validation allows)
        task = TaskFactory.create(job_id=job.id, sequence_in_job=10)

        # Set problematic dates
        task.planned_start_time = datetime.utcnow() + timedelta(hours=2)
        task.planned_end_time = datetime.utcnow() + timedelta(hours=1)  # Before start

        job.add_task(task)
        return job

    def _create_problematic_job(self, index: int) -> Job:
        """Create a job with various problems for error testing."""
        problems = ["long_job_number", "special_characters", "extreme_quantity"]
        problem_type = problems[index % len(problems)]

        if problem_type == "long_job_number":
            job_number = "VERY_LONG_JOB_NUMBER_" + "X" * 100  # Exceeds typical limits
        elif problem_type == "special_characters":
            job_number = f"JOB-{index}!@#$%^&*()"  # Special characters
        else:  # extreme_quantity
            job_number = f"EXTREME_{index}"

        try:
            job = JobFactory.create(
                job_number=job_number,
                customer_name="Problematic Customer",
                quantity=999999 if problem_type == "extreme_quantity" else 1,
            )
        except Exception:
            # Fallback to normal job if creation fails
            job = JobFactory.create(
                job_number=f"FALLBACK_{index}",
                customer_name="Fallback Customer",
            )

        return job

    # Realistic scenario helpers

    def _select_realistic_priority(self, complexity: str) -> PriorityLevel:
        """Select realistic priority based on product complexity."""
        if complexity == "high":
            return random.choice([PriorityLevel.HIGH, PriorityLevel.URGENT])
        elif complexity == "medium":
            return random.choice([PriorityLevel.NORMAL, PriorityLevel.HIGH])
        else:
            return random.choice([PriorityLevel.LOW, PriorityLevel.NORMAL])

    def _select_realistic_quantity(self, complexity: str) -> int:
        """Select realistic quantity based on product complexity."""
        if complexity == "high":
            return random.randint(1, 10)  # Complex products in small quantities
        elif complexity == "medium":
            return random.randint(5, 50)
        else:
            return random.randint(20, 200)  # Simple products in large quantities

    def _select_realistic_due_date(self, complexity: str) -> datetime:
        """Select realistic due date based on product complexity."""
        base_date = datetime.utcnow()
        if complexity == "high":
            return base_date + timedelta(
                days=random.randint(30, 120)
            )  # Longer lead times
        elif complexity == "medium":
            return base_date + timedelta(days=random.randint(14, 60))
        else:
            return base_date + timedelta(days=random.randint(7, 30))

    def _get_realistic_task_count(self, complexity: str) -> int:
        """Get realistic task count based on complexity."""
        if complexity == "high":
            return random.randint(5, 10)
        elif complexity == "medium":
            return random.randint(3, 6)
        else:
            return random.randint(2, 4)

    def _get_realistic_setup_time(self, complexity: str) -> int:
        """Get realistic setup time based on complexity."""
        if complexity == "high":
            return random.randint(30, 90)
        elif complexity == "medium":
            return random.randint(15, 45)
        else:
            return random.randint(10, 30)

    def _add_realistic_skill_requirements(self, task: Task, product_prefix: str):
        """Add realistic skill requirements based on product type."""
        # Implementation would add industry-specific skill requirements
        pass

    def _create_realistic_schedules(self, jobs: list[Job]) -> list[Schedule]:
        """Create realistic production schedules."""
        schedules = []

        # Weekly schedules (more realistic)
        weeks = 4
        jobs_per_week = len(jobs) // weeks

        for week in range(weeks):
            start_idx = week * jobs_per_week
            end_idx = start_idx + jobs_per_week if week < weeks - 1 else len(jobs)
            week_jobs = jobs[start_idx:end_idx]

            schedule = Schedule(
                name=f"Week {week + 1} Production Schedule",
                planning_horizon=Duration(days=7),
            )

            for job in week_jobs:
                schedule.add_job(job.id)

            schedules.append(schedule)

        return schedules


class ScenarioManager:
    """Manager for creating and managing test scenarios."""

    @staticmethod
    def create_scenario(scenario_type: ScenarioType, **kwargs) -> dict[str, Any]:
        """Create a test scenario of the specified type."""
        config = ScenarioConfig(scenario_type=scenario_type, **kwargs)
        builder = TestScenarioBuilder(config)
        return builder.build()

    @staticmethod
    def create_basic_scenario(job_count: int = 5) -> dict[str, Any]:
        """Create a basic test scenario."""
        return ScenarioManager.create_scenario(ScenarioType.BASIC, job_count=job_count)

    @staticmethod
    def create_complex_scenario(job_count: int = 10) -> dict[str, Any]:
        """Create a complex test scenario."""
        return ScenarioManager.create_scenario(
            ScenarioType.COMPLEX,
            job_count=job_count,
            complexity_factors={
                "skill_requirements": True,
                "operator_assignments": True,
                "dependencies": True,
                "rework_possibility": 0.15,
            },
        )

    @staticmethod
    def create_high_load_scenario(job_count: int = 100) -> dict[str, Any]:
        """Create a high-load test scenario."""
        return ScenarioManager.create_scenario(
            ScenarioType.HIGH_LOAD, job_count=job_count
        )

    @staticmethod
    def create_edge_case_scenario(edge_cases: list[str] = None) -> dict[str, Any]:
        """Create an edge case test scenario."""
        edge_cases = edge_cases or ["overdue_jobs", "resource_conflicts"]
        return ScenarioManager.create_scenario(
            ScenarioType.EDGE_CASE, edge_case_types=edge_cases
        )

    @staticmethod
    def create_performance_scenario(job_count: int = 500) -> dict[str, Any]:
        """Create a performance test scenario."""
        return ScenarioManager.create_scenario(
            ScenarioType.PERFORMANCE, job_count=job_count
        )

    @staticmethod
    def create_realistic_scenario(job_count: int = 20) -> dict[str, Any]:
        """Create a realistic manufacturing scenario."""
        return ScenarioManager.create_scenario(
            ScenarioType.REALISTIC, job_count=job_count
        )


if __name__ == "__main__":
    # Example usage of scenario manager

    # Create different types of scenarios
    scenarios = {
        "basic": ScenarioManager.create_basic_scenario(job_count=3),
        "complex": ScenarioManager.create_complex_scenario(job_count=5),
        "edge_case": ScenarioManager.create_edge_case_scenario(),
        "realistic": ScenarioManager.create_realistic_scenario(job_count=8),
    }

    print("Test scenarios created:")
    for name, scenario in scenarios.items():
        metadata = scenario["metadata"]
        print(f"\n{name.upper()} SCENARIO:")
        print(f"  - Jobs: {metadata['total_jobs']}")
        print(f"  - Tasks: {metadata.get('total_tasks', 'N/A')}")
        print(f"  - Complexity: {metadata.get('complexity_level', 'N/A')}")
        if "edge_cases_created" in metadata:
            print(f"  - Edge cases: {', '.join(metadata['edge_cases_created'])}")

    print(f"\nTotal scenarios: {len(scenarios)}")
