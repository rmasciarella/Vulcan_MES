# Manufacturing Scheduling Domain Model

A Domain-Driven Design (DDD) specification for a hybrid flexible flow shop scheduling domain with operator skill constraints and business calendar restrictions. This document captures the ubiquitous language, architecture, and invariants of the scheduling subdomain. It replaces earlier embedded code examples with a stable, implementation-agnostic specification.

## Goals
- Optimize task sequencing and resource allocation across machines and operators
- Respect skills, certifications, attendance modes (attended vs unattended), and business calendars
- Provide clear aggregates, domain events, and policies to enable multiple implementations

## Bounded Context
- Scheduling Context: Owns task assignment, calendars, and conflict resolution
- Personnel Context: Owns operators, skills, and certifications
- Equipment Context: Owns machines and capabilities

## Ubiquitous Language (Selected)
- Task: An operation within a Job that requires a Machine and possibly Operators
- Job: A collection of ordered Tasks with due date and priority
- Machine: A production resource with skill requirements and availability
- Operator: A person with skills, certifications, and availability
- Business Calendar: Working hours and holidays used to constrain schedules
- Time Window: A closed interval [start, end] in business time
- Critical Tasks: Tasks requiring elevated prioritization for flow efficiency

## Aggregates and Entities
- Job (Aggregate Root)
  - Tasks (Entity)
    - Attributes: operation number, machine options, skill requirements, predecessors
    - State: status (pending, ready, scheduled, in_progress, completed), planned/actual times
- Machine (Entity)
  - Skill requirements and maintenance windows; attended vs unattended behavior
- Operator (Aggregate Root)
  - Skills (Value Objects), availability windows, assignments
- Schedule (Aggregate Root)
  - Assignments: task_id -> (machine_id, operator_ids, time window)
  - Resource timelines for conflict detection

## Value Objects
- Duration (minutes; non-negative; arithmetic operations)
- Time Window (start < end; overlaps, contains, duration)
- Skill Requirement (skill type, minimum level)
- Skill Proficiency (skill type, level 1–3, validity range)

## Domain Events (Selected)
- TaskScheduled(task_id, job_id, machine_id, operator_ids, planned_start, planned_end)
- TaskStarted(task_id, job_id, actual_start, machine_id, operator_ids)
- TaskCompleted(task_id, job_id, actual_end, actual_duration)
- OperatorAssigned(operator_id, task_id, assignment_type)
- OperatorReleased(operator_id, task_id)
- JobDelayed(job_id, original_due_date, expected_completion, delay_hours)

## Invariants and Policies
- Precedence: A Task cannot start before its predecessors complete
- Calendar: Assignments must occur within business hours (or be normalized to the next working time)
- Resource Conflicts: No overlapping Time Windows per Machine or Operator
- Skills: Assigned Operators must meet Machine Skill Requirements on the effective date
- Attended/Unattended:
  - Attended machines require operators for the full duration
  - Unattended machines require operators for setup only

## Domain Services
- SkillMatcher: Determines qualified/best operators for a machine
- ScheduleValidator: Validates precedence, calendar, and resource conflicts
- ResourceAllocator: Finds earliest feasible assignment given preferences and constraints
- CriticalSequenceManager: Identifies critical sequences and prioritizes jobs

## Read Models and Projections
- Machine Utilization by time bucket
- Operator Load and availability
- Job Flow metrics (throughput, makespan)

## Diagrams (Informative)
- Context Diagram: Scheduling <-> Personnel <-> Equipment
- Aggregate Relationships: Job—Task, Schedule—Assignment, Operator—Skills
- Sequence: Allocate resources for a task, validate, and commit assignment

## API Integration Considerations
- Expose read endpoints for schedule status, resource utilization, and job progress
- Command endpoints to assign, start, complete tasks—idempotent with event sourcing potential
- Observability: emit domain events for audit and downstream processing

## Extensibility
- Multi-skill assignments; skill substitution rules
- Shift patterns, lunch breaks, and overtime policies in calendar
- Multi-operator tasks; setup-only attendance windows
- Heuristics and optimization integrations (e.g., metaheuristics, MILP)

## Non-Functional Requirements
- Deterministic validation and clear error reporting
- Performance: Validate typical schedules (100–1,000 tasks) within interactive latencies
- Testability: Domain services should be pure and unit-testable

## Migration Notes
- The previous embedded code examples have been superseded by this specification. Implementation should live under backend/app/domain/scheduling/ as Python modules, with tests under backend/tests/domain/scheduling/.
# ============================================================================

@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=datetime.now)
    aggregate_id: UUID = None


@dataclass(frozen=True)
class TaskScheduled(DomainEvent):
    """Raised when a task is scheduled to a machine with operators."""
    task_id: UUID
    job_id: UUID
    machine_id: UUID
    operator_ids: List[UUID]
    planned_start: datetime
    planned_end: datetime


@dataclass(frozen=True)
class TaskStarted(DomainEvent):
    """Raised when task production begins."""
    task_id: UUID
    job_id: UUID
    actual_start: datetime
    machine_id: UUID
    operator_ids: List[UUID]


@dataclass(frozen=True)
class TaskCompleted(DomainEvent):
    """Raised when task production ends."""
    task_id: UUID
    job_id: UUID
    actual_end: datetime
    actual_duration: Duration


@dataclass(frozen=True)
class OperatorAssigned(DomainEvent):
    """Raised when operator is assigned to a task."""
    operator_id: UUID
    task_id: UUID
    assignment_type: str  # 'full_duration' or 'setup_only'


@dataclass(frozen=True)
class OperatorReleased(DomainEvent):
    """Raised when operator is released from a task."""
    operator_id: UUID
    task_id: UUID


@dataclass(frozen=True)
class JobDelayed(DomainEvent):
    """Raised when job due date is at risk."""
    job_id: UUID
    original_due_date: datetime
    expected_completion: datetime
    delay_hours: Decimal


# ============================================================================
# VALUE OBJECTS
# ============================================================================

