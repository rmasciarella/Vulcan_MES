"""
Integration Tests for Schedule Repository Implementation

Tests the actual database operations for schedules, including assignments,
resource allocations, and complex schedule operations with real database transactions.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.domain.scheduling.entities.schedule import (
    Schedule,
    ScheduleAssignment,
    ScheduleStatus,
)
from app.domain.scheduling.value_objects.duration import Duration
from app.infrastructure.database.repositories.schedule_repository import (
    SQLScheduleRepository,
)


@pytest.mark.database
@pytest.mark.integration
class TestSQLScheduleRepositoryIntegration:
    """Integration tests for SQLScheduleRepository with actual database."""

    @pytest.fixture
    def schedule_repository(self, db_session: Session):
        """Create schedule repository with database session."""
        return SQLScheduleRepository(db_session)

    @pytest.fixture
    def sample_schedule(self):
        """Create a sample schedule for testing."""
        return Schedule(
            name="Integration Test Schedule",
            planning_horizon=Duration(days=14),
            created_by=uuid4(),
        )

    @pytest.fixture
    def sample_assignment(self):
        """Create a sample schedule assignment."""
        start_time = datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=3)

        return ScheduleAssignment(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4(), uuid4()],
            start_time=start_time,
            end_time=end_time,
            setup_duration=Duration(minutes=30),
            processing_duration=Duration(minutes=150),
        )

    async def test_save_and_retrieve_schedule(
        self, schedule_repository, sample_schedule, db_session
    ):
        """Test saving and retrieving a schedule from database."""
        # Save schedule
        saved_schedule = await schedule_repository.save(sample_schedule)
        db_session.commit()

        # Verify saved schedule
        assert saved_schedule.id == sample_schedule.id
        assert saved_schedule.name == sample_schedule.name

        # Retrieve schedule
        retrieved_schedule = await schedule_repository.get_by_id(sample_schedule.id)

        # Verify retrieved schedule
        assert retrieved_schedule is not None
        assert retrieved_schedule.id == sample_schedule.id
        assert retrieved_schedule.name == sample_schedule.name
        assert (
            retrieved_schedule.planning_horizon.days
            == sample_schedule.planning_horizon.days
        )
        assert retrieved_schedule.status == sample_schedule.status
        assert retrieved_schedule.created_by == sample_schedule.created_by

    async def test_save_schedule_with_jobs(
        self, schedule_repository, sample_schedule, db_session
    ):
        """Test saving schedule with associated jobs."""
        # Add jobs to schedule
        job_ids = [uuid4(), uuid4(), uuid4()]
        for job_id in job_ids:
            sample_schedule.add_job(job_id)

        # Save schedule
        await schedule_repository.save(sample_schedule)
        db_session.commit()

        # Retrieve and verify
        retrieved_schedule = await schedule_repository.get_by_id(sample_schedule.id)

        assert retrieved_schedule is not None
        assert len(retrieved_schedule.job_ids) == 3
        assert set(retrieved_schedule.job_ids) == set(job_ids)

    async def test_save_schedule_with_assignments(
        self, schedule_repository, sample_schedule, sample_assignment, db_session
    ):
        """Test saving schedule with task assignments."""
        # Add assignment to schedule
        sample_schedule.assignments.append(sample_assignment)

        # Save schedule
        await schedule_repository.save(sample_schedule)
        db_session.commit()

        # Retrieve and verify
        retrieved_schedule = await schedule_repository.get_by_id(sample_schedule.id)

        assert retrieved_schedule is not None
        assert len(retrieved_schedule.assignments) == 1

        assignment = retrieved_schedule.assignments[0]
        assert assignment.task_id == sample_assignment.task_id
        assert assignment.machine_id == sample_assignment.machine_id
        assert set(assignment.operator_ids) == set(sample_assignment.operator_ids)
        assert assignment.start_time == sample_assignment.start_time
        assert assignment.end_time == sample_assignment.end_time
        assert (
            assignment.setup_duration.minutes
            == sample_assignment.setup_duration.minutes
        )

    async def test_update_schedule(
        self, schedule_repository, sample_schedule, db_session
    ):
        """Test updating an existing schedule."""
        # Save initial schedule
        await schedule_repository.save(sample_schedule)
        db_session.commit()

        # Update schedule properties
        sample_schedule.name = "Updated Schedule Name"
        sample_schedule.description = "Updated description"
        sample_schedule._status = ScheduleStatus.PUBLISHED

        # Update in database
        updated_schedule = await schedule_repository.update(sample_schedule)
        db_session.commit()

        # Verify update
        assert updated_schedule.name == "Updated Schedule Name"
        assert updated_schedule.description == "Updated description"
        assert updated_schedule.status == ScheduleStatus.PUBLISHED

        # Retrieve and verify persistence
        retrieved_schedule = await schedule_repository.get_by_id(sample_schedule.id)
        assert retrieved_schedule.name == "Updated Schedule Name"
        assert retrieved_schedule.description == "Updated description"
        assert retrieved_schedule.status == ScheduleStatus.PUBLISHED

    async def test_delete_schedule(
        self, schedule_repository, sample_schedule, db_session
    ):
        """Test deleting a schedule from database."""
        # Save schedule
        await schedule_repository.save(sample_schedule)
        db_session.commit()

        # Verify schedule exists
        retrieved_schedule = await schedule_repository.get_by_id(sample_schedule.id)
        assert retrieved_schedule is not None

        # Delete schedule
        await schedule_repository.delete(sample_schedule.id)
        db_session.commit()

        # Verify schedule is deleted
        deleted_schedule = await schedule_repository.get_by_id(sample_schedule.id)
        assert deleted_schedule is None

    async def test_get_nonexistent_schedule(self, schedule_repository):
        """Test retrieving non-existent schedule returns None."""
        nonexistent_id = uuid4()
        schedule = await schedule_repository.get_by_id(nonexistent_id)
        assert schedule is None

    async def test_find_schedules_by_status(self, schedule_repository, db_session):
        """Test finding schedules filtered by status."""
        # Create schedules with different statuses
        draft_schedule = Schedule(
            name="Draft Schedule",
            planning_horizon=Duration(days=7),
        )
        published_schedule = Schedule(
            name="Published Schedule",
            planning_horizon=Duration(days=7),
        )
        published_schedule._status = ScheduleStatus.PUBLISHED

        active_schedule = Schedule(
            name="Active Schedule",
            planning_horizon=Duration(days=7),
        )
        active_schedule._status = ScheduleStatus.ACTIVE

        # Save all schedules
        await schedule_repository.save(draft_schedule)
        await schedule_repository.save(published_schedule)
        await schedule_repository.save(active_schedule)
        db_session.commit()

        # Find draft schedules
        draft_schedules = await schedule_repository.find_by_status(ScheduleStatus.DRAFT)
        draft_names = [sched.name for sched in draft_schedules]
        assert "Draft Schedule" in draft_names
        assert "Published Schedule" not in draft_names

        # Find published schedules
        published_schedules = await schedule_repository.find_by_status(
            ScheduleStatus.PUBLISHED
        )
        published_names = [sched.name for sched in published_schedules]
        assert "Published Schedule" in published_names
        assert "Draft Schedule" not in published_names

        # Find active schedules
        active_schedules = await schedule_repository.find_by_status(
            ScheduleStatus.ACTIVE
        )
        active_names = [sched.name for sched in active_schedules]
        assert "Active Schedule" in active_names

    async def test_find_schedules_by_created_by(self, schedule_repository, db_session):
        """Test finding schedules by creator."""
        user1_id = uuid4()
        user2_id = uuid4()

        # Create schedules by different users
        user1_schedule1 = Schedule(
            name="User1 Schedule 1",
            planning_horizon=Duration(days=5),
            created_by=user1_id,
        )
        user1_schedule2 = Schedule(
            name="User1 Schedule 2",
            planning_horizon=Duration(days=10),
            created_by=user1_id,
        )
        user2_schedule = Schedule(
            name="User2 Schedule",
            planning_horizon=Duration(days=7),
            created_by=user2_id,
        )

        # Save all schedules
        await schedule_repository.save(user1_schedule1)
        await schedule_repository.save(user1_schedule2)
        await schedule_repository.save(user2_schedule)
        db_session.commit()

        # Find schedules by user1
        user1_schedules = await schedule_repository.find_by_created_by(user1_id)
        user1_names = [sched.name for sched in user1_schedules]

        assert len(user1_schedules) == 2
        assert "User1 Schedule 1" in user1_names
        assert "User1 Schedule 2" in user1_names
        assert "User2 Schedule" not in user1_names

        # Find schedules by user2
        user2_schedules = await schedule_repository.find_by_created_by(user2_id)
        user2_names = [sched.name for sched in user2_schedules]

        assert len(user2_schedules) == 1
        assert "User2 Schedule" in user2_names

    async def test_find_schedules_containing_job(self, schedule_repository, db_session):
        """Test finding schedules that contain a specific job."""
        target_job_id = uuid4()
        other_job_id = uuid4()

        # Create schedules with and without the target job
        schedule_with_job = Schedule(
            name="Schedule With Target Job",
            planning_horizon=Duration(days=7),
        )
        schedule_with_job.add_job(target_job_id)
        schedule_with_job.add_job(other_job_id)

        schedule_without_job = Schedule(
            name="Schedule Without Target Job",
            planning_horizon=Duration(days=7),
        )
        schedule_without_job.add_job(other_job_id)

        schedule_empty = Schedule(
            name="Empty Schedule",
            planning_horizon=Duration(days=7),
        )

        # Save all schedules
        await schedule_repository.save(schedule_with_job)
        await schedule_repository.save(schedule_without_job)
        await schedule_repository.save(schedule_empty)
        db_session.commit()

        # Find schedules containing target job
        schedules_with_job = await schedule_repository.find_containing_job(
            target_job_id
        )
        names_with_job = [sched.name for sched in schedules_with_job]

        assert "Schedule With Target Job" in names_with_job
        assert "Schedule Without Target Job" not in names_with_job
        assert "Empty Schedule" not in names_with_job

    async def test_get_active_schedules(self, schedule_repository, db_session):
        """Test getting only active schedules."""
        # Create schedules in different states
        draft_schedule = Schedule(
            name="Draft Schedule",
            planning_horizon=Duration(days=7),
        )

        published_schedule = Schedule(
            name="Published Schedule",
            planning_horizon=Duration(days=7),
        )
        published_schedule._status = ScheduleStatus.PUBLISHED

        active_schedule = Schedule(
            name="Active Schedule",
            planning_horizon=Duration(days=7),
        )
        active_schedule._status = ScheduleStatus.ACTIVE

        completed_schedule = Schedule(
            name="Completed Schedule",
            planning_horizon=Duration(days=7),
        )
        completed_schedule._status = ScheduleStatus.COMPLETED

        # Save all schedules
        schedules = [
            draft_schedule,
            published_schedule,
            active_schedule,
            completed_schedule,
        ]
        for schedule in schedules:
            await schedule_repository.save(schedule)
        db_session.commit()

        # Get active schedules
        active_schedules = await schedule_repository.get_active_schedules()
        active_names = [sched.name for sched in active_schedules]

        # Only active and published schedules should be considered "active"
        assert "Active Schedule" in active_names
        assert "Published Schedule" in active_names
        assert "Draft Schedule" not in active_names
        assert "Completed Schedule" not in active_names

    async def test_get_schedules_in_date_range(self, schedule_repository, db_session):
        """Test getting schedules within a date range."""
        now = datetime.utcnow()
        start_range = now - timedelta(days=1)
        end_range = now + timedelta(days=1)

        # Create schedules with different creation dates
        old_schedule = Schedule(
            name="Old Schedule",
            planning_horizon=Duration(days=7),
        )
        old_schedule._created_at = now - timedelta(days=5)

        current_schedule = Schedule(
            name="Current Schedule",
            planning_horizon=Duration(days=7),
        )
        current_schedule._created_at = now

        future_schedule = Schedule(
            name="Future Schedule",
            planning_horizon=Duration(days=7),
        )
        future_schedule._created_at = now + timedelta(days=5)

        # Save all schedules
        await schedule_repository.save(old_schedule)
        await schedule_repository.save(current_schedule)
        await schedule_repository.save(future_schedule)
        db_session.commit()

        # Get schedules in date range
        schedules_in_range = await schedule_repository.get_schedules_in_date_range(
            start_range, end_range
        )
        names_in_range = [sched.name for sched in schedules_in_range]

        assert "Current Schedule" in names_in_range
        assert "Old Schedule" not in names_in_range
        assert "Future Schedule" not in names_in_range

    async def test_schedule_with_complex_assignments(
        self, schedule_repository, db_session
    ):
        """Test schedule with multiple complex assignments."""
        schedule = Schedule(
            name="Complex Assignment Schedule",
            planning_horizon=Duration(days=3),
        )

        # Create multiple assignments with different patterns
        now = datetime.utcnow()

        # Morning shift assignment
        morning_assignment = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=8),
            end_time=now + timedelta(hours=16),
            setup_duration=Duration(minutes=60),
            processing_duration=Duration(minutes=420),
        )

        # Afternoon shift assignment (different machine, multiple operators)
        afternoon_assignment = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4(), uuid4(), uuid4()],
            start_time=now + timedelta(hours=16),
            end_time=now + timedelta(hours=24),
            setup_duration=Duration(minutes=30),
            processing_duration=Duration(minutes=450),
        )

        # Overnight assignment (minimal setup)
        overnight_assignment = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=24),
            end_time=now + timedelta(hours=32),
            setup_duration=Duration(minutes=15),
            processing_duration=Duration(minutes=465),
        )

        # Add assignments to schedule
        schedule.assignments.extend(
            [morning_assignment, afternoon_assignment, overnight_assignment]
        )

        # Save schedule
        await schedule_repository.save(schedule)
        db_session.commit()

        # Retrieve and verify
        retrieved_schedule = await schedule_repository.get_by_id(schedule.id)

        assert retrieved_schedule is not None
        assert len(retrieved_schedule.assignments) == 3

        # Verify assignment details
        assignments_by_start = sorted(
            retrieved_schedule.assignments, key=lambda a: a.start_time
        )

        # Check morning assignment
        morning = assignments_by_start[0]
        assert morning.setup_duration.minutes == 60
        assert len(morning.operator_ids) == 1

        # Check afternoon assignment
        afternoon = assignments_by_start[1]
        assert afternoon.setup_duration.minutes == 30
        assert len(afternoon.operator_ids) == 3

        # Check overnight assignment
        overnight = assignments_by_start[2]
        assert overnight.setup_duration.minutes == 15
        assert len(overnight.operator_ids) == 1

    async def test_schedule_assignment_queries(self, schedule_repository, db_session):
        """Test querying schedule assignments."""
        schedule = Schedule(
            name="Assignment Query Schedule",
            planning_horizon=Duration(days=2),
        )

        # Create assignments with specific machine and time patterns
        machine1_id = uuid4()
        machine2_id = uuid4()
        now = datetime.utcnow()

        # Multiple assignments for machine1
        assignment1 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=machine1_id,
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            setup_duration=Duration(minutes=30),
            processing_duration=Duration(minutes=90),
        )

        assignment2 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=machine1_id,
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=4),
            end_time=now + timedelta(hours=6),
            setup_duration=Duration(minutes=15),
            processing_duration=Duration(minutes=105),
        )

        # One assignment for machine2
        assignment3 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=machine2_id,
            operator_ids=[uuid4(), uuid4()],
            start_time=now + timedelta(hours=2),
            end_time=now + timedelta(hours=5),
            setup_duration=Duration(minutes=45),
            processing_duration=Duration(minutes=135),
        )

        schedule.assignments.extend([assignment1, assignment2, assignment3])

        # Save schedule
        await schedule_repository.save(schedule)
        db_session.commit()

        # Retrieve schedule
        retrieved_schedule = await schedule_repository.get_by_id(schedule.id)

        # Test assignment filtering by machine
        machine1_assignments = [
            a for a in retrieved_schedule.assignments if a.machine_id == machine1_id
        ]
        assert len(machine1_assignments) == 2

        machine2_assignments = [
            a for a in retrieved_schedule.assignments if a.machine_id == machine2_id
        ]
        assert len(machine2_assignments) == 1

        # Test assignment filtering by time window
        time_window_start = now + timedelta(hours=1.5)
        time_window_end = now + timedelta(hours=4.5)

        overlapping_assignments = [
            a
            for a in retrieved_schedule.assignments
            if a.start_time < time_window_end and a.end_time > time_window_start
        ]
        assert len(overlapping_assignments) == 3  # All assignments overlap this window

        # Test assignment filtering by setup duration
        long_setup_assignments = [
            a for a in retrieved_schedule.assignments if a.setup_duration.minutes >= 30
        ]
        assert len(long_setup_assignments) == 2  # assignment1 and assignment3

    async def test_schedule_metrics_calculation(self, schedule_repository, db_session):
        """Test calculating schedule metrics from database."""
        schedule = Schedule(
            name="Metrics Test Schedule",
            planning_horizon=Duration(days=1),
        )

        # Add jobs and assignments
        job_ids = [uuid4(), uuid4(), uuid4()]
        for job_id in job_ids:
            schedule.add_job(job_id)

        # Create assignments with overlapping times to test makespan
        now = datetime.utcnow()
        earliest_start = now + timedelta(hours=1)
        latest_end = now + timedelta(hours=10)

        assignment1 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            start_time=earliest_start,
            end_time=now + timedelta(hours=4),
            setup_duration=Duration(minutes=30),
            processing_duration=Duration(minutes=150),
        )

        assignment2 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=7),
            setup_duration=Duration(minutes=15),
            processing_duration=Duration(minutes=225),
        )

        assignment3 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=uuid4(),
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=6),
            end_time=latest_end,
            setup_duration=Duration(minutes=45),
            processing_duration=Duration(minutes=195),
        )

        schedule.assignments.extend([assignment1, assignment2, assignment3])

        # Save schedule
        await schedule_repository.save(schedule)
        db_session.commit()

        # Retrieve and calculate metrics
        retrieved_schedule = await schedule_repository.get_by_id(schedule.id)

        # Test basic metrics
        assert len(retrieved_schedule.assignments) == 3
        assert len(retrieved_schedule.job_ids) == 3

        # Test makespan calculation (should be from earliest start to latest end)
        makespan = retrieved_schedule.calculate_makespan()
        expected_makespan_hours = (latest_end - earliest_start).total_seconds() / 3600
        assert abs(makespan.hours - expected_makespan_hours) < 0.1

    async def test_bulk_schedule_operations(self, schedule_repository, db_session):
        """Test bulk operations on schedules."""
        # Create multiple schedules
        schedules = []
        for i in range(5):
            schedule = Schedule(
                name=f"Bulk Schedule {i+1}",
                planning_horizon=Duration(days=7),
                created_by=uuid4(),
            )
            # Add some jobs to each schedule
            for _j in range(3):
                schedule.add_job(uuid4())
            schedules.append(schedule)

        # Bulk save
        saved_schedules = await schedule_repository.save_batch(schedules)
        db_session.commit()

        # Verify all schedules were saved
        assert len(saved_schedules) == 5
        for i, schedule in enumerate(saved_schedules):
            assert schedule.name == f"Bulk Schedule {i+1}"
            assert len(schedule.job_ids) == 3

        # Verify all schedules can be retrieved
        for schedule in saved_schedules:
            retrieved_schedule = await schedule_repository.get_by_id(schedule.id)
            assert retrieved_schedule is not None
            assert retrieved_schedule.name == schedule.name

    async def test_schedule_search_and_filtering(self, schedule_repository, db_session):
        """Test complex schedule search and filtering operations."""
        datetime.utcnow()
        user1_id = uuid4()
        user2_id = uuid4()

        # Create schedules with different characteristics
        schedules = [
            # User1's schedules
            Schedule(
                name="User1 Active Manufacturing",
                planning_horizon=Duration(days=5),
                created_by=user1_id,
            ),
            Schedule(
                name="User1 Weekly Planning",
                planning_horizon=Duration(days=7),
                created_by=user1_id,
            ),
            # User2's schedules
            Schedule(
                name="User2 Daily Operations",
                planning_horizon=Duration(days=1),
                created_by=user2_id,
            ),
        ]

        # Set different statuses
        schedules[0]._status = ScheduleStatus.ACTIVE
        schedules[1]._status = ScheduleStatus.PUBLISHED
        schedules[2]._status = ScheduleStatus.DRAFT

        # Save all schedules
        for schedule in schedules:
            await schedule_repository.save(schedule)
        db_session.commit()

        # Test search by name pattern
        manufacturing_schedules = await schedule_repository.search_schedules(
            {"name_pattern": "Manufacturing"}
        )
        manufacturing_names = [s.name for s in manufacturing_schedules]
        assert "User1 Active Manufacturing" in manufacturing_names
        assert len([n for n in manufacturing_names if "Manufacturing" in n]) >= 1

        # Test search by multiple criteria
        user1_active_schedules = await schedule_repository.search_schedules(
            {
                "created_by": user1_id,
                "status": ScheduleStatus.ACTIVE,
            }
        )
        assert len(user1_active_schedules) == 1
        assert user1_active_schedules[0].name == "User1 Active Manufacturing"

        # Test search by planning horizon
        short_schedules = await schedule_repository.search_schedules(
            {"max_planning_days": 3}
        )
        short_names = [s.name for s in short_schedules]
        assert "User2 Daily Operations" in short_names

    async def test_schedule_assignment_time_conflicts(
        self, schedule_repository, db_session
    ):
        """Test detecting time conflicts in schedule assignments."""
        schedule = Schedule(
            name="Conflict Detection Schedule",
            planning_horizon=Duration(days=1),
        )

        machine_id = uuid4()
        now = datetime.utcnow()

        # Create overlapping assignments on the same machine
        assignment1 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=machine_id,
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=4),
            setup_duration=Duration(minutes=15),
            processing_duration=Duration(minutes=165),
        )

        # This assignment overlaps with assignment1
        assignment2 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=machine_id,
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=3),  # Starts before assignment1 ends
            end_time=now + timedelta(hours=6),
            setup_duration=Duration(minutes=20),
            processing_duration=Duration(minutes=160),
        )

        # This assignment doesn't overlap
        assignment3 = ScheduleAssignment(
            task_id=uuid4(),
            machine_id=machine_id,
            operator_ids=[uuid4()],
            start_time=now + timedelta(hours=7),  # Starts after assignment2 ends
            end_time=now + timedelta(hours=10),
            setup_duration=Duration(minutes=10),
            processing_duration=Duration(minutes=170),
        )

        schedule.assignments.extend([assignment1, assignment2, assignment3])

        # Save schedule (conflicts should be detectable after save)
        await schedule_repository.save(schedule)
        db_session.commit()

        # Retrieve schedule and detect conflicts
        retrieved_schedule = await schedule_repository.get_by_id(schedule.id)

        # Get assignments for the machine, sorted by start time
        machine_assignments = sorted(
            [a for a in retrieved_schedule.assignments if a.machine_id == machine_id],
            key=lambda a: a.start_time,
        )

        assert len(machine_assignments) == 3

        # Check for overlaps
        overlaps = []
        for i in range(len(machine_assignments) - 1):
            current = machine_assignments[i]
            next_assignment = machine_assignments[i + 1]

            if current.end_time > next_assignment.start_time:
                overlaps.append((current.task_id, next_assignment.task_id))

        assert (
            len(overlaps) == 1
        )  # Should detect one overlap (assignment1 and assignment2)
        assert (assignment1.task_id, assignment2.task_id) in overlaps


@pytest.mark.performance
class TestScheduleRepositoryPerformance:
    """Performance tests for schedule repository operations."""

    @pytest.fixture
    def schedule_repository(self, db_session: Session):
        """Create schedule repository with database session."""
        return SQLScheduleRepository(db_session)

    async def test_large_schedule_save_performance(
        self, schedule_repository, db_session, performance_monitor
    ):
        """Test performance of saving schedules with many assignments."""
        # Create a schedule with many assignments
        schedule = Schedule(
            name="Large Schedule Performance Test",
            planning_horizon=Duration(days=30),
        )

        # Add many jobs
        for i in range(50):
            schedule.add_job(uuid4())

        # Create many assignments
        now = datetime.utcnow()
        for i in range(200):
            assignment = ScheduleAssignment(
                task_id=uuid4(),
                machine_id=uuid4(),
                operator_ids=[uuid4()],
                start_time=now + timedelta(hours=i * 2),
                end_time=now + timedelta(hours=i * 2 + 1.5),
                setup_duration=Duration(minutes=15),
                processing_duration=Duration(minutes=75),
            )
            schedule.assignments.append(assignment)

        # Time the save operation
        with performance_monitor.time_operation("save_large_schedule"):
            await schedule_repository.save(schedule)
            db_session.commit()

        # Verify performance
        stats = performance_monitor.get_stats()
        assert stats["error_count"] == 0
        assert stats["max_time"] < 15.0  # Should complete within 15 seconds

        # Test retrieval performance
        with performance_monitor.time_operation("retrieve_large_schedule"):
            retrieved_schedule = await schedule_repository.get_by_id(schedule.id)

        assert retrieved_schedule is not None
        assert len(retrieved_schedule.assignments) == 200
        assert len(retrieved_schedule.job_ids) == 50

        # Retrieval should be reasonably fast
        stats = performance_monitor.get_stats()
        retrieval_time = max(
            op["duration"]
            for op in stats["operations"]
            if op["name"] == "retrieve_large_schedule"
        )
        assert retrieval_time < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
