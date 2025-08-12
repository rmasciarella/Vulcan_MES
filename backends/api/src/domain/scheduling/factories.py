"""Factory and builder classes for creating scheduling domain entities."""

from datetime import date, datetime, time
from uuid import UUID

from .entities import (
    Job,
    Machine,
    MachineCapability,
    Operation,
    Operator,
    OperatorAssignment,
    ProductionZone,
    RequiredSkill,
    Task,
)
from .value_objects.common import (
    ContactInfo,
    Duration,
    OperatorSkill,
    Skill,
    WorkingHours,
)
from .value_objects.enums import (
    AssignmentType,
    MachineAutomationLevel,
    PriorityLevel,
    SkillLevel,
)


class JobBuilder:
    """Builder for creating Job entities with fluent interface."""

    def __init__(self, job_number: str, due_date: datetime):
        self._job_number = job_number
        self._due_date = due_date
        self._customer_name: str | None = None
        self._part_number: str | None = None
        self._quantity = 1
        self._priority = PriorityLevel.NORMAL
        self._created_by: str | None = None
        self._tasks: list[Task] = []

    def customer(self, customer_name: str) -> "JobBuilder":
        """Set customer name."""
        self._customer_name = customer_name
        return self

    def part(self, part_number: str) -> "JobBuilder":
        """Set part number."""
        self._part_number = part_number
        return self

    def quantity(self, quantity: int) -> "JobBuilder":
        """Set quantity."""
        self._quantity = quantity
        return self

    def priority(self, priority: PriorityLevel) -> "JobBuilder":
        """Set priority level."""
        self._priority = priority
        return self

    def created_by(self, creator: str) -> "JobBuilder":
        """Set who created the job."""
        self._created_by = creator
        return self

    def add_task(self, task: Task) -> "JobBuilder":
        """Add a task to the job."""
        self._tasks.append(task)
        return self

    def build(self) -> Job:
        """Build the Job entity."""
        job = Job.create(
            job_number=self._job_number,
            due_date=self._due_date,
            customer_name=self._customer_name,
            part_number=self._part_number,
            quantity=self._quantity,
            priority=self._priority,
            created_by=self._created_by,
        )

        # Add tasks to job
        for task in self._tasks:
            job.add_task(task)

        return job


class TaskBuilder:
    """Builder for creating Task entities with fluent interface."""

    def __init__(self, job_id: UUID, operation_id: UUID, sequence: int):
        self._job_id = job_id
        self._operation_id = operation_id
        self._sequence = sequence
        self._planned_duration: int | None = None
        self._setup_duration = 0
        self._machine_id: UUID | None = None
        self._operator_assignments: list[OperatorAssignment] = []
        self._is_critical = False

    def duration(self, minutes: int) -> "TaskBuilder":
        """Set planned duration in minutes."""
        self._planned_duration = minutes
        return self

    def setup_time(self, minutes: int) -> "TaskBuilder":
        """Set setup duration in minutes."""
        self._setup_duration = minutes
        return self

    def machine(self, machine_id: UUID) -> "TaskBuilder":
        """Assign machine to task."""
        self._machine_id = machine_id
        return self

    def operator(
        self,
        operator_id: UUID,
        assignment_type: AssignmentType = AssignmentType.FULL_DURATION,
    ) -> "TaskBuilder":
        """Add operator assignment."""
        assignment = OperatorAssignment(
            task_id=UUID(),  # Will be set when task is created
            operator_id=operator_id,
            assignment_type=assignment_type,
        )
        self._operator_assignments.append(assignment)
        return self

    def critical_path(self) -> "TaskBuilder":
        """Mark task as critical path."""
        self._is_critical = True
        return self

    def build(self) -> Task:
        """Build the Task entity."""
        task = Task.create(
            job_id=self._job_id,
            operation_id=self._operation_id,
            sequence_in_job=self._sequence,
            planned_duration_minutes=self._planned_duration,
            setup_duration_minutes=self._setup_duration,
        )

        task.assigned_machine_id = self._machine_id

        if self._is_critical:
            task.mark_critical_path()

        # Add operator assignments
        for assignment in self._operator_assignments:
            assignment.task_id = task.id
            task.add_operator_assignment(assignment)

        return task