class TaskStatus(Enum):
    """Enumeration of possible task states."""
    PENDING = auto()      # Not yet ready (waiting for predecessors)
    READY = auto()        # All predecessors complete, awaiting resources
    SCHEDULED = auto()    # Resources assigned, awaiting start
    IN_PROGRESS = auto()  # Currently being processed
    COMPLETED = auto()    # Processing finished
    CANCELLED = auto()    # Task cancelled
    ON_HOLD = auto()      # Temporarily suspended


class SkillType(Enum):
    """Types of skills in the manufacturing system."""
    MACHINING = "machining"
    WELDING = "welding"
    INSPECTION = "inspection"
    ASSEMBLY = "assembly"
    PROGRAMMING = "programming"


@dataclass(frozen=True)
class SkillProficiency:
    """
    Represents an operator's proficiency in a specific skill.
    Immutable value object.
    """
    skill_type: SkillType
    level: int  # 1-3 scale
    certified_date: date
    expiry_date: Optional[date] = None

    def __post_init__(self):
        if not 1 <= self.level <= 3:
            raise ValueError(f"Skill level must be 1-3, got {self.level}")
        if self.expiry_date and self.expiry_date <= self.certified_date:
            raise ValueError("Expiry date must be after certification date")

    def is_valid_on(self, check_date: date) -> bool:
        """Check if skill is valid on given date."""
        if check_date < self.certified_date:
            return False
        if self.expiry_date and check_date >= self.expiry_date:
            return False
        return True

    def meets_requirement(self, requirement: SkillRequirement, check_date: date) -> bool:
        """Check if this proficiency meets a skill requirement."""
        return (self.skill_type == requirement.skill_type and
                self.level >= requirement.minimum_level and
                self.is_valid_on(check_date))


@dataclass(frozen=True)
class SkillRequirement:
    """
    Represents a skill requirement for operating a machine.
    Immutable value object.
    """
    skill_type: SkillType
    minimum_level: int

    def __post_init__(self):
        if not 1 <= self.minimum_level <= 3:
            raise ValueError(f"Minimum level must be 1-3, got {self.minimum_level}")


@dataclass(frozen=True)
class Duration:
    """
    Represents a time duration in minutes.
    Immutable value object with validation.
    """
    minutes: Decimal

    def __post_init__(self):
        if self.minutes < 0:
            raise ValueError(f"Duration cannot be negative: {self.minutes}")

    @classmethod
    def from_hours(cls, hours: float) -> Duration:
        """Create duration from hours."""
        return cls(Decimal(str(hours * 60)))

    def to_timedelta(self) -> timedelta:
        """Convert to Python timedelta."""
        return timedelta(minutes=float(self.minutes))

    def __add__(self, other: Duration) -> Duration:
        return Duration(self.minutes + other.minutes)

    def __mul__(self, factor: Decimal) -> Duration:
        return Duration(self.minutes * factor)


@dataclass(frozen=True)
class TimeWindow:
    """
    Represents a time interval with start and end.
    Immutable value object.
    """
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.end <= self.start:
            raise ValueError(f"End time {self.end} must be after start time {self.start}")

    def duration(self) -> Duration:
        """Calculate duration of time window."""
        delta = self.end - self.start
        return Duration(Decimal(delta.total_seconds() / 60))

    def overlaps(self, other: TimeWindow) -> bool:
        """Check if this window overlaps with another."""
        return self.start < other.end and other.start < self.end

    def contains(self, timestamp: datetime) -> bool:
        """Check if timestamp is within this window."""
        return self.start <= timestamp <= self.end


@dataclass(frozen=True)
class MachineOption:
    """
    Represents a machine option for a task with associated durations.
    Immutable value object.
    """
    machine_id: UUID
    setup_duration: Duration
    processing_duration: Duration
    requires_operator_full_duration: bool

    def total_duration(self) -> Duration:
        """Calculate total duration (setup + processing)."""
        return self.setup_duration + self.processing_duration


@dataclass(frozen=True)
class BusinessHours:
    """
    Represents daily business hours.
    Immutable value object.
    """
    start_time: time
    end_time: time

    def __post_init__(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")

    def is_within_hours(self, check_time: time) -> bool:
        """Check if a time is within business hours."""
        return self.start_time <= check_time <= self.end_time


@dataclass(frozen=True)
class BusinessCalendar:
    """
    Represents business calendar with working hours and holidays.
    Immutable value object.
    """
    weekday_hours: Dict[int, BusinessHours]  # 0=Monday, 6=Sunday
    holidays: Set[date]
    lunch_break: Optional[TimeWindow] = None

    @classmethod
    def standard_calendar(cls) -> BusinessCalendar:
        """Factory method for standard Mon-Fri 7am-4pm calendar."""
        weekday_hours = {
            0: BusinessHours(time(7, 0), time(16, 0)),  # Monday
            1: BusinessHours(time(7, 0), time(16, 0)),  # Tuesday
            2: BusinessHours(time(7, 0), time(16, 0)),  # Wednesday
            3: BusinessHours(time(7, 0), time(16, 0)),  # Thursday
            4: BusinessHours(time(7, 0), time(16, 0)),  # Friday
        }
        return cls(weekday_hours=weekday_hours, holidays=set())

    def is_working_time(self, check_datetime: datetime) -> bool:
        """Check if datetime is during working hours."""
        check_date = check_datetime.date()
        if check_date in self.holidays:
            return False

        weekday = check_datetime.weekday()
        if weekday not in self.weekday_hours:
            return False

        hours = self.weekday_hours[weekday]
        return hours.is_within_hours(check_datetime.time())

    def next_working_time(self, from_time: datetime) -> datetime:
        """Find next available working time."""
        current = from_time
        while not self.is_working_time(current):
            current += timedelta(minutes=15)
        return current


# ============================================================================
# ENTITIES
# ============================================================================

class Entity(ABC):
    """Base class for all entities with identity."""

    def __init__(self, entity_id: Optional[UUID] = None):
        self._id = entity_id or uuid4()
        self._domain_events: List[DomainEvent] = []

    @property
    def id(self) -> UUID:
        return self._id

    def add_domain_event(self, event: DomainEvent):
        """Add a domain event to be dispatched."""
        self._domain_events.append(event)

    def get_domain_events(self) -> List[DomainEvent]:
        """Get and clear domain events."""
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

    def __eq__(self, other):
        if not isinstance(other, Entity):
            return False
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)


