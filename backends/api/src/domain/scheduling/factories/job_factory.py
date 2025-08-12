"""
Job Factory

Factory methods for creating jobs with standard configurations,
matching DOMAIN.md specification exactly.
"""

from datetime import datetime, timedelta
from uuid import uuid4

from ..entities.job import Job
from ..entities.task import Task
from ..value_objects.enums import JobStatus, PriorityLevel
from ..value_objects.machine_option import MachineOption
from ..value_objects.skill_proficiency import SkillRequirement, SkillType


class JobFactory:
    """Factory for creating jobs with standard configurations."""

    @staticmethod
    def create_standard_job(
        job_number: str,
        operation_count: int = 100,
        priority: int = 0,
        due_date: datetime | None = None,
    ) -> Job:
        """
        Factory method to create a standard job with 100 operations.
        90% single machine options, 10% with 2 machine options.
        Matches DOMAIN.md specification exactly.

        Args:
            job_number: Unique job identifier
            operation_count: Number of operations (default 100)
            priority: Job priority (0-3)
            due_date: Optional due date

        Returns:
            Fully configured Job with tasks
        """
        # Convert numeric priority to PriorityLevel
        priority_map = {
            0: PriorityLevel.LOW,
            1: PriorityLevel.NORMAL,
            2: PriorityLevel.HIGH,
            3: PriorityLevel.CRITICAL,
        }
        priority_level = priority_map.get(priority, PriorityLevel.NORMAL)

        # Create the job
        job = Job(
            job_number=job_number, priority=priority_level, status=JobStatus.PLANNED
        )

        # Set due date if provided
        if due_date:
            job.due_date = due_date
        else:
            # Default to 7 days from now
            job.due_date = datetime.now() + timedelta(days=7)

        # Create tasks with appropriate machine options
        previous_task_id = None

        for op_num in range(operation_count):
            # 10% chance of having 2 machine options
            num_options = 2 if op_num % 10 == 0 else 1

            machine_options = []
            for _i in range(num_options):
                # Generate different machine IDs for options
                machine_id = uuid4()

                machine_options.append(
                    MachineOption.from_minutes(
                        machine_id=machine_id,
                        setup_minutes=15,  # 15 min setup
                        processing_minutes=30 + op_num,  # Variable processing
                        requires_operator_full_duration=(
                            op_num % 3 == 0
                        ),  # 33% attended
                    )
                )

            # Create skill requirements based on operation number
            skill_reqs = []
            if op_num < 20:  # First 20 ops need machining
                skill_reqs.append(SkillRequirement(SkillType.MACHINING, 2))
            elif op_num < 40:  # Next 20 need welding
                skill_reqs.append(SkillRequirement(SkillType.WELDING, 1))
            elif op_num < 60:  # Assembly
                skill_reqs.append(SkillRequirement(SkillType.ASSEMBLY, 2))
            elif op_num < 80:  # Inspection
                skill_reqs.append(SkillRequirement(SkillType.INSPECTION, 3))
            else:  # Programming
                skill_reqs.append(SkillRequirement(SkillType.PROGRAMMING, 1))

            # Determine predecessors (simple sequential for now)
            predecessor_ids = [] if previous_task_id is None else [previous_task_id]

            # Mark critical operations (every 10th operation)
            is_critical = op_num % 10 == 5

            # Calculate planned duration from machine options
            min_duration = min(opt.total_duration() for opt in machine_options)

            task = Task(
                job_id=job.id,
                operation_id=uuid4(),
                sequence_in_job=op_num + 1,  # 1-based sequence
                machine_options=machine_options,
                skill_requirements=skill_reqs,
                predecessor_ids=predecessor_ids,
                is_critical=is_critical,
                planned_duration=min_duration,
                planned_setup_duration=machine_options[0].setup_duration,
            )

            job.add_task(task)
            previous_task_id = task.id

        return job

    @staticmethod
    def create_simple_job(
        job_number: str,
        operation_count: int = 10,
        priority: PriorityLevel = PriorityLevel.NORMAL,
        due_date: datetime | None = None,
    ) -> Job:
        """
        Create a simple job with fewer operations for testing.

        Args:
            job_number: Unique job identifier
            operation_count: Number of operations
            priority: Job priority level
            due_date: Optional due date

        Returns:
            Simple Job with basic configuration
        """
        job = Job(job_number=job_number, priority=priority, status=JobStatus.PLANNED)

        if due_date:
            job.due_date = due_date

        previous_task_id = None

        for op_num in range(operation_count):
            # Single machine option for simplicity
            machine_option = MachineOption.from_minutes(
                machine_id=uuid4(),
                setup_minutes=10,
                processing_minutes=30,
                requires_operator_full_duration=True,
            )

            # Basic skill requirement
            skill_req = SkillRequirement(SkillType.MACHINING, 1)

            predecessor_ids = [] if previous_task_id is None else [previous_task_id]

            task = Task(
                job_id=job.id,
                operation_id=uuid4(),
                sequence_in_job=op_num + 1,
                machine_options=[machine_option],
                skill_requirements=[skill_req],
                predecessor_ids=predecessor_ids,
                is_critical=False,
                planned_duration=machine_option.total_duration(),
            )

            job.add_task(task)
            previous_task_id = task.id

        return job

    @staticmethod
    def create_rush_job(
        job_number: str, operation_count: int = 50, due_hours: int = 24
    ) -> Job:
        """
        Create a rush job with high priority and tight deadline.

        Args:
            job_number: Unique job identifier
            operation_count: Number of operations
            due_hours: Hours until due date

        Returns:
            Rush Job with high priority and tight schedule
        """
        due_date = datetime.now() + timedelta(hours=due_hours)

        job = Job(
            job_number=job_number,
            priority=PriorityLevel.CRITICAL,
            status=JobStatus.PLANNED,
            due_date=due_date,
        )

        previous_task_id = None

        for op_num in range(operation_count):
            # Faster processing for rush job
            machine_option = MachineOption.from_minutes(
                machine_id=uuid4(),
                setup_minutes=5,  # Reduced setup
                processing_minutes=15,  # Faster processing
                requires_operator_full_duration=True,
            )

            skill_req = SkillRequirement(SkillType.MACHINING, 2)
            predecessor_ids = [] if previous_task_id is None else [previous_task_id]

            task = Task(
                job_id=job.id,
                operation_id=uuid4(),
                sequence_in_job=op_num + 1,
                machine_options=[machine_option],
                skill_requirements=[skill_req],
                predecessor_ids=predecessor_ids,
                is_critical=(op_num % 5 == 0),  # More critical operations
                planned_duration=machine_option.total_duration(),
            )

            job.add_task(task)
            previous_task_id = task.id

        return job

    @staticmethod
    def create_complex_job(
        job_number: str,
        operation_count: int = 200,
        priority: PriorityLevel = PriorityLevel.HIGH,
    ) -> Job:
        """
        Create a complex job with multiple skill requirements and machine options.

        Args:
            job_number: Unique job identifier
            operation_count: Number of operations
            priority: Job priority level

        Returns:
            Complex Job with varied requirements
        """
        job = Job(
            job_number=job_number,
            priority=priority,
            status=JobStatus.PLANNED,
            due_date=datetime.now() + timedelta(days=14),
        )

        previous_task_id = None

        for op_num in range(operation_count):
            # Vary machine options based on operation type
            if op_num % 4 == 0:  # 25% have 3 options
                num_options = 3
            elif op_num % 2 == 0:  # 50% have 2 options
                num_options = 2
            else:  # 25% have 1 option
                num_options = 1

            machine_options = []
            for i in range(num_options):
                machine_options.append(
                    MachineOption.from_minutes(
                        machine_id=uuid4(),
                        setup_minutes=10 + (i * 5),  # Varying setup times
                        processing_minutes=25 + (op_num % 30),  # Varying processing
                        requires_operator_full_duration=(i % 2 == 0),
                    )
                )

            # Multiple skill requirements for complex operations
            skill_reqs = []
            if op_num % 20 < 10:  # Machining operations
                skill_reqs.append(
                    SkillRequirement(SkillType.MACHINING, 2 + (op_num % 2))
                )
                if op_num % 5 == 0:  # Some need programming too
                    skill_reqs.append(SkillRequirement(SkillType.PROGRAMMING, 1))
            else:  # Assembly/Inspection operations
                skill_reqs.append(
                    SkillRequirement(SkillType.ASSEMBLY, 1 + (op_num % 3))
                )
                if op_num % 10 == 0:  # Some need inspection
                    skill_reqs.append(SkillRequirement(SkillType.INSPECTION, 2))

            predecessor_ids = [] if previous_task_id is None else [previous_task_id]
            is_critical = op_num % 15 == 7  # More scattered critical operations

            min_duration = min(opt.total_duration() for opt in machine_options)

            task = Task(
                job_id=job.id,
                operation_id=uuid4(),
                sequence_in_job=op_num + 1,
                machine_options=machine_options,
                skill_requirements=skill_reqs,
                predecessor_ids=predecessor_ids,
                is_critical=is_critical,
                planned_duration=min_duration,
            )

            job.add_task(task)
            previous_task_id = task.id

        return job