class MachineBuilder:
    """Builder for creating Machine entities with fluent interface."""

    def __init__(self, machine_code: str, machine_name: str):
        self._machine_code = machine_code
        self._machine_name = machine_name
        self._automation_level = MachineAutomationLevel.ATTENDED
        self._zone_id: UUID | None = None
        self._efficiency = 1.0
        self._is_bottleneck = False
        self._capabilities: list[MachineCapability] = []
        self._required_skills: list[RequiredSkill] = []

    def automation(self, level: MachineAutomationLevel) -> "MachineBuilder":
        """Set automation level."""
        self._automation_level = level
        return self

    def zone(self, zone_id: UUID) -> "MachineBuilder":
        """Assign to production zone."""
        self._zone_id = zone_id
        return self

    def efficiency(self, factor: float) -> "MachineBuilder":
        """Set efficiency factor."""
        self._efficiency = factor
        return self

    def bottleneck(self) -> "MachineBuilder":
        """Mark as bottleneck resource."""
        self._is_bottleneck = True
        return self

    def capability(
        self,
        operation_id: UUID,
        processing_minutes: int,
        setup_minutes: int = 0,
        is_primary: bool = False,
    ) -> "MachineBuilder":
        """Add operation capability."""
        capability = MachineCapability.create(
            machine_id=UUID(),  # Will be set when machine is created
            operation_id=operation_id,
            processing_time_minutes=processing_minutes,
            setup_time_minutes=setup_minutes,
            is_primary=is_primary,
        )
        self._capabilities.append(capability)
        return self

    def requires_skill(
        self,
        skill_code: str,
        skill_name: str,
        minimum_level: SkillLevel,
        category: str | None = None,
    ) -> "MachineBuilder":
        """Add skill requirement."""
        skill = Skill(
            skill_code=skill_code, skill_name=skill_name, skill_category=category
        )
        required_skill = RequiredSkill(
            machine_id=UUID(),  # Will be set when machine is created
            skill=skill,
            minimum_level=minimum_level,
        )
        self._required_skills.append(required_skill)
        return self

    def build(self) -> Machine:
        """Build the Machine entity."""
        machine = Machine.create(
            machine_code=self._machine_code,
            machine_name=self._machine_name,
            automation_level=self._automation_level,
            production_zone_id=self._zone_id,
            efficiency_factor=self._efficiency,
        )

        if self._is_bottleneck:
            machine.mark_as_bottleneck()

        # Add capabilities
        for capability in self._capabilities:
            capability.machine_id = machine.id
            machine.add_capability(capability)

        # Add skill requirements
        for required_skill in self._required_skills:
            required_skill.machine_id = machine.id
            machine.add_required_skill(required_skill)

        return machine


class OperatorBuilder:
    """Builder for creating Operator entities with fluent interface."""

    def __init__(self, employee_id: str, first_name: str, last_name: str):
        self._employee_id = employee_id
        self._first_name = first_name
        self._last_name = last_name
        self._email: str | None = None
        self._phone: str | None = None
        self._working_hours: WorkingHours | None = None
        self._hire_date: date | None = None
        self._skills: list[OperatorSkill] = []

    def email(self, email: str) -> "OperatorBuilder":
        """Set email address."""
        self._email = email
        return self

    def phone(self, phone: str) -> "OperatorBuilder":
        """Set phone number."""
        self._phone = phone
        return self

    def shift(
        self,
        start_time: time = time(7, 0),
        end_time: time = time(16, 0),
        lunch_start: time = time(12, 0),
        lunch_minutes: int = 30,
    ) -> "OperatorBuilder":
        """Set working hours."""
        self._working_hours = WorkingHours(
            start_time=start_time,
            end_time=end_time,
            lunch_start=lunch_start,
            lunch_duration=Duration(minutes=lunch_minutes),
        )
        return self

    def hired(self, hire_date: date) -> "OperatorBuilder":
        """Set hire date."""
        self._hire_date = hire_date
        return self

    def skill(
        self,
        skill_code: str,
        skill_name: str,
        proficiency: SkillLevel,
        certified_date: datetime | None = None,
        expiry_date: datetime | None = None,
        category: str | None = None,
    ) -> "OperatorBuilder":
        """Add skill to operator."""
        skill_obj = Skill(
            skill_code=skill_code, skill_name=skill_name, skill_category=category
        )
        operator_skill = OperatorSkill(
            skill=skill_obj,
            proficiency_level=proficiency,
            certified_date=certified_date,
            expiry_date=expiry_date,
        )
        self._skills.append(operator_skill)
        return self

    def build(self) -> Operator:
        """Build the Operator entity."""
        contact_info = None
        if self._email or self._phone:
            contact_info = ContactInfo(email=self._email, phone=self._phone)

        operator = Operator.create(
            employee_id=self._employee_id,
            first_name=self._first_name,
            last_name=self._last_name,
            working_hours=self._working_hours,
            contact_info=contact_info,
            hire_date=self._hire_date,
        )

        # Add skills
        for skill in self._skills:
            operator.add_skill(skill)

        return operator