class Task(Entity):
    """
    Represents a single operation within a job.
    Entity with identity and mutable state.
    """

    def __init__(
        self,
        task_id: Optional[UUID] = None,
        job_id: Optional[UUID] = None,
        operation_number: int = 0,
        machine_options: List[MachineOption] = None,
        skill_requirements: List[SkillRequirement] = None,
        is_critical: bool = False,
        predecessor_ids: List[UUID] = None
    ):
        super().__init__(task_id)
        self._job_id = job_id
        self._operation_number = operation_number
        self._machine_options = machine_options or []
        self._skill_requirements = skill_requirements or []
        self._is_critical = is_critical
        self._predecessor_ids = predecessor_ids or []

        # Mutable state
        self._status = TaskStatus.PENDING
        self._assigned_machine_id: Optional[UUID] = None
        self._assigned_operator_ids: List[UUID] = []
        self._planned_start: Optional[datetime] = None
        self._planned_end: Optional[datetime] = None
        self._actual_start: Optional[datetime] = None
        self._actual_end: Optional[datetime] = None

        self._validate()

    def _validate(self):
        """Validate task invariants."""
        if self._operation_number < 0:
            raise ValueError(f"Operation number must be non-negative: {self._operation_number}")
        if not self._machine_options:
            raise ValueError("Task must have at least one machine option")

    @property
    def job_id(self) -> UUID:
        return self._job_id

    @property
    def operation_number(self) -> int:
        return self._operation_number

    @property
    def status(self) -> TaskStatus:
        return self._status

    @property
    def is_critical(self) -> bool:
        return self._is_critical

    @property
    def machine_options(self) -> List[MachineOption]:
        return self._machine_options.copy()

    @property
    def skill_requirements(self) -> List[SkillRequirement]:
        return self._skill_requirements.copy()

    @property
    def predecessor_ids(self) -> List[UUID]:
        return self._predecessor_ids.copy()

    def can_start(self, predecessor_statuses: Dict[UUID, TaskStatus]) -> bool:
        """Check if all predecessors are complete."""
        for pred_id in self._predecessor_ids:
            if predecessor_statuses.get(pred_id) != TaskStatus.COMPLETED:
                return False
        return True

    def schedule(
        self,
        machine_id: UUID,
        operator_ids: List[UUID],
        planned_start: datetime,
        planned_end: datetime
    ):
        """Schedule task to machine with operators."""
        if self._status not in [TaskStatus.PENDING, TaskStatus.READY]:
            raise ValueError(f"Cannot schedule task in status {self._status}")

        # Validate machine option exists
        if not any(opt.machine_id == machine_id for opt in self._machine_options):
            raise ValueError(f"Machine {machine_id} is not a valid option for this task")

        self._assigned_machine_id = machine_id
        self._assigned_operator_ids = operator_ids.copy()
        self._planned_start = planned_start
        self._planned_end = planned_end
        self._status = TaskStatus.SCHEDULED

        # Raise domain event
        self.add_domain_event(TaskScheduled(
            task_id=self.id,
            job_id=self._job_id,
            machine_id=machine_id,
            operator_ids=operator_ids,
            planned_start=planned_start,
            planned_end=planned_end,
            aggregate_id=self._job_id
        ))

    def start(self, actual_start: datetime):
        """Mark task as started."""
        if self._status != TaskStatus.SCHEDULED:
            raise ValueError(f"Cannot start task in status {self._status}")

        self._actual_start = actual_start
        self._status = TaskStatus.IN_PROGRESS

        self.add_domain_event(TaskStarted(
            task_id=self.id,
            job_id=self._job_id,
            actual_start=actual_start,
            machine_id=self._assigned_machine_id,
            operator_ids=self._assigned_operator_ids,
            aggregate_id=self._job_id
        ))

    def complete(self, actual_end: datetime):
        """Mark task as completed."""
        if self._status != TaskStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete task in status {self._status}")

        self._actual_end = actual_end
        self._status = TaskStatus.COMPLETED

        duration = Duration(Decimal((actual_end - self._actual_start).total_seconds() / 60))

        self.add_domain_event(TaskCompleted(
            task_id=self.id,
            job_id=self._job_id,
            actual_end=actual_end,
            actual_duration=duration,
            aggregate_id=self._job_id
        ))

    def mark_ready(self):
        """Mark task as ready when all predecessors complete."""
        if self._status != TaskStatus.PENDING:
            raise ValueError(f"Cannot mark task ready from status {self._status}")
        self._status = TaskStatus.READY


