# Production Scheduling Domain Model

This module implements a comprehensive Domain-Driven Design (DDD) model for production scheduling, based on the SQL schema that defines tables for production zones, operations, skills, machines, operators, jobs, tasks, machine capabilities, operator skills, business calendar, maintenance, and constraints.

## Architecture Overview

The domain model follows DDD principles with:

- **Entities**: Objects with identity and lifecycle
- **Value Objects**: Immutable objects defined by their values
- **Aggregate Roots**: Entities that control consistency boundaries
- **Domain Events**: Events raised when important business events occur
- **Domain Services**: Business logic that doesn't belong to a single entity
- **Factories & Builders**: Clean object creation with fluent interfaces

## Core Entities

### Job (Aggregate Root)
- Coordinates multiple tasks in sequence to produce a finished product
- Manages priority, scheduling, and progress tracking
- Enforces business rules about task progression and resource allocation
- Status transitions: planned → released → in_progress → completed/cancelled/on_hold

### Task
- Represents individual work assignments within a job
- Manages resource assignments, timing, and status progression
- Tracks critical path, delays, and rework
- Status transitions: pending → ready → scheduled → in_progress → completed/failed/cancelled

### Operation
- Defines standard manufacturing operations (1-100 sequence)
- Specifies standard durations, setup times, and requirements
- Can be marked as critical to the manufacturing process

### Machine
- Production equipment with capabilities and requirements
- Manages what operations it can perform and required operator skills
- Tracks availability, efficiency, and maintenance windows
- Supports different automation levels (attended/unattended)

### Operator
- Human resources with skills, schedules, and availability
- Manages skill certifications with expiry tracking
- Supports availability overrides and custom working hours

### ProductionZone
- Physical or logical areas with Work-In-Progress (WIP) limits
- Prevents bottlenecks by constraining concurrent jobs
- Tracks current utilization and capacity

## Value Objects

### Core Value Objects
- **Duration**: Time periods with validation and operations
- **TimeWindow**: Start/end time pairs with overlap detection
- **WorkingHours**: Daily schedules with lunch breaks
- **Skill & OperatorSkill**: Skill definitions with proficiency levels
- **EfficiencyFactor**: Machine/operator efficiency multipliers
- **Quantity**: Product quantities with units

### Domain Enums
- **JobStatus**: planned, released, in_progress, completed, on_hold, cancelled
- **TaskStatus**: pending, ready, scheduled, in_progress, completed, cancelled, failed
- **MachineStatus**: available, busy, maintenance, offline
- **OperatorStatus**: available, assigned, on_break, off_shift, absent
- **SkillLevel**: 1 (beginner), 2 (intermediate), 3 (expert)
- **PriorityLevel**: low, normal, high, critical

## Domain Events

The model raises events for important business occurrences:

### Job Events
- `JobStatusChanged`: When job status transitions
- `JobScheduleChanged`: When job timing changes
- `JobDelayed`: When job is delayed beyond due date
- `TaskProgressUpdated`: When task completion updates job progress

### Task Events
- `TaskStatusChanged`: When task status transitions
- `TaskAssignmentChanged`: When resource assignments change
- `TaskDelayed`: When task is delayed

### Resource Events
- `MachineStatusChanged`: When machine status changes
- `OperatorStatusChanged`: When operator status changes
- `SkillCertificationExpiring`: When operator certification expires soon
- `WipChanged`: When WIP levels change in production zones

## Business Rules Enforced

### Job Rules
- Jobs must have future due dates
- Only released jobs can be scheduled
- Tasks must complete in sequence
- Job completion requires all tasks to be done or reaching operation 100

### Task Rules
- Tasks follow strict status transitions
- Cannot schedule tasks that aren't ready
- Cannot complete tasks that haven't started
- Resource assignments must meet capability requirements

### Resource Rules
- Operators must have required skills at minimum levels
- Machines can only perform operations they're capable of
- WIP limits prevent zone overload
- Skill certifications must be valid (not expired)

### Scheduling Rules
- Start times must be before end times
- Tasks cannot be scheduled in the past
- Resource conflicts are prevented
- Maintenance windows block machine availability

## Usage Examples

### Creating a Job with Tasks

