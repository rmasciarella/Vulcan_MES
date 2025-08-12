"""Examples demonstrating the use of scheduling domain entities."""

from datetime import datetime, timedelta
from uuid import uuid4

from .factories import SchedulingDomainFactory
from .value_objects.enums import JobStatus, PriorityLevel, SkillLevel, TaskStatus


def create_sample_job_with_tasks():
    """
    Example: Create a complete job with tasks using domain entities.

    This demonstrates the proper use of DDD patterns:
    - Aggregate root (Job) coordinates child entities (Tasks)
    - Business rules are enforced by the domain model
    - Events are raised for important state changes
    """

    # Create a sample manufacturing setup
    manufacturing_setup = SchedulingDomainFactory.create_sample_manufacturing_line()

    zones = manufacturing_setup["zones"]
    operations = manufacturing_setup["operations"]
    machines = manufacturing_setup["machines"]
    operators = manufacturing_setup["operators"]

    print(f"Created {len(zones)} production zones")
    print(f"Created {len(operations)} operations")
    print(f"Created {len(machines)} machines")
    print(f"Created {len(operators)} operators")

    # Create a high-priority job
    due_date = datetime.utcnow() + timedelta(days=5)
    job = (
        SchedulingDomainFactory.job("URGENT-001", due_date)
        .customer("Critical Customer Inc.")
        .part("PART-URGENT-500")
        .quantity(25)
        .priority(PriorityLevel.CRITICAL)
        .created_by("production_manager")
        .build()
    )

    print(f"\nCreated job: {job.job_number}")
    print(f"Customer: {job.customer_name}")
    print(f"Due date: {job.due_date}")
    print(f"Priority: {job.priority.value}")

    # Create tasks for each operation
    tasks = []
    for operation in operations:
        task = (
            SchedulingDomainFactory.task(
                job.id, operation.id, operation.sequence_number
            )
            .duration(operation.standard_duration.minutes)
            .setup_time(operation.setup_duration.minutes)
            .build()
        )

        # Mark critical operations as critical path
        if operation.is_critical:
            task.mark_critical_path()

        tasks.append(task)
        job.add_task(task)

    print(f"Added {len(tasks)} tasks to job")

    # Release the job (business rule: only released jobs can be scheduled)
    job.change_status(JobStatus.RELEASED, "ready_for_production")

    # Schedule first task (demonstrates business rules)
    first_task = job.get_task_by_sequence(10)  # Material Prep
    if first_task and first_task.status == TaskStatus.READY:
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(minutes=first_task.planned_duration.minutes)

        first_task.schedule(start_time, end_time)
        print(f"Scheduled first task: {first_task.sequence_in_job}")
        print(f"Start: {first_task.planned_start_time}")
        print(f"End: {first_task.planned_end_time}")

    # Demonstrate WIP management
    prep_zone = zones[0]  # Preparation zone
    print("\nWIP Management Demo:")
    print(f"Zone: {prep_zone.zone_name}")
    print(f"WIP Limit: {prep_zone.wip_limit}")
    print(f"Current WIP: {prep_zone.current_wip}")

    # Add job to zone WIP
    try:
        prep_zone.add_job(job.id)
        print(f"Added job to zone. New WIP: {prep_zone.current_wip}")
    except Exception as e:
        print(f"WIP limit error: {e}")

    # Demonstrate operator skills matching
    cnc_machine = machines[0]  # CNC machine
    john = operators[0]  # John (has CNC skills)

    print("\nSkill Matching Demo:")
    print(f"Machine: {cnc_machine.machine_name}")
    print(f"Operator: {john.full_name}")

    can_operate = cnc_machine.operator_can_operate(john.active_skills)
    print(f"Can {john.full_name} operate {cnc_machine.machine_name}? {can_operate}")

    # Show job progress
    print("\nJob Progress:")
    print(f"Completion: {job.completion_percentage:.1f}%")
    print(f"Ready tasks: {len(job.get_ready_tasks())}")
    print(f"Active tasks: {len(job.get_active_tasks())}")

    # Get domain events (would normally be published by infrastructure)
    all_events = []
    all_events.extend(job.get_domain_events())
    all_events.extend(prep_zone.get_domain_events())

    print(f"\nDomain Events Generated: {len(all_events)}")
    for event in all_events:
        print(f"- {event.__class__.__name__}")

    return job, manufacturing_setup