class Job(Entity):
    """
    Aggregate root for work orders containing multiple tasks.
    Maintains consistency across task operations.
    """

    def __init__(
        self,
        job_id: Optional[UUID] = None,
        job_number: str = "",
        priority: int = 0,
        due_date: Optional[datetime] = None,
        release_date: Optional[datetime] = None
    ):
        super().__init__(job_id)
        self._job_number = job_number
        self._priority = priority
        self._due_date = due_date
        self._release_date = release_date or datetime.now()
        self._tasks: Dict[UUID, Task] = {}
        self._task_sequence: List[UUID] = []  # Ordered task IDs

        self._validate()

    def _validate(self):
        """Validate job invariants."""
        if not self._job_number:
            raise ValueError("Job must have a job number")
        if self._priority < 0:
            raise ValueError(f"Priority must be non-negative: {self._priority}")
        if self._due_date and self._due_date < self._release_date:
            raise ValueError("Due date cannot be before release date")

    @property
    def job_number(self) -> str:
        return self._job_number

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def due_date(self) -> Optional[datetime]:
        return self._due_date

    @property
    def release_date(self) -> datetime:
        return self._release_date

    def add_task(self, task: Task):
        """Add task to job, maintaining sequence order."""
        if task.job_id != self.id:
            raise ValueError(f"Task job_id {task.job_id} doesn't match job {self.id}")

        self._tasks[task.id] = task

        # Insert in sequence order
        insert_pos = 0
        for i, task_id in enumerate(self._task_sequence):
            if self._tasks[task_id].operation_number > task.operation_number:
                insert_pos = i
                break
            insert_pos = i + 1

        self._task_sequence.insert(insert_pos, task.id)

    def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def get_tasks_in_sequence(self) -> List[Task]:
        """Get all tasks in operation sequence order."""
        return [self._tasks[task_id] for task_id in self._task_sequence]

    def get_critical_tasks(self) -> List[Task]:
        """Get all critical tasks."""
        return [task for task in self._tasks.values() if task.is_critical]

    def update_task_readiness(self):
        """Update task statuses based on predecessor completion."""
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING:
                predecessor_statuses = {
                    pred_id: self._tasks[pred_id].status
                    for pred_id in task.predecessor_ids
                    if pred_id in self._tasks
                }
                if task.can_start(predecessor_statuses):
                    task.mark_ready()

    def check_delay_risk(self, expected_completion: datetime):
        """Check if job is at risk of missing due date."""
        if self._due_date and expected_completion > self._due_date:
            delay_hours = Decimal((expected_completion - self._due_date).total_seconds() / 3600)
            self.add_domain_event(JobDelayed(
                job_id=self.id,
                original_due_date=self._due_date,
                expected_completion=expected_completion,
                delay_hours=delay_hours,
                aggregate_id=self.id
            ))
            return True
        return False

    @classmethod
    def create_standard_job(
        cls,
        job_number: str,
        operation_count: int = 100,
        priority: int = 0,
        due_date: Optional[datetime] = None
    ) -> Job:
        """
        Factory method to create a standard job with 100 operations.
        90% single machine options, 10% with 2 machine options.
        """
        job = cls(
            job_number=job_number,
            priority=priority,
            due_date=due_date
        )

        # Create tasks with appropriate machine options
        for op_num in range(operation_count):
            # 10% chance of having 2 machine options
            num_options = 2 if op_num % 10 == 0 else 1

            machine_options = []
            for i in range(num_options):
                machine_options.append(MachineOption(
                    machine_id=uuid4(),  # Would be actual machine IDs
                    setup_duration=Duration(Decimal(15)),  # 15 min setup
                    processing_duration=Duration(Decimal(30 + op_num)),  # Variable processing
                    requires_operator_full_duration=(op_num % 3 == 0)  # 33% attended
                ))

            # Create skill requirements
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
            predecessor_ids = [] if op_num == 0 else [job._task_sequence[-1]]

            # Mark critical operations (every 10th operation)
            is_critical = (op_num % 10 == 5)

            task = Task(
                job_id=job.id,
                operation_number=op_num,
                machine_options=machine_options,
                skill_requirements=skill_reqs,
                is_critical=is_critical,
                predecessor_ids=predecessor_ids
            )

            job.add_task(task)

        return job


class Machine(Entity):
    """
    Represents a production machine with capabilities.
    Entity with identity and state tracking.
    """

    def __init__(
        self,
        machine_id: Optional[UUID] = None,
        name: str = "",
        zone: str = "",
        skill_requirements: List[SkillRequirement] = None,
        is_attended: bool = True
    ):
        super().__init__(machine_id)
        self._name = name
        self._zone = zone
        self._skill_requirements = skill_requirements or []
        self._is_attended = is_attended
        self._is_available = True
        self._current_task_id: Optional[UUID] = None
        self._maintenance_windows: List[TimeWindow] = []

        self._validate()

    def _validate(self):
        """Validate machine invariants."""
        if not self._name:
            raise ValueError("Machine must have a name")
        if not self._zone:
            raise ValueError("Machine must have a zone")

    @property
    def name(self) -> str:
        return self._name

    @property
    def zone(self) -> str:
        return self._zone

    @property
    def is_attended(self) -> bool:
        return self._is_attended

    @property
    def is_available(self) -> bool:
        return self._is_available and self._current_task_id is None

    @property
    def skill_requirements(self) -> List[SkillRequirement]:
        return self._skill_requirements.copy()

    def allocate_to_task(self, task_id: UUID):
        """Allocate machine to a task."""
        if not self._is_available:
            raise ValueError(f"Machine {self._name} is not available")
        if self._current_task_id:
            raise ValueError(f"Machine {self._name} is already allocated to task {self._current_task_id}")

        self._current_task_id = task_id

    def release_from_task(self):
        """Release machine from current task."""
        self._current_task_id = None

    def schedule_maintenance(self, window: TimeWindow):
        """Schedule a maintenance window."""
        # Check for overlaps
        for existing in self._maintenance_windows:
            if existing.overlaps(window):
                raise ValueError(f"Maintenance window overlaps with existing window")

        self._maintenance_windows.append(window)

    def is_available_during(self, window: TimeWindow) -> bool:
        """Check if machine is available during time window."""
        if not self._is_available:
            return False

        for maint in self._maintenance_windows:
            if maint.overlaps(window):
                return False

        return True