class SchedulingDomainFactory:
    """Factory class for creating scheduling domain entities."""

    @staticmethod
    def job(job_number: str, due_date: datetime) -> JobBuilder:
        """Create a job builder."""
        return JobBuilder(job_number, due_date)

    @staticmethod
    def task(job_id: UUID, operation_id: UUID, sequence: int) -> TaskBuilder:
        """Create a task builder."""
        return TaskBuilder(job_id, operation_id, sequence)

    @staticmethod
    def machine(machine_code: str, machine_name: str) -> MachineBuilder:
        """Create a machine builder."""
        return MachineBuilder(machine_code, machine_name)

    @staticmethod
    def operator(employee_id: str, first_name: str, last_name: str) -> OperatorBuilder:
        """Create an operator builder."""
        return OperatorBuilder(employee_id, first_name, last_name)

    @staticmethod
    def operation(
        operation_code: str,
        operation_name: str,
        sequence_number: int,
        standard_duration_minutes: int,
        setup_duration_minutes: int = 0,
        production_zone_id: UUID | None = None,
        is_critical: bool = False,
    ) -> Operation:
        """Create an operation entity."""
        return Operation.create(
            operation_code=operation_code,
            operation_name=operation_name,
            sequence_number=sequence_number,
            standard_duration_minutes=standard_duration_minutes,
            setup_duration_minutes=setup_duration_minutes,
            production_zone_id=production_zone_id,
            is_critical=is_critical,
        )

    @staticmethod
    def production_zone(
        zone_code: str, zone_name: str, wip_limit: int, description: str | None = None
    ) -> ProductionZone:
        """Create a production zone entity."""
        return ProductionZone.create(
            zone_code=zone_code,
            zone_name=zone_name,
            wip_limit=wip_limit,
            description=description,
        )

    @staticmethod
    def create_sample_manufacturing_job(
        job_number: str = "JOB-SAMPLE-001", due_days: int = 7
    ) -> Job:
        """Create a sample manufacturing job for testing/demo purposes."""
        due_date = datetime.utcnow().replace(hour=16, minute=0, second=0, microsecond=0)
        due_date = due_date.replace(day=due_date.day + due_days)

        return (
            SchedulingDomainFactory.job(job_number, due_date)
            .customer("Sample Customer")
            .part("PART-ABC-123")
            .quantity(10)
            .priority(PriorityLevel.HIGH)
            .created_by("system")
            .build()
        )

    @staticmethod
    def create_sample_manufacturing_line() -> dict[str, object]:
        """Create a sample manufacturing setup for testing/demo."""
        # Create production zones
        prep_zone = SchedulingDomainFactory.production_zone(
            "PREP", "Preparation Area", 5, "Material preparation and initial setup"
        )

        machining_zone = SchedulingDomainFactory.production_zone(
            "MACH", "Machining Area", 3, "CNC machining and precision work"
        )

        assembly_zone = SchedulingDomainFactory.production_zone(
            "ASSY", "Assembly Area", 4, "Product assembly and integration"
        )

        # Create operations
        operations = [
            SchedulingDomainFactory.operation(
                "OP010", "Material Prep", 10, 30, 10, prep_zone.id
            ),
            SchedulingDomainFactory.operation(
                "OP020", "CNC Machining", 20, 90, 20, machining_zone.id, True
            ),
            SchedulingDomainFactory.operation(
                "OP030", "Quality Check", 30, 15, 5, machining_zone.id
            ),
            SchedulingDomainFactory.operation(
                "OP040", "Assembly", 40, 60, 15, assembly_zone.id
            ),
            SchedulingDomainFactory.operation(
                "OP050", "Final Test", 50, 30, 10, assembly_zone.id
            ),
        ]

        # Create machines
        cnc_machine = (
            SchedulingDomainFactory.machine("CNC-001", "CNC Mill #1")
            .automation(MachineAutomationLevel.UNATTENDED)
            .zone(machining_zone.id)
            .efficiency(0.95)
            .capability(operations[1].id, 90, 20, True)  # CNC Machining
            .requires_skill(
                "CNC_PROG", "CNC Programming", SkillLevel.LEVEL_2, "Technical"
            )
            .build()
        )

        assembly_station = (
            SchedulingDomainFactory.machine("ASSY-001", "Assembly Station #1")
            .automation(MachineAutomationLevel.ATTENDED)
            .zone(assembly_zone.id)
            .capability(operations[3].id, 60, 15, True)  # Assembly
            .requires_skill("ASSEMBLY", "Manual Assembly", SkillLevel.LEVEL_1, "Manual")
            .build()
        )

        # Create operators
        john = (
            SchedulingDomainFactory.operator("EMP001", "John", "Smith")
            .email("john.smith@company.com")
            .skill("CNC_PROG", "CNC Programming", SkillLevel.LEVEL_3)
            .skill("QUALITY", "Quality Inspection", SkillLevel.LEVEL_2)
            .build()
        )

        jane = (
            SchedulingDomainFactory.operator("EMP002", "Jane", "Doe")
            .email("jane.doe@company.com")
            .skill("ASSEMBLY", "Manual Assembly", SkillLevel.LEVEL_2)
            .skill("QUALITY", "Quality Inspection", SkillLevel.LEVEL_3)
            .build()
        )

        return {
            "zones": [prep_zone, machining_zone, assembly_zone],
            "operations": operations,
            "machines": [cnc_machine, assembly_station],
            "operators": [john, jane],
        }
