"""
Test Data Factories

Factory classes for creating test data for database tests.
These factories provide consistent and reusable test data creation.
"""

import random
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import OperatorAssignment, Task
from app.domain.scheduling.value_objects.enums import (
    AssignmentType,
    JobStatus,
    PriorityLevel,
    TaskStatus,
)


class JobFactory:
    """Factory for creating Job test instances."""

    @staticmethod
    def create(
        job_number: str | None = None,
        customer_name: str | None = None,
        part_number: str | None = None,
        quantity: int = 1,
        priority: PriorityLevel = PriorityLevel.NORMAL,
        status: JobStatus = JobStatus.PLANNED,
        due_date: datetime | None = None,
        created_by: str | None = None,
        **kwargs,
    ) -> Job:
        """Create a Job instance with optional parameters."""
        if job_number is None:
            job_number = (
                f"J{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            )

        if customer_name is None:
            customers = [
                "Acme Corp",
                "Global Industries",
                "Tech Solutions",
                "Manufacturing Co",
                "Quality Parts",
            ]
            customer_name = random.choice(customers)

        if part_number is None:
            part_number = (
                f"PART-{random.randint(100, 999)}{random.choice(['A', 'B', 'C'])}"
            )

        if due_date is None:
            due_date = datetime.utcnow() + timedelta(days=random.randint(1, 30))

        if created_by is None:
            created_by = f"user_{random.randint(1, 10)}"

        job = Job.create(
            job_number=job_number,
            due_date=due_date,
            customer_name=customer_name,
            part_number=part_number,
            quantity=quantity,
            priority=priority,
            created_by=created_by,
        )

        # Set additional properties if provided in kwargs
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

        return job

    @staticmethod
    def create_with_tasks(task_count: int = 3, **job_kwargs) -> Job:
        """Create a Job with multiple tasks."""
        job = JobFactory.create(**job_kwargs)

        for i in range(1, task_count + 1):
            task = TaskFactory.create(
                job_id=job.id,
                sequence_in_job=i * 10,
                planned_duration_minutes=random.randint(30, 180),
            )
            job.add_task(task)

        return job

    @staticmethod
    def create_overdue() -> Job:
        """Create an overdue job."""
        return JobFactory.create(
            due_date=datetime.utcnow() - timedelta(days=random.randint(1, 10))
        )

    @staticmethod
    def create_urgent() -> Job:
        """Create an urgent priority job."""
        return JobFactory.create(
            priority=PriorityLevel.URGENT,
            due_date=datetime.utcnow() + timedelta(hours=random.randint(1, 48)),
        )

    @staticmethod
    def create_batch(count: int = 10) -> list[Job]:
        """Create a batch of jobs with variety."""
        jobs = []
        priorities = list(PriorityLevel)

        for i in range(count):
            priority = random.choice(priorities)
            due_days = random.randint(1, 60)
            quantity = random.randint(1, 100)

            job = JobFactory.create(
                job_number=f"BATCH-{i+1:03d}",
                priority=priority,
                quantity=quantity,
                due_date=datetime.utcnow() + timedelta(days=due_days),
            )
            jobs.append(job)

        return jobs


class TaskFactory:
    """Factory for creating Task test instances."""

    @staticmethod
    def create(
        job_id: UUID | None = None,
        operation_id: UUID | None = None,
        sequence_in_job: int = 10,
        status: TaskStatus = TaskStatus.PENDING,
        planned_duration_minutes: int | None = None,
        setup_duration_minutes: int = 0,
        **kwargs,
    ) -> Task:
        """Create a Task instance with optional parameters."""
        if job_id is None:
            job_id = uuid4()

        if operation_id is None:
            operation_id = uuid4()

        if planned_duration_minutes is None:
            planned_duration_minutes = random.randint(30, 240)

        task = Task.create(
            job_id=job_id,
            operation_id=operation_id,
            sequence_in_job=sequence_in_job,
            planned_duration_minutes=planned_duration_minutes,
            setup_duration_minutes=setup_duration_minutes,
        )

        # Set additional properties if provided
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        return task

    @staticmethod
    def create_ready(job_id: UUID | None = None) -> Task:
        """Create a task in READY status."""
        task = TaskFactory.create(job_id=job_id, sequence_in_job=10)
        task.mark_ready()
        return task

    @staticmethod
    def create_scheduled(
        job_id: UUID | None = None, start_offset_hours: int = 1, duration_hours: int = 2
    ) -> Task:
        """Create a scheduled task."""
        task = TaskFactory.create_ready(job_id=job_id)

        start_time = datetime.utcnow() + timedelta(hours=start_offset_hours)
        end_time = start_time + timedelta(hours=duration_hours)
        machine_id = uuid4()

        task.schedule(start_time, end_time, machine_id)
        return task

    @staticmethod
    def create_in_progress(job_id: UUID | None = None) -> Task:
        """Create a task in progress."""
        task = TaskFactory.create_scheduled(job_id=job_id, start_offset_hours=0)
        task.start()
        return task

    @staticmethod
    def create_completed(job_id: UUID | None = None) -> Task:
        """Create a completed task."""
        task = TaskFactory.create_in_progress(job_id=job_id)
        completion_time = datetime.utcnow() + timedelta(minutes=random.randint(1, 10))
        task.complete(completion_time)
        return task

    @staticmethod
    def create_critical_path(job_id: UUID | None = None) -> Task:
        """Create a critical path task."""
        task = TaskFactory.create(job_id=job_id)
        task.mark_critical_path()
        return task

    @staticmethod
    def create_with_delay(job_id: UUID | None = None, delay_minutes: int = 30) -> Task:
        """Create a delayed task."""
        task = TaskFactory.create_ready(job_id=job_id)

        original_start = datetime.utcnow() + timedelta(hours=1)
        delayed_start = original_start + timedelta(minutes=delay_minutes)
        end_time = delayed_start + timedelta(hours=2)

        # Schedule with original time first
        task.schedule(original_start, original_start + timedelta(hours=2))
        # Then reschedule with delay
        task.reschedule(delayed_start, end_time, "resource_conflict")

        return task

    @staticmethod
    def create_with_rework(job_id: UUID | None = None, rework_count: int = 1) -> Task:
        """Create a task with rework history."""
        task = TaskFactory.create(job_id=job_id)

        for i in range(rework_count):
            reasons = [
                "quality_issue",
                "dimension_out_of_spec",
                "surface_finish",
                "assembly_error",
            ]
            reason = random.choice(reasons)
            task.record_rework(f"{reason}_{i+1}")

        return task

    @staticmethod
    def create_batch(
        job_id: UUID, count: int = 5, start_sequence: int = 10
    ) -> list[Task]:
        """Create a batch of tasks for a job."""
        tasks = []

        for i in range(count):
            sequence = start_sequence + (i * 10)
            duration = random.randint(30, 180)
            setup = random.randint(0, 30)

            task = TaskFactory.create(
                job_id=job_id,
                sequence_in_job=sequence,
                planned_duration_minutes=duration,
                setup_duration_minutes=setup,
            )
            tasks.append(task)

        return tasks


class OperatorAssignmentFactory:
    """Factory for creating OperatorAssignment test instances."""

    @staticmethod
    def create(
        task_id: UUID | None = None,
        operator_id: UUID | None = None,
        assignment_type: AssignmentType = AssignmentType.FULL_DURATION,
        planned_duration_hours: int = 2,
        **kwargs,
    ) -> OperatorAssignment:
        """Create an OperatorAssignment instance."""
        if task_id is None:
            task_id = uuid4()

        if operator_id is None:
            operator_id = uuid4()

        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=planned_duration_hours)

        assignment = OperatorAssignment(
            task_id=task_id,
            operator_id=operator_id,
            assignment_type=assignment_type,
            planned_start_time=start_time,
            planned_end_time=end_time,
        )

        # Set additional properties
        for key, value in kwargs.items():
            if hasattr(assignment, key):
                setattr(assignment, key, value)

        return assignment

    @staticmethod
    def create_active(
        task_id: UUID | None = None, operator_id: UUID | None = None
    ) -> OperatorAssignment:
        """Create an active operator assignment."""
        assignment = OperatorAssignmentFactory.create(
            task_id=task_id, operator_id=operator_id
        )
        assignment.start_assignment(datetime.utcnow())
        return assignment

    @staticmethod
    def create_completed(
        task_id: UUID | None = None,
        operator_id: UUID | None = None,
        duration_minutes: int = 90,
    ) -> OperatorAssignment:
        """Create a completed operator assignment."""
        assignment = OperatorAssignmentFactory.create_active(
            task_id=task_id, operator_id=operator_id
        )

        end_time = assignment.actual_start_time + timedelta(minutes=duration_minutes)
        assignment.complete_assignment(end_time)
        return assignment

    @staticmethod
    def create_setup_only(
        task_id: UUID | None = None, operator_id: UUID | None = None
    ) -> OperatorAssignment:
        """Create a setup-only operator assignment."""
        return OperatorAssignmentFactory.create(
            task_id=task_id,
            operator_id=operator_id,
            assignment_type=AssignmentType.SETUP_ONLY,
            planned_duration_hours=0.5,
        )

    @staticmethod
    def create_batch(
        task_id: UUID, operator_count: int = 3
    ) -> list[OperatorAssignment]:
        """Create multiple operator assignments for a task."""
        assignments = []
        assignment_types = [
            AssignmentType.FULL_DURATION,
            AssignmentType.SETUP_ONLY,
            AssignmentType.PARTIAL_DURATION,
        ]

        for _i in range(operator_count):
            assignment_type = random.choice(assignment_types)
            duration = random.randint(1, 4)

            assignment = OperatorAssignmentFactory.create(
                task_id=task_id,
                operator_id=uuid4(),
                assignment_type=assignment_type,
                planned_duration_hours=duration,
            )
            assignments.append(assignment)

        return assignments