class Operator(Entity):
    """
    Aggregate root for operators with skills and availability.
    Manages operator assignments and skill validations.
    """

    def __init__(
        self,
        operator_id: Optional[UUID] = None,
        name: str = "",
        employee_id: str = "",
        skills: List[SkillProficiency] = None,
        shift_pattern: str = "day"  # day, night, swing
    ):
        super().__init__(operator_id)
        self._name = name
        self._employee_id = employee_id
        self._skills = skills or []
        self._shift_pattern = shift_pattern
        self._current_task_ids: Set[UUID] = set()
        self._availability_windows: List[TimeWindow] = []

        self._validate()

    def _validate(self):
        """Validate operator invariants."""
        if not self._name:
            raise ValueError("Operator must have a name")
        if not self._employee_id:
            raise ValueError("Operator must have an employee ID")

        # Check for duplicate skill types
        skill_types = [s.skill_type for s in self._skills]
        if len(skill_types) != len(set(skill_types)):
            raise ValueError("Operator cannot have duplicate skill types")

    @property
    def name(self) -> str:
        return self._name

    @property
    def employee_id(self) -> str:
        return self._employee_id

    @property
    def skills(self) -> List[SkillProficiency]:
        return self._skills.copy()

    @property
    def is_available(self) -> bool:
        return len(self._current_task_ids) == 0

    def has_skill(self, requirement: SkillRequirement, check_date: date = None) -> bool:
        """Check if operator meets skill requirement."""
        check_date = check_date or date.today()
        for skill in self._skills:
            if skill.meets_requirement(requirement, check_date):
                return True
        return False

    def can_operate_machine(self, machine: Machine, check_date: date = None) -> bool:
        """Check if operator can operate a specific machine."""
        check_date = check_date or date.today()
        for requirement in machine.skill_requirements:
            if not self.has_skill(requirement, check_date):
                return False
        return True

    def assign_to_task(self, task_id: UUID):
        """Assign operator to a task."""
        self._current_task_ids.add(task_id)
        self.add_domain_event(OperatorAssigned(
            operator_id=self.id,
            task_id=task_id,
            assignment_type='full_duration',
            aggregate_id=self.id
        ))

    def release_from_task(self, task_id: UUID):
        """Release operator from a task."""
        if task_id in self._current_task_ids:
            self._current_task_ids.remove(task_id)
            self.add_domain_event(OperatorReleased(
                operator_id=self.id,
                task_id=task_id,
                aggregate_id=self.id
            ))

    def add_availability(self, window: TimeWindow):
        """Add an availability window."""
        self._availability_windows.append(window)

    def is_available_during(self, window: TimeWindow) -> bool:
        """Check if operator is available during time window."""
        for avail in self._availability_windows:
            if avail.contains(window.start) and avail.contains(window.end):
                return True
        return False

    def update_skill(self, new_skill: SkillProficiency):
        """Update or add a skill proficiency."""
        # Remove existing skill of same type
        self._skills = [s for s in self._skills if s.skill_type != new_skill.skill_type]
        self._skills.append(new_skill)

    @classmethod
    def create_skilled_operator(
        cls,
        name: str,
        employee_id: str,
        skill_types: List[Tuple[SkillType, int]]  # (type, level) pairs
    ) -> Operator:
        """Factory method to create operator with multiple skills."""
        skills = []
        for skill_type, level in skill_types:
            skills.append(SkillProficiency(
                skill_type=skill_type,
                level=level,
                certified_date=date.today() - timedelta(days=365),  # Certified 1 year ago
                expiry_date=date.today() + timedelta(days=365)  # Expires in 1 year
            ))

        return cls(
            name=name,
            employee_id=employee_id,
            skills=skills
        )


class Schedule(Entity):
    """
    Aggregate root for schedule containing resource assignments.
    Coordinates task scheduling and resource allocation.
    """

    def __init__(
        self,
        schedule_id: Optional[UUID] = None,
        version: int = 1,
        effective_date: datetime = None,
        calendar: BusinessCalendar = None
    ):
        super().__init__(schedule_id)
        self._version = version
        self._effective_date = effective_date or datetime.now()
        self._calendar = calendar or BusinessCalendar.standard_calendar()

        # Task assignments: task_id -> (machine_id, operator_ids, time_window)
        self._assignments: Dict[UUID, Tuple[UUID, List[UUID], TimeWindow]] = {}

        # Resource timelines for conflict detection
        self._machine_timeline: Dict[UUID, List[TimeWindow]] = {}
        self._operator_timeline: Dict[UUID, List[TimeWindow]] = {}

    @property
    def version(self) -> int:
        return self._version

    @property
    def effective_date(self) -> datetime:
        return self._effective_date

    def assign_task(
        self,
        task: Task,
        machine_id: UUID,
        operator_ids: List[UUID],
        start_time: datetime,
        duration: Duration
    ):
        """
        Assign task to machine and operators at specified time.
        Validates no conflicts and business calendar constraints.
        """
        end_time = start_time + duration.to_timedelta()
        window = TimeWindow(start_time, end_time)

        # Validate business calendar
        if not self._calendar.is_working_time(start_time):
            start_time = self._calendar.next_working_time(start_time)
            end_time = start_time + duration.to_timedelta()
            window = TimeWindow(start_time, end_time)

        # Check machine conflicts
        if machine_id in self._machine_timeline:
            for existing_window in self._machine_timeline[machine_id]:
                if existing_window.overlaps(window):
                    raise ValueError(f"Machine {machine_id} has conflicting assignment")

        # Check operator conflicts
        for op_id in operator_ids:
            if op_id in self._operator_timeline:
                for existing_window in self._operator_timeline[op_id]:
                    if existing_window.overlaps(window):
                        raise ValueError(f"Operator {op_id} has conflicting assignment")

        # Create assignment
        self._assignments[task.id] = (machine_id, operator_ids, window)

        # Update timelines
        if machine_id not in self._machine_timeline:
            self._machine_timeline[machine_id] = []
        self._machine_timeline[machine_id].append(window)

        for op_id in operator_ids:
            if op_id not in self._operator_timeline:
                self._operator_timeline[op_id] = []
            self._operator_timeline[op_id].append(window)

        # Update task
        task.schedule(machine_id, operator_ids, window.start, window.end)

    def get_assignment(self, task_id: UUID) -> Optional[Tuple[UUID, List[UUID], TimeWindow]]:
        """Get assignment for a task."""
        return self._assignments.get(task_id)

    def get_machine_schedule(self, machine_id: UUID) -> List[TimeWindow]:
        """Get all time windows for a machine."""
        return self._machine_timeline.get(machine_id, []).copy()

    def get_operator_schedule(self, operator_id: UUID) -> List[TimeWindow]:
        """Get all time windows for an operator."""
        return self._operator_timeline.get(operator_id, []).copy()

    def calculate_makespan(self) -> Optional[Duration]:
        """Calculate total schedule duration."""
        if not self._assignments:
            return None

        latest_end = max(window.end for _, _, window in self._assignments.values())
        earliest_start = min(window.start for _, _, window in self._assignments.values())

        return Duration(Decimal((latest_end - earliest_start).total_seconds() / 60))


# ============================================================================
# DOMAIN SERVICES
# ============================================================================