def demonstrate_task_lifecycle():
    """
    Example: Complete task lifecycle with status transitions and business rules.
    """

    print("\n" + "=" * 50)
    print("TASK LIFECYCLE DEMONSTRATION")
    print("=" * 50)

    # Create minimal setup
    job_id = uuid4()
    operation_id = uuid4()

    task = (
        SchedulingDomainFactory.task(job_id, operation_id, 20)
        .duration(45)  # 45 minutes
        .setup_time(15)  # 15 minutes setup
        .critical_path()
        .build()
    )

    print(f"Created task {task.sequence_in_job} with status: {task.status.value}")

    # Task lifecycle: pending -> ready -> scheduled -> in_progress -> completed

    # 1. Mark as ready (prerequisites met)
    task.mark_ready()
    print(f"Task marked ready: {task.status.value}")

    # 2. Schedule the task
    start_time = datetime.utcnow() + timedelta(hours=2)
    end_time = start_time + timedelta(minutes=60)  # 45 min + 15 min setup

    task.schedule(start_time, end_time)
    print(f"Task scheduled: {task.status.value}")
    print(f"  Start: {task.planned_start_time}")
    print(f"  Duration: {task.planned_duration}")

    # 3. Start the task
    actual_start = start_time + timedelta(minutes=5)  # 5 minutes late
    task.start(actual_start)
    print(f"Task started: {task.status.value}")
    print(f"  Actual start: {task.actual_start_time}")

    # 4. Complete the task
    actual_end = actual_start + timedelta(minutes=50)  # Took 50 minutes (5 extra)
    task.complete(actual_end)
    print(f"Task completed: {task.status.value}")
    print(f"  Actual duration: {task.actual_duration}")
    print(f"  Was delayed: {task.is_delayed}")
    print(f"  Delay minutes: {task.delay_minutes}")

    # Show domain events
    events = task.get_domain_events()
    print(f"\nEvents generated: {len(events)}")
    for event in events:
        print(f"- {event.__class__.__name__}: {getattr(event, 'reason', 'N/A')}")


def demonstrate_business_rules():
    """
    Example: Business rule enforcement in the domain model.
    """

    print("\n" + "=" * 50)
    print("BUSINESS RULES DEMONSTRATION")
    print("=" * 50)

    # Create a production zone with WIP limit
    zone = SchedulingDomainFactory.production_zone(
        "LIMIT_TEST", "Limited Zone", wip_limit=2, description="Testing WIP limits"
    )

    print(f"Created zone '{zone.zone_name}' with WIP limit: {zone.wip_limit}")

    # Add jobs up to the limit
    job1_id, job2_id, job3_id = uuid4(), uuid4(), uuid4()

    zone.add_job(job1_id)
    print(f"Added job 1. WIP: {zone.current_wip}/{zone.wip_limit}")

    zone.add_job(job2_id)
    print(f"Added job 2. WIP: {zone.current_wip}/{zone.wip_limit}")

    # Try to exceed the limit (should fail)
    try:
        zone.add_job(job3_id)
        print("ERROR: Should have failed!")
    except Exception as e:
        print(f"✓ WIP limit enforced: {e}")

    # Create operator with skills
    operator = (
        SchedulingDomainFactory.operator("EMP999", "Test", "Operator")
        .skill("WELDING", "Arc Welding", SkillLevel.LEVEL_3)
        .skill("QUALITY", "Quality Control", SkillLevel.LEVEL_2)
        .build()
    )

    print(f"\nCreated operator with {operator.skill_count} skills")

    # Create machine requiring higher skill level
    machine = (
        SchedulingDomainFactory.machine("WELD-001", "Advanced Welder")
        .requires_skill(
            "WELDING", "Arc Welding", SkillLevel.LEVEL_2
        )  # Operator has level 3
        .requires_skill(
            "SAFETY", "Safety Certification", SkillLevel.LEVEL_1
        )  # Operator lacks this
        .build()
    )

    # Test skill matching
    can_operate = machine.operator_can_operate(operator.active_skills)
    print(f"Can operator run machine? {can_operate}")
    print("(Should be False - missing SAFETY skill)")

    # Add missing skill
    from .value_objects.common import OperatorSkill, Skill

    safety_skill = OperatorSkill(
        skill=Skill(skill_code="SAFETY", skill_name="Safety Certification"),
        proficiency_level=SkillLevel.LEVEL_2,
    )
    operator.add_skill(safety_skill)

    # Test again
    can_operate = machine.operator_can_operate(operator.active_skills)
    print(f"After adding skill, can operate? {can_operate}")
    print("(Should be True - all requirements met)")


if __name__ == "__main__":
    """Run all examples."""

    print("DDD SCHEDULING DOMAIN EXAMPLES")
    print("=" * 50)

    # Run examples
    job, setup = create_sample_job_with_tasks()
    demonstrate_task_lifecycle()
    demonstrate_business_rules()

    print("\n" + "=" * 50)
    print("EXAMPLES COMPLETED")
    print("=" * 50)