class TestDataBuilder:
    """Builder class for creating complex test scenarios."""

    @staticmethod
    def create_manufacturing_scenario(
        job_count: int = 5, tasks_per_job: int = 4, operators_per_task: int = 2
    ) -> tuple[list[Job], list[Task], list[OperatorAssignment]]:
        """Create a complete manufacturing scenario with jobs, tasks, and assignments."""
        all_jobs = []
        all_tasks = []
        all_assignments = []

        for job_idx in range(job_count):
            # Create job with varying priorities and due dates
            priority = random.choice(list(PriorityLevel))
            due_days = random.randint(1, 30)

            job = JobFactory.create(
                job_number=f"SCENARIO-{job_idx + 1:03d}",
                priority=priority,
                due_date=datetime.utcnow() + timedelta(days=due_days),
            )
            all_jobs.append(job)

            # Create tasks for this job
            job_tasks = TaskFactory.create_batch(
                job_id=job.id, count=tasks_per_job, start_sequence=10
            )

            # Add tasks to job and collect them
            for task in job_tasks:
                job.add_task(task)
                all_tasks.append(task)

                # Create operator assignments for each task
                task_assignments = OperatorAssignmentFactory.create_batch(
                    task_id=task.id, operator_count=operators_per_task
                )

                # Add assignments to task
                for assignment in task_assignments:
                    task.add_operator_assignment(assignment)
                    all_assignments.append(assignment)

        return all_jobs, all_tasks, all_assignments

    @staticmethod
    def create_workload_scenario() -> dict:
        """Create a realistic workload scenario for performance testing."""
        # Create jobs in different states
        planned_jobs = [JobFactory.create(status=JobStatus.PLANNED) for _ in range(20)]
        released_jobs = [
            JobFactory.create(status=JobStatus.RELEASED) for _ in range(15)
        ]
        in_progress_jobs = [
            JobFactory.create(status=JobStatus.IN_PROGRESS) for _ in range(10)
        ]
        completed_jobs = [
            JobFactory.create(status=JobStatus.COMPLETED) for _ in range(5)
        ]

        # Create overdue jobs
        overdue_jobs = [JobFactory.create_overdue() for _ in range(5)]

        # Create urgent jobs
        urgent_jobs = [JobFactory.create_urgent() for _ in range(3)]

        all_jobs = (
            planned_jobs
            + released_jobs
            + in_progress_jobs
            + completed_jobs
            + overdue_jobs
            + urgent_jobs
        )

        # Create tasks in various states
        all_tasks = []
        for job in all_jobs:
            task_count = random.randint(2, 8)
            for i in range(task_count):
                if job.status == JobStatus.PLANNED:
                    task = TaskFactory.create(
                        job_id=job.id, sequence_in_job=(i + 1) * 10
                    )
                elif job.status == JobStatus.RELEASED:
                    if i == 0:
                        task = TaskFactory.create_ready(job_id=job.id)
                        task.sequence_in_job = (i + 1) * 10
                    else:
                        task = TaskFactory.create(
                            job_id=job.id, sequence_in_job=(i + 1) * 10
                        )
                elif job.status == JobStatus.IN_PROGRESS:
                    if i < task_count // 2:
                        task = TaskFactory.create_completed(job_id=job.id)
                        task.sequence_in_job = (i + 1) * 10
                    elif i == task_count // 2:
                        task = TaskFactory.create_in_progress(job_id=job.id)
                        task.sequence_in_job = (i + 1) * 10
                    else:
                        task = TaskFactory.create(
                            job_id=job.id, sequence_in_job=(i + 1) * 10
                        )
                else:  # COMPLETED
                    task = TaskFactory.create_completed(job_id=job.id)
                    task.sequence_in_job = (i + 1) * 10

                job.add_task(task)
                all_tasks.append(task)

        return {
            "jobs": all_jobs,
            "tasks": all_tasks,
            "planned_jobs": planned_jobs,
            "released_jobs": released_jobs,
            "in_progress_jobs": in_progress_jobs,
            "completed_jobs": completed_jobs,
            "overdue_jobs": overdue_jobs,
            "urgent_jobs": urgent_jobs,
        }