class SkillMatcher:
    """Domain service for matching operators to machines based on skills."""

    @staticmethod
    def find_qualified_operators(
        machine: Machine,
        operators: List[Operator],
        check_date: date = None
    ) -> List[Operator]:
        """Find all operators qualified to operate a machine."""
        check_date = check_date or date.today()
        qualified = []

        for operator in operators:
            if operator.can_operate_machine(machine, check_date):
                qualified.append(operator)

        return qualified

    @staticmethod
    def find_best_operator(
        machine: Machine,
        operators: List[Operator],
        check_date: date = None,
        prefer_available: bool = True
    ) -> Optional[Operator]:
        """
        Find best operator for machine based on skill level and availability.
        Returns operator with highest skill level, preferring available operators.
        """
        qualified = SkillMatcher.find_qualified_operators(machine, operators, check_date)

        if not qualified:
            return None

        # Sort by availability and skill level
        def score_operator(op: Operator) -> Tuple[int, int]:
            availability_score = 1 if op.is_available else 0

            # Calculate max skill level for required skills
            max_level = 0
            for req in machine.skill_requirements:
                for skill in op.skills:
                    if skill.skill_type == req.skill_type:
                        max_level = max(max_level, skill.level)

            return (availability_score if prefer_available else 0, max_level)

        qualified.sort(key=score_operator, reverse=True)
        return qualified[0]


class ScheduleValidator:
    """Domain service for validating schedule constraints."""

    def __init__(self, calendar: BusinessCalendar):
        self._calendar = calendar

    def validate_precedence_constraints(self, job: Job, schedule: Schedule) -> List[str]:
        """Validate that all precedence constraints are satisfied."""
        violations = []

        for task in job.get_tasks_in_sequence():
            assignment = schedule.get_assignment(task.id)
            if not assignment:
                continue

            _, _, task_window = assignment

            for pred_id in task.predecessor_ids:
                pred_assignment = schedule.get_assignment(pred_id)
                if not pred_assignment:
                    violations.append(f"Predecessor {pred_id} not scheduled for task {task.id}")
                    continue

                _, _, pred_window = pred_assignment
                if pred_window.end > task_window.start:
                    violations.append(
                        f"Task {task.id} starts before predecessor {pred_id} completes"
                    )

        return violations

    def validate_calendar_constraints(self, schedule: Schedule) -> List[str]:
        """Validate that all tasks are scheduled during business hours."""
        violations = []

        for task_id, (_, _, window) in schedule._assignments.items():
            if not self._calendar.is_working_time(window.start):
                violations.append(f"Task {task_id} starts outside business hours")
            if not self._calendar.is_working_time(window.end):
                violations.append(f"Task {task_id} ends outside business hours")

        return violations

    def validate_resource_conflicts(self, schedule: Schedule) -> List[str]:
        """Validate no resource conflicts exist."""
        violations = []

        # Check machine conflicts
        for machine_id, windows in schedule._machine_timeline.items():
            for i, window1 in enumerate(windows):
                for window2 in windows[i+1:]:
                    if window1.overlaps(window2):
                        violations.append(f"Machine {machine_id} has overlapping assignments")

        # Check operator conflicts
        for operator_id, windows in schedule._operator_timeline.items():
            for i, window1 in enumerate(windows):
                for window2 in windows[i+1:]:
                    if window1.overlaps(window2):
                        violations.append(f"Operator {operator_id} has overlapping assignments")

        return violations

    def validate_complete(self, job: Job, schedule: Schedule) -> Tuple[bool, List[str]]:
        """Complete validation of schedule for a job."""
        all_violations = []

        all_violations.extend(self.validate_precedence_constraints(job, schedule))
        all_violations.extend(self.validate_calendar_constraints(schedule))
        all_violations.extend(self.validate_resource_conflicts(schedule))

        return len(all_violations) == 0, all_violations


class ResourceAllocator:
    """Domain service for allocating resources to tasks."""

    def __init__(
        self,
        machines: List[Machine],
        operators: List[Operator],
        skill_matcher: SkillMatcher
    ):
        self._machines = {m.id: m for m in machines}
        self._operators = {o.id: o for o in operators}
        self._skill_matcher = skill_matcher

    def allocate_resources_for_task(
        self,
        task: Task,
        schedule: Schedule,
        preferred_start: datetime
    ) -> Optional[Tuple[UUID, List[UUID], TimeWindow]]:
        """
        Allocate best available machine and operators for a task.
        Returns (machine_id, operator_ids, time_window) or None if not possible.
        """
        best_allocation = None
        earliest_start = None

        for machine_option in task.machine_options:
            machine = self._machines.get(machine_option.machine_id)
            if not machine:
                continue

            # Find earliest available time for this machine
            machine_start = self._find_earliest_available_time(
                machine.id,
                preferred_start,
                machine_option.total_duration(),
                schedule
            )

            if not machine_start:
                continue

            # Find qualified operators
            required_operators = []
            if machine.is_attended:
                # Need operator for full duration
                operators_needed = 1  # Could be more for complex operations
                qualified = self._skill_matcher.find_qualified_operators(
                    machine,
                    list(self._operators.values())
                )

                # Find available operators
                available_ops = []
                duration = machine_option.total_duration()
                window = TimeWindow(machine_start, machine_start + duration.to_timedelta())

                for op in qualified:
                    if self._is_operator_available(op.id, window, schedule):
                        available_ops.append(op)

                if len(available_ops) < operators_needed:
                    continue

                required_operators = [op.id for op in available_ops[:operators_needed]]
            else:
                # Need operator for setup only
                setup_window = TimeWindow(
                    machine_start,
                    machine_start + machine_option.setup_duration.to_timedelta()
                )

                qualified = self._skill_matcher.find_qualified_operators(
                    machine,
                    list(self._operators.values())
                )

                setup_operator = None
                for op in qualified:
                    if self._is_operator_available(op.id, setup_window, schedule):
                        setup_operator = op
                        break

                if not setup_operator:
                    continue

                required_operators = [setup_operator.id]

            # Check if this is the best allocation so far
            if earliest_start is None or machine_start < earliest_start:
                earliest_start = machine_start
                end_time = machine_start + machine_option.total_duration().to_timedelta()
                best_allocation = (
                    machine.id,
                    required_operators,
                    TimeWindow(machine_start, end_time)
                )

        return best_allocation

    def _find_earliest_available_time(
        self,
        machine_id: UUID,
        preferred_start: datetime,
        duration: Duration,
        schedule: Schedule
    ) -> Optional[datetime]:
        """Find earliest time machine is available for duration."""
        machine_windows = schedule.get_machine_schedule(machine_id)

        if not machine_windows:
            return preferred_start

        # Sort windows by start time
        machine_windows.sort(key=lambda w: w.start)

        # Check if we can start at preferred time
        test_window = TimeWindow(
            preferred_start,
            preferred_start + duration.to_timedelta()
        )

        for existing in machine_windows:
            if existing.overlaps(test_window):
                # Try starting after this window
                preferred_start = existing.end
                test_window = TimeWindow(
                    preferred_start,
                    preferred_start + duration.to_timedelta()
                )

        return preferred_start

    def _is_operator_available(
        self,
        operator_id: UUID,
        window: TimeWindow,
        schedule: Schedule
    ) -> bool:
        """Check if operator is available during window."""
        operator_windows = schedule.get_operator_schedule(operator_id)

        for existing in operator_windows:
            if existing.overlaps(window):
                return False

        return True