```python
from backend.app.domain.scheduling import SchedulingDomainFactory

# Create a manufacturing job
due_date = datetime.utcnow() + timedelta(days=7)
job = (SchedulingDomainFactory.job("JOB-001", due_date)
       .customer("Acme Corp")
       .part("WIDGET-123")
       .quantity(50)
       .priority(PriorityLevel.HIGH)
       .build())

# Add tasks for operations
task1 = (SchedulingDomainFactory.task(job.id, operation1.id, 10)
         .duration(45)
         .setup_time(15)
         .critical_path()
         .build())

job.add_task(task1)
job.change_status(JobStatus.RELEASED)
```

### Resource Management

```python
# Create machine with capabilities
machine = (SchedulingDomainFactory.machine("CNC-001", "CNC Mill")
           .automation(MachineAutomationLevel.UNATTENDED)
           .efficiency(0.95)
           .capability(operation_id, 60, 10, is_primary=True)
           .requires_skill("CNC_PROG", "CNC Programming", SkillLevel.LEVEL_2)
           .build())

# Create operator with skills
operator = (SchedulingDomainFactory.operator("EMP001", "John", "Smith")
            .skill("CNC_PROG", "CNC Programming", SkillLevel.LEVEL_3)
            .shift(time(7,0), time(16,0))
            .build())

# Check if operator can run machine
can_operate = machine.operator_can_operate(operator.active_skills)
```

### WIP Management

```python
# Create production zone with limits
zone = SchedulingDomainFactory.production_zone(
    "MACHINING", "CNC Machining Area", wip_limit=3
)

# Add jobs (enforces WIP limits)
zone.add_job(job1.id)  # WIP = 1
zone.add_job(job2.id)  # WIP = 2
zone.add_job(job3.id)  # WIP = 3
zone.add_job(job4.id)  # Raises WipLimitExceeded exception
```

## Factory and Builder Patterns

The domain provides fluent builder patterns for clean object creation:

```python
# Using builders for complex object creation
job = (SchedulingDomainFactory.job("JOB-001", due_date)
       .customer("Customer Name")
       .part("PART-123")
       .quantity(10)
       .priority(PriorityLevel.CRITICAL)
       .build())

machine = (SchedulingDomainFactory.machine("MACHINE-001", "Machine Name")
           .automation(MachineAutomationLevel.ATTENDED)
           .zone(zone_id)
           .efficiency(1.1)
           .capability(op_id, 60, 15)
           .requires_skill("SKILL", "Skill Name", SkillLevel.LEVEL_2)
           .build())
```

## Integration Points

### Database Persistence
- Entities use UUID primary keys for distributed systems
- Rich domain models map to the existing SQL schema
- Repository pattern abstracts persistence concerns

### Event Publishing
- Domain events can be collected and published by infrastructure
- Supports event sourcing and CQRS patterns
- Enables loose coupling between bounded contexts

### API Layer
- Entities provide summary methods for API responses
- Factory methods enable clean request/response mapping
- Business rules prevent invalid API operations

## Testing Support

The domain includes comprehensive examples and test data:

- `create_sample_manufacturing_job()`: Complete job setup
- `create_sample_manufacturing_line()`: Full production setup
- `examples.py`: Demonstrates all major features
- Business rule violation examples

## File Structure

```
backend/app/domain/scheduling/
├── __init__.py                 # Package exports
├── entities/                   # Domain entities
│   ├── __init__.py
│   ├── job.py                 # Job aggregate root
│   ├── task.py                # Task entity
│   ├── operation.py           # Operation entity
│   ├── machine.py             # Machine entity
│   ├── operator.py            # Operator entity
│   └── production_zone.py     # ProductionZone entity
├── value_objects/             # Value objects and enums
│   ├── __init__.py
│   ├── common.py             # Common value objects
│   └── enums.py              # Domain enumerations
├── factories.py              # Factory and builder classes
├── examples.py               # Usage examples
└── README.md                 # This file
```

## Benefits of This Design

1. **Business Logic Centralization**: All scheduling rules are in the domain
2. **Rich Behavior**: Entities have behavior, not just data
3. **Consistency**: Aggregate roots maintain invariants
4. **Testability**: Pure domain logic is easy to unit test
5. **Flexibility**: Easy to extend with new business rules
6. **Event-Driven**: Domain events enable reactive patterns
7. **Type Safety**: Strong typing with Pydantic validation
8. **Immutability**: Value objects prevent accidental mutations

This domain model provides a solid foundation for building a production scheduling system that is maintainable, extensible, and aligned with business requirements.