class CriticalSequenceManager:
    """Domain service for managing critical operation sequences."""

    def identify_critical_sequences(self, job: Job) -> List[List[Task]]:
        """
        Identify sequences of critical tasks that must be prioritized.
        Returns list of task sequences.
        """
        sequences = []
        current_sequence = []

        for task in job.get_tasks_in_sequence():
            if task.is_critical:
                current_sequence.append(task)
            else:
                if len(current_sequence) >= 2:  # Sequence of at least 2 critical tasks
                    sequences.append(current_sequence)
                current_sequence = []

        # Don't forget last sequence
        if len(current_sequence) >= 2:
            sequences.append(current_sequence)

        return sequences

    def calculate_sequence_duration(self, sequence: List[Task]) -> Duration:
        """Calculate minimum duration for a critical sequence."""
        total = Duration(Decimal(0))

        for task in sequence:
            # Use minimum duration from machine options
            min_duration = min(
                opt.total_duration()
                for opt in task.machine_options
            )
            total = total + min_duration

        return total

    def prioritize_job_sequence(self, jobs: List[Job]) -> List[Job]:
        """
        Sort jobs by criticality and due date.
        Jobs with more critical sequences get higher priority.
        """
        def job_priority_score(job: Job) -> Tuple[int, int, datetime]:
            critical_sequences = self.identify_critical_sequences(job)
            num_critical_tasks = sum(len(seq) for seq in critical_sequences)

            # Return (negative critical count for descending sort, priority, due_date)
            return (
                -num_critical_tasks,
                -job.priority,  # Negative for descending sort
                job.due_date or datetime.max
            )

        return sorted(jobs, key=job_priority_score)


# ============================================================================
# REPOSITORY INTERFACES
# ============================================================================

class Repository(Protocol):
    """Base repository interface."""

    def save(self, entity: Entity) -> None:
        """Save an entity."""
        ...

    def find_by_id(self, entity_id: UUID) -> Optional[Entity]:
        """Find entity by ID."""
        ...

    def find_all(self) -> List[Entity]:
        """Find all entities."""
        ...

    def delete(self, entity_id: UUID) -> None:
        """Delete an entity."""
        ...


class JobRepository(Protocol):
    """Repository interface for Job aggregate."""

    def save(self, job: Job) -> None:
        """Save job with all tasks."""
        ...

    def find_by_id(self, job_id: UUID) -> Optional[Job]:
        """Find job by ID with all tasks loaded."""
        ...

    def find_by_job_number(self, job_number: str) -> Optional[Job]:
        """Find job by job number."""
        ...

    def find_by_status(self, status: TaskStatus) -> List[Job]:
        """Find jobs containing tasks with given status."""
        ...

    def find_overdue(self, as_of: datetime) -> List[Job]:
        """Find jobs past their due date."""
        ...


class MachineRepository(Protocol):
    """Repository interface for Machine entities."""

    def save(self, machine: Machine) -> None:
        """Save machine."""
        ...

    def find_by_id(self, machine_id: UUID) -> Optional[Machine]:
        """Find machine by ID."""
        ...

    def find_by_zone(self, zone: str) -> List[Machine]:
        """Find machines in a zone."""
        ...

    def find_available(self, time_window: TimeWindow) -> List[Machine]:
        """Find machines available during time window."""
        ...

    def find_by_skill_requirement(self, skill: SkillRequirement) -> List[Machine]:
        """Find machines requiring specific skill."""
        ...


class OperatorRepository(Protocol):
    """Repository interface for Operator aggregate."""

    def save(self, operator: Operator) -> None:
        """Save operator with skills."""
        ...

    def find_by_id(self, operator_id: UUID) -> Optional[Operator]:
        """Find operator by ID."""
        ...

    def find_by_employee_id(self, employee_id: str) -> Optional[Operator]:
        """Find operator by employee ID."""
        ...

    def find_by_skill(self, skill_type: SkillType, min_level: int) -> List[Operator]:
        """Find operators with skill at minimum level."""
        ...

    def find_available(self, time_window: TimeWindow) -> List[Operator]:
        """Find operators available during time window."""
        ...


class ScheduleRepository(Protocol):
    """Repository interface for Schedule aggregate."""

    def save(self, schedule: Schedule) -> None:
        """Save schedule with all assignments."""
        ...

    def find_by_id(self, schedule_id: UUID) -> Optional[Schedule]:
        """Find schedule by ID."""
        ...

    def find_by_version(self, version: int) -> Optional[Schedule]:
        """Find schedule by version number."""
        ...

    def find_active(self, as_of: datetime) -> Optional[Schedule]:
        """Find active schedule for given date."""
        ...

    def create_new_version(self, base_schedule: Schedule) -> Schedule:
        """Create new version from existing schedule."""
        ...


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_basic_scheduling():
    """Example of basic scheduling workflow."""

    # Create business calendar
    calendar = BusinessCalendar.standard_calendar()

    # Create machines
    machine1 = Machine(
        name="CNC-01",
        zone="Zone-A",
        skill_requirements=[SkillRequirement(SkillType.MACHINING, 2)],
        is_attended=True
    )

    machine2 = Machine(
        name="WELD-01",
        zone="Zone-B",
        skill_requirements=[SkillRequirement(SkillType.WELDING, 1)],
        is_attended=False  # Unattended after setup
    )

    # Create operators
    operator1 = Operator.create_skilled_operator(
        name="John Smith",
        employee_id="EMP001",
        skill_types=[(SkillType.MACHINING, 3), (SkillType.WELDING, 2)]
    )

    operator2 = Operator.create_skilled_operator(
        name="Jane Doe",
        employee_id="EMP002",
        skill_types=[(SkillType.MACHINING, 2), (SkillType.INSPECTION, 3)]
    )

    # Create a job
    job = Job.create_standard_job(
        job_number="JOB-2024-001",
        operation_count=10,  # Simplified for example
        priority=1,
        due_date=datetime.now() + timedelta(days=5)
    )

    # Create schedule
    schedule = Schedule(
        version=1,
        effective_date=datetime.now(),
        calendar=calendar
    )

    # Create services
    skill_matcher = SkillMatcher()
    validator = ScheduleValidator(calendar)
    allocator = ResourceAllocator(
        machines=[machine1, machine2],
        operators=[operator1, operator2],
        skill_matcher=skill_matcher
    )

    # Schedule first task
    first_task = job.get_tasks_in_sequence()[0]

    # Manually assign for demonstration
    schedule.assign_task(
        task=first_task,
        machine_id=machine1.id,
        operator_ids=[operator1.id],
        start_time=datetime.now() + timedelta(hours=1),
        duration=Duration.from_hours(2)
    )

    # Validate schedule
    is_valid, violations = validator.validate_complete(job, schedule)

    print(f"Schedule valid: {is_valid}")
    if not is_valid:
        print(f"Violations: {violations}")

    # Get events from entities
    events = []
    events.extend(job.get_domain_events())
    events.extend(first_task.get_domain_events())
    events.extend(operator1.get_domain_events())

    print(f"Domain events raised: {len(events)}")
    for event in events:
        print(f"  - {type(event).__name__}: {event.occurred_at}")


def example_resource_allocation():
    """Example of automatic resource allocation."""

    # Setup (similar to above)
    machines = [
        Machine(
            name=f"MACHINE-{i}",
            zone=f"Zone-{chr(65 + i // 3)}",
            skill_requirements=[SkillRequirement(SkillType.MACHINING, 1)],
            is_attended=(i % 2 == 0)
        )
        for i in range(10)
    ]

    operators = [
        Operator.create_skilled_operator(
            name=f"Operator-{i}",
            employee_id=f"EMP{i:03d}",
            skill_types=[
                (SkillType.MACHINING, 1 + (i % 3)),
                (SkillType.WELDING, 1 + ((i + 1) % 3))
            ]
        )
        for i in range(10)
    ]

    job = Job.create_standard_job(
        job_number="JOB-2024-002",
        operation_count=20,
        priority=2,
        due_date=datetime.now() + timedelta(days=3)
    )

    schedule = Schedule()
    skill_matcher = SkillMatcher()
    allocator = ResourceAllocator(machines, operators, skill_matcher)

    # Allocate resources for each task
    current_time = datetime.now()

    for task in job.get_tasks_in_sequence()[:5]:  # First 5 tasks
        allocation = allocator.allocate_resources_for_task(
            task=task,
            schedule=schedule,
            preferred_start=current_time
        )

        if allocation:
            machine_id, operator_ids, window = allocation
            print(f"Task {task.operation_number}: Machine {machine_id}, "
                  f"Operators {len(operator_ids)}, "
                  f"Start {window.start.strftime('%Y-%m-%d %H:%M')}")

            # Update task to ready since no predecessors in this example
            task._status = TaskStatus.READY

            # Assign in schedule
            schedule.assign_task(
                task=task,
                machine_id=machine_id,
                operator_ids=operator_ids,
                start_time=window.start,
                duration=window.duration()
            )

            # Update current time for next task
            current_time = window.end
        else:
            print(f"Could not allocate resources for task {task.operation_number}")

    # Calculate makespan
    makespan = schedule.calculate_makespan()
    if makespan:
        print(f"Schedule makespan: {makespan.minutes} minutes")


def example_critical_sequence_management():
    """Example of handling critical operation sequences."""

    # Create jobs with critical operations
    jobs = []
    for i in range(3):
        job = Job.create_standard_job(
            job_number=f"JOB-2024-{i:03d}",
            operation_count=50,
            priority=i,
            due_date=datetime.now() + timedelta(days=7-i)
        )
        jobs.append(job)

    # Use critical sequence manager
    critical_mgr = CriticalSequenceManager()

    for job in jobs:
        sequences = critical_mgr.identify_critical_sequences(job)
        print(f"Job {job.job_number}: {len(sequences)} critical sequences")

        for seq in sequences:
            duration = critical_mgr.calculate_sequence_duration(seq)
            print(f"  - Sequence of {len(seq)} tasks, "
                  f"minimum duration: {duration.minutes} minutes")

    # Prioritize jobs
    prioritized = critical_mgr.prioritize_job_sequence(jobs)
    print("\nPrioritized job sequence:")
    for job in prioritized:
        print(f"  - {job.job_number} (priority: {job.priority}, "
              f"due: {job.due_date.strftime('%Y-%m-%d')})")


if __name__ == "__main__":
    print("=== Manufacturing Scheduling Domain Model Examples ===\n")

    print("1. Basic Scheduling Example:")
    print("-" * 40)
    example_basic_scheduling()

    print("\n2. Resource Allocation Example:")
    print("-" * 40)
    example_resource_allocation()

    print("\n3. Critical Sequence Management Example:")
    print("-" * 40)
    example_critical_sequence_management()
